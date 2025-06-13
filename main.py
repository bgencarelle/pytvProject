# main.py
"""
Retro-TV emulator entry point.
Uses:
  - pygame              (window, input, drawing, fallback audio)
  - numpy               (array handling)
  - pyav                (video/audio decoding)
  - sounddevice         (primary audio output; falls back to pygame.mixer)
Helpers:
  - channel_manager.py  (unchanged)
  - video_player.py     (unchanged)
  - transitions.py      (unchanged)
  - config.py           (unchanged)
Save this file next to those modules and run:  python main.py
"""
import time
import pygame
from pygame.locals import K_ESCAPE, K_q, K_RIGHT, K_LEFT, K_SPACE

from config import *
from channel_manager import ChannelManager
from video_player import VideoPlayer
from transitions import static_transition, fade_transition

# ────────────────────────────────────────────────────────────────
#  Overlay helpers (draw directly on the main surface)
# ────────────────────────────────────────────────────────────────
pygame.font.init()
_FONT_CH = pygame.font.Font(None, 36)
_FONT_TS = pygame.font.Font(None, 24)

def draw_overlay(surface: pygame.Surface, channel: int, seconds: float) -> None:
    """Draw channel label and MM:SS timer onto *surface*."""
    # Channel label (green)
    ch_text = f"CH {channel:02d}"
    ch_surf = _FONT_CH.render(ch_text, True, (0, 255, 0))
    ch_bg = pygame.Surface((ch_surf.get_width() + 10, ch_surf.get_height() + 4), pygame.SRCALPHA)
    ch_bg.fill((0, 0, 0, 128))
    ch_bg.blit(ch_surf, (5, 2))
    surface.blit(ch_bg, (10, 10))

    # Elapsed time (white)
    mm, ss = divmod(int(seconds), 60)
    ts_text = f"{mm:02d}:{ss:02d}"
    ts_surf = _FONT_TS.render(ts_text, True, (255, 255, 255))
    ts_bg = pygame.Surface((ts_surf.get_width() + 10, ts_surf.get_height() + 4), pygame.SRCALPHA)
    ts_bg.fill((0, 0, 0, 128))
    ts_bg.blit(ts_surf, (5, 2))
    x = surface.get_width()  - ts_bg.get_width()  - 10
    y = surface.get_height() - ts_bg.get_height() - 10
    surface.blit(ts_bg, (x, y))

# ────────────────────────────────────────────────────────────────
#  Main application
# ────────────────────────────────────────────────────────────────
def main() -> None:
    pygame.init()
    pygame.mixer.init(frequency=44100, channels=2, size=-16)

    # Create display
    if FULLSCREEN:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(WINDOWED_SIZE)

    clock          = pygame.time.Clock()
    ch_mgr         = ChannelManager(MOVIES_PATH)
    current_ch     = START_CHANNEL or ch_mgr.min_ch
    reference_time = REFERENCE_START_TIME

    # Prepare first channel
    player = VideoPlayer()
    offset = ch_mgr.offset(current_ch, time.time(), reference_time)
    player.open(ch_mgr.channels[current_ch].path, start_offset=offset)

    running = True
    while running:
        # ── Input ────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key in (K_ESCAPE, K_q):
                    running = False
                    break

                elif ev.key in (K_RIGHT, K_SPACE):
                    # 1) stop current video+audio
                    player.close()

                    # 2) play static transition
                    if TRANSITION_TYPE == "static":
                        static_transition(screen)

                    # 3) advance channel and compute offset
                    current_ch = ch_mgr.next(current_ch)
                    offset = ch_mgr.offset(current_ch, time.time(), reference_time)

                    # 4) open new channel (starts its audio+video)
                    player.open(ch_mgr.channels[current_ch].path, start_offset=offset)

                elif ev.key == K_LEFT:
                    # 1) stop current video+audio
                    player.close()

                    # 2) play static transition
                    if TRANSITION_TYPE == "static":
                        static_transition(screen)

                    # 3) go to previous channel and compute offset
                    current_ch = ch_mgr.prev(current_ch)
                    offset = ch_mgr.offset(current_ch, time.time(), reference_time)

                    # 4) open new channel
                    player.open(ch_mgr.channels[current_ch].path, start_offset=offset)

        # ── Decode video frame ───────────────────────────────────
        frame_arr = player.decode_frame()
        if frame_arr is None:  # <-- remove or comment out this block
            running = False
            break

        frame_surf = pygame.image.frombuffer(
            frame_arr, (frame_arr.shape[1], frame_arr.shape[0]), "RGB"
        )

        # Fit to window with letter/pillar-boxing
        sw, sh   = screen.get_size()
        vw, vh   = frame_surf.get_size()
        scale    = min(sw / vw, sh / vh)
        new_w, new_h = int(vw * scale), int(vh * scale)
        frame_surf  = pygame.transform.scale(frame_surf, (new_w, new_h))
        screen.fill((0, 0, 0))
        screen.blit(frame_surf, ((sw - new_w) // 2, (sh - new_h) // 2))

        # ── Draw overlay and flip ────────────────────────────────
        elapsed   = ch_mgr.offset(current_ch, time.time(), reference_time)
        draw_overlay(screen, current_ch, elapsed)
        pygame.display.flip()
        clock.tick(30)   # cap at 30 FPS for efficiency

    # ── Shutdown ────────────────────────────────────────────────
    player.close()
    pygame.quit()

if __name__ == "__main__":
    main()
