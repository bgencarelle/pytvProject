#!/usr/bin/env python3
"""
playlist_builder.py – pause-card aware

• Adds a 3-second pause sentinel (“__PAUSE__”) after every movie and after the
  last one.  If `config.SINGLE_VID_PAUSE` is True, single-clip channels get
  the pause too.
• Can be run as a script **or** imported and called via
      build_all_playlists(path=None)
"""

from __future__ import annotations
import argparse, json, os, re, sys
from typing import List, Tuple

import av                               # PyAV
import config

# ── constants ──────────────────────────────────────────────────────────────
CHAN_RE        = re.compile(r"^chan_(\d+)$", re.IGNORECASE)
VIDEO_RE       = re.compile(r"\.(mkv|mp4|mov|avi|webm|flv)$", re.IGNORECASE)
PAUSE_SENTINEL = "__PAUSE__"
PAUSE_US       = 3_000_000              # 3-second nominal gap


# ── low-level helpers ──────────────────────────────────────────────────────
def _probe_duration_us(fp: str) -> int:
    try:
        with av.open(fp) as c:
            s   = next((s for s in c.streams if s.type == "video"), None)
            dur = (
                s.duration * s.time_base if s and s.duration
                else c.duration / av.time_base if c.duration else 0
            )
            return max(0, int(dur * 1_000_000))
    except Exception:
        return 0


def _build_channel(dir_path: str) -> Tuple[List[str], List[int]]:
    """Return (files, durations_us) including pause sentinels."""
    files, durs = [], []
    for name in sorted(os.listdir(dir_path)):
        if VIDEO_RE.search(name):
            fp = os.path.join(dir_path, name)
            if os.path.isfile(fp):
                dur = _probe_duration_us(fp)
                if dur:
                    files.append(name)
                    durs.append(dur)

    add_pause = len(files) > 1 or getattr(config, "SINGLE_VID_PAUSE", False)
    if not add_pause:
        return files, durs

    out_f, out_d = [], []
    for fn, dur in zip(files, durs):
        out_f.extend([fn, PAUSE_SENTINEL])
        out_d.extend([dur, PAUSE_US])

    return out_f, out_d


def _write_playlist(dir_path: str, files: List[str], durs: List[int]) -> None:
    if not files:
        print(f"  └─ No playable videos in {os.path.basename(dir_path)} – skipped")
        return

    start_us = [0]
    for d in durs[:-1]:
        start_us.append(start_us[-1] + d)
    total_us = start_us[-1] + durs[-1]

    data = {
        "files":        files,
        "durations_us": durs,
        "start_us":     start_us,
        "total_us":     total_us,
    }

    out_fp = os.path.join(dir_path, "playlist.json")
    try:
        with open(out_fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"  └─ wrote {out_fp}")
    except Exception as exc:
        print(f"  └─ ERROR writing {out_fp}: {exc}", file=sys.stderr)


# ── public API ─────────────────────────────────────────────────────────────
def build_all_playlists(root: str | None = None) -> None:
    """
    Build / refresh playlist.json in every chan_<n> folder under *root*.

    Parameters
    ----------
    root : str | None
        Root directory that contains the channel sub-folders.
        Defaults to config.MOVIES_PATH.
    """
    root = os.path.abspath(root or getattr(config, "MOVIES_PATH", "movies"))
    if not os.path.isdir(root):
        sys.exit(f"Movies path not found: {root}")

    print(f"Scanning {root}")
    for ent in os.scandir(root):
        if ent.is_dir() and CHAN_RE.match(ent.name):
            ch = int(CHAN_RE.match(ent.name).group(1))
            print(f"· Channel {ch:02d} ({ent.path})")
            files, durs = _build_channel(ent.path)
            _write_playlist(ent.path, files, durs)


# ── CLI entry-point ────────────────────────────────────────────────────────
def _cli() -> None:
    ap = argparse.ArgumentParser(description="Generate playlist.json caches.")
    ap.add_argument(
        "movies_path",
        nargs="?",
        default=None,
        help="Root dir containing chan_<n> folders "
             "(defaults to config.MOVIES_PATH)",
    )
    args = ap.parse_args()
    build_all_playlists(args.movies_path)


if __name__ == "__main__":
    _cli()
