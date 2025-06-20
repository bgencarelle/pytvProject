# =========  app.py  =========
import os, time, threading, random, pygame
from pygame.locals import *
import config
from channel_manager import ChannelManager
from video_player    import VideoPlayer
from overlays        import draw_overlay
from renderer        import render_frame
from gi.repository   import Gst
from timing import wall_clock

DRIFT_OK = 0.02   # seconds considered “in-sync”

class TVEmulator:
    # ---------------------------------------------------------------- init
    def __init__(self):
        pygame.init(); pygame.mixer.init()
        self.screen = pygame.display.set_mode(
            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
            pygame.FULLSCREEN if config.FULLSCREEN else 0)
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        # core ---------------------------------------------------------------
        self.ch_mgr   = ChannelManager(config.MOVIES_PATH)
        self.ref_time = config.REFERENCE_START_TIME
        self.curr_ch  = config.START_CHANNEL or self.ch_mgr.min_ch
        self.player   = VideoPlayer(); self.curr_path = ""

        # static resources ---------------------------------------------------
        self.static_fp  = os.path.join(config.MOVIES_PATH, "static_video.mp4")
        self.static_len = self._probe_len(self.static_fp)
        self.min_static = getattr(config, "STATIC_DURATION", 0.5)
        self.static_vp  = VideoPlayer() if self.static_len else None
        if self.static_vp: self._prime_static()

        # transition & overlay state ----------------------------------------
        self.phase   = "normal"     # normal | static
        self.static_start = 0.0
        self.next_ch = None
        self.tmp_vp  = None
        self.tid     = 0            # generation token
        self.overlay_expire = time.time() + config.OVERLAY_DURATION
        self.force_overlay  = False
        if not hasattr(config, "SHOW_OVERLAYS"): config.SHOW_OVERLAYS = False

        self._open_channel(self.curr_ch)

    # ---------------------------------------------------------------- helpers
    def _probe_len(self, fp: str) -> float:
        """Return clip length in seconds, or 0 if unreadable."""
        try:
            import av
            with av.open(fp) as c:
                v  = next((s for s in c.streams if s.type == "video"), None)
                tb = v.time_base if v else c.streams[0].time_base
                return float((v.duration or c.duration) * tb)
        except Exception:
            return 0.0

    def _prime_static(self):
        if not self.static_vp:
            return
        off = random.uniform(0, max(0, self.static_len - self.min_static))
        self.static_vp.open(self.static_fp, off)
        self.static_vp.set_volume(1.0)
        self.static_vp.player.set_state(Gst.State.PAUSED)

    def _path_off(self, ch: int, when: float):
        chan = self.ch_mgr.channels.get(ch)
        if not chan or not chan.files:
            off = ((when - self.ref_time) % self.static_len) if self.static_len else 0.0
            return self.static_fp, off
        off = self.ch_mgr.offset(ch, self.ref_time + wall_clock(), self.ref_time)

        return chan.path, off

    def _open_channel(self, ch: int):
        path, off = self._path_off(ch, time.time())
        self.player.open(path, off); self.curr_path = path
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

    def _close_tmp(self):
        if self.tmp_vp:
            self.tmp_vp.close(); self.tmp_vp = None

    # ---------------------------------------------------------------- transition
    def _begin_static(self, dest: int):
        """Start a channel change masked by static."""
        self.player.close()                      # stop current channel

        if self.static_vp:                       # show / resume snow
            if self.static_vp.player.get_state(0)[1] != Gst.State.PLAYING:
                self.static_vp.player.set_state(Gst.State.PLAYING)
            self.static_vp.set_volume(1.0)

        self.phase        = "static"
        self.static_start = time.time()
        self.next_ch      = dest
        self.tid         += 1
        self._close_tmp()
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

        threading.Thread(
            target=self._loader, args=(dest, self.tid), daemon=True
        ).start()

    def _loader(self, dest_ch: int, tid_tag: int):
        """Background thread: open target once at reveal timestamp."""
        reveal_ts = self.static_start + self.min_static
        path, off = self._path_off(dest_ch, reveal_ts)

        vp = VideoPlayer()
        try:
            vp.open(path, off)
            vp.set_volume(0.0)          # keep audio muted while hidden
        except Exception:
            return

        # Push reveal out by 50 ms guard if preroll slower than window
        reveal_ts = max(reveal_ts, time.time() + 0.05)
        delay = reveal_ts - time.time()
        if delay > 0:
            time.sleep(delay)

        if tid_tag == self.tid:
            self.tmp_vp = vp
        else:
            vp.close()

    def _maybe_finish_static(self):
        if self.phase != "static" or not self.tmp_vp:
            return
        if time.time() - self.static_start < self.min_static:
            return

        if self.static_vp:
            self.static_vp.set_volume(0.0)
            self.static_vp.player.set_state(Gst.State.PAUSED)
            self._prime_static()

        self.tmp_vp.set_volume(1.0)     # un-mute new channel
        self.player     = self.tmp_vp
        self.curr_ch    = self.next_ch
        self.curr_path  = self.player.path
        self.tmp_vp     = None
        self.phase      = "normal"

    # ---------------------------------------------------------------- main loop
    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == QUIT:
                    running = False
                elif e.type == KEYDOWN:
                    if e.key in (K_ESCAPE, K_q):
                        running = False
                    elif e.key == K_i:
                        self.force_overlay = not self.force_overlay
                    elif e.key in (K_RIGHT, K_SPACE, K_LEFT) and self.phase == "normal":
                        nxt = self.ch_mgr.next(self.curr_ch) if e.key in (K_RIGHT, K_SPACE) \
                              else self.ch_mgr.prev(self.curr_ch)
                        self._begin_static(nxt)
                    elif e.key == K_f:
                        config.FULLSCREEN ^= True
                        self.screen = pygame.display.set_mode(
                            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
                            pygame.FULLSCREEN if config.FULLSCREEN else 0)
                        pygame.mouse.set_visible(False)

            # life-cycle updates
            if self.phase == "normal":
                p_now, _ = self._path_off(self.curr_ch, time.time())
                if p_now != self.curr_path:
                    self.player.open(*self._path_off(self.curr_ch, time.time()))
                    self.curr_path = p_now
            else:
                self._maybe_finish_static()

            # render background layer
            if self.phase == "static" and self.static_vp:
                frame = self.static_vp.decode_frame()
                surf  = pygame.image.frombuffer(frame, frame.shape[1::-1], "RGB")
                surf  = pygame.transform.scale(surf, self.screen.get_size())
                self.screen.blit(surf, (0, 0))
                if self.tmp_vp:          # keep hidden pipeline warm
                    self.tmp_vp.decode_frame()
            else:
                frame = self.player.decode_frame()
                render_frame(self.screen, frame, self.player.sar)

            # overlay (honour timeout and ‘i’ toggle)
            show_overlay = self.force_overlay or time.time() < self.overlay_expire
            if show_overlay:
                draw_overlay(
                    self.screen,
                    self.curr_ch if self.phase == "normal" else self.next_ch,
                    self.ch_mgr,
                    self.ref_time,
                    time.time() - self.static_start if self.phase == "static" else 0.0,
                    self.phase == "static"
                )

            pygame.display.flip()
            self.clock.tick(config.FPS)

        self.player.close()
        if self.static_vp: self.static_vp.close()
        pygame.quit()


if __name__ == "__main__":
    TVEmulator().run()
