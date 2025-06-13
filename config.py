"""
Configuration settings for the video switcher.
Contains adjustable parameters for display, channel setup, and behavior.
"""
import datetime

# Reference start time for synchronized playback (UTC).
REFERENCE_START_TIME = datetime.datetime(2025, 1, 1, 0, 0, 0).timetuple()

# Full-screen mode by default. Set to False for windowed mode.
FULLSCREEN = True
# Windowed mode size if not full-screen
WINDOWED_SIZE = (800, 600)

# Path to video files directory
MOVIES_PATH = "movies"

# Starting channel (None to start at lowest channel)
START_CHANNEL = None

# Transition type: "static" or "fade"
TRANSITION_TYPE = "static"
