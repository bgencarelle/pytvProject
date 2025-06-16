import os, time, pygame, av
from pygame.locals import K_ESCAPE, K_q, K_RIGHT, K_LEFT, K_SPACE, K_i, QUIT, KEYDOWN

import config
from channel_manager import ChannelManager
from video_player import VideoPlayer
from transitions import static_transition
from overlays import draw_overlay
from renderer import render_frame

class TVEmulator:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, channels=2, size=-16)
        pygame.mouse.set_visible(False)

        self.screen = (
            pygame.display.set_mode((0,0), pygame.FULLSCREEN)
            if config.FULLSCREEN
            else pygame.display.set_mode(config.WINDOWED_SIZE)
        )

        self.clock      = pygame.time.Clock()
        self.ch_mgr     = ChannelManager(config.MOVIES_PATH)
        self.current_ch = config.START_CHANNEL or self.ch_mgr.min_ch
        self.ref_time   = config.REFERENCE_START_TIME

        # Probe static clip once
        self.static_fp = os.path.join(config.MOVIES_PATH, "static_video.mp4")
        self.static_dur = 0.0
        if os.path.exists(self.static_fp):
            try:
                c = av.open(self.static_fp)
                vs = next((s for s in c.streams if s.type=="video"), None)
                tb = vs.time_base if vs else c.streams[0].time_base
                self.static_dur = float((vs.duration or c.duration) * tb)
                c.close()
            except:
                pass

        self.player = VideoPlayer()

        self.overlay_expire    = 0.0
        self.last_ch_change_ts = 0.0

    def open_channel(self, ch_num: int):
        """Open movie or static loop at correct offset."""
        chan = self.ch_mgr.channels.get(ch_num)
        now  = time.time()
        if chan and chan.files:
            off  = self.ch_mgr.offset(ch_num, now, self.ref_time)
            path = chan.path
        else:
            off  = ((now - self.ref_time) % self.static_dur) if self.static_dur > 0 else 0.0
            path = self.static_fp

        self.player.open(path, start_offset=off)

    def run(self):
        # Start the first channel
        self.open_channel(self.current_ch)
        self.overlay_expire = time.time() + config.OVERLAY_DURATION

        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == QUIT:
                    running = False

                elif ev.type == KEYDOWN:
                    # universal quit
                    if ev.key in (K_ESCAPE, K_q):
                        running = False
                        break

                    # info overlay
                    elif ev.key == K_i:
                        self.overlay_expire = time.time() + config.INFO_OVERLAY_DURATION

                    # channel change
                    elif ev.key in (K_RIGHT, K_SPACE, K_LEFT):
                        now = time.time()
                        if now - self.last_ch_change_ts < config.CHANNEL_CHANGE_DEBOUNCE:
                            continue
                        self.last_ch_change_ts = now

                        # pick next or previous
                        next_ch = (
                            self.ch_mgr.next(self.current_ch)
                            if ev.key in (K_RIGHT, K_SPACE)
                            else self.ch_mgr.prev(self.current_ch)
                        )

                        # overlay callback for static transition
                        def overlay_on_static(surf):
                            if self.ch_mgr.channels[next_ch].files:
                                elapsed = self.ch_mgr.offset(next_ch, time.time(), self.ref_time)
                            else:
                                elapsed = ((time.time()-self.ref_time) % self.static_dur) if self.static_dur>0 else 0.0
                            draw_overlay(surf, next_ch, elapsed)

                        self.overlay_expire = time.time() + config.OVERLAY_DURATION

                        # close current, show static, clear repeats
                        self.player.close()
                        static_transition(self.screen, overlay_fn=overlay_on_static)
                        pygame.event.clear([pygame.KEYDOWN, pygame.KEYUP])

                        # open new
                        self.current_ch = next_ch
                        self.open_channel(self.current_ch)
                    elif ev.key == pygame.K_f:
                        # toggle the fullscreen config bit
                        config.FULLSCREEN = not config.FULLSCREEN

                        # recreate the screen surface
                        if config.FULLSCREEN:
                            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode(config.WINDOWED_SIZE)

            # Render one frame of whichever channel is active
            frame = self.player.decode_frame()
            render_frame(self.screen, frame, getattr(self.player, "sar", 1.0))

            # Draw overlay if still fresh
            if time.time() < self.overlay_expire:
                if self.ch_mgr.channels[self.current_ch].files:
                    elapsed = self.ch_mgr.offset(self.current_ch, time.time(), self.ref_time)
                else:
                    elapsed = ((time.time()-self.ref_time) % self.static_dur) if self.static_dur>0 else 0.0
                draw_overlay(self.screen, self.current_ch, elapsed)

            pygame.display.flip()
            self.clock.tick(config.FPS)

        # Tear down
        self.player.close()
        pygame.quit()
