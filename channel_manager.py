# channel_manager.py
"""
Channel management: discover channels as subfolders whose names contain “chan_<number>”,
play their videos in a loop (naturally sorted), and compute per-file seek offsets
based on a shared reference time.
"""
import os
import re
import av

def natural_key(s: str):
    """
    Split a string into a list of int and text chunks for natural sorting.
    e.g. "movie12.mp4" → ["movie", 12, ".mp4"]
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", s)
    ]

class Channel:
    def __init__(self, number: int, path: str, duration: float):
        self.number = number         # channel number
        self.path = path             # current file path
        self.duration = duration     # current file duration (seconds)
        # Attributes set by ChannelManager:
        # self.files            – list of file paths in this channel
        # self.durations        – list of durations matching files
        # self.total_duration   – sum(self.durations)

class ChannelManager:
    def __init__(self, movies_path: str):
        self.channels = {}

        # 1) Find subdirectories whose names contain "chan_<number>" anywhere
        entries = [
            e for e in os.listdir(movies_path)
            if os.path.isdir(os.path.join(movies_path, e))
        ]
        chan_pattern = re.compile(r"(?i)chan[_\-]?0*(\d+)")
        dir_map = {}
        for d in entries:
            m = chan_pattern.search(d)   # search anywhere in folder name
            if m:
                num = int(m.group(1))
                dir_map[num] = d

        if dir_map:
            # Build each channel from its matching directory
            for num in sorted(dir_map):
                subdir = dir_map[num]
                full_dir = os.path.join(movies_path, subdir)

                # Find video files and sort naturally
                vids = [
                    f for f in os.listdir(full_dir)
                    if f.lower().endswith((".mp4", ".mkv", ".avi"))
                ]
                vids.sort(key=natural_key)

                # Full paths and durations
                files = [os.path.join(full_dir, f) for f in vids]
                durations = [self._get_duration(fp) for fp in files]
                total = sum(durations)

                # Initialize Channel
                first_path = files[0] if files else ""
                first_dur  = durations[0] if durations else 0.0
                ch = Channel(num, first_path, first_dur)
                ch.files = files
                ch.durations = durations
                ch.total_duration = total
                self.channels[num] = ch

        else:
            # Fallback: flat files in movies_path → one-per-channel
            vids = [
                f for f in os.listdir(movies_path)
                if f.lower().endswith((".mp4", ".mkv", ".avi"))
            ]
            vids.sort(key=natural_key)

            num = 1
            for f in vids:
                fp = os.path.join(movies_path, f)
                dur = self._get_duration(fp)
                ch = Channel(num, fp, dur)
                ch.files = [fp]
                ch.durations = [dur]
                ch.total_duration = dur
                self.channels[num] = ch
                num += 1

        # Determine channel range
        nums = list(self.channels.keys())
        self.min_ch = min(nums) if nums else 1
        self.max_ch = max(nums) if nums else 0

    def _get_duration(self, filepath: str) -> float:
        """Return video duration in seconds using PyAV metadata."""
        try:
            cont = av.open(filepath)
            vs = next((s for s in cont.streams if s.type == "video"), None)
            if vs and vs.duration:
                dur = float(vs.duration * vs.time_base)
            else:
                dur = float(cont.duration * cont.streams[0].time_base)
            cont.close()
            return dur
        except Exception:
            return 0.0

    def next(self, cur: int) -> int:
        """Return the next channel number, wrapping to min_ch."""
        if not self.channels:
            return cur
        nxt = cur + 1
        return nxt if nxt in self.channels else self.min_ch

    def prev(self, cur: int) -> int:
        """Return the previous channel number, wrapping to max_ch."""
        if not self.channels:
            return cur
        prv = cur - 1
        return prv if prv in self.channels else self.max_ch

    def offset(self, ch: int, now_ts: float, ref_ts: float) -> float:
        """
        Compute seek offset within the appropriate file for channel `ch`,
        based on (now_ts - ref_ts). Updates `channels[ch].path` and
        `.duration` to the selected file. Returns offset in seconds.
        """
        chan = self.channels.get(ch)
        if not chan or chan.total_duration <= 0:
            return 0.0

        elapsed = now_ts - ref_ts
        if elapsed < 0:
            elapsed = 0.0

        # position within the total loop
        t = elapsed % chan.total_duration

        # find which file contains time t
        cum = 0.0
        for fp, d in zip(chan.files, chan.durations):
            if t < cum + d:
                offset_in_file = t - cum
                chan.path     = fp
                chan.duration = d
                return offset_in_file
            cum += d

        # fallback to last file
        last_fp = chan.files[-1]
        last_d  = chan.durations[-1]
        chan.path     = last_fp
        chan.duration = last_d
        return t - (cum - last_d)
