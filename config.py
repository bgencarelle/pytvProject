# config.py
"""
Configuration settings for the TV emulator.
"""
import datetime

FPS = 30

# Minimum real-time gap (s) between accepted channel-change key presses
CHANNEL_CHANGE_DEBOUNCE = 0.25

# Reference start time (UTC epoch) for synchronized playback
REFERENCE_START_TIME = datetime.datetime(1978, 11, 17, 7, 11, 0).timestamp()

# Display settings
FULLSCREEN = True
WINDOWED_SIZE = (800, 600)

# Path to directory containing video channel files
MOVIES_PATH = "movies"

# Starting channel: None means the lowest channel
START_CHANNEL = 0x01

# Transition effect type: "static" or "fade"
TRANSITION_TYPE = "static"

# ── Overlay durations ────────────────────────────────────────────
OVERLAY_DURATION      = 4.0   # seconds to show overlay after channel change
INFO_OVERLAY_DURATION = 8.0   # seconds to show overlay on “i”

# ── Static‐transition defaults (blocky CRT snow + filtered hiss) ──
STATIC_DURATION           = 1.5
STATIC_BLOCK_SIZE         = 1
STATIC_CUTOFF_HZ          = 2000.0
STATIC_SCANLINE_INTENSITY = .95
STATIC_TEAR_BAND_PCT      = 0.10
STATIC_TEAR_MAX_SHIFT     = 50
STATIC_FLICKER_RANGE      = (0.99, 1.1)
STATIC_GAUSS_SIGMA        = 10.0
# Extra CRT-look knobs (optional)
STATIC_BLUR_TAPS        = 2     # vertical blur kernel (odd, 3–9 recommended)
STATIC_PERLINE_JITTER   = 9     # ±pixels to roll each scan-line every frame
STATIC_VIGNETTE_STRENGTH= 0.01  # 0 = none, 1 = strong dark corners
STATIC_PERSISTENCE      = 0.1  # 0 = no ghosting, 0.3 = mild phosphor trail
# Overall brightness gain (1.0 = no change, >1 = brighter)
STATIC_BRIGHTNESS_GAIN = 1.9

# How much to fade in/out the static audio (in seconds)
STATIC_AUDIO_CROSSFADE = 0.2
# ── Static‐movie generator defaults ────────────────────────────
# Length of the generated loop, in seconds
STATIC_GEN_DURATION      = 900.0

# Frame rate for the generated loop (will be capped at 30)
STATIC_GEN_FPS           = 30

# Audio bitrate (fixed high‐quality)
STATIC_GEN_AUDIO_BITRATE = "320k"

# Where to write the output by default
STATIC_GEN_OUTPUT_FOLDER = MOVIES_PATH   # uses your MOVIES_PATH from above