# config.py
"""
Configuration settings for the TV emulator.
"""
import datetime

# Reference start time (UTC epoch) for synchronized playback
REFERENCE_START_TIME = datetime.datetime(2025, 1, 1, 0, 0, 0).timestamp()

# Display settings
FULLSCREEN = True
WINDOWED_SIZE = (800, 600)

# Path to directory containing video channel files
MOVIES_PATH = "movies"

# Starting channel: None means the lowest channel
START_CHANNEL = None

# Transition effect type: "static" or "fade"
TRANSITION_TYPE = "static"

# ── Overlay durations ────────────────────────────────────────────
OVERLAY_DURATION      = 2.0   # seconds to show overlay after channel change
INFO_OVERLAY_DURATION = 3.0   # seconds to show overlay on “i”

# ── Static‐transition defaults (blocky CRT snow + filtered hiss) ──
STATIC_DURATION           = 1.5
STATIC_BLOCK_SIZE         = 8
STATIC_CUTOFF_HZ          = 2000.0
STATIC_SCANLINE_INTENSITY = 0.5
STATIC_TEAR_BAND_PCT      = 0.10
STATIC_TEAR_MAX_SHIFT     = 50
STATIC_FLICKER_RANGE      = (0.9, 1.1)
STATIC_GAUSS_SIGMA        = 40.0
