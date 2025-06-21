"""
playlist_builder.py  – one-shot playlist cache creator
Adds µ-second timeline fields required by the revised ChannelManager.
Old fields stay intact.
"""
from __future__ import annotations
import os, re, json, time, av, typing as _t, pathlib

TICK_HZ = 1_000_000                         # 1 tick = 1 µs

# ---------- natural sort --------------------------------------------------
def _nat_key(s: str) -> list[_t.Union[int, str]]:
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]

# ---------- probe ---------------------------------------------------------
def _probe(fp: str) -> tuple[float, int, float]:
    """
    Return (seconds, frames, fps) – frames > 0 on success.
    Final fallback: decode to last frame PTS.
    """
    try:
        with av.open(fp) as c:
            vs = next((s for s in c.streams if s.type == "video"), None)
            if not vs:
                return 0.0, 0, 0.0

            if vs.frames and vs.average_rate:                     # meta
                dur = vs.frames / float(vs.average_rate)
                return dur, vs.frames, float(vs.average_rate)

            if vs.duration and vs.time_base:
                dur = float(vs.duration * vs.time_base)
                if vs.average_rate:
                    fps = float(vs.average_rate)
                    frm = int(round(dur * fps))
                    return dur, frm, fps

            # brute-force last frame
            last_pts = None
            for f in c.decode(video=vs.index):
                last_pts = f.pts
            if last_pts is not None and vs.time_base and vs.average_rate:
                fps  = float(vs.average_rate)
                dur  = last_pts * vs.time_base
                frm  = int(round(dur * fps))
                return dur, frm, fps
    except Exception:
        pass
    return 0.0, 0, 0.0

# ---------- builder -------------------------------------------------------
def build_cache(movies_path: str, cache_path: str | None = None) -> dict:
    if cache_path is None:
        cache_path = os.path.join(movies_path, ".playlist_cache.json")

    print("[playlist_builder] scanning movie folders …")
    pat = re.compile(r"(?i)chan[_\-]?0*(\d+)")
    dir_map = {
        int(m.group(1)): os.path.join(movies_path, d)
        for d in os.listdir(movies_path)
        if (m := pat.search(d)) and os.path.isdir(os.path.join(movies_path, d))
    }

    channels: dict[str, dict] = {}

    def _add_channel(idx: int, files: list[str]):
        rec = {
            "files":           [],
            "durations":       [],
            "duration_us":     [],
            "start_us":        [],
            "frames":          [],
            "fps":             [],
            "total_duration":  0.0,
            "total_frames":    0,
            "total_us":        0
        }

        cum_us = 0
        for fp in files:
            dur, frm, fps = _probe(fp)
            if frm == 0:
                print(f"  ! skipping unreadable file: {fp}")
                continue

            dur_us = int(round(dur * TICK_HZ))

            rec["files"].append(fp)
            rec["durations"].append(dur)
            rec["duration_us"].append(dur_us)
            rec["start_us"].append(cum_us)
            rec["frames"].append(frm)
            rec["fps"].append(fps)

            rec["total_duration"] += dur
            rec["total_frames"]   += frm
            cum_us += dur_us

        rec["total_us"] = cum_us
        if rec["files"]:
            channels[str(idx)] = rec

    # --- normal chan_* folders ------------------------------------------
    for num, full_dir in sorted(dir_map.items()):
        vids = [f for f in os.listdir(full_dir)
                if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))]
        vids.sort(key=_nat_key)
        _add_channel(num, [os.path.join(full_dir, v) for v in vids])

    # --- fallback: loose files as channels -------------------------------
    if not channels:
        vids = [f for f in os.listdir(movies_path)
                if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))]
        vids.sort(key=_nat_key)
        for idx, fn in enumerate(vids, 1):
            _add_channel(idx, [os.path.join(movies_path, fn)])

    data = {"generated": time.time(), "channels": channels}
    pathlib.Path(cache_path).write_text(json.dumps(data, indent=2))
    print(f"[playlist_builder] cache written → {cache_path}")
    return data


# -------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(description="Rebuild playlist cache")
    ap.add_argument("root", nargs="?", default="movies",
                    help="root movie folder (default: ./movies)")
    args = ap.parse_args()

    build_cache(args.root)
