# test_tone.py
import numpy as np
import sounddevice as sd

fs = 44100         # sample rate
duration = 2.0     # seconds
t = np.linspace(0, duration, int(fs*duration), endpoint=False)
tone = 0.2 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave at 20% volume

print("Default output device:", sd.default.device)
print("Available devices:\n", sd.query_devices())
print("Playing tone through sounddevice...")
sd.play(tone, fs)
sd.wait()
print("Done.")
