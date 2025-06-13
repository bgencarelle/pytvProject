# config.py
"""
Configuration settings for the TV emulator.
"""
import datetime

# Reference start time (UTC epoch) for synchronized playback
REFERENCE_START_TIME = datetime.datetime(2025, 1, 1, 0, 0, 0).timestamp()

# Display settings
FULLSCREEN = True            # start in fullscreen
WINDOWED_SIZE = (800, 600)   # if not fullscreen

# Path to directory containing video channel files
MOVIES_PATH = "movies"

# Starting channel: None means the lowest channel
START_CHANNEL = None

# Transition effect type: "static" or "fade"
TRANSITION_TYPE = "static"
