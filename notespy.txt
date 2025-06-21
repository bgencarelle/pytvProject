Big-picture goal
----------------
Build a “fake television” application that:

• Reads a movies/ directory containing channel sub-folders chan_<num>.
• Uses wall-clock time + a fixed epoch to decide **exactly** which frame each PC
  should show, so multiple machines stay in perfect sync with no networking.
• Supports channel up / down keys; shows CRT-style static while switching.
• Displays an optional overlay (clock, CPU, playlist info, timestamp).
• Loops seamlessly inside each video and across an entire playlist.

Current file roles & flaws
--------------------------
config.py
    Constants. One global FPS (30) and IPS (1000 “ticks/s”). IPS is a stub.

channel_manager.py
    Runtime scan → Channel objects {files, durations, total_duration}.
    offset() floors wall-time to 1/IPS seconds to pick file + offset.
    ✗ Assumes constant FPS, no per-file frame counts, no cache – minor drift.

video_player.py
    GStreamer wrapper. Works, but seek → previous key-frame so small drift is
    possible; no µ-second PTS query.

overlays.py
    Draws badge, clock, playlist panel. Uses ChannelManager.offset().
    ✗ If offset drifts, overlay “remaining” drifts too.

transitions.py
    Legacy static-burst helper – **unused**.

renderer.py
    Scales / letterboxes frame – fine.

timing.py
    Just wraps time.time() – redundant.

app.py
    Main loop. On every frame:
        • Checks channel_manager._path_off().
        • If file path changed it **re-opens** a new VideoPlayer instantly.
    ✗ If duration rounding is off by <1 s it closes & reopens every second,
       causing the one-second loop / jump you observed.
    ✗ No drift correction other than IPS flooring.

Why the 1-second loop happens
-----------------------------
  true boundary = 299.700 s
  IPS (1 ms) floor  → 299.000 s
  → app thinks playlist rolled 0.7 s early, reopens next file at 0.0 s,
    shows ~1 s, offset catches up, flips again → stutter loop.

Minimal to-do list (no code written yet)
----------------------------------------
1. **Stop reopening players every frame.**
   Keep current VideoPlayer until its PTS passes real clip length (+1 frame).

2. **Add playlist_builder.py cache**:
   Store frames, fps, duration_us, start_us, total_us once per file.

3. **Switch offset() to µ-second timeline** (1 µs ticks), drop IPS magic.

4. **Drift guard**:
   Every 0.5 s compare player PTS vs expected µs; seek if off > 1 frame.

5. **Overlay** reads cached totals so “remaining” is correct.

6. Clean git: drop dead duplicates and transitions.py.
