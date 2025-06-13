import sys
import time
import ctypes
from ctypes import util as _ctypes_util

import pygame
import vlc

"""video_player.py – embed VLC video in a Pygame window **universally**
=====================================================================

This drop‑in module works on **Windows, Linux/X11/Wayland, and macOS**
(Python ≤3.11 and ≥3.12) without any optional dependencies (PyObjC, etc.).
It discovers the correct native drawable/handle that libVLC expects for
each platform and feeds it through *python‑vlc* so the video is rendered
*inside* the existing Pygame window instead of in a detached VLC window.
"""

__all__ = ["VideoPlayer"]

# ----------------------------------------------------------------------
# Helpers – convert SDL handles (ints / PyCapsules) ➔ ctypes void*
# ----------------------------------------------------------------------

def _capsule_to_void_p(capsule: object) -> ctypes.c_void_p:
    """Extract the pointer from a *PyCapsule* regardless of its *name*."""
    api = ctypes.pythonapi
    api.PyCapsule_GetPointer.restype = ctypes.c_void_p
    api.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
    api.PyCapsule_GetName.restype = ctypes.c_char_p
    api.PyCapsule_GetName.argtypes = [ctypes.py_object]

    try:  # unnamed fast path (historical wheels)
        return ctypes.c_void_p(api.PyCapsule_GetPointer(capsule, None))
    except ValueError:  # name check failed – fetch and retry
        name = api.PyCapsule_GetName(capsule)
        return ctypes.c_void_p(api.PyCapsule_GetPointer(capsule, name))


def _obj_to_void_p(obj) -> ctypes.c_void_p:
    """Return *ctypes.c_void_p* for an int | PyCapsule | c_void_p."""
    if isinstance(obj, ctypes.c_void_p):
        return obj
    if isinstance(obj, int):
        return ctypes.c_void_p(obj)
    # Assume PyCapsule
    return _capsule_to_void_p(obj)

# ----------------------------------------------------------------------
# macOS: obtain NSView* for VLC (no PyObjC required)
# ----------------------------------------------------------------------

def _macos_get_nsview(wm_info: dict) -> ctypes.c_void_p | None:
    """Return an ``NSView*`` (c_void_p) for VLC on macOS.

    SDL ≥2.24 stores the pointer directly under ``nsview``.
    Older SDL versions provide only ``window`` (NSWindow*).  We use the
    Objective‑C runtime (via *ctypes*) to call ``-contentView`` on that
    window and obtain the backing NSView* – this avoids requiring PyObjC.
    """

    # 1. Preferred: SDL already gives the view.
    for key in ("nsview", "view"):
        if key in wm_info and wm_info[key]:
            return _obj_to_void_p(wm_info[key])

    # 2. Fallback: derive from NSWindow* (if present).
    win_obj = wm_info.get("window")
    if not win_obj:
        return None

    win_ptr = _obj_to_void_p(win_obj)  # NSWindow*

    try:
        objc = ctypes.cdll.LoadLibrary(_ctypes_util.find_library("objc"))

        # sel_registerName("contentView") ➔ SEL
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        sel_contentView = ctypes.c_void_p(
            objc.sel_registerName(b"contentView"))

        # objc_msgSend(id, SEL) ➔ id (we treat as void*)
        objc.objc_msgSend.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        view_ptr = objc.objc_msgSend(win_ptr, sel_contentView)
        if view_ptr:
            return ctypes.c_void_p(view_ptr)
    except Exception:
        pass  # fallthrough: return NSWindow* (VLC will spawn its own window)

    return win_ptr

# ----------------------------------------------------------------------
# Public API – VideoPlayer
# ----------------------------------------------------------------------

class VideoPlayer:
    """Thin bridge between *python‑vlc* and a Pygame SDL2 window."""

    def __init__(self):
        self._vlc = vlc.Instance()
        self._player: vlc.MediaPlayer | None = None

    # ---------- lifecycle --------------------------------------------------

    def open(self, filepath: str, start_offset: float = 0.0):
        """Load *filepath* and start playing at *start_offset* seconds."""
        self.close()

        self._player = self._vlc.media_player_new()
        self._player.set_media(self._vlc.media_new(filepath))

        wm_info = pygame.display.get_wm_info()
        plat = sys.platform
        if plat.startswith("win"):
            self._player.set_hwnd(wm_info["window"])               # HWND
        elif plat == "darwin":
            drawable = _macos_get_nsview(wm_info)
            if drawable is not None:
                self._player.set_nsobject(drawable)                # NSView*
        else:  # X11 / Wayland
            self._player.set_xwindow(wm_info["window"])            # Window id

        self._player.play()
        time.sleep(0.1)  # let decoders warm‑up
        self._player.set_time(int(start_offset * 1000))            # seek (ms)

    def close(self):
        if self._player is not None:
            self._player.stop()
            self._player.release()
            self._player = None
