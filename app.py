"""
app.py – pause-card edition (static-safe)

Plays movies, shows pause cards, masks channel switches with static,
synchronised by the µ-second ChannelManager timeline.
"""

from __future__ import annotations

import bisect, os, random, threading, time
from typing import Optional

import gi                        # silence version warning
gi.require_version("Gst", "1.0") # must precede import Gst
from gi.repository import Gst

import pygame
from pygame.locals import *

import config
from channel_manager import ChannelManager, PAUSE_SENTINEL
from overlays         import draw_overlay
from renderer         import render_frame
from video_player     import VideoPlayer


# ── helpers ────────────────────────────────────────────────────────────────
def _probe_len(fp: str) -> float:
    """Best-effort clip length in seconds (0.0 on failure)."""
    try:
        import av
        with av.open(fp) as c:
            v  = next((s for s in c.streams if s.type == "video"), None)
            tb = v.time_base if v else c.streams[0].time_base
            return float((v.duration or c.duration or 0) * tb)
    except Exception:
        return 0.0


def _draw_pause_card(surface: pygame.Surface,
                     ch_mgr: ChannelManager,
                     ch: int,
                     ref_time: float) -> None:
    """Full-screen black with centred green programme titles."""
    w, h = surface.get_size()
    surface.fill((0, 0, 0))

    chan = ch_mgr.channels.get(ch)
    if not chan:
        return

    rel_us = int((time.time() - ref_time) * 1_000_000) % chan.total_us
    idx    = bisect.bisect_right(chan.start_us, rel_us) - 1
    files  = chan.files
    n      = len(files)

    # previous real clip
    prev = (idx - 1) % n
    while files[prev] == PAUSE_SENTINEL:
        prev = (prev - 1) % n
    prev_fn = os.path.basename(files[prev])

    # next real clip
    nxt = (idx + 1) % n
    while files[nxt] == PAUSE_SENTINEL:
        nxt = (nxt + 1) % n
    next_fn = os.path.basename(files[nxt])

    font  = pygame.font.SysFont("monospace", h // 24)
    green = (0, 255, 0)
    lines = ["Just played:", prev_fn, "", "Coming up next:", next_fn]
    total = len(lines) * font.get_linesize()
    y     = (h - total) // 2
    for ln in lines:
        txt = font.render(ln, True, green)
        x   = (w - txt.get_width()) // 2
        surface.blit(txt, (x, y)); y += font.get_linesize()


# ── main application ───────────────────────────────────────────────────────
class TVEmulator:
    def __init__(self):
        Gst.init(None)

        # window ----------------------------------------------------------
        pygame.init(); pygame.mixer.init()
        self.screen = pygame.display.set_mode(
            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
            pygame.FULLSCREEN if config.FULLSCREEN else 0,
        )
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        # core state ------------------------------------------------------
        self.ch_mgr   = ChannelManager(config.MOVIES_PATH)
        self.ref_time = config.REFERENCE_START_TIME
        self.curr_ch  = config.START_CHANNEL or self.ch_mgr.min_ch
        self.player   = VideoPlayer()
        self.curr_path = ""
        self.dest_path = None          # NEW: what static will reveal

        # static resources ------------------------------------------------
        self.static_fp  = os.path.join(config.MOVIES_PATH, "static_video.mp4")
        self.static_len = _probe_len(self.static_fp)
        self.min_static = getattr(config, "STATIC_DURATION", 0.5)
        self.static_vp  = VideoPlayer() if self.static_len else None
        if self.static_vp: self._prime_static()

        # transition / overlay -------------------------------------------
        self.phase, self.static_start = "normal", 0.0
        self.next_ch: Optional[int] = None
        self.tmp_vp:  Optional[VideoPlayer] = None
        self.tid = 0
        self.overlay_expire = time.time() + config.OVERLAY_DURATION
        self.force_overlay  = False
        if not hasattr(config, "SHOW_OVERLAYS"): config.SHOW_OVERLAYS = False

        self._open_channel(self.curr_ch)

    # ── helpers ----------------------------------------------------------
    def _prime_static(self):
        off = random.uniform(0, max(0, self.static_len - self.min_static))
        self.static_vp.open(self.static_fp, off)
        self.static_vp.set_volume(1.0)
        self.static_vp.player.set_state(Gst.State.PAUSED)

    def _path_off(self, ch: int, when: float):
        chan = self.ch_mgr.channels.get(ch)
        if not chan or not chan.files:
            off = ((when - self.ref_time) % self.static_len) if self.static_len else 0.0
            return self.static_fp, off
        off = self.ch_mgr.offset(ch, when, self.ref_time)
        return chan.path, off

    def _open_channel(self, ch: int):
        path, off = self._path_off(ch, time.time())
        if path != PAUSE_SENTINEL:
            self.player.open(path, off)
        else:
            self.player.close()
        self.curr_path = path
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

    # ── static-masked transition ---------------------------------------
    def _close_tmp(self):
        if self.tmp_vp: self.tmp_vp.close(); self.tmp_vp = None

    def _begin_static(self, dest: int):
        self.player.close()
        if self.static_vp:
            self.static_vp.player.set_state(Gst.State.PLAYING)
            self.static_vp.set_volume(1.0)

        self.phase, self.static_start = "static", time.time()
        self.next_ch, self.tid = dest, self.tid + 1
        self._close_tmp()
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

        # decide upfront what we will show at burst end
        self.dest_path, dest_off = self._path_off(dest, self.static_start + self.min_static)
        if self.dest_path != PAUSE_SENTINEL:
            threading.Thread(target=self._loader,
                             args=(dest, self.tid, dest_off),
                             daemon=True).start()

    # --- inside _loader() ---------------------------------------------------
    def _loader(self, dest_ch: int, tid_tag: int, off: float):
        vp = VideoPlayer()
        try:
            vp.open(self.dest_path, off)
            vp.set_volume(0.0)
            vp.player.set_state(Gst.State.PAUSED)  # <<< freeze immediately
        except Exception:
            return

        reveal_ts = self.static_start + self.min_static  # no extra +50 ms
        time_to_go = reveal_ts - time.time()
        if time_to_go > 0:
            time.sleep(time_to_go)

        # start the clock exactly on cue
        vp.player.set_state(Gst.State.PLAYING)

        if tid_tag == self.tid:
            self.tmp_vp = vp
        else:
            vp.close()

    def _maybe_finish_static(self):
        if self.phase != "static": return
        if time.time() - self.static_start < self.min_static: return

        # ready when either pause card or preloaded vp is in place
        if self.dest_path == PAUSE_SENTINEL or self.tmp_vp:
            if self.static_vp:
                self.static_vp.player.set_state(Gst.State.PAUSED)
                self.static_vp.set_volume(0.0); self._prime_static()

            if self.dest_path == PAUSE_SENTINEL:
                self.player.close(); self.curr_path = PAUSE_SENTINEL
            else:
                self.tmp_vp.set_volume(1.0)
                self.player     = self.tmp_vp
                self.curr_path  = self.player.path
                self.tmp_vp     = None

            self.curr_ch = self.next_ch
            self.phase   = "normal"

    # ── main loop -------------------------------------------------------
    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                if   e.type == QUIT: running = False
                elif e.type == KEYDOWN:
                    if   e.key in (K_ESCAPE, K_q): running = False
                    elif e.key == K_i: self.force_overlay ^= True
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

            if self.phase == "normal":
                p_now, _ = self._path_off(self.curr_ch, time.time())
                if p_now != self.curr_path: self._open_channel(self.curr_ch)
            else:
                self._maybe_finish_static()

            # draw --------------------------------------------------------
            if self.curr_path == PAUSE_SENTINEL:
                _draw_pause_card(self.screen, self.ch_mgr, self.curr_ch, self.ref_time)

            elif self.phase == "static" and self.static_vp:
                frame = self.static_vp.decode_frame()
                surf  = pygame.image.frombuffer(frame, frame.shape[1::-1], "RGB")
                surf  = pygame.transform.scale(surf, self.screen.get_size())
                self.screen.blit(surf, (0, 0))
                if self.tmp_vp: self.tmp_vp.decode_frame()

            else:
                frame = self.player.decode_frame()
                render_frame(self.screen, frame, self.player.sar)

            # overlay -----------------------------------------------------
            show = self.force_overlay or time.time() < self.overlay_expire
            if show:
                draw_overlay(
                    self.screen,
                    self.curr_ch if self.phase == "normal" else self.next_ch,
                    self.ch_mgr,
                    self.ref_time,
                    time.time() - self.static_start if self.phase == "static" else 0.0,
                    self.phase == "static",
                )

            pygame.display.flip()
            self.clock.tick(config.FPS)

        # shutdown -------------------------------------------------------
        self.player.close()
        if self.static_vp: self.static_vp.close()
        pygame.quit()


if __name__ == "__main__":
    TVEmulator().run()
