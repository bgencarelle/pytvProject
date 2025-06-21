"""
channel_manager.py

Synchronized channel/playlist manager for the fake-television emulator.

Key changes
-----------
* Replaces the old millisecond “IPS” clock with a micro-second timeline
  (`TICK_HZ = 1_000_000`), eliminating truncation-induced drift.
* Reads (and, if missing, writes) a `playlist.json` cache created by
  `playlist_builder.py`, so each file is probed only once.
* Keeps all per-channel math in micro-seconds; lookup is O(1) via `bisect`.
* Public API – `offset()`, `next()`, `prev()`, `.channels`, `.min_ch`,
  `.max_ch` – matches the old module, so the rest of the codebase needs
  no changes.
"""

from __future__ import annotations

import bisect
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import av  # PyAV – thin FFmpeg bindings

import config

# ── Timing ──────────────────────────────────────────────────────────────────
TICK_HZ = 1_000_000          # micro-seconds per second – our global tick rate

# ── Regex helpers ───────────────────────────────────────────────────────────
_VIDEO_RE = re.compile(r"\.(?:mkv|mp4|mov|avi|webm|flv)$", re.IGNORECASE)
_CHAN_RE  = re.compile(r"^chan_(\d+)$", re.IGNORECASE)


# ── Duration probe ──────────────────────────────────────────────────────────
def _probe_duration_us(fp: str) -> int:
    """Return clip length in **micro-seconds**. Zero on error."""
    try:
        with av.open(fp) as container:
            stream = next(
                (s for s in container.streams if s.type == "video"),
                container.streams[0],
            )

            if stream.duration:
                dur = stream.duration * stream.time_base
            elif container.duration:
                dur = container.duration / av.time_base
            else:
                dur = 0.0

            return max(0, int(dur * 1_000_000))
    except Exception:
        return 0


# ── Data structures ─────────────────────────────────────────────────────────
@dataclass
class Channel:
    files: List[str] = field(default_factory=list)
    durations_us: List[int] = field(default_factory=list)
    start_us: List[int] = field(default_factory=list)   # cumulative start times
    total_us: int = 0

    # Updated by `offset()` for the caller’s convenience
    path: Optional[str] = None
    duration_us: int = 0
    duration: float = 0.0            # seconds version of `duration_us`


# ── Channel manager ─────────────────────────────────────────────────────────
class ChannelManager:
    """Discovers *chan_<n>* folders and answers timeline queries."""

    # ---------------------------------------------------------------- init
    def __init__(self, root_dir: str | None = None) -> None:
        self.root_dir = os.path.abspath(root_dir or config.MOVIES_PATH)
        self.channels: Dict[int, Channel] = {}
        self._discover()

        self.min_ch: Optional[int] = min(self.channels) if self.channels else None
        self.max_ch: Optional[int] = max(self.channels) if self.channels else None

    # ----------------------------------------------------------- discovery
    def _discover(self) -> None:
        if not os.path.isdir(self.root_dir):
            return

        for entry in os.scandir(self.root_dir):
            if not entry.is_dir():
                continue
            m = _CHAN_RE.match(entry.name)
            if not m:
                continue

            ch_num = int(m.group(1))
            chan = self._load_channel(entry.path)
            if chan.files:              # skip empty / unreadable folders
                self.channels[ch_num] = chan

    # ----------------------------------------------------------- channel load
    def _load_channel(self, dir_path: str) -> Channel:
        playlist = os.path.join(dir_path, "playlist.json")

        # 1. Try cache
        if os.path.isfile(playlist):
            try:
                with open(playlist, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Channel(
                    files=[os.path.join(dir_path, fp) for fp in data["files"]],
                    durations_us=data["durations_us"],
                    start_us=data["start_us"],
                    total_us=data["total_us"],
                )
            except Exception:
                pass  # fall through to probing

        # 2. Probe directory
        files, durations = [], []
        for name in sorted(os.listdir(dir_path)):
            fp = os.path.join(dir_path, name)
            if os.path.isfile(fp) and _VIDEO_RE.search(name):
                dur_us = _probe_duration_us(fp)
                if dur_us:
                    files.append(fp)
                    durations.append(dur_us)

        if not files:
            return Channel()            # nothing usable in this folder

        start_us = [0]
        for d in durations[:-1]:
            start_us.append(start_us[-1] + d)
        total_us = start_us[-1] + durations[-1]

        chan = Channel(
            files=files,
            durations_us=durations,
            start_us=start_us,
            total_us=total_us,
        )

        # 3. Write cache for next start-up (best effort)
        try:
            with open(playlist, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "files": [os.path.basename(p) for p in files],
                        "durations_us": durations,
                        "start_us": start_us,
                        "total_us": total_us,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

        return chan

    # ---------------------------------------------------------------- offset
    def offset(self, ch: int, now: float, ref: float) -> float:
        """
        Return **seconds** offset inside the current clip for channel *ch*.

        Side effects
        ------------
        * Updates `chan.path`, `chan.duration_us`, and `chan.duration` so the
          caller knows which file to open and its length.
        """
        chan = self.channels.get(ch)
        if not chan or not chan.total_us:
            return 0.0

        elapsed_us = int((now - ref) * TICK_HZ)
        rel_us = elapsed_us % chan.total_us

        idx = max(0, bisect.bisect_right(chan.start_us, rel_us) - 1)

        chan.path = chan.files[idx]
        chan.duration_us = chan.durations_us[idx]
        chan.duration = chan.duration_us / 1_000_000

        return (rel_us - chan.start_us[idx]) / 1_000_000

    # ------------------------------------------------------------- navigation
    def next(self, cur: int) -> int:
        keys = sorted(self.channels)
        if not keys:
            return cur
        if cur not in keys:
            return keys[0]
        return keys[(keys.index(cur) + 1) % len(keys)]

    def prev(self, cur: int) -> int:
        keys = sorted(self.channels)
        if not keys:
            return cur
        if cur not in keys:
            return keys[-1]
        return keys[(keys.index(cur) - 1) % len(keys)]
