# main.py
"""
Retro-TV emulator entry point.
Empty channels now loop a long static_video.mp4 with proper offsets.
"""
import os
import time
import pygame
import av
from pygame.locals import K_ESCAPE, K_q, K_RIGHT, K_LEFT, K_SPACE, K_i

import config
from channel_manager import ChannelManager
from video_player import VideoPlayer
from transitions import static_transition, fade_transition

# ────────────────────────────────────────────────────────────────
# Overlay helpers
# ────────────────────────────────────────────────────────────────
pygame.font.init()
_FONT_CH = pygame.font.Font(None, 36)
_FONT_TS = pygame.font.Font(None, 24)

def draw_overlay(surface: pygame.Surface, channel: int, seconds: float) -> None:
    """Draw channel label and MM:SS timer onto *surface*."""
    # Channel label
    ch_text = f"CH {channel:02d}"
    ch_surf = _FONT_CH.render(ch_text, True, (0, 255, 0))
    bg = pygame.Surface((ch_surf.get_width()+10, ch_surf.get_height()+4), pygame.SRCALPHA)
    bg.fill((0,0,0,128)); bg.blit(ch_surf, (5,2))
    surface.blit(bg, (10,10))

    # Elapsed time
    mm, ss = divmod(int(seconds), 60)
    ts_text = f"{mm:02d}:{ss:02d}"
    ts_surf = _FONT_TS.render(ts_text, True, (255,255,255))
    bg2 = pygame.Surface((ts_surf.get_width()+10, ts_surf.get_height()+4), pygame.SRCALPHA)
    bg2.fill((0,0,0,128)); bg2.blit(ts_surf, (5,2))
    x = surface.get_width() - bg2.get_width() - 10
    y = surface.get_height() - bg2.get_height() - 10
    surface.blit(bg2, (x,y))


# ────────────────────────────────────────────────────────────────
# Main application
# ────────────────────────────────────────────────────────────────
def main() -> None:
    pygame.init()
    pygame.mixer.init(frequency=44100, channels=2, size=-16)
    pygame.mouse.set_visible(False)

    # Setup display
    if config.FULLSCREEN:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(config.WINDOWED_SIZE)

    clock      = pygame.time.Clock()
    ch_mgr     = ChannelManager(config.MOVIES_PATH)
    current_ch = config.START_CHANNEL or ch_mgr.min_ch
    ref_time   = config.REFERENCE_START_TIME

    # Path to the long static loop
    static_fp = os.path.join(config.MOVIES_PATH, "static_video.mp4")
    # Try to read its duration
    static_dur = 0.0
    if os.path.exists(static_fp):
        try:
            c = av.open(static_fp)
            vs = next((s for s in c.streams if s.type=="video"), None)
            if vs and vs.duration:
                static_dur = float(vs.duration * vs.time_base)
            else:
                static_dur = float(c.duration * c.streams[0].time_base)
            c.close()
        except:
            static_dur = 0.0

    # Overlay expiration timer
    overlay_expire = time.time() + config.OVERLAY_DURATION

    # Create player
    player = VideoPlayer()

    # Helper to open either a real movie or the static loop
    def open_channel(ch_num):
        chan = ch_mgr.channels.get(ch_num)
        now = time.time()
        if chan and chan.files:
            offset = ch_mgr.offset(ch_num, now, ref_time)
            path   = chan.path
        else:
            # Empty channel → use static_video.mp4 if available
            if static_dur > 0:
                offset = ((now - ref_time) % static_dur)
            else:
                offset = 0.0
            path = static_fp
        player.open(path, start_offset=offset)

    # Open first channel
    open_channel(current_ch)
    overlay_expire = time.time() + config.OVERLAY_DURATION

    running = True
    while running:
        # ── Input ─────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key in (K_ESCAPE, K_q):
                    running = False
                    break

                elif ev.key == K_i:
                    # Show info for INFO_OVERLAY_DURATION
                    overlay_expire = time.time() + config.INFO_OVERLAY_DURATION

                elif ev.key in (K_RIGHT, K_SPACE):
                    # Channel up
                    player.close()
                    if config.TRANSITION_TYPE == "static":
                        static_transition(screen)

                    current_ch = ch_mgr.next(current_ch)
                    open_channel(current_ch)
                    overlay_expire = time.time() + config.OVERLAY_DURATION

                elif ev.key == K_LEFT:
                    # Channel down
                    player.close()
                    if config.TRANSITION_TYPE == "static":
                        static_transition(screen)

                    current_ch = ch_mgr.prev(current_ch)
                    open_channel(current_ch)
                    overlay_expire = time.time() + config.OVERLAY_DURATION

        # ── Decode & draw ─────────────────────────────────────
        frame_arr = player.decode_frame()
        frame_surf = pygame.image.frombuffer(
            frame_arr, (frame_arr.shape[1], frame_arr.shape[0]), "RGB"
        )

        sw, sh    = screen.get_size()
        vw, vh    = frame_surf.get_size()
        scale     = min(sw/vw, sh/vh)
        new_w     = int(vw*scale)
        new_h     = int(vh*scale)
        frame_surf = pygame.transform.scale(frame_surf, (new_w, new_h))

        screen.fill((0,0,0))
        screen.blit(frame_surf, ((sw-new_w)//2, (sh-new_h)//2))

        # ── Overlay ───────────────────────────────────────────
        if time.time() < overlay_expire:
            # compute elapsed based on whichever path is playing
            chan = ch_mgr.channels.get(current_ch)
            if chan and chan.files:
                elapsed = ch_mgr.offset(current_ch, time.time(), ref_time)
            else:
                # static loop elapsed
                if static_dur > 0:
                    elapsed = (time.time() - ref_time) % static_dur
                else:
                    elapsed = 0.0
            draw_overlay(screen, current_ch, elapsed)

        pygame.display.flip()
        clock.tick(30)

    # ── Cleanup ─────────────────────────────────────────────
    player.close()
    pygame.quit()


if __name__ == "__main__":
    main()
