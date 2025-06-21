"""
overlays.py

Pygame overlay renderer for the fake-TV emulator.
"""

from __future__ import annotations

import os, time, pygame, config
from channel_manager import PAUSE_SENTINEL          # NEW

# ── colours ────────────────────────────────────────────────────────────────
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED   = (255,  50, 50)
YEL   = (200, 200, 50)
BG    = (0, 0, 0, 180)

if not hasattr(config, "SHOW_OVERLAYS"):
    config.SHOW_OVERLAYS = False
if not hasattr(config, "STATIC_BURST_SEC"):
    config.STATIC_BURST_SEC = 0.50

pygame.font.init()


# ── helpers ────────────────────────────────────────────────────────────────
def _compute_font_sizes(h: int) -> tuple[int, int, int]:
    return max(12, h // 60), max(16, h // 45), max(24, h // 15)


def _fmt_hms(sec: float) -> str:
    sec = int(max(0, sec))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_hmsf(sec: float, fps: int) -> str:
    tf     = int(max(0.0, sec) * fps + 1e-4)
    frame  = tf % fps
    s_int  = tf // fps
    m, s   = divmod(s_int, 60)
    h, m   = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{frame:02d}"


def _next_real(index: int, files: list[str]) -> int:
    """Return the index of the next entry that is **not** a pause sentinel."""
    n = len(files)
    for i in range(1, n + 1):
        j = (index + i) % n
        if files[j] != PAUSE_SENTINEL:
            return j
    return index  # fallback – should never reach


# ── main entry point ───────────────────────────────────────────────────────
def draw_overlay(
    surface: pygame.Surface,
    ch_num: int,
    ch_mgr,
    ref_time: float,
    static_elapsed: float,
    transitioning: bool,
) -> None:
    sw, sh = surface.get_width(), surface.get_height()
    tiny_pt, small_pt, large_pt = _compute_font_sizes(sh)
    FT = pygame.font.SysFont("monospace", tiny_pt)
    FS = pygame.font.SysFont("monospace", small_pt)
    FL = pygame.font.SysFont("monospace", large_pt)

    # ── channel badge (always) ───────────────────────────────────────────
    chsurf = FL.render(f"CH {ch_num:02d}", True, GREEN)
    chbg   = pygame.Surface(
        (chsurf.get_width() + large_pt // 3, chsurf.get_height() + large_pt // 5),
        pygame.SRCALPHA,
    )
    chbg.fill(BG)
    chbg.blit(chsurf, (large_pt // 6, large_pt // 10))
    surface.blit(chbg, (sw - chbg.get_width() - 10, 10))

    if not config.SHOW_OVERLAYS:
        return

    now = time.time()

    # ── wall clock ───────────────────────────────────────────────────────
    run_ms            = pygame.time.get_ticks()
    run_m, run_s      = divmod(run_ms // 1000, 60)
    clock_txt         = f"{time.strftime('%H:%M:%S')}  +{run_m:02d}:{run_s:02d}"
    clocksurf         = FS.render(clock_txt, True, YEL)
    clockbg           = pygame.Surface(
        (clocksurf.get_width() + small_pt // 3, clocksurf.get_height() + small_pt // 5),
        pygame.SRCALPHA,
    )
    clockbg.fill(BG)
    clockbg.blit(clocksurf, (small_pt // 6, small_pt // 10))
    surface.blit(clockbg, (10, 10))

    # ── CPU load ─────────────────────────────────────────────────────────
    try:
        cpu_pct = os.getloadavg()[0] / os.cpu_count() * 100
    except Exception:
        cpu_pct = 0.0
    cpusurf = FS.render(f"CPU {cpu_pct:.0f}%", True, RED)
    cpubg   = pygame.Surface(
        (cpusurf.get_width() + small_pt // 3, cpusurf.get_height() + small_pt // 5),
        pygame.SRCALPHA,
    )
    cpubg.fill(BG)
    cpubg.blit(cpusurf, (small_pt // 6, small_pt // 10))
    surface.blit(cpubg, (10, 10 + clockbg.get_height() + 5))

    # ── playlist panel ──────────────────────────────────────────────────
    lines: list[str] = []
    chan             = ch_mgr.channels.get(ch_num)

    if chan and chan.files:
        durations = [d / 1_000_000 for d in chan.durations_us]
        total_dur = chan.total_us / 1_000_000

        lines.append(f"Total len  {_fmt_hms(total_dur)}")

        off      = ch_mgr.offset(ch_num, now, ref_time)
        pin      = off % total_dur
        lines.append(f"Position      {_fmt_hms(pin)}")

        idx      = chan.files.index(chan.path)
        cur_fp   = "PAUSE" if chan.path == PAUSE_SENTINEL else os.path.basename(chan.path)
        cur_len  = durations[idx]
        remain   = max(0.0, cur_len - off)

        nxt_idx  = _next_real(idx, chan.files)
        nxt_fp   = os.path.basename(chan.files[nxt_idx])

        lines += [
            f"Current  {cur_fp}",
            f"   rem   {_fmt_hms(remain)}",
            f"Next    {nxt_fp}",
            "——  upcoming  ——",
        ]

        cum = 0.0
        for fp, dur in zip(chan.files, durations):
            start = cum
            cum  += dur
            if fp == PAUSE_SENTINEL:
                continue  # skip pauses in the list
            until = start - pin if start >= pin else total_dur - pin + start
            lines.append(f"{os.path.basename(fp)}  in {_fmt_hms(until)}")
    else:
        lines.append("No videos – static loop")

    if transitioning:
        lines.append(
            f"Static burst {_fmt_hms(static_elapsed)} / "
            f"{_fmt_hms(config.STATIC_BURST_SEC)}"
        )

    # ── panel background ────────────────────────────────────────────────
    widest = max(FT.size(t)[0] for t in lines)
    pbg = pygame.Surface(
        (widest + 20, len(lines) * (FT.get_linesize() + 2) + 10),
        pygame.SRCALPHA,
    )
    pbg.fill(BG)
    y = 5
    for t in lines:
        pbg.blit(FT.render(t, True, WHITE), (10, y))
        y += FT.get_linesize() + 2
    surface.blit(pbg, (sw - pbg.get_width() - 10, 10 + chbg.get_height() + 10))

    # ── bottom-right timestamp ──────────────────────────────────────────
    ttxt = (
        f"{static_elapsed:04.1f}s"
        if transitioning
        else _fmt_hmsf(
            off if chan and chan.files else static_elapsed,
            config.FPS,
        )
    )
    tssurf = FS.render(ttxt, True, WHITE)
    tsbg   = pygame.Surface(
        (tssurf.get_width() + small_pt // 3, tssurf.get_height() + small_pt // 5),
        pygame.SRCALPHA,
    )
    tsbg.fill(BG)
    tsbg.blit(tssurf, (small_pt // 6, small_pt // 10))
    surface.blit(tsbg, (sw - tsbg.get_width() - 10, sh - tsbg.get_height() - 10))
