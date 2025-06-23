#!/usr/bin/env python3
"""
events.py  – central hub

• Translates raw Pygame events to high-level action dicts.
• Exposes a thread-safe queue so *any* external source can inject
  the same actions (GPIO, web API, HID, etc.).
"""

from __future__ import annotations
import queue
from pygame.locals import *

Action = dict      # alias for readability


class EventManager:
    _fifo: "queue.Queue[Action]" = queue.Queue()      # global, thread-safe

    # ── SDL / keyboard path ────────────────────────────────────────────
    @classmethod
    def handle(cls, event, phase, current_ch, ch_mgr) -> None:
        """Translate one Pygame event → action and enqueue it."""
        act = cls._translate_pygame(event, phase, current_ch, ch_mgr)
        if act:
            cls._fifo.put(act)

    # ── external / programmatic path ───────────────────────────────────
    @classmethod
    def post(cls, action: Action) -> None:
        """
        Any thread may call this to inject an already-formed action dict, e.g.:
            EventManager.post({"type":"switch_channel","to":11})
        """
        cls._fifo.put(action)

    # ── main-loop consumer ─────────────────────────────────────────────
    @classmethod
    def poll(cls) -> Action | None:
        """Return next queued action or None (non-blocking)."""
        try:
            return cls._fifo.get_nowait()
        except queue.Empty:
            return None

    # ── internal translator ───────────────────────────────────────────
    @staticmethod
    def _translate_pygame(event, phase, current_ch, ch_mgr) -> Action | None:
        if event.type == QUIT:
            return {"type": "quit"}

        if event.type == KEYDOWN:
            if event.key in (K_ESCAPE, K_q):
                return {"type": "quit"}
            if event.key == K_i:
                return {"type": "toggle_overlay"}
            if phase == "normal" and event.key in (K_RIGHT, K_SPACE, K_LEFT):
                dest = ch_mgr.next(current_ch) if event.key in (K_RIGHT, K_SPACE) \
                      else ch_mgr.prev(current_ch)
                return {"type": "switch_channel", "to": dest}
            if event.key == K_f:
                return {"type": "toggle_fullscreen"}

        return None
