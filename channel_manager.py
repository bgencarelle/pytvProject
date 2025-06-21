"""
channel_manager.py  – µ-second timeline, pause-aware
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

# ── timing ────────────────────────────────────────────────────────────────
TICK_HZ = 1_000_000                    # µ-seconds / second

# ── sentinels & constants ─────────────────────────────────────────────────
PAUSE_SENTINEL = "__PAUSE__"
PAUSE_BASE_US  = 3_000_000             # nominal 3-second card

# ── regex helpers ────────────────────────────────────────────────────────
_VIDEO_RE = re.compile(r"\.(?:mkv|mp4|mov|avi|webm|flv)$", re.IGNORECASE)
_CHAN_RE  = re.compile(r"^chan_(\d+)$", re.IGNORECASE)


# ── duration probe ───────────────────────────────────────────────────────
def _probe_duration_us(fp: str) -> int:
    try:
        with av.open(fp) as c:
            s = next((s for s in c.streams if s.type == "video"), c.streams[0])
            dur = (
                s.duration * s.time_base
                if s.duration
                else c.duration / av.time_base if c.duration else 0.0
            )
            return max(0, int(dur * 1_000_000))
    except Exception:
        return 0


# ── dataclass ────────────────────────────────────────────────────────────
@dataclass
class Channel:
    files:        List[str] = field(default_factory=list)
    durations_us: List[int] = field(default_factory=list)
    start_us:     List[int] = field(default_factory=list)   # cumulative
    total_us:     int      = 0

    # convenience – refreshed by offset()
    path:         Optional[str] = None
    duration_us:  int          = 0
    duration:     float        = 0.0


# ── manager ──────────────────────────────────────────────────────────────
class ChannelManager:
    """
    Discovers chan_<n> folders and maps wall-clock → (file, intra-offset).
    Handles the PAUSE_SENTINEL as a synthetic clip.
    """

    # ---------------------------------------------------------------- init
    def __init__(self, root_dir: str | None = None) -> None:
        self.root_dir = os.path.abspath(root_dir or config.MOVIES_PATH)
        self.channels: Dict[int, Channel] = {}
        self._discover()

        self.min_ch = min(self.channels) if self.channels else None
        self.max_ch = max(self.channels) if self.channels else None

    # ----------------------------------------------------------- discovery
    def _discover(self) -> None:
        if not os.path.isdir(self.root_dir):
            return
        for ent in os.scandir(self.root_dir):
            m = _CHAN_RE.match(ent.name) if ent.is_dir() else None
            if m:
                ch_num = int(m.group(1))
                chan   = self._load_channel(ent.path)
                if chan.files:
                    self.channels[ch_num] = chan

    # ----------------------------------------------------------- load one
    def _load_channel(self, dir_path: str) -> Channel:
        cache_fp = os.path.join(dir_path, "playlist.json")

        # 1. cached JSON
        if os.path.isfile(cache_fp):
            try:
                with open(cache_fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                files = [
                    (PAUSE_SENTINEL if fn == PAUSE_SENTINEL
                     else os.path.join(dir_path, fn))
                    for fn in data["files"]
                ]
                return Channel(
                    files        = files,
                    durations_us = data["durations_us"],
                    start_us     = data["start_us"],
                    total_us     = data["total_us"],
                )
            except Exception:
                pass  # fall through to probe

        # 2. probe directory
        files, durs = [], []
        for name in sorted(os.listdir(dir_path)):
            if _VIDEO_RE.search(name):
                fp = os.path.join(dir_path, name)
                dur = _probe_duration_us(fp)
                if dur:
                    files.append(fp)
                    durs.append(dur)

        if not files:
            return Channel()

        start_us = [0]
        for d in durs[:-1]:
            start_us.append(start_us[-1] + d)
        total_us = start_us[-1] + durs[-1]

        # write cache for next run
        try:
            with open(cache_fp, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "files":        [os.path.basename(p) for p in files],
                        "durations_us": durs,
                        "start_us":     start_us,
                        "total_us":     total_us,
                    },
                    f, indent=2,
                )
        except Exception:
            pass

        return Channel(files, durs, start_us, total_us)

    # ---------------------------------------------------------------- offset
    def offset(self, ch: int, now: float, ref: float) -> float:
        """
        Return **seconds** offset inside the current clip (or pause card).

        Side-effects: updates chan.path, chan.duration_us, chan.duration.
        """
        chan = self.channels.get(ch)
        if not chan or not chan.total_us:
            return 0.0

        rel_us = int((now - ref) * TICK_HZ) % chan.total_us
        idx    = max(0, bisect.bisect_right(chan.start_us, rel_us) - 1)

        sel_file = chan.files[idx]

        # ── normal movie ────────────────────────────────────────────────
        if sel_file != PAUSE_SENTINEL:
            chan.path        = sel_file
            chan.duration_us = chan.durations_us[idx]
            chan.duration    = chan.duration_us / 1_000_000
            return (rel_us - chan.start_us[idx]) / 1_000_000

        # ── synthetic pause clip ───────────────────────────────────────
        pad_us = (TICK_HZ - (rel_us % TICK_HZ)) % TICK_HZ   # 0-999 999 µs
        chan.path        = PAUSE_SENTINEL
        chan.duration_us = PAUSE_BASE_US + pad_us
        chan.duration    = chan.duration_us / 1_000_000
        return (rel_us - chan.start_us[idx]) / 1_000_000

    # ------------------------------------------------------------- navigation
    def next(self, cur: int) -> int:
        keys = sorted(self.channels)
        if cur not in keys:
            return keys[0] if keys else cur
        return keys[(keys.index(cur) + 1) % len(keys)]

    def prev(self, cur: int) -> int:
        keys = sorted(self.channels)
        if cur not in keys:
            return keys[-1] if keys else cur
        return keys[(keys.index(cur) - 1) % len(keys)]
