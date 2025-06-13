# video_player.py
import threading
import queue
import time

import av
import numpy as np
import pyaudio


class VideoPlayer:
    """
    PyAV video + PyAudio streaming audio with crossfade on channel switch:
      - open(): starts PyAudio stream & decode thread
      - close(): stops/joins thread, stops audio stream
      - fade_out()/fade_in(): smooth volume ramps
    """

    def __init__(self):
        # Video
        self.container = None
        self.video_stream = None

        # Audio queue / thread control
        self._audio_q = queue.Queue(maxsize=100)
        self._audio_thr = None
        self._stop_audio = threading.Event()

        # PyAudio handles
        self._pa = None
        self._audio_stream = None
        self._audio_rate = None
        self._audio_ch = None

        # Current volume for crossfade [0.0–1.0]
        self._volume = 1.0

    def open(self, filepath: str, start_offset: float = 0.0):
        """Open video+audio at start_offset, launch audio stream & decode."""
        self.close()

        # ── Probe audio stream to get rate & channels ───────────
        probe = av.open(filepath)
        a_st = next((s for s in probe.streams if s.type == "audio"), None)
        if a_st:
            self._audio_rate = a_st.rate
            self._audio_ch   = len(a_st.layout.channels)
        probe.close()

        if a_st:
            # ── PyAudio callback applies self._volume ────────────
            def pa_callback(in_data, frame_count, time_info, status):
                # float buffer for volume multiply
                buf = np.zeros((frame_count, self._audio_ch), dtype=np.float32)
                filled = 0
                while filled < frame_count:
                    try:
                        chunk = self._audio_q.get_nowait()
                    except queue.Empty:
                        break
                    take = min(len(chunk), frame_count - filled)
                    # scale to float, apply volume
                    buf[filled:filled+take] = chunk[:take].astype(np.float32) * self._volume
                    if take < len(chunk):
                        # push back remainder
                        self._audio_q.put(chunk[take:], block=False)
                    filled += take
                # convert back to int16
                out = np.clip(buf, -32768, 32767).astype(np.int16)
                return (out.tobytes(), pyaudio.paContinue)

            # ── Start PyAudio stream ────────────────────────────
            self._pa = pyaudio.PyAudio()
            self._audio_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._audio_ch,
                rate=self._audio_rate,
                output=True,
                frames_per_buffer=1024,
                stream_callback=pa_callback
            )
            self._audio_stream.start_stream()

            # Reset volume to full on open
            self._volume = 1.0

            # ── Audio decode thread ────────────────────────────
            def audio_decode():
                ac = av.open(filepath)
                a_stream = next(s for s in ac.streams if s.type == "audio")
                # seek to offset
                ac.seek(int(start_offset / a_stream.time_base),
                         any_frame=False, backward=True, stream=a_stream)
                try:
                    while not self._stop_audio.is_set():
                        for pkt in ac.demux(a_stream):
                            for frm in pkt.decode():
                                raw = frm.to_ndarray().T
                                # scale floats → int16
                                if raw.dtype.kind == "f":
                                    pcm = (raw * 32767).astype(np.int16)
                                else:
                                    pcm = raw.astype(np.int16)
                                # enqueue in 1024-sample chunks
                                for i in range(0, len(pcm), 1024):
                                    self._audio_q.put(pcm[i:i+1024], block=True)
                            if self._stop_audio.is_set():
                                break
                        # loop by seeking back
                        ac.seek(0, any_frame=False, backward=True, stream=a_stream)
                except Exception as e:
                    print(f"[VideoPlayer] Audio decode error: {e}")
                finally:
                    try: ac.close()
                    except: pass

            self._stop_audio.clear()
            self._audio_thr = threading.Thread(target=audio_decode, daemon=True)
            self._audio_thr.start()

        # ── Video setup & seek ──────────────────────────────────
        self.container = av.open(filepath)
        self.video_stream = next(s for s in self.container.streams if s.type == "video")
        ts = int(start_offset / float(self.video_stream.time_base))
        self.container.seek(ts, any_frame=False, backward=True, stream=self.video_stream)

    def decode_frame(self):
        """Return next RGB frame (HxWx3), auto-loop on EOF."""
        while True:
            for pkt in self.container.demux(self.video_stream):
                for frm in pkt.decode():
                    return frm.to_ndarray(format="rgb24")
            self.container.seek(0, stream=self.video_stream)

    def close(self):
        """Stop audio thread & stream, close video container."""
        # Stop video
        if self.container:
            try: self.container.close()
            except: pass
        self.container = None
        self.video_stream = None

        # Fade out instantly
        self._volume = 0.0

        # Signal audio thread to stop
        self._stop_audio.set()
        # Wait for join
        if self._audio_thr:
            self._audio_thr.join(timeout=1.0)
            self._audio_thr = None

        # Stop PyAudio stream
        if self._audio_stream:
            try:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            except: pass
        if self._pa:
            try: self._pa.terminate()
            except: pass

        self._audio_stream = None
        self._pa = None

        # Clear any queued samples
        with self._audio_q.mutex:
            self._audio_q.queue.clear()

    # ────────────────────────────────────────────────────────────
    # Crossfade helpers
    # ────────────────────────────────────────────────────────────
    def fade_out(self, duration: float = 0.1):
        """
        Ramp volume from current level to 0 over `duration` seconds.
        Blocks for duration.
        """
        if not self._audio_stream: return
        steps = max(1, int(duration * self._audio_rate / 1024))
        for i in range(steps):
            self._volume *= (1 - (i+1)/steps)
            time.sleep(1024/self._audio_rate)
        self._volume = 0.0

    def fade_in(self, duration: float = 0.1):
        """
        Ramp volume from 0 to 1 over `duration` seconds.
        Blocks for duration.
        """
        if not self._audio_stream: return
        steps = max(1, int(duration * self._audio_rate / 1024))
        for i in range(steps):
            self._volume = (i+1)/steps
            time.sleep(1024/self._audio_rate)
        self._volume = 1.0
