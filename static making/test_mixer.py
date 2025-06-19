# test_mixer.py
import pygame
import numpy as np

pygame.init()
# Try a standard rate/channel
pygame.mixer.init(frequency=44100, size=-16, channels=2)
fs = 44100
t = np.linspace(0, 1.0, fs, False)
tone = (0.2 * np.sin(2*np.pi*440*t) * 32767).astype(np.int16)
# make stereo by duplicating
pcm = np.repeat(tone[:, None], 2, axis=1)
sound = pygame.sndarray.make_sound(pcm.copy(order='C'))
print("Playing via pygame.mixer...")
sound.play()
pygame.time.delay(1500)
pygame.quit()
print("Done.")
