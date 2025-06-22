#!/usr/bin/env python3
"""
app.py – single-playbin static-burst edition

Plays movies and static bursts using a single VideoPlayer. All audio goes
through the same GStreamer sink, avoiding sink contention on embedded platforms.
Transitions are masked by a static clip played in-line.
"""
from __future__ import annotations

import bisect, os, random, time
from typing import Optional

import gi  # silence version warning
gi.require_version("Gst", "1.0")
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
        surface.blit(txt, (x, y))
        y += font.get_linesize()


# ── main application ───────────────────────────────────────────────────────
class TVEmulator:
    def __init__(self):
        Gst.init(None)

        # window ----------------------------------------------------------
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode(
            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
            pygame.FULLSCREEN if config.FULLSCREEN else 0,
        )
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        # core state ------------------------------------------------------
        self.ch_mgr    = ChannelManager(config.MOVIES_PATH)
        self.ref_time  = config.REFERENCE_START_TIME
        self.curr_ch   = config.START_CHANNEL or self.ch_mgr.min_ch
        self.player    = VideoPlayer()
        self.curr_path = ""
        # where to go after static
        self.next_file: Optional[str] = None
        self.next_off:  float         = 0.0

        # static resources ------------------------------------------------
        self.static_fp  = os.path.join(config.MOVIES_PATH, "static_video.mp4")
        self.static_len = _probe_len(self.static_fp)
        # how long to show static
        self.min_static = getattr(config, "STATIC_BURST_SEC", 1.0)

        # transition / overlay -------------------------------------------
        self.phase          = "normal"     # normal | static
        self.static_start   = 0.0
        self.next_ch: Optional[int] = None
        self.tid            = 0
        self.overlay_expire = time.time() + config.OVERLAY_DURATION
        self.force_overlay  = False
        if not hasattr(config, "SHOW_OVERLAYS"):
            config.SHOW_OVERLAYS = False

        # kick off first channel
        self._open_channel(self.curr_ch)

    # ── path/offset --------------------------------------------------------
    def _path_off(self, ch: int, when: float):
        chan = self.ch_mgr.channels.get(ch)
        if not chan or not chan.files:
            # static-only
            off = ((when - self.ref_time) % self.static_len) if self.static_len else 0.0
            return self.static_fp, off
        off = self.ch_mgr.offset(ch, when, self.ref_time)
        return chan.path, off

    def _open_channel(self, ch: int):
        path, off = self._path_off(ch, time.time())
        if path not in (PAUSE_SENTINEL, self.static_fp):
            self.player.open(path, off)
        else:
            self.player.close()
        self.curr_path = path
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

    # ── static-masked transition -----------------------------------------
    def _begin_static(self, dest: int):
        # 1. preload next channel in the background
        self.next_file, self.next_off = self._path_off(
            dest,
            time.time() + self.min_static
        )

        # 2. cut to static on the same player
        off = random.uniform(0.0, max(0.0, self.static_len - self.min_static))
        self.player.open(self.static_fp, off)
        self.player.set_volume(1.0)

        # 3. update state
        self.phase        = "static"
        self.static_start = time.time()
        self.next_ch      = dest
        self.tid         += 1
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

    def _maybe_finish_static(self):
        if self.phase != "static":
            return
        if time.time() - self.static_start < self.min_static:
            return

        # 4. swap into preloaded channel
        if self.next_file and self.next_file != PAUSE_SENTINEL:
            self.player.open(self.next_file, self.next_off)
        else:
            # sentinel or missing – close to show overlay/pause-card
            self.player.close()

        self.curr_ch   = self.next_ch
        self.curr_path = self.next_file or ""
        self.phase     = "normal"

    # ── main loop ---------------------------------------------------------
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
                        self.force_overlay ^= True
                    elif e.key in (K_RIGHT, K_SPACE, K_LEFT) and self.phase == "normal":
                        nxt = (
                            self.ch_mgr.next(self.curr_ch)
                            if e.key in (K_RIGHT, K_SPACE)
                            else self.ch_mgr.prev(self.curr_ch)
                        )
                        self._begin_static(nxt)
                    elif e.key == K_f:
                        config.FULLSCREEN ^= True
                        self.screen = pygame.display.set_mode(
                            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
                            pygame.FULLSCREEN if config.FULLSCREEN else 0
                        )
                        pygame.mouse.set_visible(False)

            if self.phase == "normal":
                p_now, _ = self._path_off(self.curr_ch, time.time())
                if p_now != self.curr_path:
                    self._open_channel(self.curr_ch)
            else:
                self._maybe_finish_static()

            # ── draw ------------------------------------------------------
            if self.curr_path == PAUSE_SENTINEL:
                _draw_pause_card(
                    self.screen,
                    self.ch_mgr,
                    self.curr_ch,
                    self.ref_time
                )
            else:
                frame = self.player.decode_frame()
                render_frame(self.screen, frame, self.player.sar)

            # ── overlay ---------------------------------------------------
            show = self.force_overlay or (time.time() < self.overlay_expire)
            if show:
                draw_overlay(
                    self.screen,
                    self.curr_ch if self.phase == "normal" else self.next_ch,
                    self.ch_mgr,
                    self.ref_time,
                    time.time() - self.static_start
                    if self.phase == "static" else 0.0,
                    self.phase == "static",
                )

            pygame.display.flip()
            self.clock.tick(config.FPS)

        self.player.close()
        pygame.quit()


if __name__ == "__main__":
    TVEmulator().run()
