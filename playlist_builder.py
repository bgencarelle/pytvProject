#!/usr/bin/env python3
"""
playlist_builder.py
-------------------
One-shot cache generator for the fake-television emulator.

• Walks MOVIES_PATH (from config.py, default “movies/”).
• Finds sub-directories matching  chan_<n>  (n = integer channel number).
• Probes every playable video in each channel folder via PyAV.
• Writes  playlist.json  with:
      {
        "files":        ["file1.mp4", ...]             # basenames
        "durations_us": [297654321, ...]              # micro-seconds
        "start_us":     [0, 297654321, ...]           # cumulative start times
        "total_us":     592004444                     # sum of durations_us
      }
  These keys are exactly what `channel_manager.py` expects.

Run from the project root:

    $ python playlist_builder.py
    or
    $ python playlist_builder.py /custom/path/to/movies
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import List, Tuple

import av  # PyAV – thin FFmpeg bindings

# ── constants ───────────────────────────────────────────────────────────────
CHAN_RE = re.compile(r"^chan_(\d+)$", re.IGNORECASE)
VIDEO_RE = re.compile(r"\.(mkv|mp4|mov|avi|webm|flv)$", re.IGNORECASE)

# ── helpers ─────────────────────────────────────────────────────────────────
def probe_duration_us(fp: str) -> int:
    """Return clip length in micro-seconds or 0 if unknown/unreadable."""
    try:
        with av.open(fp) as c:
            stream = next((s for s in c.streams if s.type == "video"), None)
            if stream and stream.duration:                          # in stream time-base
                length = stream.duration * stream.time_base
            elif c.duration:                                        # container field
                length = c.duration / av.time_base
            else:
                return 0
            return max(0, int(length * 1_000_000))
    except Exception:
        return 0


def build_playlist(dir_path: str) -> Tuple[List[str], List[int]]:
    """Return (files, durations_us) for a channel directory; empty lists on failure."""
    files: List[str] = []
    durations: List[int] = []

    for name in sorted(os.listdir(dir_path)):
        if not VIDEO_RE.search(name):
            continue
        fp = os.path.join(dir_path, name)
        if not os.path.isfile(fp):
            continue
        dur_us = probe_duration_us(fp)
        if dur_us:
            files.append(name)       # store basenames only (relative inside channel)
            durations.append(dur_us)

    return files, durations


def write_cache(dir_path: str, files: List[str], durations: List[int]) -> None:
    """Write playlist.json in *dir_path* (best effort)."""
    if not files:
        print(f"  └─ No playable videos in {os.path.basename(dir_path)} – skipping.")
        return

    start_us = [0]
    for d in durations[:-1]:
        start_us.append(start_us[-1] + d)
    total_us = start_us[-1] + durations[-1]

    data = {
        "files": files,
        "durations_us": durations,
        "start_us": start_us,
        "total_us": total_us,
    }

    out_fp = os.path.join(dir_path, "playlist.json")
    try:
        with open(out_fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"  └─ wrote {out_fp}")
    except Exception as exc:
        print(f"  └─ ERROR writing {out_fp}: {exc}", file=sys.stderr)


# ── main ─────────────────────────────────────────────────────────────────────
def main(root: str):
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        sys.exit(f"Movies path not found: {root}")

    print(f"Scanning {root}")

    for entry in os.scandir(root):
        if not entry.is_dir():
            continue
        m = CHAN_RE.match(entry.name)
        if not m:
            continue

        ch_num = int(m.group(1))
        dir_path = entry.path
        print(f"· Channel {ch_num:02d}  ({dir_path})")
        files, durations = build_playlist(dir_path)
        write_cache(dir_path, files, durations)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate playlist.json caches.")
    ap.add_argument(
        "movies_path",
        nargs="?",
        default=None,
        help="Root directory containing chan_<n> folders (defaults to config.MOVIES_PATH).",
    )
    args = ap.parse_args()

    # Lazy-import config only when we need its default path
    if args.movies_path is None:
        try:
            import config

            args.movies_path = getattr(config, "MOVIES_PATH", "movies")
        except Exception:
            args.movies_path = "movies"

    main(args.movies_path)
