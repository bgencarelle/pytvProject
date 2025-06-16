# transitions.py
"""
Transition effects between channels: play random 2 s chunks
of a pre-rendered static_video.mp4 (video+audio), drawing an
overlay each frame, and now fading out the static’s audio.
"""
import os
import time
import random

import av
import pygame

import config
from video_player import VideoPlayer

_STATIC_CLIP    = os.path.join(config.MOVIES_PATH, "static_video.mp4")
_CHUNK_DURATION = 1.0    # seconds of static per transition
_FADE_OUT_SEC   = 0.01   # fade out static audio over last 0.5 s

def static_transition(screen: pygame.Surface, overlay_fn=None):
    """
    Play a random 2 s snippet of static_video.mp4, draw overlay_fn each
    frame on top, then fade the static audio out over the last 0.5 s.
    """
    pygame.mouse.set_visible(False)

    # ── Probe clip duration ─────────────────────────────────────
    try:
        c     = av.open(_STATIC_CLIP)
        vs    = next(s for s in c.streams if s.type == "video")
        tb    = vs.time_base
        total = float((vs.duration or c.duration) * tb)
        c.close()
    except:
        total = 0.0

    # ── Pick random start (so we loop through different snow each time) ──
    start_off = random.uniform(0, max(0, total - _CHUNK_DURATION))

    # ── Launch a temporary VideoPlayer for the static snippet ─────────
    vp = VideoPlayer()
    vp.open(_STATIC_CLIP, start_offset=start_off)

    sw, sh = screen.get_size()
    t_end  = time.time() + _CHUNK_DURATION
    t_fade = t_end - _FADE_OUT_SEC

    # ── Render loop ───────────────────────────────────────────────
    while True:
        now = time.time()
        if now >= t_end:
            break

        # decode & display one frame
        frame = vp.decode_frame()
        surf  = pygame.image.frombuffer(frame, (frame.shape[1], frame.shape[0]), "RGB")
        surf  = pygame.transform.scale(surf, (sw, sh))
        screen.blit(surf, (0, 0))

        # overlay badge on top
        if overlay_fn:
            overlay_fn(screen)

        pygame.display.flip()
        pygame.time.delay(16)

        # start fading out static audio when we hit t_fade
        if now >= t_fade:
            # linear fade over remaining time
            remaining = t_end - now
            # avoid calling fade_out repeatedly
            if remaining > 0:
                vp.fade_out(remaining)
                # clamp so we don't fade again
                t_fade = float('inf')

    # ── Clean up ─────────────────────────────────────────────────
    vp.close()
