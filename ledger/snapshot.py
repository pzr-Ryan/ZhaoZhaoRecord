"""Capture a Tk page into a PhotoImage using only the Windows GDI.

The page-switch animation needs a real 1.0 -> 0.0 fade for the outgoing
content.  Tk frames cannot be made translucent per widget, so we take one
client-area screenshot and fade a borderless top-level window that shows it.
Everything here is best effort: non-Windows hosts and capture failures return
None and let the caller use its non-screenshot fallback.
"""
from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

from . import raster


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 1),
    ]


def _gdi():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(_BITMAPINFO), wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    return user32, gdi32


def _rgba_from_hwnd(hwnd):
    width = height = 0
    screen = memory = bitmap = 0
    old_bitmap = 0
    dirty = None
    user32, gdi32 = _gdi()
    try:
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        width, height = int(rect.right), int(rect.bottom)
        if width <= 1 or height <= 1:
            return None

        screen = user32.GetDC(0)
        if not screen:
            return None
        memory = gdi32.CreateCompatibleDC(screen)
        bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
        if not memory or not bitmap:
            return None
        old_bitmap = gdi32.SelectObject(memory, bitmap)

        painted = user32.PrintWindow(hwnd, memory, 2)
        if not painted:
            point = wintypes.POINT(0, 0)
            if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
                return None
            if not gdi32.BitBlt(
                    memory, 0, 0, width, height, screen,
                    point.x, point.y, 0x00CC0020):
                return None

        info = _BITMAPINFO()
        header = info.bmiHeader
        header.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0
        size = width * height * 4
        dirty = ctypes.create_string_buffer(size)
        if not gdi32.GetDIBits(
                memory, bitmap, 0, height, dirty, ctypes.byref(info), 0):
            return None

        bgra = dirty.raw
        rgba = bytearray(size)
        rgba[0::4] = bgra[2::4]
        rgba[1::4] = bgra[1::4]
        rgba[2::4] = bgra[0::4]
        rgba[3::4] = b"\xff" * (width * height)
        return width, height, rgba
    finally:
        try:
            if memory and old_bitmap:
                gdi32.SelectObject(memory, old_bitmap)
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if memory:
                gdi32.DeleteDC(memory)
            if screen:
                user32.ReleaseDC(0, screen)
        except Exception:
            pass


def capture_page(widget, master):
    """Return an opaque tk.PhotoImage of the widget client area, or None."""
    if sys.platform != "win32":
        return None
    try:
        hwnd = int(widget.winfo_id())
        result = _rgba_from_hwnd(hwnd)
        if result is None:
            return None
        width, height, rgba = result
        return raster.photo_from_rgba(master, width, height, rgba)
    except Exception:
        logging.exception("page snapshot failed")
        return None
