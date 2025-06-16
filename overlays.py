"""
Draws on-screen overlays: timestamp and channel label.
"""
import pygame

pygame.font.init()
_ts_font = pygame.font.Font(None, 24)
_ch_font = pygame.font.Font(None, 36)

def draw_timestamp(screen, secs):
    pygame.mouse.set_visible(False)
    mm = int(secs//60); ss = int(secs%60)
    txt = f"{mm:02d}:{ss:02d}"
    surf = _ts_font.render(txt, True, (255,255,255))
    r = surf.get_rect(bottomright=(screen.get_width()-10, screen.get_height()-10))
    bg = pygame.Surface((r.width+10, r.height+5), pygame.SRCALPHA)
    bg.fill((0,0,0,128)); bg.blit(surf, (5,0))
    screen.blit(bg, r.topleft)

def draw_channel(screen, ch):
    txt = f"CH {ch:02d}"
    pygame.mouse.set_visible(False)
    surf = _ch_font.render(txt, True, (0,255,0))
    r = surf.get_rect(topleft=(10,10))
    bg = pygame.Surface((r.width+10, r.height+5), pygame.SRCALPHA)
    bg.fill((0,0,0,128)); bg.blit(surf, (5,0))
    screen.blit(bg, r.topleft)
