"""Dependency-free anti-aliased images for Tk (no Pillow required).

Shapes are rasterised at a supersampled resolution and box-filtered down,
then encoded as PNG and loaded through tk.PhotoImage (Tk 8.6 supports it).
Rendered images are cached by geometry and colour, so resizing windows only
re-renders when a widget's pixel size actually changes.
"""
from __future__ import annotations

import base64
import bisect
import math
import struct
import tkinter as tk
import zlib

from .theme import _hex_to_rgb, mix

# Supersampling factor for small images (buttons, chips, corners).
SS_SMALL = 4
# Supersampling factor for larger images (chart rings).
SS_LARGE = 3

_CACHE = {}


def clear_cache():
    _CACHE.clear()


def cache_size():
    return len(_CACHE)


# --------------------------------------------------------------------------- png
def _png(width, height, rgba):
    stride = width * 4
    raw = bytearray((stride + 1) * height)
    for y in range(height):
        raw[y * (stride + 1)] = 0
        raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] = rgba[
            y * stride:(y + 1) * stride
        ]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def _photo(master, width, height, rgba):
    data = base64.b64encode(_png(width, height, rgba)).decode("ascii")
    return tk.PhotoImage(master=master, data=data)


def photo_from_rgba(master, width, height, rgba):
    """Build a PhotoImage from a tightly packed RGBA byte buffer."""
    return _photo(master, max(1, int(width)), max(1, int(height)), rgba)


class Surface:
    """An RGBA supersampled canvas."""

    def __init__(self, width, height, ss, bg=None):
        self.w = max(1, int(width))
        self.h = max(1, int(height))
        self.ss = max(1, int(ss))
        self.pw = self.w * self.ss
        self.ph = self.h * self.ss
        self.buf = bytearray(self.pw * self.ph * 4)
        if bg is not None:
            self._fill(bg)

    def _fill(self, color):
        r, g, b = _hex_to_rgb(color)
        self.buf[:] = bytes((r, g, b, 255)) * (self.pw * self.ph)

    def span(self, sy, x0, x1, color):
        if sy < 0 or sy >= self.ph:
            return
        x0 = max(0, int(math.ceil(x0)))
        x1 = min(self.pw, int(math.ceil(x1)))
        if x1 <= x0:
            return
        r, g, b = _hex_to_rgb(color)
        start = (sy * self.pw + x0) * 4
        end = (sy * self.pw + x1) * 4
        self.buf[start:end] = bytes((r, g, b, 255)) * (x1 - x0)

    def clear_span(self, sy, x0, x1):
        if sy < 0 or sy >= self.ph:
            return
        x0 = max(0, int(math.ceil(x0)))
        x1 = min(self.pw, int(math.ceil(x1)))
        if x1 <= x0:
            return
        start = (sy * self.pw + x0) * 4
        end = (sy * self.pw + x1) * 4
        self.buf[start:end] = b"\x00" * ((x1 - x0) * 4)

    def opaque_at(self, sx, sy):
        index = (sy * self.pw + sx) * 4 + 3
        return self.buf[index] > 0

    def downsample(self):
        ss = self.ss
        out = bytearray(self.w * self.h * 4)
        src = self.buf
        pw = self.pw
        for y in range(self.h):
            for x in range(self.w):
                r = g = b = a = 0
                for dy in range(ss):
                    row = ((y * ss + dy) * pw + x * ss) * 4
                    for dx in range(ss):
                        i = row + dx * 4
                        alpha = src[i + 3]
                        if alpha:
                            r += src[i] * alpha
                            g += src[i + 1] * alpha
                            b += src[i + 2] * alpha
                            a += alpha
                o = (y * self.w + x) * 4
                if a:
                    out[o] = r // a
                    out[o + 1] = g // a
                    out[o + 2] = b // a
                    out[o + 3] = a // (ss * ss)
        return out

    def image(self, master):
        return _photo(master, self.w, self.h, self.downsample())


# --------------------------------------------------------------------------- shapes
def _fill_circle(surface, cx, cy, radius, color):
    if radius <= 0:
        return
    ss = surface.ss
    top = max(0, int(math.floor((cy - radius) * ss)))
    bottom = min(surface.ph, int(math.ceil((cy + radius) * ss)))
    r2 = radius * radius
    for sy in range(top, bottom):
        v = (sy + 0.5) / ss - cy
        if abs(v) > radius:
            continue
        dx = math.sqrt(max(0.0, r2 - v * v))
        surface.span(sy, (cx - dx) * ss, (cx + dx) * ss, color)


