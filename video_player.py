# =========  video_player.py  =========
"""
GStreamer RGB VideoPlayer:

• open(path, offset)
• decode_frame()  → latest frame (HxWx3 uint8)
• get_position_sec()
• seek_to(sec)
• set_volume(0.0-1.0)          NEW
• seamless loop on EOS
• .path  → current file path
• .sar   → sample-aspect ratio
"""
import gi, threading, queue, numpy as np, pygame
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject

class VideoPlayer:
    def __init__(self):
        Gst.init(None)
        self.player = Gst.ElementFactory.make("playbin", "player")
        vs = Gst.ElementFactory.make("appsink", "vsink")
        vs.set_property("emit-signals", True)
        vs.set_property("max-buffers", 2)
        vs.set_property("drop", True)
        vs.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
        vs.connect("new-sample", self._on_sample)
        self.player.set_property("video-sink", vs)
        self.player.set_property("audio-sink",
                                 Gst.ElementFactory.make("autoaudiosink", "aud"))
        self._q, self._last = queue.Queue(maxsize=1), None
        self._w = self._h = 0
        self.sar  = 1.0
        self.path = ""
        self._ml  = None
        self._ml_thread = None

    # ── public ──────────────────────────────────────────────────
    def open(self, fp: str, start: float = 0.0):
        self.close()
        while not self._q.empty(): self._q.get_nowait()
        self.path = fp
        self.player.set_property("uri", Gst.filename_to_uri(fp))
        self.player.set_state(Gst.State.PAUSED)

        bus = self.player.get_bus()
        msg = bus.timed_pop_filtered(5*Gst.SECOND,
                                     Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR)
        if msg and msg.type == Gst.MessageType.ERROR:
            raise RuntimeError(msg.parse_error()[0])

        caps = self.player.get_property("video-sink").get_static_pad("sink") \
                           .get_current_caps().get_structure(0)
        self._w, self._h = caps.get_int("width")[1], caps.get_int("height")[1]
        if caps.has_field("pixel-aspect-ratio"):
            num, den = caps.get_fraction("pixel-aspect-ratio")[-2:]
            self.sar = num/den if den else 1.0

        self.seek_to(start)
        self.player.set_state(Gst.State.PLAYING)
        pygame.mouse.set_visible(False)

        data = self._q.get(timeout=2.0)
        self._last = self._bytes_to_arr(data)

        self._ml = GObject.MainLoop()
        bus.add_signal_watch(); bus.connect("message", self._on_bus_msg)
        self._ml_thread = threading.Thread(target=self._ml.run, daemon=True)
        self._ml_thread.start()

    def decode_frame(self):
        try:
            data = self._q.get_nowait()
            self._last = self._bytes_to_arr(data)
        except queue.Empty:
            pass
        return self._last

    def get_position_sec(self):
        ok, pos = self.player.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else 0.0

    def seek_to(self, sec: float):
        self.player.seek_simple(Gst.Format.TIME,
                                Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                                int(max(0.0, sec) * Gst.SECOND))

    # NEW: mute / un-mute
    def set_volume(self, vol: float):
        self.player.set_property("volume", max(0.0, min(1.0, vol)))

    def close(self):
        if self._ml: self._ml.quit(); self._ml = None
        if self._ml_thread and threading.current_thread() is not self._ml_thread:
            self._ml_thread.join(timeout=0.5)
        self._ml_thread = None
        self.player.set_state(Gst.State.NULL)
        self.path = ""

    stop = close  # alias

    # ── internals ───────────────────────────────────────────────
    def _bytes_to_arr(self, data: bytes):
        stride = len(data)//self._h
        rows   = np.frombuffer(data, np.uint8).reshape((self._h, stride))
        return np.ascontiguousarray(rows[:, : self._w*3]
                                    .reshape((self._h, self._w, 3)))

    def _on_sample(self, sink):
        samp = sink.emit("pull-sample")
        if samp:
            buf = samp.get_buffer(); ok, mi = buf.map(Gst.MapFlags.READ)
            if ok:
                try: self._q.put_nowait(bytes(mi.data))
                except queue.Full: pass
                buf.unmap(mi)
        return Gst.FlowReturn.OK

    def _on_bus_msg(self, bus, msg):
        if msg.type == Gst.MessageType.EOS:
           # self.seek_to(0.0)
            return
        elif msg.type == Gst.MessageType.ERROR:
            print("GStreamer error:", *msg.parse_error()); self.close()
        return True
