import gi
import threading
import queue
import time
import numpy as np

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject

class VideoPlayer:
    """GStreamer backend, drop-in for original PyAV API,
    with correct stride-cropping, seamless looping, cursor hiding,
    and guaranteed C-contiguous frames."""
    def __init__(self):
        Gst.init(None)

        # playbin: demux→decode→A/V sync
        self.player = Gst.ElementFactory.make("playbin", "player")
        if not self.player:
            raise RuntimeError("GStreamer playbin not available")

        # appsink: clock-synced, drop old if slow
        vs = Gst.ElementFactory.make("appsink", "vsink")
        vs.set_property("emit-signals", True)
        vs.set_property("max-buffers", 2)
        vs.set_property("drop", True)
        vs.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
        vs.connect("new-sample", self._on_sample)
        self.video_sink = vs
        self.player.set_property("video-sink", vs)

        # stereo audio
        self.player.set_property(
            "audio-sink",
            Gst.ElementFactory.make("autoaudiosink", "audiosink")
        )

        # internal state
        self._frame_q    = queue.Queue(maxsize=1)
        self._last_frame = None
        self._w = self._h = None
        self._offset     = 0.0
        self._ml         = None
        self._ml_thread  = None

        # sample-aspect ratio (main.py expects this)
        self.sar = 1.0

    def open(self, filepath: str, start_offset: float = 0.0):
        """Begin playback from `start_offset` seconds (blocks until first frame)."""
        # ── stop any running playback ──────────────────────
        self.close()

        # ── purge stale frames ─────────────────────────────
        while not self._frame_q.empty():
            self._frame_q.get_nowait()
        self._last_frame = None
        self._w = self._h = None

        # ── set URI & offset ──────────────────────────────
        self._offset = max(0.0, start_offset)
        self.player.set_property("uri", Gst.filename_to_uri(filepath))

        # 1) preroll in PAUSED to read caps & allow seek
        self.player.set_state(Gst.State.PAUSED)
        bus = self.player.get_bus()
        msg = bus.timed_pop_filtered(
            5 * Gst.SECOND,
            Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR
        )
        if msg and msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            raise RuntimeError(f"GStreamer preroll error: {err}")

        # 2) read negotiated width/height and pixel-aspect
        pad = self.video_sink.get_static_pad("sink")
        caps = pad.get_current_caps().get_structure(0)

        # dimensions
        self._w = caps.get_int("width")[1]
        self._h = caps.get_int("height")[1]

        # extract aspect numerator/denominator
        def _read_frac(field):
            try:
                frac = caps.get_fraction(field)
            except Exception:
                return 1, 1
            # get_fraction may return (ok, num, den) or (num, den)
            if isinstance(frac, tuple):
                if len(frac) == 3:
                    _, num, den = frac
                elif len(frac) == 2:
                    num, den = frac
                else:
                    return 1, 1
                return num, den
            return 1, 1

        if caps.has_field("pixel-aspect-ratio"):
            num, den = _read_frac("pixel-aspect-ratio")
        elif caps.has_field("display-aspect-ratio"):
            num, den = _read_frac("display-aspect-ratio")
        else:
            num, den = 1, 1

        self.sar = (num / den) if den else 1.0

        # 3) seek if requested
        if self._offset > 0:
            ok = self.player.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                int(self._offset * Gst.SECOND)
            )
            if not ok:
                print("Warning: seek_simple failed")

        # 4) start PLAYING
        self.player.set_state(Gst.State.PLAYING)

        # hide the mouse and grab it
        try:
            import pygame
            pygame.mouse.set_visible(False)
            pygame.event.set_grab(True)
        except ImportError:
            pass

        # 5) block for first frame and enforce C-contiguity
        try:
            data = self._frame_q.get(timeout=2.0)
        except queue.Empty:
            raise RuntimeError("Timeout waiting for first video frame")
        arr = self._crop_frame(data)
        if not arr.flags["C_CONTIGUOUS"]:
            arr = np.ascontiguousarray(arr)
        self._last_frame = arr

        # 6) background the GObject loop
        self._ml = GObject.MainLoop()
        self._ml_thread = threading.Thread(target=self._gst_loop, daemon=True)
        self._ml_thread.start()

    def decode_frame(self):
        """
        Non-blocking: return the most recent frame as HxWx3 uint8 array.
        Always returns a valid, C-contiguous frame once open() has succeeded.
        """
        try:
            data = self._frame_q.get_nowait()
            arr = self._crop_frame(data)
            if not arr.flags["C_CONTIGUOUS"]:
                arr = np.ascontiguousarray(arr)
            self._last_frame = arr
        except queue.Empty:
            pass
        return self._last_frame
    def fade_out(self, duration: float = 0.1):
        pass

    def fade_in(self, duration: float = 0.1):
        pass

    def close(self):
        """Stop playback and clean up (avoids joining current thread)."""
        if self._ml:
            self._ml.quit()
            self._ml = None
        if self._ml_thread and threading.current_thread() is not self._ml_thread:
            self._ml_thread.join(timeout=0.5)
        self._ml_thread = None
        self.player.set_state(Gst.State.NULL)

    stop = close  # legacy alias

    # internal helpers
    def _crop_frame(self, data: bytes) -> np.ndarray:
        """
        Reshape raw bytes including stride to (h, stride), crop to (h, w*3),
        then reshape to (h, w, 3).
        """
        h, w = self._h, self._w
        stride_bytes = len(data) // h
        rowdata = np.frombuffer(data, np.uint8).reshape((h, stride_bytes))
        cropped = rowdata[:, : w * 3]
        return cropped.reshape((h, w, 3))

    def _on_sample(self, sink):
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR
        buf = sample.get_buffer()
        ok, mi = buf.map(Gst.MapFlags.READ)
        if ok:
            try:
                self._frame_q.put_nowait(bytes(mi.data))
            except queue.Full:
                pass
            buf.unmap(mi)
        return Gst.FlowReturn.OK

    def _gst_loop(self):
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_msg)
        try:
            self._ml.run()
        except Exception as e:
            print("GStreamer loop exited:", e)

    def _on_bus_msg(self, bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            print("GStreamer error:", err, dbg)
            self.close()
        elif msg.type == Gst.MessageType.EOS:
            # loop seamlessly
            self.player.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                0
            )
        return True
