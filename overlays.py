# =========  overlays.py  =========
import os, time, pygame, config

# fallbacks
if not hasattr(config, "SHOW_OVERLAYS"):
    config.SHOW_OVERLAYS = False
if not hasattr(config, "STATIC_BURST_SEC"):
    config.STATIC_BURST_SEC = 0.50

pygame.font.init()

# ---------------------------------------------------------------- helpers
def _compute_font_sizes(h):
    return max(12, h // 60), max(16, h // 45), max(24, h // 15)

def _fmt_hms(sec: float) -> str:
    m, s = divmod(int(sec + 0.5), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def _fmt_hmsf(sec: float, fps: int) -> str:
    """
    HH:MM:SS:FF where FF = frame number within the second (00 … fps-1)
    """
    total_frames = int(sec * fps + 0.0001)       # guard rounding error
    frames = total_frames % fps
    s_int  = total_frames // fps
    m, s   = divmod(s_int, 60)
    h, m   = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}:{frames:02d}"

# ---------------------------------------------------------------- main
def draw_overlay(surface, ch_num, ch_mgr, ref_time, static_elapsed, transitioning):
    sw, sh = surface.get_width(), surface.get_height()
    tiny, small, large = _compute_font_sizes(sh)
    FT, FS, FL = (pygame.font.SysFont("monospace", sz) for sz in (tiny, small, large))

    WHITE = (255, 255, 255); GREEN = (0, 255, 0)
    RED   = (255, 50, 50);   YEL   = (200, 200, 50)
    BG    = (0, 0, 0, 180)

    # ---------- channel label (always) ----------
    chsurf = FL.render(f"CH {ch_num:02d}", True, GREEN)
    chbg   = pygame.Surface((chsurf.get_width()+large//3,
                             chsurf.get_height()+large//5),
                            pygame.SRCALPHA); chbg.fill(BG)
    chbg.blit(chsurf, (large//6, large//10))
    surface.blit(chbg, (sw - chbg.get_width() - 10, 10))

    if not config.SHOW_OVERLAYS:
        return

    now = time.time()

    # ---------- real clock + run time ----------
    rt = time.strftime("%H:%M:%S")
    run_sec = pygame.time.get_ticks() // 1000
    rm, rs = divmod(run_sec, 60)
    clocksurf = FS.render(f"{rt}  +{rm:02d}:{rs:02d}", True, YEL)
    clockbg   = pygame.Surface((clocksurf.get_width()+small//3,
                                clocksurf.get_height()+small//5),
                               pygame.SRCALPHA); clockbg.fill(BG)
    clockbg.blit(clocksurf, (small//6, small//10))
    surface.blit(clockbg, (10, 10))

    # ---------- CPU load ----------
    try:
        cpu_pct = (os.getloadavg()[0] / os.cpu_count()) * 100
    except Exception:
        cpu_pct = 0.0
    cpusurf = FS.render(f"CPU {cpu_pct:.0f}%", True, RED)
    cpubg   = pygame.Surface((cpusurf.get_width()+small//3,
                              cpusurf.get_height()+small//5),
                             pygame.SRCALPHA); cpubg.fill(BG)
    cpubg.blit(cpusurf, (small//6, small//10))
    surface.blit(cpubg, (10, sh - cpubg.get_height() - 10))

    # ---------- playlist panel ----------
    chan = ch_mgr.channels.get(ch_num)
    lines = []
    if chan and chan.files:
        pin = (now - ref_time) % chan.total_duration
        lines += [f"Playlist len  {_fmt_hms(chan.total_duration)}",
                  f"Position      {_fmt_hms(pin)}"]

        off = ch_mgr.offset(ch_num, now, ref_time)
        cur_idx = chan.files.index(chan.path)
        cur_fp  = os.path.basename(chan.path)
        cur_len = chan.durations[cur_idx]
        remain  = cur_len - off
        nxt_fp  = os.path.basename(chan.files[(cur_idx + 1) % len(chan.files)])

        lines += [f"Current  {cur_fp}",
                  f"   rem   {_fmt_hms(remain)}",
                  f"Next    {nxt_fp}",
                  "——  upcoming  ——"]

        cum = 0.0
        for fp, dur in zip(chan.files, chan.durations):
            start = cum; cum += dur
            until = start - pin if start >= pin else chan.total_duration - pin + start
            lines.append(f"{os.path.basename(fp)}  in {_fmt_hms(until)}")
    else:
        lines.append("No videos – static loop")

    if transitioning:
        lines.append(f"Static burst {_fmt_hms(static_elapsed)} / "
                     f"{_fmt_hms(config.STATIC_BURST_SEC)}")

    # panel rendering
    widest = max(FT.size(l)[0] for l in lines)
    ph     = len(lines) * (FT.get_linesize() + 2) + 10
    pbg    = pygame.Surface((widest + 20, ph), pygame.SRCALPHA); pbg.fill(BG)
    y = 5
    for l in lines:
        pbg.blit(FT.render(l, True, WHITE), (10, y))
        y += FT.get_linesize() + 2
    surface.blit(pbg, (sw - pbg.get_width() - 10, 10 + chbg.get_height() + 10))

    # ---------- timestamp bottom-right ----------
    if transitioning:
        ttxt = f"{static_elapsed:04.1f}s"
    else:
        # show HH:MM:SS:FF (frame number) for current video
        ttxt = _fmt_hmsf(off if chan and chan.files else static_elapsed,
                         config.FPS)

    tssurf = FS.render(ttxt, True, WHITE)
    tsbg   = pygame.Surface((tssurf.get_width()+small//3,
                             tssurf.get_height()+small//5),
                            pygame.SRCALPHA); tsbg.fill(BG)
    tsbg.blit(tssurf, (small//6, small//10))
    surface.blit(tsbg, (sw - tsbg.get_width() - 10,
                        sh - tsbg.get_height() - 10))
