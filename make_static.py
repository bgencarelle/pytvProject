#!/usr/bin/env python3
"""
interactive_static_generator.py

Interactive helper to generate an analog‐style static loop video:
  • Uses the same static‐frame algorithm as transitions.py (configurable via config.py)
  • Applies a matching single‐pole low-pass filter (-af lowpass:p=1) to the audio via FFmpeg
  • Prompts for resolution, duration, FPS, audio bitrate, output filename/folder
  • Prerenders frames if total count ≤ threshold, otherwise streams them on demand
  • Pipes raw RGB frames into FFmpeg alongside the filtered anoisesrc track
  • Encodes to h264 @ CRF30, selectable framerate, yuv420p + AAC at high bitrate
"""

import os
import shlex
import subprocess
import sys

import pygame
import numpy as np

import config  # your config.py with STATIC_* settings

def detect_resolution():
    pygame.init()
    info = pygame.display.Info()
    w, h = info.current_w, info.current_h
    pygame.quit()
    return w, h

def prompt(text, default):
    resp = input(f"{text} [{default}]: ").strip()
    return resp or default

def parse_resolution(res_str):
    try:
        w_str, h_str = res_str.lower().split('x')
        return int(w_str), int(h_str)
    except:
        print("Invalid resolution. Use WIDTHxHEIGHT, e.g. 1920x1080.")
        sys.exit(1)

def generate_static_frame(w, h):
    """Generate one frame of blocky static using config.STATIC_* parameters."""
    bs    = config.STATIC_BLOCK_SIZE
    sigma = config.STATIC_GAUSS_SIGMA
    scan  = config.STATIC_SCANLINE_INTENSITY
    tear_pct   = config.STATIC_TEAR_BAND_PCT
    tear_shift = config.STATIC_TEAR_MAX_SHIFT
    flick_min, flick_max = config.STATIC_FLICKER_RANGE

    small_w = (w + bs - 1) // bs
    small_h = (h + bs - 1) // bs

    # 1) Gaussian mid-gray noise
    base = np.random.normal(128, sigma, (small_h, small_w))
    img = np.clip(base, 0, 255).astype(np.uint8)[..., None]
    img = np.repeat(img, 3, axis=2)

    # 2) Upscale to full size
    img = np.repeat(np.repeat(img, bs, axis=0), bs, axis=1)[:h, :w]

    # 3) Scan-lines
    img[::2, :] = (img[::2, :] * scan).astype(np.uint8)

    # 4) Horizontal tear
    band_h = int(h * tear_pct)
    y0 = np.random.randint(0, h - band_h) if band_h < h else 0
    dx = np.random.randint(-tear_shift, tear_shift)
    img[y0:y0+band_h] = np.roll(img[y0:y0+band_h], dx, axis=1)

    # 5) Global brightness flicker
    flick = np.random.uniform(flick_min, flick_max)
    img = np.clip(img * flick, 0, 255).astype(np.uint8)

    return img

def main():
    print("=== Interactive Static Movie Generator ===\n")

    # 1) Resolution
    w0, h0 = detect_resolution()
    print(f"Detected resolution: {w0}x{h0}")
    res = prompt("Enter resolution", f"{w0}x{h0}")
    w, h = parse_resolution(res)

    # 2) Duration
    dur_str = prompt("Duration in seconds", "3600")
    try:
        duration = float(dur_str)
    except:
        print("Invalid duration.")
        sys.exit(1)

    # 3) Frame rate
    fps_str = prompt("Frame rate (fps)", "15")
    try:
        fps = int(fps_str)
    except:
        print("Invalid fps.")
        sys.exit(1)

    # 4) Audio settings (highest quality AAC)
    default_ab = "320k"
    ab = prompt("Audio bitrate for high fidelity (e.g. 320k)", default_ab)

    # 5) Output file & folder
    default_out = f"static_{int(duration)}s_{w}x{h}.mp4"
    out_fn = prompt("Output filename", default_out)
    folder = prompt("Target folder (will be created)", ".")
    os.makedirs(folder, exist_ok=True)
    output_path = os.path.join(folder, out_fn)

    total_frames = int(duration * fps)
    prerender_threshold = 2000  # frames

    # 6) Build FFmpeg command with single‐pole lowpass (p=1)
    ff_cmd = [
        "ffmpeg", "-y",
        # raw video in via pipe
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{w}x{h}", "-framerate", str(fps),
        "-i", "pipe:0",
        # static hiss audio
        "-f", "lavfi", "-i", f"anoisesrc=color=white:duration={duration}",
        # apply a single-pole lowpass filter to match in-app static
        "-af", f"lowpass=f={config.STATIC_CUTOFF_HZ}:p=1",
        # encode video
        "-c:v", "libx264", "-preset", "fast", "-tune", "zerolatency",
        "-crf", "30", "-pix_fmt", "yuv420p", "-r", str(fps),
        # encode audio at high bitrate
        "-c:a", "aac", "-b:a", ab, "-ar", "48000", "-ac", "2",
        # output
        output_path
    ]

    print("\nAbout to run:\n  " + " ".join(shlex.quote(a) for a in ff_cmd))
    if prompt("Proceed? [Y/n]", "Y").lower() != "y":
        print("Aborted.")
        return

    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)

    if total_frames <= prerender_threshold:
        print(f"Prerendering {total_frames} frames…")
        for i in range(total_frames):
            frame = generate_static_frame(w, h)
            proc.stdin.write(frame.tobytes())
            if (i + 1) % fps == 0:
                print(f"  {i+1}/{total_frames} frames generated")
    else:
        print(f"Streaming {total_frames} frames on demand…")
        for i in range(total_frames):
            frame = generate_static_frame(w, h)
            proc.stdin.write(frame.tobytes())
            if (i + 1) % (fps * 10) == 0:
                print(f"  {i+1}/{total_frames} frames generated")

    proc.stdin.close()
    proc.wait()
    print(f"\n✔️  Done! Saved to {output_path}")

if __name__ == "__main__":
    main()

