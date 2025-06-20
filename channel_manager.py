"""
channel_manager.py

• Discovers channels as sub-folders whose names contain “chan_<number>”
• Builds a natural-order playlist for each channel
• Empty folders fall back to static (handled upstream)
• next()/prev() skip gaps in numbering
• Integer-tick clock index (IPS) keeps all players frame-locked
"""
import os, re, av, math
import config

# ------------------------------------------------------------------ timing
IPS = config.IPS            # integer ticks / second (e.g. 60)

# ------------------------------------------------------------------ helpers
def natural_key(s: str):
    """Split a string into ints / text chunks for human sorting."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]

# ------------------------------------------------------------------ data
class Channel:
    def __init__(self, number: int):
        self.number         = number
        self.files          = []        # [str]
        self.durations      = []        # [float] – seconds
        self.total_duration = 0.0       # seconds

        # mutable at runtime
        self.path     = ""
        self.duration = 0.0

# ------------------------------------------------------------------ main
class ChannelManager:
    def __init__(self, movies_path: str):
        self.channels = {}

        # ── discover “chan_<num>” sub-dirs ───────────────────────────────
        pat      = re.compile(r"(?i)chan[_\-]?0*(\d+)")
        dir_map  = {}
        for entry in os.listdir(movies_path):
            full = os.path.join(movies_path, entry)
            if os.path.isdir(full):
                m = pat.search(entry)
                if m:
                    dir_map[int(m.group(1))] = full

        # ── build channels from folders ──────────────────────────────────
        for num, full_dir in sorted(dir_map.items()):
            vids = [f for f in os.listdir(full_dir)
                    if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))]
            vids.sort(key=natural_key)

            ch = Channel(num)
            for v in vids:
                fp  = os.path.join(full_dir, v)
                dur = self._get_duration(fp)
                ch.files.append(fp)
                ch.durations.append(dur)
                ch.total_duration += dur
            if ch.files:
                ch.path, ch.duration = ch.files[0], ch.durations[0]
            self.channels[num] = ch

        # ── fallback: flat files if no chan_X folders ────────────────────
        if not self.channels:
            vids = [f for f in os.listdir(movies_path)
                    if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov"))]
            vids.sort(key=natural_key)
            for idx, fn in enumerate(vids, 1):
                fp  = os.path.join(movies_path, fn)
                dur = self._get_duration(fp)
                ch  = Channel(idx)
                ch.files = [fp]; ch.durations = [dur]
                ch.total_duration = dur
                ch.path, ch.duration = fp, dur
                self.channels[idx] = ch

        keys = sorted(self.channels)
        self.min_ch = keys[0] if keys else 1
        self.max_ch = keys[-1] if keys else 0

    # ------------------------------------------------------------------ io
    @staticmethod
    def _get_duration(fp: str) -> float:
        try:
            cont = av.open(fp)
            vs   = next((s for s in cont.streams if s.type == "video"), None)
            if vs and vs.duration:
                dur = float(vs.duration * vs.time_base)
            else:
                dur = float(cont.duration * cont.streams[0].time_base)
            cont.close()
            return max(0.0, dur)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------ navigation
    def next(self, cur: int) -> int:
        keys = sorted(self.channels)
        if not keys: return cur
        if cur not in keys: return keys[0]
        return keys[(keys.index(cur) + 1) % len(keys)]

    def prev(self, cur: int) -> int:
        keys = sorted(self.channels)
        if not keys: return cur
        if cur not in keys: return keys[-1]
        return keys[(keys.index(cur) - 1) % len(keys)]

    # ------------------------------------------------------------------ timing core
    def offset(self, ch: int, now: float, ref: float) -> float:
        """
        Return playback offset (seconds) within current file of channel *ch*
        based on integer ticks.  Also updates chan.path / chan.duration.
        """
        chan = self.channels.get(ch)
        if not chan or chan.total_duration <= 0:
            return 0.0

        total_ticks = int(round(chan.total_duration * IPS))
        if total_ticks == 0:
            return 0.0

        ticks       = int((now - ref) * IPS)
        t_in_sec    = (ticks % total_ticks) / IPS

        cum = 0.0
        for fp, dur in zip(chan.files, chan.durations):
            if t_in_sec < cum + dur:
                chan.path     = fp
                chan.duration = dur
                return t_in_sec - cum
            cum += dur

        # Shouldn’t reach here, but fall back gracefully
        chan.path, chan.duration = chan.files[-1], chan.durations[-1]
        return 0.0


