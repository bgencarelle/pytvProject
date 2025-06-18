"""
Draws on-screen overlays: channel label (always),
plus timestamp, CPU usage, and real+run time (when enabled).
Font sizes scale relative to the screen height.
Positions and margins are declared at the top.
"""
import pygame
import os
import time
import config  # for SHOW_OVERLAYS

pygame.font.init()

# Margins (in pixels) for overlay placement
CHANNEL_MARGIN_X     = 10  # from right edge for channel label
CHANNEL_MARGIN_Y     = 10  # from top edge for channel label
TIMESTAMP_MARGIN_X   = 10  # from right edge for video timestamp
TIMESTAMP_MARGIN_Y   = 10  # from bottom edge for video timestamp
CPU_MARGIN_X         = 10  # from left edge for CPU usage
CPU_MARGIN_Y         = 10  # from bottom edge for CPU usage
REALTIME_MARGIN_X    = 10  # from left edge for real+run time
REALTIME_MARGIN_Y    = 10  # from top edge for real+run time

def _compute_font_sizes(screen_height: int):
    # Base divisor values tuned for 1080p reference
    ts_size = max(12, screen_height // 45)
    ch_size = max(18, screen_height // 15)
    return ts_size, ch_size

def draw_overlay(surface: pygame.Surface, channel: int, seconds: float):
    sh = surface.get_height()
    sw = surface.get_width()
    ts_size, ch_size = _compute_font_sizes(sh)
    ts_font = pygame.font.Font(None, ts_size)
    ch_font = pygame.font.Font(None, ch_size)

    # --- Channel label (always drawn, top-right) ---
    ch_text = f"CH {channel:02d}"
    ch_surf = ch_font.render(ch_text, True, (0,255,0))
    ch_bg = pygame.Surface((ch_surf.get_width() + ch_size//3,
                            ch_surf.get_height() + ch_size//5),
                           pygame.SRCALPHA)
    ch_bg.fill((0,0,0,128))
    ch_bg.blit(ch_surf, (ch_size//6, ch_size//10))
    x_ch = sw - ch_bg.get_width() - CHANNEL_MARGIN_X
    y_ch = CHANNEL_MARGIN_Y
    surface.blit(ch_bg, (x_ch, y_ch))

    if not config.SHOW_OVERLAYS:
        return

    # --- Video timestamp (bottom-right) ---
    mm, ss = divmod(int(seconds), 60)
    ts_text = f"{mm:02d}:{ss:02d}"
    ts_surf = ts_font.render(ts_text, True, (255,255,255))
    ts_bg = pygame.Surface((ts_surf.get_width() + ts_size//3,
                            ts_surf.get_height() + ts_size//5),
                           pygame.SRCALPHA)
    ts_bg.fill((0,0,0,128))
    ts_bg.blit(ts_surf, (ts_size//6, ts_size//10))
    x_ts = sw - ts_bg.get_width() - TIMESTAMP_MARGIN_X
    y_ts = sh - ts_bg.get_height() - TIMESTAMP_MARGIN_Y
    surface.blit(ts_bg, (x_ts, y_ts))

    # --- CPU usage (bottom-left) ---
    try:
        load1, _, _ = os.getloadavg()
        cpu_pct = (load1 / os.cpu_count()) * 100
    except Exception:
        cpu_pct = 0.0
    cpu_text = f"CPU {cpu_pct:.0f}%"
    cpu_surf = ts_font.render(cpu_text, True, (255,50,50))
    cpu_bg = pygame.Surface((cpu_surf.get_width() + ts_size//3,
                             cpu_surf.get_height() + ts_size//5),
                            pygame.SRCALPHA)
    cpu_bg.fill((0,0,0,128))
    cpu_bg.blit(cpu_surf, (ts_size//6, ts_size//10))
    x_cpu = CPU_MARGIN_X
    y_cpu = sh - cpu_bg.get_height() - CPU_MARGIN_Y
    surface.blit(cpu_bg, (x_cpu, y_cpu))

    # --- Real time + run time (upper-left) ---
    now_str = time.strftime("%H:%M:%S")
    run_sec = pygame.time.get_ticks() // 1000
    rm, rs = divmod(int(run_sec), 60)
    rt_text = f"{now_str} +{rm:02d}:{rs:02d}"
    rt_surf = ts_font.render(rt_text, True, (200,200,50))
    rt_bg = pygame.Surface((rt_surf.get_width() + ts_size//3,
                            rt_surf.get_height() + ts_size//5),
                           pygame.SRCALPHA)
    rt_bg.fill((0,0,0,128))
    rt_bg.blit(rt_surf, (ts_size//6, ts_size//10))
    x_rt = REALTIME_MARGIN_X
    y_rt = REALTIME_MARGIN_Y
    surface.blit(rt_bg, (x_rt, y_rt))


def draw_timestamp(screen: pygame.Surface, secs: float):
    if not config.SHOW_OVERLAYS:
        return
    pygame.mouse.set_visible(False)

    sh = screen.get_height()
    sw = screen.get_width()
    ts_size, _ = _compute_font_sizes(sh)
    ts_font = pygame.font.Font(None, ts_size)

    mm, ss = divmod(int(secs), 60)
    txt = f"{mm:02d}:{ss:02d}"
    surf = ts_font.render(txt, True, (255,255,255))
    r = surf.get_rect(bottomright=(sw - TIMESTAMP_MARGIN_X,
                                   sh - TIMESTAMP_MARGIN_Y))
    bg = pygame.Surface((r.width + ts_size//3,
                         r.height + ts_size//5),
                        pygame.SRCALPHA)
    bg.fill((0,0,0,128))
    bg.blit(surf, (ts_size//6, ts_size//10))
    screen.blit(bg, r.topleft)


def draw_channel(screen: pygame.Surface, ch: int):
    # channel label always drawn (same position as in draw_overlay)
    pygame.mouse.set_visible(False)

    sh = screen.get_height()
    _, ch_size = _compute_font_sizes(sh)
    ch_font = pygame.font.Font(None, ch_size)

    txt = f"CH {ch:02d}"
    surf = ch_font.render(txt, True, (0,255,0))
    r = surf.get_rect(topright=(screen.get_width() - CHANNEL_MARGIN_X,
                                CHANNEL_MARGIN_Y))
    bg = pygame.Surface((r.width + ch_size//3,
                         r.height + ch_size//5),
                        pygame.SRCALPHA)
    bg.fill((0,0,0,128))
    bg.blit(surf, (ch_size//6, ch_size//10))
    screen.blit(bg, r.topleft)
