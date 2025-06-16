import pygame

def render_frame(screen: pygame.Surface, frame, sar: float):


    """
    Scale and letter-/pillar-box a raw RGB frame onto `screen`.
    """
    surf = pygame.image.frombuffer(frame, frame.shape[1::-1], "RGB")
    sw, sh = screen.get_size()
    vw, vh = surf.get_size()
    scale = min(sw / (vw * sar), sh / vh)
    surf = pygame.transform.scale(
        surf,
        (int(vw * scale * sar), int(vh * scale))
    )
    screen.fill((0,0,0))
    x = (sw - surf.get_width()) // 2
    y = (sh - surf.get_height()) // 2
    screen.blit(surf, (x, y))