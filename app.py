#!/usr/bin/env python3
"""
app.py – single-playbin static-burst edition (with EventManager)

Plays movies and static bursts using a single VideoPlayer.  All audio goes
through the same GStreamer sink.  Input is dispatched by events.py.
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
from events           import EventManager    # ← new import


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
        pygame.mouse.set_visible(False)
        self.screen = pygame.display.set_mode(
            (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
            pygame.FULLSCREEN if config.FULLSCREEN else 0,
        )
        self.clock = pygame.time.Clock()

        # core state ------------------------------------------------------
        self.ch_mgr    = ChannelManager(config.MOVIES_PATH)
        self.ref_time  = config.REFERENCE_START_TIME
        self.time_offset = 0.0  # <— your new, mutable offset
        self.curr_ch   = config.START_CHANNEL or self.ch_mgr.min_ch
        self.player    = VideoPlayer()
        self.curr_path = ""
        self.next_file: Optional[str] = None
        self.next_off:  float         = 0.0

        # static resources ------------------------------------------------
        self.static_fp  = os.path.join(config.MOVIES_PATH, "static_video.mp4")
        self.static_len = _probe_len(self.static_fp)
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

        self._open_channel(self.curr_ch)

    # ── path/offset --------------------------------------------------------
    def _path_off(self, ch: int, when: float):
        """
        Return (path, offset-in-seconds) for channel *ch* at wall-clock
        time *when*, honouring the runtime-adjustable self.time_offset.
        """
        effective_ref = self.ref_time + self.time_offset      # ← updated each call

        chan = self.ch_mgr.channels.get(ch)
        if not chan or not chan.files:                        # static loop
            off = ((when - effective_ref) % self.static_len) if self.static_len else 0.0
            return self.static_fp, off

        # NORMAL CHANNEL: use the shifted reference here too
        off = self.ch_mgr.offset(ch, when, effective_ref)
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
        # preload next channel
        self.next_file, self.next_off = self._path_off(
            dest,
            time.time() + self.min_static
        )

        # cut to static on the same pipeline
        off = random.uniform(0.0, max(0.0, self.static_len - self.min_static))
        self.player.open(self.static_fp, off)
        self.player.set_volume(1.0)

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

        # swap into preloaded channel
        if self.next_file and self.next_file != PAUSE_SENTINEL:
            self.player.open(self.next_file, self.next_off)
        else:
            self.player.close()

        self.curr_ch   = self.next_ch
        self.curr_path = self.next_file or ""
        self.phase     = "normal"

    # ── main loop ---------------------------------------------------------
    def run(self):
        running = True
        pygame.mouse.set_visible(False)
        while running:
            # --- inside TVEmulator.run() main loop --------------------------------
            for e in pygame.event.get():
                EventManager.handle(e, self.phase, self.curr_ch, self.ch_mgr)

            # NEW: drain external queue (non-blocking)
            while (act := EventManager.poll()):
                t = act["type"]
                if t == "quit":
                    running = False
                elif t == "toggle_overlay":
                    self.force_overlay ^= True
                elif t == "switch_channel":
                    dest = act["to"]
                    if dest == "next":
                        dest = self.ch_mgr.next(self.curr_ch)
                    elif dest == "prev":
                        dest = self.ch_mgr.prev(self.curr_ch)
                    self._begin_static(dest)
                elif t == "toggle_fullscreen":
                    config.FULLSCREEN ^= True
                    self.screen = pygame.display.set_mode(
                        (0, 0) if config.FULLSCREEN else config.WINDOWED_SIZE,
                        pygame.FULLSCREEN if config.FULLSCREEN else 0)
                    pygame.mouse.set_visible(False)
                elif t == "adjust_offset":
                    # 1) bump the global skew
                    self.time_offset += act.get("delta", 0.0)

                    # 2) recompute where the play-head should sit *now*
                    now = time.time()
                    path, off = self._path_off(self.curr_ch, now)

                    # 3) if we crossed into another file, open it; otherwise just seek
                    if path != self.curr_path:
                        self.curr_path = path
                        if path not in (PAUSE_SENTINEL, self.static_fp):
                            self.player.open(path, off)
                        else:
                            self.player.close()  # static or pause sentinel
                    else:
                        self.player.seek_to(off)  # same file → quick seek

            if self.phase == "normal":
                p_now, _ = self._path_off(self.curr_ch, time.time())
                if p_now != self.curr_path:
                    self._open_channel(self.curr_ch)
            else:
                self._maybe_finish_static()

            # draw
            if self.curr_path == PAUSE_SENTINEL:
                _draw_pause_card(self.screen, self.ch_mgr, self.curr_ch, self.ref_time)
            else:
                frame = self.player.decode_frame()
                render_frame(self.screen, frame, self.player.sar)

            # overlay
            show = self.force_overlay or (time.time() < self.overlay_expire)
            if show:
                draw_overlay(
                    self.screen,
                    self.curr_ch if self.phase == "normal" else self.next_ch,
                    self.ch_mgr,
                    self.ref_time,
                    time.time() - self.static_start if self.phase == "static" else 0.0,
                    self.phase == "static",
                    self.time_offset,
                )

            pygame.display.flip()
            self.clock.tick(config.FPS)

        self.player.close()
        pygame.quit()


if __name__ == "__main__":
    TVEmulator().run()
