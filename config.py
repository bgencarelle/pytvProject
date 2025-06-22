# config.py
"""
Configuration settings for the TV emulator.
"""
import datetime
# config.py
import time
FPS   = 30

EPOCH = time.time()          # single constant
SINGLE_VID_PAUSE = True
RUN_PLAYLIST_BUILDER = True

# ── Basic Application Settings ──────────────────────────────────────────────

SHOW_OVERLAYS = True

# Path to directory containing video channel files
MOVIES_PATH = "movies"

# Reference start time (UTC epoch) for synchronized playback
REFERENCE_START_TIME = datetime.datetime(1978, 11, 17, 7, 11, 0).timestamp()

# Starting channel: None means the lowest channel
START_CHANNEL = 0x00

# Minimum real-time gap (s) between accepted channel-change key presses
CHANNEL_CHANGE_DEBOUNCE = 0.35

# Display settings
FULLSCREEN = True
WINDOWED_SIZE = (800, 600)

# Transition effect type: "static" or "fade"
TRANSITION_TYPE = "static"

# ── Overlay durations ──────────────────────────────────────────────────────

OVERLAY_DURATION      = 4.0   # seconds to show overlay after channel change
INFO_OVERLAY_DURATION = 8.0   # seconds to show overlay on “i”

# ── Static‐transition defaults (blocky CRT snow + filtered hiss) ───────────

STATIC_BURST_SEC           = .75
STATIC_BLOCK_SIZE         = 1
STATIC_CUTOFF_HZ          = 2000.0
STATIC_SCANLINE_INTENSITY = 0.95
STATIC_TEAR_BAND_PCT      = 0.10
STATIC_TEAR_MAX_SHIFT     = 50
STATIC_FLICKER_RANGE      = (0.99, 1.1)
STATIC_GAUSS_SIGMA        = 10.0

# Extra CRT-look knobs (optional)
STATIC_BLUR_TAPS          = 2     # vertical blur kernel (odd, 3–9 recommended)
STATIC_PER_LINE_JITTER     = 9     # ±pixels to roll each scan-line every frame
STATIC_VIGNETTE_STRENGTH  = 0.01  # 0 = none, 1 = strong dark corners
STATIC_PERSISTENCE        = 0.1   # 0 = no ghosting, 0.3 = mild phosphor trail
STATIC_BRIGHTNESS_GAIN    = 1.9   # Overall brightness gain (1.0 = no change, >1 = brighter)

# How much to fade in/out the static audio (in seconds)
STATIC_AUDIO_CROSSFADE    = 0.1

# ── Static‐movie generator defaults ────────────────────────────────────────

STATIC_GEN_DURATION       = 900.0      # Length of the generated loop, in seconds
STATIC_GEN_FPS            = 30         # Frame rate for the generated loop (will be capped at 30)
STATIC_GEN_AUDIO_BITRATE  = "320k"     # Audio bitrate (fixed high‐quality)
STATIC_GEN_OUTPUT_FOLDER  = MOVIES_PATH   # uses your MOVIES_PATH from above

# ── Internal/Private Generation Knobs ──────────────────────────────────────

_CHUNK_DURATION = .50    # seconds of static per transition
_FADE_OUT_SEC   = 0.01    # fade out static audio over last 0.5 s

