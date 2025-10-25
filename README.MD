# PyTV – A Time-Synchronized TV Emulator

PyTV is a multi-channel TV emulator that synchronizes playback using a shared, internal time source.  
It is conceived as a *self-portrait*: every frame is calculated from one fixed “birth” timestamp (`REFERENCE_START_TIME`) in **config.py**.

---

## Architecture – A Deterministic Time-Based Scheduler

* **Universal timeline** — anchored to `REFERENCE_START_TIME`, the “birth” of the system.  
* **Scheduler (`channel_manager.py`)** — pure function  
  `f(current_wall_time, REFERENCE_START_TIME, user_time_offset) → (file_path, file_offset)`
* **Enforcer (`app.py`)** — main loop that compares the *correct* state to the current player state each frame.  
* **“Dumb” player (`video_player.py`)** — obeys whatever the Enforcer tells it; its PTS clock is irrelevant.  
* **Synchronized UI (`overlays.py`)** — queries the Scheduler so overlays always show the mathematically correct time.

---

## Features

* **Deterministic sync** – playback is fully derived from the wall clock.  
* **Multi-channel playlists** – auto-loads `movies/chan_NN` directories.  
* **Pause-aware playlists** – `playlist_builder.py` inserts `__PAUSE__` sentinels.  
* **Web-based remote control** – `main.py` runs a `web_remote` server.  
* **Dynamic time-shifting** – `adjust_offset` skews the whole timeline (not just a seek).  
* **Extensible events** – central `EventManager.post()` API for new inputs.

---

## Getting Started

### 1. Dependencies

#### Python packages (see `requirements.txt`)

