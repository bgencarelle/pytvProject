"""
overlay_window.py – draws timestamp / channel overlays in a second SDL2
window that sits above the main Pygame window.

No reliance on `_sdl2` flag constants; we set window attributes after
creation, so it runs on any Pygame ≥ 2.1 (tested with 2.6.1).
"""

from __future__ import annotations
import pygame
from pygame._sdl2 import Window

pygame.font.init()
_TS_FONT = pygame.font.Font(None, 24)
_CH_FONT = pygame.font.Font(None, 36)


class OverlayWindow:
    """Transparent, always-on-top SDL window for on-screen display."""

    def __init__(self, size: tuple[int, int], title: str = "overlay"):
        # Create a plain SDL2 window first …
        self.win: Window = Window(title, size=size)

        # … then make it border-less, on-top and transparent where supported.
        if hasattr(self.win, "borderless"):
            self.win.borderless = True
        if hasattr(self.win, "always_on_top"):
            self.win.always_on_top = True
        if hasattr(self.win, "transparent"):
            self.win.transparent = True      # per-pixel alpha
        elif hasattr(self.win, "opacity"):
            self.win.opacity = 1.0           # ensure alpha values respected

        self.surface: pygame.Surface = self.win.get_surface()

    # ------------ drawing helpers --------------------------------------

    def clear(self) -> None:
        """Erase previous frame (keep full transparency)."""
        self.surface.fill((0, 0, 0, 0))

    def draw_timestamp(self, secs: float) -> None:
        mm, ss = divmod(int(secs), 60)
        surf = _TS_FONT.render(f"{mm:02d}:{ss:02d}", True, (255, 255, 255))
        r = surf.get_rect(
            bottomright=(self.surface.get_width() - 10,
                         self.surface.get_height() - 10))
        bg = pygame.Surface((r.width + 10, r.height + 5), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 128))
        bg.blit(surf, (5, 0))
        self.surface.blit(bg, r.topleft)

    def draw_channel(self, ch: int) -> None:
        surf = _CH_FONT.render(f"CH {ch:02d}", True, (0, 255, 0))
        r = surf.get_rect(topleft=(10, 10))
        bg = pygame.Surface((r.width + 10, r.height + 5), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 128))
        bg.blit(surf, (5, 0))
        self.surface.blit(bg, r.topleft)

    # ------------ present / keep in sync --------------------------------

    def flip(self) -> None:
        self.win.flip()

    def sync_to(self, main_win: Window) -> None:
        """Follow the main window’s position/size each frame."""
        self.win.position = main_win.position
        if self.win.size != main_win.size:
            self.win.size = main_win.size
