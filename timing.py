# =========  timing.py  =========
"""
Deterministic wall-clock helpers.
The math mirrors index_calculator.calculate_free_clock_index() but
operates in *seconds*, not images.
"""

import time
import datetime
import math
import config

# If you ever want a reproducible “from-birth” start, just fill these:
REFERENCE_TZ   = datetime.timezone.utc
REFERENCE_TIME = config.REFERENCE_START_TIME   # already an epoch float

def wall_clock() -> float:
    """
    Returns seconds elapsed since the reference epoch as a float
    (monotonic with real time).
    """
    return time.time() - REFERENCE_TIME

def pingpong_phase(period: float, *, dual_pivot: bool = True) -> float:
    """
    Mirrors phase within a period:
        0 → period/2  : forward ramp
        period/2 → 0  : backward ramp
    If dual_pivot==False the wave touches the ends once (|\/|…).  When
    True it pauses one frame at both ends (|\/\|).
    """
    if period <= 0:
        return 0.0

    full = period * (2 if dual_pivot else 2)
    p    = math.fmod(wall_clock(), full)
    if p < 0:
        p += full

    if p < period:
        return p                # forward
    else:
        return (full - p)       # mirrored back
