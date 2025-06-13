"""
Transition effects between channels: static noise or fade.
"""
import time, numpy as np, pygame

def static_transition(screen, duration=0.5):
    sr = 44100
    cnt = int(sr*duration)
    buf = (np.random.randn(cnt)*32767//4).astype(np.int16)
    stereo = np.repeat(buf[:, None], 2, axis=1)
    snd = pygame.sndarray.make_sound(np.ascontiguousarray(stereo))
    snd.play()
    h,w = screen.get_size()[1], screen.get_size()[0]
    t0 = time.time()
    while time.time()-t0 < duration:
        noise = np.random.randint(0,256,(h,w,3),dtype=np.uint8)
        pygame.surfarray.blit_array(screen, noise.swapaxes(0,1))
        pygame.display.flip()
        pygame.time.delay(16)
    snd.stop()

def fade_transition(screen, old_surf, new_surf, duration=0.5):
    steps = max(1, int(duration*30))
    # fade out
    for i in range(steps):
        alpha = int(255 * (i/steps))
        screen.blit(old_surf, (0,0))
        ov = pygame.Surface(screen.get_size()); ov.fill((0,0,0)); ov.set_alpha(alpha)
        screen.blit(ov, (0,0)); pygame.display.flip()
        pygame.time.delay(int((duration/2)*1000/steps))
    # fade in
    for i in range(steps):
        alpha = int(255 * (1 - i/steps))
        screen.fill((0,0,0))
        ns = new_surf.copy(); ns.set_alpha(alpha)
        screen.blit(ns, (0,0)); pygame.display.flip()
        pygame.time.delay(int((duration/2)*1000/steps))
    screen.blit(new_surf, (0,0)); pygame.display.flip()
