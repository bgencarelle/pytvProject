# overlay_window.py
"""
Draws timestamp and channel overlays in a transparent SDL2 window above the main video.
"""
import pygame
from pygame._sdl2 import Window

pygame.font.init()
_TS_FONT = pygame.font.Font(None, 24)
_CH_FONT = pygame.font.Font(None, 36)

class OverlayWindow:
    def __init__(self, size, title="overlay"):
        # Create an SDL2 window for overlay
        self.win = Window(title, size=size)
        # Make it borderless, always-on-top, transparent
        if hasattr(self.win, "borderless"):
            self.win.borderless = True
        if hasattr(self.win, "always_on_top"):
            self.win.always_on_top = True
        if hasattr(self.win, "transparent"):
            self.win.transparent = True   # enable per-pixel alpha
        elif hasattr(self.win, "opacity"):
            self.win.opacity = 1.0        # full opacity but with alpha support
        self.surface = self.win.get_surface()

    def clear(self):
        """Clear previous frame (keep full transparency)."""
        self.surface.fill((0,0,0,0))

    def draw_timestamp(self, secs):
        """Draw MM:SS timestamp at bottom-right."""
        mm, ss = divmod(int(secs), 60)
        text = f"{mm:02d}:{ss:02d}"
        surf = _TS_FONT.render(text, True, (255,255,255))
        r = surf.get_rect(bottomright=(self.surface.get_width()-10, self.surface.get_height()-10))
        bg = pygame.Surface((r.width+10, r.height+5), pygame.SRCALPHA)
        bg.fill((0,0,0,128))
        bg.blit(surf, (5, 0))
        self.surface.blit(bg, r.topleft)

    def draw_channel(self, ch):
        """Draw 'CH XX' label at top-left."""
        text = f"CH {ch:02d}"
        surf = _CH_FONT.render(text, True, (0,255,0))
        r = surf.get_rect(topleft=(10, 10))
        bg = pygame.Surface((r.width+10, r.height+5), pygame.SRCALPHA)
        bg.fill((0,0,0,128))
        bg.blit(surf, (5, 0))
        self.surface.blit(bg, r.topleft)

    def flip(self):
        self.win.flip()

    def sync_to(self, main_win):
        """Keep position and size synced to main window."""
        self.win.position = main_win.position
        if self.win.size != main_win.size:
            self.win.size = main_win.size