def _clear_circle(surface, cx, cy, radius):
    if radius <= 0:
        return
    ss = surface.ss
    top = max(0, int(math.floor((cy - radius) * ss)))
    bottom = min(surface.ph, int(math.ceil((cy + radius) * ss)))
    r2 = radius * radius
    for sy in range(top, bottom):
        v = (sy + 0.5) / ss - cy
        if abs(v) > radius:
            continue
        dx = math.sqrt(max(0.0, r2 - v * v))
        surface.clear_span(sy, (cx - dx) * ss, (cx + dx) * ss)


def _fill_capsule(surface, x1, y1, x2, y2, width, color):
    half = width / 2.0
    if half <= 0:
        return
    ss = surface.ss
    dx = x2 - x1
    dy = y2 - y1
    length2 = dx * dx + dy * dy
    if length2 == 0:
        _fill_circle(surface, x1, y1, half, color)
        return
    min_x = min(x1, x2) - half
    max_x = max(x1, x2) + half
    min_y = min(y1, y2) - half
    max_y = max(y1, y2) + half
    top = max(0, int(math.floor(min_y * ss)))
    bottom = min(surface.ph, int(math.ceil(max_y * ss)))
    left = max(0, int(math.floor(min_x * ss)))
    right = min(surface.pw, int(math.ceil(max_x * ss)))
    r, g, b = _hex_to_rgb(color)
    pixel = bytes((r, g, b, 255))
    for sy in range(top, bottom):
        v = (sy + 0.5) / ss
        for sx in range(left, right):
            u = (sx + 0.5) / ss
            t = ((u - x1) * dx + (v - y1) * dy) / length2
            t = max(0.0, min(1.0, t))
            px = x1 + t * dx
            py = y1 + t * dy
            if (u - px) ** 2 + (v - py) ** 2 <= half * half:
                index = (sy * surface.pw + sx) * 4
                surface.buf[index:index + 4] = pixel


