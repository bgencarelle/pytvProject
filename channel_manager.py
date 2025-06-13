# channel_manager.py
"""
Channel management: find video files, read durations, compute time offsets.
"""
import os
import av

class Channel:
    def __init__(self, number, path, duration):
        self.number = number
        self.path = path
        self.duration = duration

class ChannelManager:
    def __init__(self, movies_path):
        # Scan directory for video files (e.g. .mp4), sorted
        files = sorted([f for f in os.listdir(movies_path) if f.lower().endswith(('.mp4', '.mkv', '.avi'))])
        self.channels = {}
        num = 1
        for fn in files:
            full = os.path.join(movies_path, fn)
            dur = self._get_duration(full)
            self.channels[num] = Channel(num, full, dur)
            num += 1
        self.min_ch = min(self.channels) if self.channels else 1
        self.max_ch = max(self.channels) if self.channels else 0

    def _get_duration(self, filepath):
        """Return video duration in seconds using PyAV metadata."""
        try:
            container = av.open(filepath)
            # Prefer stream duration if available
            vs = next((s for s in container.streams if s.type == 'video'), None)
            if vs and vs.duration:
                dur = float(vs.duration * vs.time_base)
            else:
                dur = float(container.duration * container.streams[0].time_base)
            container.close()
            return dur
        except Exception:
            return 0.0

    def next(self, cur):
        if not self.channels:
            return cur
        nxt = cur + 1
        return nxt if nxt in self.channels else self.min_ch

    def prev(self, cur):
        if not self.channels:
            return cur
        prv = cur - 1
        return prv if prv in self.channels else self.max_ch

    def offset(self, ch, now_ts, ref_ts):
        """Compute playback offset (in seconds) for channel ch."""
        chan = self.channels.get(ch)
        if not chan or chan.duration <= 0:
            return 0.0
        elapsed = now_ts - ref_ts
        if elapsed < 0:
            elapsed = 0.0
        return elapsed % chan.duration
