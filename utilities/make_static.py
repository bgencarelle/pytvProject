#!/usr/bin/env python3
"""
interactive_static_generator.py — CRT-style static loop maker
H.264/H.265 selectable output, with default filename reflecting
resolution, codec, and length, and a minimum 10 Mbps video bitrate.
"""

import os, shlex, subprocess, sys
import numpy as np
import pygame
import config

def detect_resolution():
    pygame.init()
    info = pygame.display.Info()
    w, h = info.current_w, info.current_h
    pygame.quit()
    return w, h

def prompt(msg, default):
    v = input(f"{msg} [{default}]: ").strip()
    return v or default

def parse_res(s):
    try:
        w, h = map(int, s.lower().split('x'))
        return w, h
    except Exception:
        sys.exit("Bad resolution (use WxH)")

def parse_duration(s):
    try:
        value = float(s)
        if value <= 0:
            raise ValueError
        return value
    except Exception:
        sys.exit("Bad duration (must be a positive number of seconds)")

# ── CRT parameters from config ─────────────────────────────────
BLUR_TAPS   = getattr(config, "STATIC_BLUR_TAPS",        5) | 1
LINE_JITTER = getattr(config, "STATIC_PERLINE_JITTER",   0)
VIGNETTE    = getattr(config, "STATIC_VIGNETTE_STRENGTH",0.0)
PERSIST     = getattr(config, "STATIC_PERSISTENCE",      0.0)
BLOCK_SIZE  = max(1, getattr(config, "STATIC_BLOCK_SIZE",1))

def vignette_mask(w, h, strength):
    if strength <= 0:
        return None
    y, x = np.ogrid[-1:1:h*1j, -1:1:w*1j]
    d = np.sqrt(x*x + y*y)
    return (1.0 - strength * np.clip(d, 0, 1)).astype(np.float32)

def generate_frame(w, h, prev=None, vmask=None):
    bs = BLOCK_SIZE
    if bs > 1:
        sw = (w + bs - 1) // bs
        sh = (h + bs - 1) // bs
        src = np.random.randint(0, 256, (sh, sw), dtype=np.uint8)
        f = np.repeat(np.repeat(src, bs, 0), bs, 1)[:h, :w]
    else:
        f = np.random.randint(0, 256, (h, w), dtype=np.uint8)

    # vertical blur
    if BLUR_TAPS > 1:
        acc = f.astype(np.uint32)
        for k in range(1, BLUR_TAPS // 2 + 1):
            acc += np.roll(f, k, 0) + np.roll(f, -k, 0)
        f = (acc // BLUR_TAPS).astype(np.uint8)

    # scan-lines
    f[::2] = (f[::2].astype(np.uint16) * config.STATIC_SCANLINE_INTENSITY).astype(np.uint8)

    # per-line jitter
    if LINE_JITTER > 0:
        for y in range(h):
            shift = np.random.randint(-LINE_JITTER, LINE_JITTER + 1)
            f[y] = np.roll(f[y], shift)

    # tear band
    band_h = max(1, int(h * config.STATIC_TEAR_BAND_PCT))
    if band_h > 0:
        y0 = np.random.randint(0, h - band_h + 1)
        dx = np.random.randint(-config.STATIC_TEAR_MAX_SHIFT,
                                config.STATIC_TEAR_MAX_SHIFT + 1)
        f[y0:y0 + band_h] = np.roll(f[y0:y0 + band_h], dx, 1)

    # flicker & brightness
    flick = np.random.uniform(*config.STATIC_FLICKER_RANGE)
    gain  = getattr(config, "STATIC_BRIGHTNESS_GAIN", 1.0)
    f = np.clip(f.astype(np.float32) * flick * gain, 0, 255).astype(np.uint8)

    # persistence ghost
    if prev is not None and PERSIST > 0:
        f = np.clip(
            f.astype(np.float32) * (1 - PERSIST) + prev.astype(np.float32) * PERSIST,
            0, 255
        ).astype(np.uint8)

    # vignette
    if vmask is not None:
        f = np.clip(f.astype(np.float32) * vmask, 0, 255).astype(np.uint8)

    return np.stack([f, f, f], 2)  # to RGB

def main():
    print("=== CRT Static Generator ===\n")

    # 1) resolution
    dw, dh = detect_resolution()
    w, h = parse_res(prompt("Resolution", f"{dw}x{dh}"))

    # 2) duration
    default_dur = str(getattr(config, "STATIC_GEN_DURATION", 10))
    dur = parse_duration(prompt("Length (seconds)", default_dur))

    fps = min(getattr(config, "STATIC_GEN_FPS", 30), 30)
    br  = getattr(config, "STATIC_GEN_AUDIO_BITRATE", "128k")
    folder = getattr(config, "STATIC_GEN_OUTPUT_FOLDER", "out")

    # 3) codec
    codec = prompt("Codec? (h264/h265)", "h264").lower()
    if codec not in ("h264", "h265"):
        sys.exit("Codec must be 'h264' or 'h265'.")

    # 4) default filename: dimensions_codec_length
    length_str = str(int(dur)) if dur.is_integer() else str(dur)
    default_fn = f"{w}x{h}_{codec}_{length_str}s.mp4"
    fname = prompt("Output filename", default_fn)
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, fname)

    # 5) codec settings + enforce ≥10 Mbps video bitrate
    if codec == "h264":
        video_codec = "libx264"
        codec_opts = ["-preset", "fast", "-tune", "zerolatency", "-crf", "30"]
    else:
        video_codec = "libx265"
        codec_opts = ["-preset", "fast", "-crf", "30"]

    total = int(dur * fps)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
        "-f", "lavfi", "-i", f"anoisesrc=color=white:duration={dur}",
        "-af", f"lowpass=f={getattr(config, 'STATIC_CUTOFF_HZ', 4000)}:p=1",
        "-c:v", video_codec,
        *codec_opts,
        "-b:v", "1M",                    # enforce at least 10 Mbps
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", br, "-ar", "48000", "-ac", "2",
        out
    ]

    print("\nffmpeg:\n ", " ".join(shlex.quote(a) for a in cmd))
    if prompt("Proceed?", "Y").lower() != "y":
        sys.exit("Aborted.")

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    vmask = vignette_mask(w, h, VIGNETTE)
    prev = None

    for i in range(total):
        frame = generate_frame(w, h, prev, vmask)
        prev = frame[:, :, 0].copy()
        proc.stdin.write(frame.tobytes())
        if (i + 1) % fps == 0:
            print(f"  {i + 1}/{total}")

    proc.stdin.close()
    proc.wait()
    print("\n✔️  Saved to", out)

if __name__ == "__main__":
    main()