def _fill_round_rect(surface, x0, y0, x1, y1, radius, color):
    if x1 <= x0 or y1 <= y0:
        return
    radius = max(0.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    ss = surface.ss
    top = max(0, int(math.floor(y0 * ss)))
    bottom = min(surface.ph, int(math.ceil(y1 * ss)))
    if radius <= 0:
        for sy in range(top, bottom):
            surface.span(sy, x0 * ss, x1 * ss, color)
        return
    r2 = radius * radius
    for sy in range(top, bottom):
        v = (sy + 0.5) / ss
        if v < y0 + radius:
            delta = radius - (v - y0)
            if delta > radius:
                continue
            dx = math.sqrt(max(0.0, r2 - delta * delta))
            left = x0 + radius - dx
            right = x1 - radius + dx
        elif v > y1 - radius:
            delta = radius - (y1 - v)
            if delta > radius:
                continue
            dx = math.sqrt(max(0.0, r2 - delta * delta))
            left = x0 + radius - dx
            right = x1 - radius + dx
        else:
            left, right = x0, x1
        surface.span(sy, left * ss, right * ss, color)


def _round_rect_surface(width, height, radius, fill, border=None, bg=None,
                        border_width=1, ss=SS_SMALL):
    width = max(1, int(round(width)))
    height = max(1, int(round(height)))
    bg = bg or fill
    surface = Surface(width, height, ss, bg)
    if border:
        _fill_round_rect(surface, 0, 0, width, height, radius, border)
        inner = border_width
        _fill_round_rect(surface, inner, inner, width - inner, height - inner,
                         max(0, radius - inner), fill)
    else:
        _fill_round_rect(surface, 0, 0, width, height, radius, fill)
    return surface


# --------------------------------------------------------------------------- public images
def round_rect(master, width, height, radius, fill, border=None, bg=None,
               border_width=1):
    """Opaque rounded rectangle (used as a widget background image)."""
    width = max(1, int(round(width)))
    height = max(1, int(round(height)))
    radius = max(0, int(round(radius)))
    bg = bg or fill
    key = ("rr", master.tk, width, height, radius, fill, border, bg, border_width)
    image = _CACHE.get(key)
    if image is None:
        surface = _round_rect_surface(width, height, radius, fill, border, bg,
                                      border_width)
        image = surface.image(master)
        _CACHE[key] = image
    return image


def crop_rgba(rgba, width, x, y, crop_w, crop_h):
    out = bytearray(crop_w * crop_h * 4)
    for row in range(crop_h):
        src = ((y + row) * width + x) * 4
        dst = row * crop_w * 4
        out[dst:dst + crop_w * 4] = rgba[src:src + crop_w * 4]
    return out


def corners(master, radius, fill, border, bg):
    """Four AA corner tiles returned as a dict keyed nw/ne/sw/se."""
    radius = max(1, int(round(radius)))
    key = ("corners", master.tk, radius, fill, border, bg)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    size = radius + 1
    full = 2 * radius + 1
    surface = Surface(full, full, SS_SMALL, bg)
    _fill_round_rect(surface, 0, 0, full, full, radius, border)
    _fill_round_rect(surface, 1, 1, full - 1, full - 1, radius - 1, fill)
    rgba = surface.downsample()
    result = {}
    positions = {
        "nw": (0, 0),
        "ne": (full - size, 0),
        "sw": (0, full - size),
        "se": (full - size, full - size),
    }
    for corner, (x, y) in positions.items():
        data = crop_rgba(rgba, full, x, y, size, size)
        result[corner] = _photo(master, size, size, data)
    _CACHE[key] = result
    return result


def circle(master, diameter, color, bg):
    diameter = max(1, int(round(diameter)))
    key = ("circle", master.tk, diameter, color, bg)
    image = _CACHE.get(key)
    if image is None:
        surface = Surface(diameter, diameter, SS_SMALL, bg)
        _fill_circle(surface, diameter / 2.0, diameter / 2.0,
                     diameter / 2.0 - 0.5, color)
        image = surface.image(master)
        _CACHE[key] = image
    return image


def ring(master, diameter, thickness, color, bg):
    """A circular outline with a transparent centre."""
    diameter = max(2, int(round(diameter)))
    thickness = max(1, int(round(thickness)))
    key = ("ring", master.tk, diameter, thickness, color, bg)
    image = _CACHE.get(key)
    if image is None:
        surface = Surface(diameter, diameter, SS_SMALL, bg)
        center = diameter / 2.0
        _fill_circle(surface, center, center, center - 0.5, color)
        _clear_circle(surface, center, center, center - 0.5 - thickness)
        image = surface.image(master)
        _CACHE[key] = image
    return image


def bar(master, width, height, radius, color):
    """Solid vertical bar with rounded top corners (transparent bottom)."""
    width = max(1, int(round(width)))
    height = max(1, int(round(height)))
    radius = max(0, int(round(radius)))
    key = ("bar", master.tk, width, height, radius, color)
    image = _CACHE.get(key)
    if image is None:
        surface = Surface(width, height, SS_SMALL, None)
        _fill_round_rect(surface, 0, 0, width, height + radius,
                         min(radius, width / 2.0), color)
        image = surface.image(master)
        _CACHE[key] = image
    return image


def bar_rgba(master, width, height, radius, top_color, bottom_color):
    """Rounded-top bar with a subtle vertical gradient."""
    width = max(1, int(round(width)))
    height = max(1, int(round(height)))
    radius = max(0, int(round(radius)))
    key = ("barg", master.tk, width, height, radius, top_color, bottom_color)
    image = _CACHE.get(key)
    if image is None:
        rgba = bytearray(width * height * 4)
        top = _hex_to_rgb(top_color)
        bottom = _hex_to_rgb(bottom_color)
        r2 = radius * radius
        for y in range(height):
            ratio = y / max(1, height - 1)
            r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
            g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
            b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
            for x in range(width):
                if y < radius and (x < radius or x >= width - radius):
                    cx = radius - 0.5 if x < radius else width - radius - 0.5
                    dx = x + 0.5 - cx
                    dy = y + 0.5 - (radius - 0.5)
                    if dx * dx + dy * dy > r2:
                        continue
                i = (y * width + x) * 4
                rgba[i:i + 4] = bytes((r, g, b, 255))
        image = _photo(master, width, height, rgba)
        _CACHE[key] = image
    return image


def icon(master, name, size, color):
    """A small transparent icon rendered with AA edges."""
    size = max(8, int(round(size)))
    key = ("icon", master.tk, name, size, color)
    image = _CACHE.get(key)
    if image is None:
        surface = Surface(size, size, 4, None)
        stroke = max(1.5, size * 0.085)
        s = float(size)
        if name == "plus":
            _fill_capsule(surface, s * 0.5, s * 0.22, s * 0.5, s * 0.78, stroke, color)
            _fill_capsule(surface, s * 0.22, s * 0.5, s * 0.78, s * 0.5, stroke, color)
        elif name == "list":
            for ratio in (0.28, 0.5, 0.72):
                y = s * ratio
                _fill_circle(surface, s * 0.17, y, stroke * 0.62, color)
                _fill_capsule(surface, s * 0.34, y, s * 0.84, y, stroke, color)
        elif name == "chart":
            for ratio, top in ((0.26, 0.46), (0.5, 0.34), (0.74, 0.2)):
                x = s * ratio
                _fill_capsule(surface, x, s * 0.78, x, s * top, stroke * 1.5, color)
            _fill_capsule(surface, s * 0.12, s * 0.85, s * 0.88, s * 0.85, 1.2, color)
        elif name == "sliders":
            for index, ratio in enumerate((0.3, 0.5, 0.7)):
                y = s * ratio
                _fill_capsule(surface, s * 0.12, y, s * 0.88, y, 1.4, color)
                knob = 0.66 if index == 0 else (0.34 if index == 1 else 0.55)
                _fill_circle(surface, s * knob, y, s * 0.095, color)
                _clear_circle(surface, s * knob, y, s * 0.045)
        elif name == "calendar":
            _fill_capsule(surface, s * 0.2, s * 0.24, s * 0.8, s * 0.24, 1.2, color)
            _fill_capsule(surface, s * 0.2, s * 0.8, s * 0.8, s * 0.8, 1.2, color)
            _fill_capsule(surface, s * 0.2, s * 0.24, s * 0.2, s * 0.8, 1.2, color)
            _fill_capsule(surface, s * 0.8, s * 0.24, s * 0.8, s * 0.8, 1.2, color)
            _fill_capsule(surface, s * 0.32, s * 0.14, s * 0.32, s * 0.3, 1.4, color)
            _fill_capsule(surface, s * 0.68, s * 0.14, s * 0.68, s * 0.3, 1.4, color)
            _fill_capsule(surface, s * 0.32, s * 0.4, s * 0.68, s * 0.4, 1.1, color)
            for x in (0.36, 0.5, 0.64):
                _fill_circle(surface, s * x, s * 0.6, s * 0.035, color)
        elif name == "chevron":
            _fill_capsule(surface, s * 0.28, s * 0.42, s * 0.5, s * 0.62, 1.6, color)
            _fill_capsule(surface, s * 0.5, s * 0.62, s * 0.72, s * 0.42, 1.6, color)
        elif name == "left":
            _fill_capsule(surface, s * 0.58, s * 0.24, s * 0.36, s * 0.5, 1.6, color)
            _fill_capsule(surface, s * 0.36, s * 0.5, s * 0.58, s * 0.76, 1.6, color)
        elif name == "right":
            _fill_capsule(surface, s * 0.42, s * 0.24, s * 0.64, s * 0.5, 1.6, color)
            _fill_capsule(surface, s * 0.64, s * 0.5, s * 0.42, s * 0.76, 1.6, color)
        image = surface.image(master)
        _CACHE[key] = image
    return image


def donut(master, diameter, ring, segments):
    """Transparent ring image.

    segments is a list of (start_degrees, extent_degrees, color) where angles
    are measured clockwise from 12 o'clock.
    """
    diameter = max(2, int(round(diameter)))
    ring = max(1, int(round(ring)))
    segments = [(float(a), float(e), c) for a, e, c in segments if e]
    key = ("donut", master.tk, diameter, ring,
           tuple((round(a, 2), round(e, 2), c) for a, e, c in segments))
    image = _CACHE.get(key)
    if image is not None:
        return image
    ss = SS_LARGE if diameter <= 280 else 2
    surface = Surface(diameter, diameter, ss, None)
    c = diameter / 2.0
    outer = c - 0.5
    inner = max(0.0, outer - ring)
    starts = []
    colors = []
    total = 0.0
    for start, extent, color in segments:
        starts.append(total)
        total += abs(extent)
        colors.append(color)
    if total <= 0:
        colors = []
    ss = surface.ss
    outer2 = outer * outer
    inner2 = inner * inner
    last = -1
    for sy in range(surface.ph):
        v = (sy + 0.5) / ss - c
        if abs(v) > outer:
            continue
        dx_out = math.sqrt(max(0.0, outer2 - v * v))
        if abs(v) < inner:
            dx_in = math.sqrt(max(0.0, inner2 - v * v))
        else:
            dx_in = 0.0
        left0 = int(math.ceil((c - dx_out) * ss))
        left1 = int(math.floor((c - dx_in) * ss))
        right0 = int(math.ceil((c + dx_in) * ss))
        right1 = int(math.floor((c + dx_out) * ss))
        if colors:
            for sx in range(left0, left1):
                u = (sx + 0.5) / ss - c
                angle = math.degrees(math.atan2(u, -v)) % 360.0
                index = bisect.bisect_right(starts, angle) - 1
                if index < 0:
                    index = 0
                color = colors[index]
                if color != last:
                    rgb = _hex_to_rgb(color)
                    last = color
                index4 = (sy * surface.pw + sx) * 4
                surface.buf[index4:index4 + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))
            for sx in range(right0, right1):
                u = (sx + 0.5) / ss - c
                angle = math.degrees(math.atan2(u, -v)) % 360.0
                index = bisect.bisect_right(starts, angle) - 1
                if index < 0:
                    index = 0
                color = colors[index]
                if color != last:
                    rgb = _hex_to_rgb(color)
                    last = color
                index4 = (sy * surface.pw + sx) * 4
                surface.buf[index4:index4 + 4] = bytes((rgb[0], rgb[1], rgb[2], 255))
    image = surface.image(master)
    _CACHE[key] = image
    return image
