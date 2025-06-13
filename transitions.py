# transitions.py
"""
Transition effects between channels: blocky static noise + low-pass filtered audio,
or a fade. Parameters are read from config.py so you can tweak them there.
"""
import time
import numpy as np
import pygame
import config

def static_transition(screen):
    """
    Display blocky “analog” static for config.STATIC_DURATION seconds
    and play matching low-pass filtered sound.
    """
    # ── Audio setup ─────────────────────────────────────────────
    sr       = 44100
    n        = int(sr * config.STATIC_DURATION)
    white    = np.random.randn(n).astype(np.float32)

    # design one-pole low-pass
    dt    = 1.0 / sr
    rc    = 1.0 / (2 * np.pi * config.STATIC_CUTOFF_HZ)
    alpha = dt / (rc + dt)

    filtered = np.empty_like(white)
    filtered[0] = white[0]
    for i in range(1, n):
        filtered[i] = alpha * white[i] + (1 - alpha) * filtered[i-1]

    # scale & stereo
    buf16   = np.int16(np.clip(filtered, -1, 1) * (32767 // 4))
    stereo  = np.repeat(buf16[:, None], 2, axis=1)
    sound   = pygame.sndarray.make_sound(stereo.copy(order='C'))
    sound.play(-1)

    # ── Image setup ─────────────────────────────────────────────
    sw, sh    = screen.get_size()
    bs        = config.STATIC_BLOCK_SIZE
    small_w   = (sw + bs - 1) // bs
    small_h   = (sh + bs - 1) // bs

    t0 = time.time()
    while (time.time() - t0) < config.STATIC_DURATION:
        # 1) Gaussian mid-gray noise
        base = np.random.normal(128, config.STATIC_GAUSS_SIGMA, (small_h, small_w))
        img  = np.clip(base, 0, 255).astype(np.uint8)[..., None]
        img  = np.repeat(img, 3, axis=2)

        # 2) Upscale blocks
        img = np.repeat(np.repeat(img, bs, axis=0), bs, axis=1)[:sh, :sw]

        # 3) Scan-lines
        img[::2, :] = (img[::2, :] * config.STATIC_SCANLINE_INTENSITY).astype(np.uint8)

        # 4) Horizontal tear
        band_h = int(sh * config.STATIC_TEAR_BAND_PCT)
        y0     = np.random.randint(0, sh - band_h)
        dx     = np.random.randint(-config.STATIC_TEAR_MAX_SHIFT, config.STATIC_TEAR_MAX_SHIFT)
        img[y0:y0+band_h] = np.roll(img[y0:y0+band_h], dx, axis=1)

        # 5) Brightness flicker
        flick = np.random.uniform(*config.STATIC_FLICKER_RANGE)
        img   = np.clip(img * flick, 0, 255).astype(np.uint8)

        # Draw & flip
        pygame.surfarray.blit_array(screen, img.swapaxes(0, 1))
        pygame.display.flip()
        pygame.time.delay(16)  # ~60 FPS

    sound.stop()


def fade_transition(screen, old_surface, new_surface, duration: float = 0.5):
    """
    Fade out from old_surface, then fade in to new_surface.
    """
    steps  = max(1, int(duration * 30))
    half_ms = int((duration * 1000) / 2)

    # fade out
    for i in range(steps):
        alpha = int(255 * (i / steps))
        screen.blit(old_surface, (0, 0))
        o = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        o.fill((0, 0, 0, alpha))
        screen.blit(o, (0, 0))
        pygame.display.flip()
        pygame.time.delay(half_ms // steps)

    # fade in
    for i in range(steps):
        alpha = int(255 * (1 - i / steps))
        screen.fill((0, 0, 0))
        ns = new_surface.copy()
        ns.set_alpha(alpha)
        screen.blit(ns, (0, 0))
        pygame.display.flip()
        pygame.time.delay(half_ms // steps)

    screen.blit(new_surface, (0, 0))
    pygame.display.flip()
