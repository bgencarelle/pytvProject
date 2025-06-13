import time
import pygame
from pygame._sdl2 import Window as SDLWindow

from channel_manager import ChannelManager
from video_player import VideoPlayer
from transitions import static_transition
from overlay_window import OverlayWindow


def main():
    # -------------------------------------------------- Pygame bootstrap
    pygame.init()
    pygame.mixer.init(frequency=44_100, channels=2, size=-16)
    screen = pygame.display.set_mode((1280, 720))          # pick a size
    clock = pygame.time.Clock()

    # -------------------------------------------------- overlay window
    overlay = OverlayWindow(screen.get_size())
    main_win = SDLWindow.from_display_module()             # handle to main

    # -------------------------------------------------- TV state
    mgr = ChannelManager("movies")          # path with your .mp4 files
    current = mgr.min_ch
    epoch = time.time()

    vp = VideoPlayer()
    vp.open(mgr.channels[current].path,
            mgr.offset(current, time.time(), epoch))

    running = True
    while running:
        # ------------- input ------------------------------------------
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

                elif ev.key in (pygame.K_RIGHT, pygame.K_SPACE):
                    vp.close()
                    static_transition(screen)
                    current = mgr.next(current)
                    vp.open(mgr.channels[current].path,
                            mgr.offset(current, time.time(), epoch))

                elif ev.key == pygame.K_LEFT:
                    vp.close()
                    static_transition(screen)
                    current = mgr.prev(current)
                    vp.open(mgr.channels[current].path,
                            mgr.offset(current, time.time(), epoch))

        # ------------- overlay ---------------------------------------
        now = time.time()
        overlay.clear()
        overlay.draw_timestamp(mgr.offset(current, now, epoch))
        overlay.draw_channel(current)
        overlay.sync_to(main_win)           # follow moves / resizes
        overlay.flip()

        clock.tick(60)

    # -------------------------------------------------- shutdown
    vp.close()
    pygame.quit()


if __name__ == "__main__":
    main()
