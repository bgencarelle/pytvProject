# =========  video_player.py  =========
"""
Hardware-accelerated VideoPlayer for Raspberry Pi (Pi 3 B+ and up)

Public API
----------
open(path, offset)
decode_frame()  → latest frame (HxWx3 uint8)
get_position_sec()
seek_to(sec)
set_volume(0.0-1.0)
close() / stop()
Properties
----------
.path  → current file path
.sar   → sample-aspect ratio
"""
import gi, threading, queue, numpy as np, pygame
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject

# ────────────────────────────────────────────────────────────────────────────
class VideoPlayer:
    def __init__(self):
        Gst.init(None)

        # build a playbin
        self.player = Gst.ElementFactory.make("playbin", "player")

        # try to build the GPU-accelerated bin first
        self._vsink = None
        video_sink  = self._build_hw_sink() or self._build_sw_sink()
        self.player.set_property("video-sink", video_sink)
        self.player.set_property("audio-sink",
                                 Gst.ElementFactory.make("autoaudiosink", "aud"))

        # state
        self._q, self._last = queue.Queue(maxsize=1), None
        self._w = self._h = 0
        self.sar  = 1.0
        self.path = ""
        self._ml  = None
        self._ml_thread = None

    # ── sink builders ───────────────────────────────────────────────────────
    def _build_hw_sink(self):
        """
        Pi-optimised pipeline:
          H.264 → GPU decode (v4l2h264dec) → DMAbuf zero-copy → videoconvert
          → RGB565 (2 Bpp) → 1-buffer leaky queue → appsink (sync = True)
        Returns a Gst.Bin or None if linking fails.
        """
        desc = (
            "h264parse ! "
            "v4l2h264dec capture-io-mode=dmabuf-import ! "
            "video/x-raw(memory:DMABuf),format=NV12 ! "
            "videoconvert ! "
            "video/x-raw,format=RGB16_LE ! "
            "queue max-size-buffers=1 leaky=downstream ! "
            "appsink name=vsink emit-signals=true "
            "max-buffers=2 drop=true sync=true "
            "caps=video/x-raw,format=RGB16_LE"
        )
        try:
            bin_ = Gst.parse_bin_from_description(desc, True)
            self._vsink = bin_.get_by_name("vsink")
            self._vsink.connect("new-sample", self._on_sample)
            return bin_
        except Exception:
            # plugin missing or unable to link
            return None

    def _build_sw_sink(self):
        """
        Fallback: simple RGB appsink (software conversion).
        """
        vs = Gst.ElementFactory.make("appsink", "vsink")
        vs.set_property("emit-signals", True)
        vs.set_property("max-buffers", 2)
        vs.set_property("drop", True)
        vs.set_property("sync", True)
        vs.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
        vs.connect("new-sample", self._on_sample)
        self._vsink = vs
        return vs

    # ── public API ──────────────────────────────────────────────────────────
    def open(self, fp: str, start: float = 0.0):
        self.close()
        while not self._q.empty():
            self._q.get_nowait()

        self.path = fp
        self.player.set_property("uri", Gst.filename_to_uri(fp))
        self.player.set_state(Gst.State.PAUSED)

        # wait for preroll / caps
        bus = self.player.get_bus()
        msg = bus.timed_pop_filtered(
            5 * Gst.SECOND,
            Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR,
        )
        if msg and msg.type == Gst.MessageType.ERROR:
            raise RuntimeError(msg.parse_error()[0])

        caps = self._vsink.get_static_pad("sink").get_current_caps().get_structure(0)
        self._w, self._h = caps.get_int("width")[1], caps.get_int("height")[1]
        if caps.has_field("pixel-aspect-ratio"):
            num, den = caps.get_fraction("pixel-aspect-ratio")[-2:]
            self.sar = num / den if den else 1.0

        self.seek_to(start)
        self.player.set_state(Gst.State.PLAYING)
        pygame.mouse.set_visible(False)

        # grab first frame so decode_frame() never returns None
        data = self._q.get(timeout=2.0)
        self._last = self._bytes_to_arr(data)

        # bus watch in a side loop
        self._ml = GObject.MainLoop()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_msg)
        self._ml_thread = threading.Thread(target=self._ml.run, daemon=True)
        self._ml_thread.start()

    def decode_frame(self):
        data = None
        while True:
            try:
                data = self._q.get_nowait()
            except queue.Empty:
                break
        if data is not None:
            self._last = self._bytes_to_arr(data)
        return self._last

    def get_position_sec(self):
        ok, pos = self.player.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else 0.0

    def seek_to(self, sec: float):
        self.player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
            int(max(0.0, sec) * Gst.SECOND),
        )

    def set_volume(self, vol: float):
        self.player.set_property("volume", max(0.0, min(1.0, vol)))

    def close(self):
        if self._ml:
            self._ml.quit()
            self._ml = None
        if self._ml_thread and threading.current_thread() is not self._ml_thread:
            self._ml_thread.join(timeout=0.5)
        self._ml_thread = None
        self.player.set_state(Gst.State.NULL)
        self.path = ""

    stop = close  # alias

    # ── internals ───────────────────────────────────────────────────────────
    def _bytes_to_arr(self, data: bytes):
        """
        Convert RGB16_LE (5-6-5) → RGB888 uint8.
        Fallback RGB888 data is handled transparently.
        """
        if len(data) == self._w * self._h * 2:     # RGB565
            px = np.frombuffer(data, np.uint16).reshape((self._h, self._w))
            r = ((px >> 11) & 0x1F).astype(np.uint8) << 3
            g = ((px >> 5) & 0x3F).astype(np.uint8) << 2
            b = (px & 0x1F).astype(np.uint8) << 3
            arr = np.stack((r, g, b), axis=-1)
            return arr
        else:  # already RGB888
            stride = len(data) // self._h
            rows   = np.frombuffer(data, np.uint8).reshape((self._h, stride))
            return np.ascontiguousarray(rows[:, : self._w * 3]
                                        .reshape((self._h, self._w, 3)))

    def _on_sample(self, sink):
        samp = sink.emit("pull-sample")
        if samp:
            buf = samp.get_buffer()
            ok, mi = buf.map(Gst.MapFlags.READ)
            if ok:
                try:
                    self._q.put_nowait(bytes(mi.data))
                except queue.Full:
                    pass
                buf.unmap(mi)
        return Gst.FlowReturn.OK

    def _on_bus_msg(self, bus, msg):
        if msg.type == Gst.MessageType.EOS:
            # self.seek_to(0.0)  # seamless loop if desired
            return
        elif msg.type == Gst.MessageType.ERROR:
            print("GStreamer error:", *msg.parse_error())
            self.close()
        return True
