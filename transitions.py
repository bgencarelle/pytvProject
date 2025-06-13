# transitions.py
"""
Transition effects between channels: blocky static noise + low-pass filtered audio,
or a fade. You can adjust block size and cutoff frequency.
"""
import time
import numpy as np
import pygame

def static_transition(
    screen,
    duration: float = 1.5,
    block_size: int = 2,
    cutoff_hz: float = 4000.0
):
    """
    Display blocky white-noise static on the screen and play matching low-pass
    filtered sound.

    Args:
      screen:        pygame.Surface (your video display).
      duration:      how long the transition lasts, in seconds.
      block_size:    size of each square “pixel” of static in screen pixels.
      cutoff_hz:     low-pass cutoff frequency in Hz for the audio hiss.
    """
    # ── Prepare audio buffer ─────────────────────────────────────────
    sr  = 44100
    n   = int(sr * duration)
    # generate raw white noise (float in –1..1)
    noise = np.random.randn(n).astype(np.float32)

    # design single-pole low-pass filter (RC filter)
    dt      = 1.0 / sr
    rc      = 1.0 / (2 * np.pi * cutoff_hz)
    alpha   = dt / (rc + dt)

    # apply IIR: y[n] = alpha * x[n] + (1-alpha) * y[n-1]
    filtered = np.empty_like(noise)
    filtered[0] = noise[0]
    for i in range(1, n):
        filtered[i] = alpha * noise[i] + (1 - alpha) * filtered[i-1]

    # scale to int16 range and make stereo
    buf16    = np.int16(np.clip(filtered, -1, 1) * (32767//4))
    stereo16 = np.repeat(buf16[:, None], 2, axis=1)
    sound    = pygame.sndarray.make_sound(stereo16.copy(order='C'))

    # play the looped static audio
    sound.play(-1)

    # ── Prepare blocky static image ─────────────────────────────────
    sw, sh      = screen.get_size()
    small_w     = (sw + block_size - 1) // block_size
    small_h     = (sh + block_size - 1) // block_size

    t0 = time.time()
    while (time.time() - t0) < duration:
        # generate small noise and scale up
        block_noise = np.random.randint(
            0, 256, (small_h, small_w, 3), dtype=np.uint8
        )
        # upscale by repeating pixels
        noise_img = np.repeat(
            np.repeat(block_noise, block_size, axis=0),
            block_size, axis=1
        )
        # crop to screen size
        noise_img = noise_img[:sh, :sw]

        # blit to screen
        pygame.surfarray.blit_array(screen, noise_img.swapaxes(0, 1))
        pygame.display.flip()

        # ~60fps
        pygame.time.delay(16)

    # stop static sound
    sound.stop()

def fade_transition(screen, old_surface, new_surface, duration=0.5):
    """
    Fade out from old_surface, then fade in to new_surface.
    """
    steps = max(1, int(duration * 30))
    # fade out
    for i in range(steps):
        alpha = int(255 * (i / steps))
        screen.blit(old_surface, (0, 0))
        o = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        o.fill((0, 0, 0, alpha))
        screen.blit(o, (0, 0))
        pygame.display.flip()
        pygame.time.delay(int((duration/2) * 1000 / steps))
    # fade in
    for i in range(steps):
        alpha = int(255 * (1 - i / steps))
        screen.fill((0, 0, 0))
        ns = new_surface.copy()
        ns.set_alpha(alpha)
        screen.blit(ns, (0, 0))
        pygame.display.flip()
        pygame.time.delay(int((duration/2) * 1000 / steps))
    screen.blit(new_surface, (0, 0))
    pygame.display.flip()
