# test_pyaudio.py
import numpy as np, pyaudio, time
p = pyaudio.PyAudio()
print("PyAudio default output:", p.get_default_output_device_info())
sr = 44100
t  = np.linspace(0, 1, sr, endpoint=False)
tone = (0.2*np.sin(2*np.pi*440*t)).astype(np.float32)
stream = p.open(format=pyaudio.paFloat32, channels=1, rate=sr, output=True)
stream.write(tone.tobytes())
time.sleep(0.1)
stream.stop_stream(); stream.close(); p.terminate()
print("PyAudio beep done")
