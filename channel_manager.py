"""
channel_manager.py

• Discovers channels as sub-folders whose names contain “chan_<number>”
• Builds a playlist (natural order) per channel
• Empty folders play static (total_duration = 0 → handled upstream)
• next()/prev() now iterate through existing channel numbers,
  so gaps in numbering are skipped.
"""
import os, re, av

def natural_key(s: str):
    """Split a string into ints / text chunks for natural sorting."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]

class Channel:
    def __init__(self, number: int, first_path: str, first_duration: float):
        self.number   = number
        self.path     = first_path
        self.duration = first_duration
        # filled later
        self.files = []
        self.durations = []
        self.total_duration = 0.0

class ChannelManager:
    def __init__(self, movies_path: str):
        self.channels = {}

        # ── discover directories like “...chan_<num>...” ─────────
        dir_map = {}
        pat = re.compile(r"(?i)chan[_\-]?0*(\d+)")
        for entry in os.listdir(movies_path):
            full = os.path.join(movies_path, entry)
            if not os.path.isdir(full):
                continue
            m = pat.search(entry)
            if m:
                dir_map[int(m.group(1))] = full

        # ── build each channel ───────────────────────────────────
        for num in sorted(dir_map):
            full_dir = dir_map[num]
            vids = [f for f in os.listdir(full_dir)
                    if f.lower().endswith((".mp4", ".mkv", ".avi"))]
            vids.sort(key=natural_key)

            files      = [os.path.join(full_dir, v) for v in vids]
            durations  = [self._get_duration(fp) for fp in files]
            total_dur  = sum(durations)

            first_path = files[0] if files else ""
            first_dur  = durations[0] if durations else 0.0
            ch = Channel(num, first_path, first_dur)
            ch.files           = files
            ch.durations       = durations
            ch.total_duration  = total_dur
            self.channels[num] = ch

        # fallback: flat files as channels if no “chan_” dirs found
        if not self.channels:
            vids = [f for f in os.listdir(movies_path)
                    if f.lower().endswith((".mp4", ".mkv", ".avi"))]
            vids.sort(key=natural_key)
            for idx, fn in enumerate(vids, 1):
                fp  = os.path.join(movies_path, fn)
                dur = self._get_duration(fp)
                ch  = Channel(idx, fp, dur)
                ch.files = [fp]; ch.durations = [dur]
                ch.total_duration = dur
                self.channels[idx] = ch

        keys = sorted(self.channels)
        self.min_ch = keys[0] if keys else 1
        self.max_ch = keys[-1] if keys else 0

    # ────────────────────────────────────────────────────────────
    def _get_duration(self, fp: str) -> float:
        try:
            cont = av.open(fp)
            vs   = next((s for s in cont.streams if s.type=="video"), None)
            if vs and vs.duration:
                d = float(vs.duration * vs.time_base)
            else:
                d = float(cont.duration * cont.streams[0].time_base)
            cont.close(); return d
        except Exception:
            return 0.0

    # ── channel navigation that skips gaps ──────────────────────
    def next(self, cur: int) -> int:
        if not self.channels:
            return cur
        keys = sorted(self.channels)
        if cur not in keys:
            return keys[0]
        idx = (keys.index(cur) + 1) % len(keys)
        return keys[idx]

    def prev(self, cur: int) -> int:
        if not self.channels:
            return cur
        keys = sorted(self.channels)
        if cur not in keys:
            return keys[-1]
        idx = (keys.index(cur) - 1) % len(keys)
        return keys[idx]

    # ── compute playback offset within playlist ─────────────────
    def offset(self, ch: int, now_ts: float, ref_ts: float) -> float:
        chan = self.channels.get(ch)
        if not chan or chan.total_duration <= 0:
            return 0.0

        t = max(0.0, now_ts - ref_ts) % chan.total_duration
        cum = 0.0
        for fp, dur in zip(chan.files, chan.durations):
            if t < cum + dur:
                chan.path     = fp
                chan.duration = dur
                return t - cum
            cum += dur

        # fallback (edge rounding)
        chan.path     = chan.files[-1]
        chan.duration = chan.durations[-1]
        return t - (cum - chan.durations[-1])
