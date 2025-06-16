# main.py
"""
Retro-TV emulator entry point with debounced channel switching.
"""
import os, time, pygame, av
from pygame.locals import K_ESCAPE, K_q, K_RIGHT, K_LEFT, K_SPACE, K_i

import config
from channel_manager import ChannelManager
from video_player import VideoPlayer
from transitions import static_transition

# ────────────────────────────────────────────────────────────────
# Overlay helpers
pygame.font.init()
_FONT_CH = pygame.font.Font(None, 36)
_FONT_TS = pygame.font.Font(None, 24)

def draw_overlay(surface: pygame.Surface, channel: int, seconds: float):
    ch_s = _FONT_CH.render(f"CH {channel:02d}", True, (0,255,0))
    bg   = pygame.Surface((ch_s.get_width()+10, ch_s.get_height()+4), pygame.SRCALPHA)
    bg.fill((0,0,0,128)); bg.blit(ch_s,(5,2))
    surface.blit(bg, (10,10))

    mm, ss = divmod(int(seconds), 60)
    ts_s = _FONT_TS.render(f"{mm:02d}:{ss:02d}", True, (255,255,255))
    bg2  = pygame.Surface((ts_s.get_width()+10, ts_s.get_height()+4), pygame.SRCALPHA)
    bg2.fill((0,0,0,128)); bg2.blit(ts_s,(5,2))
    x = surface.get_width()-bg2.get_width()-10
    y = surface.get_height()-bg2.get_height()-10
    surface.blit(bg2, (x,y))

# ────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, channels=2, size=-16)
    pygame.mouse.set_visible(True)
    pygame.mouse.set_visible(False)

    screen = (pygame.display.set_mode((0,0), pygame.FULLSCREEN)
              if config.FULLSCREEN else pygame.display.set_mode(config.WINDOWED_SIZE))

    clock      = pygame.time.Clock()
    ch_mgr     = ChannelManager(config.MOVIES_PATH)
    current_ch = config.START_CHANNEL or ch_mgr.min_ch
    ref_time   = config.REFERENCE_START_TIME

    # probe static clip once
    static_fp  = os.path.join(config.MOVIES_PATH, "static_video.mp4")
    static_dur = 0.0
    if os.path.exists(static_fp):
        try:
            c = av.open(static_fp)
            vs = next((s for s in c.streams if s.type=="video"), None)
            tb = vs.time_base if vs else c.streams[0].time_base
            static_dur = float((vs.duration or c.duration) * tb)
            c.close()
        except: pass

    player = VideoPlayer()

    def open_channel(ch_num: int):
        """Open movie or static loop at correct offset."""
        chan = ch_mgr.channels.get(ch_num)
        now  = time.time()
        if chan and chan.files:
            off, path = ch_mgr.offset(ch_num, now, ref_time), chan.path
        else:
            off  = ((now - ref_time) % static_dur) if static_dur > 0 else 0.0
            path = static_fp
        player.open(path, start_offset=off)

    open_channel(current_ch)

    overlay_expire     = time.time() + config.OVERLAY_DURATION
    last_ch_change_ts  = 0.0                    # ← debounce marker

    running = True
    while running:
        for ev in pygame.event.get():
            pygame.mouse.set_visible(False)
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                # universal quit
                if ev.key in (K_ESCAPE, K_q):
                    running = False
                    break

                # info overlay
                elif ev.key == K_i:
                    overlay_expire = time.time() + config.INFO_OVERLAY_DURATION

                # channel change keys
                elif ev.key in (K_RIGHT, K_SPACE, K_LEFT):
                    now = time.time()
                    # ── Debounce ──
                    if now - last_ch_change_ts < config.CHANNEL_CHANGE_DEBOUNCE:
                        # ignore bounce / long press
                        continue
                    last_ch_change_ts = now

                    next_ch = (ch_mgr.next(current_ch)
                               if ev.key in (K_RIGHT, K_SPACE)
                               else ch_mgr.prev(current_ch))

                    # callback used by static_transition
                    def overlay_on_static(surf):
                        if ch_mgr.channels[next_ch].files:
                            elapsed = ch_mgr.offset(next_ch, time.time(), ref_time)
                        else:
                            elapsed = ((time.time()-ref_time) % static_dur) if static_dur > 0 else 0.0
                        draw_overlay(surf, next_ch, elapsed)

                    overlay_expire = time.time() + config.OVERLAY_DURATION

                    player.close()
                    static_transition(screen, overlay_fn=overlay_on_static)

                    # flush extra key repeats queued during static
                    pygame.event.clear([pygame.KEYDOWN, pygame.KEYUP])

                    current_ch = next_ch
                    open_channel(current_ch)

        # render one video frame
        frame = player.decode_frame()
        surf  = pygame.image.frombuffer(frame, frame.shape[1::-1], "RGB")

        # letter-/pillar-box with pixel-aspect compensation
        sw, sh = screen.get_size()
        vw, vh = surf.get_size()
        sar    = getattr(player, "sar", 1.0)
        scale  = min(sw / (vw * sar), sh / vh)
        surf   = pygame.transform.scale(
                    surf,
                    (int(vw * scale * sar), int(vh * scale))
                 )

        screen.fill((0,0,0))
        screen.blit(surf, ((sw - surf.get_width()) // 2,
                           (sh - surf.get_height()) // 2))

        # in-program overlay
        if time.time() < overlay_expire:
            if ch_mgr.channels[current_ch].files:
                elapsed = ch_mgr.offset(current_ch, time.time(), ref_time)
            else:
                elapsed = ((time.time() - ref_time) % static_dur) if static_dur > 0 else 0.0
            draw_overlay(screen, current_ch, elapsed)

        pygame.display.flip()
        clock.tick(30)

    player.close()
    pygame.quit()

if __name__ == "__main__":
    main()
