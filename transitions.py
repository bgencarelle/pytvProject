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

from config import _CHUNK_DURATION, _FADE_OUT_SEC, MOVIES_PATH,FPS
from video_player import VideoPlayer


_STATIC_CLIP    = os.path.join(MOVIES_PATH, "static_video.mp4")

def static_transition(screen: pygame.Surface, overlay_fn=None, clock=None):
    """
    Play a random `_CHUNK_DURATION` snippet of static_video.mp4,
    draw `overlay_fn` on top, fade audio, then return.
    """
    pygame.mouse.set_visible(True)
    pygame.mouse.set_visible(False)
    clock = clock or pygame.time.Clock()      # use main clock if caller passes it

    # ── clip duration & random start ────────────────────────────
    total = 0.0
    try:
        with av.open(_STATIC_CLIP) as c:
            v = next(s for s in c.streams if s.type == "video")
            total = float((v.duration or c.duration) * v.time_base)
    except Exception:
        pass
    start_off = random.uniform(0.0, max(0.0, total - _CHUNK_DURATION))

    # ── temp player ─────────────────────────────────────────────
    vp = VideoPlayer()
    vp.open(_STATIC_CLIP, start_offset=start_off)

    sw, sh = screen.get_size()
    t_end  = time.time() + _CHUNK_DURATION
    t_fade = t_end - _FADE_OUT_SEC

    # ── render loop ─────────────────────────────────────────────
    while (now := time.time()) < t_end:
        frame = vp.decode_frame()
        surf  = pygame.transform.scale(
                    pygame.image.frombuffer(frame, frame.shape[1::-1], "RGB"),
                    (sw, sh))
        screen.blit(surf, (0, 0))

        if overlay_fn:
            overlay_fn(screen)

        pygame.display.flip()
        clock.tick(FPS)               # ← replaces delay(16)

        if now >= t_fade:
            vp.fade_out(t_end - now)
            t_fade = float("inf")

    vp.close()
