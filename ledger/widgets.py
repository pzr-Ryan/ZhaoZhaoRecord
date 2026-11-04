"""Reusable widgets for the ledger UI.

All rounded shapes are composed from crisp Tk rectangles/lines plus cached
anti-aliased corner tiles and icons, so resizing never triggers expensive
per-pixel repaints.
"""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import raster
from .motion import Tween
from .theme import darken, font, lighten, mix, px


# --------------------------------------------------------------------------- helpers
def rounded_points(x1, y1, x2, y2, radius):
    points = []
    points.append(x1 + radius)
    points.append(y1)
    points.append(x2 - radius)
    points.append(y1)
    points.append(x2)
    points.append(y1)
    points.append(x2)
    points.append(y1 + radius)
    points.append(x2)
    points.append(y2 - radius)
    points.append(x2)
    points.append(y2)
    points.append(x2 - radius)
    points.append(y2)
    points.append(x1 + radius)
    points.append(y2)
    points.append(x1)
    points.append(y2)
    points.append(x1)
    points.append(y2 - radius)
    points.append(x1)
    points.append(y1 + radius)
    points.append(x1)
    points.append(y1)
    return points


def draw_round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """Legacy helper kept for compatibility; new code uses draw_round_box."""
    kwargs.pop("smooth", None)
    kwargs.pop("splinesteps", None)
    points = rounded_points(x1, y1, x2, y2, radius)
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


def draw_round_box(canvas, x0, y0, x1, y1, radius, fill, border, bg):
    """Crisp rectangle body plus anti-aliased corner tiles."""
    canvas.delete("all")
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0:
        return
    radius = max(0, min(int(radius), int(width) // 2, int(height) // 2))
    border = border or fill
    x1 = int(x1) - 1
    y1 = int(y1) - 1
    if radius < 2:
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=border, width=1)
        return
    canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=border, width=1)
    tiles = raster.corners(canvas, radius, fill, border, bg)
    size = radius + 1
    spots = (
        ("nw", x0, y0),
        ("ne", x1 - size + 1, y0),
        ("sw", x0, y1 - size + 1),
        ("se", x1 - size + 1, y1 - size + 1),
    )
    for corner, x, y in spots:
        canvas.create_image(x, y, anchor="nw", image=tiles[corner])


def is_descendant(widget, ancestor):
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "master", None)
    return False


def bind_wheel_tree(widget, canvas):
    """Deprecated: kept so older verify scripts keep importing."""
    try:
        widget.bind("<MouseWheel>", lambda e: canvas.yview_scroll(
            -3 if e.delta > 0 else 3, "units"))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        bind_wheel_tree(child, canvas)


def round_window(window):
    """Ask the Windows DWM for rounded corners (best effort)."""
    try:
        import ctypes
        hwnd = int(window.winfo_id())
    except Exception:
        return
    try:
        user32 = ctypes.windll.user32
        parent = user32.GetParent(hwnd)
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(2)
        for handle in (hwnd, parent):
            if handle:
                dwm.DwmSetWindowAttribute(ctypes.c_void_p(handle), 33,
                                          ctypes.byref(value), 4)
    except Exception:
        pass


def _outer_bg(master):
    try:
        return master.cget("bg")
    except tk.TclError:
        return "#FFFFFF"


# --------------------------------------------------------------------------- card
class RoundedCard(tk.Frame):
    def __init__(self, master, palette, padding=18, radius=14, bg=None, fill=None,
                 **kwargs):
        outer = bg or _outer_bg(master)
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, bg=outer, **kwargs)
        self.palette = palette
        self.padding = px(padding)
        self.radius = px(radius)
        self._bg = outer
        self.fill = fill or palette.surface
        self.border = palette.border
        self._corner_size = self.radius + 1
        self.shell = tk.Frame(self, bg=self.fill, bd=0, highlightthickness=1,
                              highlightbackground=self.border,
                              highlightcolor=self.border)
        self.shell.pack(fill="both", expand=True)
        self.body = tk.Frame(self.shell, bg=self.fill, bd=0, highlightthickness=0)
        self.body.pack(fill="both", expand=True, padx=self.padding, pady=self.padding)
        self._corners = {}
        self._install_corners()

    def _install_corners(self):
        size = self._corner_size
        tiles = raster.corners(self, self.radius, self.fill, self.border, self._bg)
        spots = {
            "nw": dict(x=0, y=0),
            "ne": dict(relx=1.0, x=-size, y=0),
            "sw": dict(x=0, rely=1.0, y=-size),
            "se": dict(relx=1.0, x=-size, rely=1.0, y=-size),
        }
        for corner in ("nw", "ne", "sw", "se"):
            holder = tk.Canvas(self, width=size, height=size, bg=self._bg,
                               bd=0, highlightthickness=0)
            holder.create_image(0, 0, anchor="nw", image=tiles[corner])
            holder.place(width=size, height=size, **spots[corner])
            tk.Misc.lift(holder)
            self._corners[corner] = holder

    def set_fill(self, fill):
        self.fill = fill
        self.shell.configure(bg=fill)
        self.body.configure(bg=fill)
        tiles = raster.corners(self, self.radius, self.fill, self.border, self._bg)
        for corner, holder in self._corners.items():
            holder.delete("all")
            holder.create_image(0, 0, anchor="nw", image=tiles[corner])


class SectionHeader(tk.Frame):
    def __init__(self, master, palette, title, subtitle=""):
        super().__init__(master, bg=_outer_bg(master))
        self.palette = palette
        left = tk.Frame(self, bg=self.cget("bg"))
        left.pack(side="left", fill="x", expand=True)
        self.title_label = tk.Label(left, text=title, bg=self.cget("bg"),
                                    fg=palette.text, font=font(13, "bold"),
                                    anchor="w")
        self.title_label.pack(fill="x")
        self.sub_label = None
        if subtitle:
            self.sub_label = tk.Label(left, text=subtitle, bg=self.cget("bg"),
                                      fg=palette.text_muted, font=font(9),
                                      anchor="w")
            self.sub_label.pack(fill="x", pady=(px(2), 0))
        self.action_area = tk.Frame(self, bg=self.cget("bg"))
        self.action_area.pack(side="right")

    def set_subtitle(self, text):
        if self.sub_label is not None:
            self.sub_label.configure(text=text)


class StatCard(RoundedCard):
    def __init__(self, master, palette, title, value="¥0.00", sub="", accent=None,
                 padding=16):
        super().__init__(master, palette, padding=padding, radius=13)
        self.accent = accent or palette.accent
        head = tk.Frame(self.body, bg=self.fill)
        head.pack(fill="x")
        dot = tk.Canvas(head, width=px(9), height=px(9), bg=self.fill, bd=0,
                        highlightthickness=0)
        dot.pack(side="left", padx=(0, px(7)), pady=(px(4), 0))
        dot.create_image(0, 0, anchor="nw",
                         image=raster.circle(dot, px(9), self.accent, self.fill))
        tk.Label(head, text=title, bg=self.fill, fg=palette.text_muted,
                 font=font(10), anchor="w").pack(side="left")
        self.value_label = tk.Label(self.body, text=value, bg=self.fill,
                                    fg=palette.text, font=font(22, "bold"),
                                    anchor="w")
        self.value_label.pack(fill="x", pady=(px(8), 0))
        self.sub_label = tk.Label(self.body, text=sub, bg=self.fill,
                                  fg=palette.text_muted, font=font(9), anchor="w")
        self.sub_label.pack(fill="x", pady=(px(3), 0))

    def set_value(self, value, sub=None):
        self.value_label.configure(text=value)
        if sub is not None:
            self.sub_label.configure(text=sub)


class EmptyState(tk.Frame):
    def __init__(self, master, palette, title="还没有记录", hint="", padding=20):
        super().__init__(master, bg=_outer_bg(master))
        art = tk.Canvas(self, width=px(96), height=px(76), bg=self.cget("bg"),
                        bd=0, highlightthickness=0)
        art.pack(pady=(px(padding), px(6)))
        diameter = px(58)
        art.create_image(px(19), px(9), anchor="nw",
                         image=raster.circle(art, diameter, palette.accent_soft,
                                             self.cget("bg")))
        art.create_image(px(48), px(37), anchor="center",
                         image=raster.icon(art, "list", px(26), palette.accent))
        tk.Label(self, text=title, bg=self.cget("bg"), fg=palette.text,
                 font=font(11, "bold")).pack()
        if hint:
            tk.Label(self, text=hint, bg=self.cget("bg"), fg=palette.text_muted,
                     font=font(9), wraplength=px(320), justify="center").pack(
                pady=(px(6), 0))


# --------------------------------------------------------------------------- button
class RoundButton(tk.Canvas):
    def __init__(self, master, palette, text, command=None, variant="primary",
                 width=None, height=34, radius=9, padx=16, size=10, bold=None,
                 bg=None):
        self.palette = palette
        self.variant = variant
        self._bg = bg or _outer_bg(master)
        self._spec = font(size, "bold" if bold else "normal")
        self._font = tkfont.Font(font=self._spec)
        self._radius = px(radius)
        self._padx = px(padx)
        self.command = command
        self.enabled = True
        self._hover = False
        self._pressed = False
        self._text = text or ""
        computed = max(px(74), self._font.measure(self._text) + 2 * self._padx)
        w = px(width) if width is not None else computed
        self._req_w = w
        super().__init__(master, width=w, height=px(height), bg=self._bg,
                         bd=0, highlightthickness=0, takefocus=1,
                         cursor="hand2")
        self._last = (0, 0)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key-space>", lambda e: self._activate())
        self.bind("<Return>", lambda e: self._activate())
        self.bind("<Configure>", self._on_configure)
        self.after_idle(self._draw)

    def _on_enter(self, _event=None):
        if not self.enabled:
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None):
        if not self.enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, event=None):
        if not self.enabled:
            return
        self._pressed = False
        inside = True
        if event is not None:
            inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._draw()
        if inside:
            self._activate()

    def _activate(self):
        if self.enabled and self.command is not None:
            self.command()

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _colors(self):
        p = self.palette
        if not self.enabled:
            return p.border, p.border, p.text_muted
        if self.variant == "primary":
            fill = p.accent
            if self._pressed:
                fill = darken(p.accent, 0.10)
            elif self._hover:
                fill = p.accent_hover
            return fill, fill, p.text_on_accent
        if self.variant == "danger":
            fill = p.danger
            if self._pressed:
                fill = darken(p.danger, 0.20)
            elif self._hover:
                fill = darken(p.danger, 0.10)
            return fill, fill, "#FFFFFF"
        if self.variant == "soft":
            fill = mix(p.accent_soft, p.accent, 0.10 if self._hover else 0.0)
            return fill, fill, p.accent
        if self.variant == "ghost":
            fill = p.surface_alt if self._hover else self._bg
            return fill, p.border, p.text
        return self._bg, self._bg, p.accent

    def _draw(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            width, height = self._req_w, int(self.cget("height"))
        self.delete("all")
        fill, border, fg = self._colors()
        if self.variant != "link":
            draw_round_box(self, 0, 0, width, height, self._radius, fill, border,
                           self._bg)
        self.create_text(width / 2.0, height / 2.0, text=self._text, fill=fg,
                         font=self._spec)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "arrow")
        self._draw()

    def set_text(self, text):
        self._text = text
        self._draw()


# --------------------------------------------------------------------------- link
class LinkLabel(tk.Label):
    """A lightweight text link.

    Canvas-based buttons are expensive to paint in long lists (the settings
    category list has two per row), so plain labels are used for text-only
    links while keeping the same accent colour and hover feedback.
    """

    def __init__(self, master, palette, text, command=None, size=9, bold=False,
                 bg=None, padx=None, **kwargs):
        self.palette = palette
        self.command = command
        self._enabled = True
        outer = bg or _outer_bg(master)
        super().__init__(master, text=text, bg=outer, fg=palette.accent,
                         font=font(size, "bold" if bold else "normal"),
                         bd=0, highlightthickness=0, cursor="hand2",
                         padx=px(2) if padx is None else padx,
                         pady=px(2), **kwargs)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _click(self, _event=None):
        if self._enabled and self.command is not None:
            self.command()

    def _enter(self, _event=None):
        if self._enabled:
            self.configure(fg=self.palette.accent_hover)

    def _leave(self, _event=None):
        self.configure(fg=self.palette.accent if self._enabled
                       else self.palette.text_muted)

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if self._enabled else "arrow",
                       fg=self.palette.accent if self._enabled
                       else self.palette.text_muted)


# --------------------------------------------------------------------------- chip
class Chip(tk.Canvas):
    def __init__(self, master, palette, text, value=None, color=None,
                 selected=False, command=None, height=30, size=9, bg=None):
        self.palette = palette
        self.value = value
        self.color = color
        self.selected = bool(selected)
        self.command = command
        self._bg = bg or _outer_bg(master)
        self._spec = font(size)
        self._bold = font(size, "bold")
        self._font = tkfont.Font(font=self._spec)
        self._h = px(height)
        self._dot = px(8)
        width = self._font.measure(text) + px(20)
        if color:
            width += px(16)
        self._text = text
        super().__init__(master, width=width, height=self._h, bg=self._bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._radius = self._h // 2
        self._hover = False
        self._last = (0, 0)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._on_configure)
        self.after_idle(self._draw)

    def _on_enter(self, _event=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._draw()

    def _click(self, _event=None):
        if self.command is not None:
            self.command(self.value)

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _draw(self):
        width = self.winfo_width() or int(self.cget("width"))
        height = self.winfo_height() or self._h
        if width <= 1:
            return
        self.delete("all")
        if self.selected:
            fill, border, fg = self.palette.accent_soft, self.palette.accent, self.palette.accent
            spec = self._bold
        else:
            fill = self.palette.surface_alt if self._hover else self.palette.surface
            border, fg, spec = self.palette.border, self.palette.text, self._spec
        draw_round_box(self, 0, 0, width, height, height // 2, fill, border, self._bg)
        left = px(12)
        if self.color:
            self.create_image(left, height / 2.0, anchor="w",
                              image=raster.circle(self, self._dot, self.color, fill))
            left += self._dot + px(7)
        self.create_text(left, height / 2.0, text=self._text, anchor="w", fill=fg,
                         font=spec)
        if self.selected:
            self._circle = (left, height)
        self.tag_lower("all")

    def set_selected(self, selected):
        self.selected = bool(selected)
        self._draw()


class FlowFrame(tk.Frame):
    def __init__(self, master, palette, hgap=8, vgap=8, bg=None):
        super().__init__(master, bg=bg or _outer_bg(master))
        self.palette = palette
        self.hgap = px(hgap)
        self.vgap = px(vgap)
        self.items = []
        self._last_width = -1
        self._last_height = -1
        self._job = None
        self.bind("<Configure>", self._on_configure)

    def add(self, widget):
        self.items.append(widget)
        widget.place(x=0, y=0)
        self._schedule()

    def clear(self):
        for widget in self.items:
            widget.destroy()
        self.items = []
        self._last_width = -1
        self._last_height = -1
        self.configure(height=1)

    def _on_configure(self, event=None):
        if event is not None and abs(event.width - self._last_width) < 1:
            return
        self._schedule()

    def _schedule(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.after_idle(self._reflow)

    def _reflow(self):
        self._job = None
        width = self.winfo_width()
        if width <= 1:
            return
        x = 0
        y = 0
        row_h = 0
        for widget in self.items:
            w = widget.winfo_reqwidth()
            h = widget.winfo_reqheight()
            if x > 0 and x + w > width:
                x = 0
                y += row_h + self.vgap
                row_h = 0
            widget.place(x=x, y=y)
            x += w + self.hgap
            row_h = max(row_h, h)
        height = y + row_h
        if height != self._last_height or width != self._last_width:
            self._last_width = width
            self._last_height = height
            self.configure(height=max(1, height))


class ChipGroup(FlowFrame):
    def __init__(self, master, palette, options=None, value=None, command=None,
                 multi=False, hgap=8, vgap=8, bg=None):
        super().__init__(master, palette, hgap=hgap, vgap=vgap, bg=bg)
        self.command = command
        self.multi = multi
        self.chips = {}
        self.selected = set()
        if multi:
            if value:
                self.selected = set(value)
        elif value is not None:
            self.selected = {value}
        self.set_options(options or {})

    def set_options(self, options):
        self.clear()
        self.chips = {}
        entries = []
        if isinstance(options, dict):
            for value, spec in options.items():
                if isinstance(spec, dict):
                    entries.append((value, spec))
                else:
                    entries.append((value, {"label": spec}))
        else:
            for item in options or []:
                if isinstance(item, dict):
                    entries.append((item.get("value"), item))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    entries.append((item[0], {"label": item[1]}))
                else:
                    entries.append((item, {"label": item}))
        for value, spec in entries:
            label = spec.get("label", value)
            color = spec.get("color")
            chip = Chip(self, self.palette, str(label), value=value, color=color,
                        selected=value in self.selected, command=self._click,
                        bg=self.cget("bg"))
            self.chips[value] = chip
            self.add(chip)
        if not self.multi and not self.selected and entries:
            first = entries[0][0]
            self.selected = {first}
            if first in self.chips:
                self.chips[first].set_selected(True)

    def _click(self, value):
        if self.multi:
            if value in self.selected:
                self.selected.discard(value)
            else:
                self.selected.add(value)
            self.chips[value].set_selected(value in self.selected)
        else:
            self.selected = {value}
            for key, chip in self.chips.items():
                chip.set_selected(key == value)
        if self.command is not None:
            self.command(self.get())

    def get(self):
        if self.multi:
            return [value for value in self.chips if value in self.selected]
        return next(iter(self.selected), None)

    def set(self, value):
        if self.multi:
            self.selected = set(value or [])
        else:
            self.selected = set() if value is None else {value}
        for key, chip in self.chips.items():
            chip.set_selected(key in self.selected)


# --------------------------------------------------------------------------- segmented
class Segmented(tk.Canvas):
    def __init__(self, master, palette, options, value=None, command=None,
                 height=32, radius=8, pad=3, size=9, bg=None):
        self.palette = palette
        self.command = command
        self._items = []
        for option in options:
            if isinstance(option, (tuple, list)) and len(option) >= 2:
                self._items.append((option[0], str(option[1])))
            else:
                self._items.append((option, str(option)))
        font_obj = tkfont.Font(font=font(size))
        seg = max(max([font_obj.measure(label) for _, label in self._items] or [0]) + px(30), px(58))
        self._seg = seg
        self._pad = px(pad)
        self._radius = px(radius)
        self._size = size
        self._spec = font(size)
        self._bold = font(size, "bold")
        self._bg = bg or _outer_bg(master)
        width = seg * max(1, len(self._items)) + 2 * self._pad
        super().__init__(master, width=width, height=px(height), bg=self._bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._h = px(height)
        self.value = value if value is not None else (
            self._items[0][0] if self._items else None)
        self._last = (0, 0)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._on_configure)
        self.after_idle(self._draw)

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _index(self):
        for index, (value, _label) in enumerate(self._items):
            if value == self.value:
                return index
        return -1

    def _draw(self):
        width = self.winfo_width() or (self._seg * len(self._items) + 2 * self._pad)
        height = self.winfo_height() or self._h
        if width <= 1:
            return
        self.delete("all")
        draw_round_box(self, 0, 0, width, height, self._radius,
                       self.palette.surface_alt, self.palette.border, self._bg)
        current = self._index()
        inner = self._pad
        for index, (value, label) in enumerate(self._items):
            x0 = self._pad + index * self._seg
            x1 = x0 + self._seg
            if index == current:
                draw_round_box(self, x0, inner, x1, height - inner,
                               max(2, self._radius - inner), self.palette.accent,
                               self.palette.accent, self.palette.surface_alt)
                fill = self.palette.text_on_accent
                spec = self._bold
            else:
                fill = self.palette.text_muted
                spec = self._spec
            self.create_text((x0 + x1) / 2.0, height / 2.0, text=label, fill=fill,
                             font=spec)

    def _click(self, event):
        if not self._items:
            return
        index = int((event.x - self._pad) // self._seg)
        index = max(0, min(len(self._items) - 1, index))
        value = self._items[index][0]
        if value != self.value:
            self.value = value
            self._draw()
            if self.command is not None:
                self.command(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._draw()


# --------------------------------------------------------------------------- text fields
class EntryField(tk.Frame):
    def __init__(self, master, palette, textvariable=None, width=18,
                 justify="left", size=11, bg=None):
        outer = bg or _outer_bg(master)
        super().__init__(master, bg=outer, bd=0, highlightthickness=0)
        self.palette = palette
        self._bg = outer
        self._focused = False
        self._last = (0, 0)
        self.canvas = tk.Canvas(self, width=1, height=1, bg=outer, bd=0,
                                highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.entry = tk.Entry(self, textvariable=textvariable, width=width,
                              justify=justify, bd=0, relief="flat",
                              bg=palette.surface, fg=palette.text,
                              insertbackground=palette.accent,
                              font=font(size), highlightthickness=0)
        self.entry.grid(row=0, column=0, sticky="nsew", padx=px(11), pady=px(7))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.bind("<Configure>", self._on_configure)
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.after_idle(self._draw)

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _draw(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        border = self.palette.accent if self._focused else self.palette.border
        draw_round_box(self.canvas, 0, 0, width, height, px(9),
                       self.palette.surface, border, self._bg)

    def _focus_in(self, _event=None):
        self._focused = True
        self._draw()

    def _focus_out(self, _event=None):
        self._focused = False
        self._draw()

    def get(self):
        return self.entry.get()

    def set(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def focus(self):
        self.entry.focus_set()

    def bind(self, sequence=None, func=None, add=None):
        if sequence is None:
            return super().bind(sequence, func, add)
        return self.entry.bind(sequence, func, add)


class FieldLabel(tk.Label):
    def __init__(self, master, palette, text):
        super().__init__(master, text=text, bg=_outer_bg(master),
                         fg=palette.text_muted, font=font(9), anchor="w")


# --------------------------------------------------------------------------- dropdown
class Dropdown(tk.Frame):
    def __init__(self, master, palette, options, value=None, command=None,
                 width=150, height=34, size=10):
        outer = _outer_bg(master)
        super().__init__(master, bg=outer, width=px(width), height=px(height),
                         bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.palette = palette
        self.command = command
        self._bg = outer
        self._box_w = px(width)
        self._box_h = px(height)
        self._size = size
        self._spec = font(size)
        self._popup = None
        self._hover = False
        self._last = (0, 0)
        self.canvas = tk.Canvas(self, bg=outer, bd=0, highlightthickness=0,
                                cursor="hand2")
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.canvas.bind("<Button-1>", self._open)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", self._on_configure)
        self.set_options(options, value)

    def set_options(self, options, value=None):
        entries = []
        if isinstance(options, dict):
            for key, spec in options.items():
                entries.append((key, spec if isinstance(spec, dict)
                                else {"label": spec}))
        else:
            for item in options or []:
                if isinstance(item, dict):
                    entries.append((item.get("value"), item))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    entries.append((item[0], {"label": item[1]}))
                else:
                    entries.append((item, {"label": item}))
        self.labels = {}
        for key, spec in entries:
            self.labels[key] = spec.get("label", key)
        self.values = [key for key, _ in entries]
        if value is not None:
            self.value = value
        elif self.values:
            self.value = self.values[0]
        else:
            self.value = None
        self._draw()

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _on_enter(self, _event=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._draw()

    def _draw(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            width, height = self._box_w, self._box_h
        self.canvas.delete("all")
        fill = self.palette.surface_alt if self._hover else self.palette.surface
        border = self.palette.accent if self._popup is not None else self.palette.border
        draw_round_box(self.canvas, 0, 0, width, height, px(9), fill, border, self._bg)
        text = self.labels.get(self.value, "")
        self.canvas.create_text(px(12), height / 2.0, text=text, anchor="w",
                                fill=self.palette.text, font=self._spec)
        self.canvas.create_image(width - px(15), height / 2.0, anchor="center",
                                 image=raster.icon(self.canvas, "chevron", px(11),
                                                   self.palette.text_muted))

    def _open(self, _event=None):
        if self._popup is not None or not self.values:
            return
        rows = min(8, len(self.values))
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(bg=self.palette.border)
        row_h = px(32)
        shell = tk.Frame(popup, bg=self.palette.surface)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        listbox = tk.Listbox(shell, bd=0, highlightthickness=0, activestyle="none",
                             bg=self.palette.surface, fg=self.palette.text,
                             selectbackground=self.palette.accent_soft,
                             selectforeground=self.palette.accent,
                             font=font(self._size), exportselection=False,
                             width=1)
        for value in self.values:
            listbox.insert("end", self.labels.get(value, value))
        listbox.configure(height=rows)
        listbox.pack(padx=px(8), pady=px(8), fill="both", expand=True)
        self.update_idletasks()
        width = max(self.winfo_width(), px(120))
        popup_h = rows * row_h + px(18)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + px(4)
        popup.geometry("%dx%d+%d+%d" % (width, popup_h, x, y))
        popup.update_idletasks()
        if y + popup_h > popup.winfo_screenheight() - px(8):
            y = self.winfo_rooty() - popup_h - px(4)
            popup.geometry("%dx%d+%d+%d" % (width, popup_h, x, y))
        popup.deiconify()
        popup.lift()
        popup.attributes("-topmost", True)
        index = self.values.index(self.value) if self.value in self.values else 0
        listbox.selection_set(index)
        listbox.see(index)
        try:
            listbox.focus_set()
        except tk.TclError:
            pass
        self._popup = popup
        self._listbox = listbox
        self._draw()
        listbox.bind("<<ListboxSelect>>", self._choose)
        listbox.bind("<Return>", self._choose)
        listbox.bind("<Escape>", lambda e: self._close())
        popup.bind("<Button-1>", self._outside)
        popup.bind("<FocusOut>", lambda e: self.after(80, self._maybe_close))
        popup.focus_set()

    def _outside(self, event):
        if event.widget is not self._listbox:
            try:
                if not (0 <= event.x <= self._listbox.winfo_width() and
                        0 <= event.y <= self._listbox.winfo_height()):
                    self._close()
            except tk.TclError:
                self._close()

    def _maybe_close(self):
        try:
            if self._popup is not None and self.focus_get() not in (self._listbox, self._popup):
                self._close()
        except Exception:
            self._close()

    def _choose(self, _event=None):
        if self._popup is None:
            return
        selection = self._listbox.curselection()
        if not selection:
            return
        self.value = self.values[selection[0]]
        self._close()
        if self.command is not None:
            self.command(self.value)

    def _close(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._listbox = None
        self._draw()

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._draw()


# --------------------------------------------------------------------------- calendar
class _DayCell(tk.Canvas):
    def __init__(self, master, palette, day, selected=False, today=False,
                 on_pick=None, width=32, height=30):
        super().__init__(master, width=px(width), height=px(height),
                         bg=palette.surface, bd=0, highlightthickness=0,
                         cursor="hand2")
        self.palette = palette
        self.day = day
        self.selected = selected
        self.today = today
        self.on_pick = on_pick
        self._hover = False
        self._last = (0, 0)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._pick)
        self.bind("<Configure>", self._configure)
        self.after_idle(self._draw)

    def _enter(self, _event=None):
        self._hover = True
        self._draw()

    def _leave(self, _event=None):
        self._hover = False
        self._draw()

    def _pick(self, _event=None):
        if self.on_pick is not None:
            self.on_pick(self.day)

    def _configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _draw(self):
        width = self.winfo_width() or px(32)
        height = self.winfo_height() or px(30)
        if width <= 1:
            return
        self.delete("all")
        p = self.palette
        if self.selected:
            fill, fg, border = p.accent, p.text_on_accent, p.accent
        elif self._hover:
            fill, fg, border = p.accent_soft, p.accent, p.accent_soft
        elif self.today:
            fill, fg, border = p.surface, p.accent, p.accent
        else:
            fill, fg, border = p.surface, p.text, p.surface
        draw_round_box(self, 0, 0, width, height, px(7), fill, border, p.surface)
        self.create_text(width / 2.0, height / 2.0, text=str(self.day), fill=fg,
                         font=font(9, "bold" if self.selected or self.today else "normal"))


class CalendarPopup(tk.Toplevel):
    def __init__(self, master, palette, initial=None, on_pick=None, anchor=None):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=palette.border)
        self.palette = palette
        self.on_pick = on_pick
        self._initial = initial
        if initial is None:
            initial = _dt.date.today()
        self.view = _dt.date(initial.year, initial.month, 1)
        shell = tk.Frame(self, bg=palette.border)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        self.body = tk.Frame(shell, bg=palette.surface, padx=px(12), pady=px(10))
        self.body.pack(fill="both", expand=True)
        header = tk.Frame(self.body, bg=palette.surface)
        header.pack(fill="x")
        prev = RoundButton(header, palette, "‹", variant="ghost", width=28,
                           height=28, padx=0, size=12,
                           command=lambda: self._shift(-1), bg=palette.surface)
        prev.pack(side="left")
        self.title_label = tk.Label(header, text="", bg=palette.surface,
                                    fg=palette.text, font=font(10, "bold"))
        self.title_label.pack(side="left", expand=True)
        nxt = RoundButton(header, palette, "›", variant="ghost", width=28,
                          height=28, padx=0, size=12,
                          command=lambda: self._shift(1), bg=palette.surface)
        nxt.pack(side="right")
        week = tk.Frame(self.body, bg=palette.surface)
        week.pack(fill="x", pady=(px(6), px(2)))
        for index, name in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            tk.Label(week, text=name, bg=palette.surface, fg=palette.text_muted,
                     font=font(8), width=4).grid(row=0, column=index, padx=1)
        self.grid_frame = tk.Frame(self.body, bg=palette.surface)
        self.grid_frame.pack(fill="both", expand=True)
        footer = tk.Frame(self.body, bg=palette.surface)
        footer.pack(fill="x", pady=(px(8), 0))
        RoundButton(footer, palette, "今天", variant="soft", height=28, size=9,
                    padx=12, command=self._today, bg=palette.surface).pack(side="left")
        RoundButton(footer, palette, "取消", variant="ghost", height=28, size=9,
                    padx=12, command=self._close, bg=palette.surface).pack(side="right")
        self._render()
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<FocusOut>", lambda e: self.after(90, self._maybe_close))
        self._anchor = anchor
        self.after(10, self._place)

    def _place(self):
        self.update_idletasks()
        if self._anchor is None:
            x = self.master.winfo_rootx()
            y = self.master.winfo_rooty() + self.master.winfo_height() + px(4)
        else:
            x, y = self._anchor
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        if x + width > screen_w - px(8):
            x = screen_w - width - px(8)
        if y + height > screen_h - px(8):
            y = y - height - px(12)
        self.geometry("%dx%d+%d+%d" % (width, height, max(0, x), max(0, y)))
        self.deiconify()
        self.lift()
        self.focus_force()

    def _render(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.title_label.configure(text="%d年%d月" % (self.view.year, self.view.month))
        first = _dt.date(self.view.year, self.view.month, 1)
        pad = (first.weekday()) % 7
        days = _calendar_month_days(self.view.year, self.view.month)
        today = _dt.date.today()
        for index in range(pad + days):
            row, column = divmod(index, 7)
            if index < pad:
                continue
            day = index - pad + 1
            date = _dt.date(self.view.year, self.view.month, day)
            cell = _DayCell(self.grid_frame, self.palette, day,
                            selected=date == self._initial,
                            today=date == today, on_pick=self._pick)
            cell.grid(row=row, column=column, padx=1, pady=1)

    def _shift(self, delta):
        month = self.view.month + delta
        year = self.view.year
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        self.view = _dt.date(year, month, 1)
        self._render()

    def _today(self):
        self._pick(_dt.date.today())

    def _pick(self, date):
        if self.on_pick is not None:
            self.on_pick(date)
        self._close()

    def _maybe_close(self):
        try:
            focused = self.focus_get()
        except Exception:
            focused = None
        if focused is None or not (focused is self or is_descendant(focused, self)):
            self._close()

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def _calendar_month_days(year, month):
    if month == 12:
        nxt = _dt.date(year + 1, 1, 1)
    else:
        nxt = _dt.date(year, month + 1, 1)
    return (nxt - _dt.date(year, month, 1)).days


class DateEntry(tk.Frame):
    def __init__(self, master, palette, value=None, width=120, height=34,
                 command=None):
        outer = _outer_bg(master)
        super().__init__(master, bg=outer, width=px(width), height=px(height),
                         bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.palette = palette
        self.command = command
        self._bg = outer
        self._focused = False
        self._last = (0, 0)
        self.var = tk.StringVar(value=value or _dt.date.today().strftime("%Y-%m-%d"))
        self.canvas = tk.Canvas(self, width=1, height=1, bg=outer, bd=0,
                                highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.entry = tk.Entry(self, textvariable=self.var, bd=0, relief="flat",
                              bg=palette.surface, fg=palette.text,
                              insertbackground=palette.accent, font=font(10),
                              highlightthickness=0)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(px(10), px(32)), pady=px(1))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_propagate(False)
        self.button = tk.Canvas(self, width=px(24), height=px(24),
                                bg=palette.surface, bd=0, highlightthickness=0,
                                cursor="hand2")
        self.button.place(relx=1.0, x=-px(6), rely=0.5, anchor="e",
                          width=px(24), height=px(24))
        self.button.create_image(px(12), px(12), anchor="center",
                                 image=raster.icon(self.button, "calendar", px(16),
                                                   palette.text_muted))
        self.button.bind("<Button-1>", lambda e: self.open())
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.bind("<Configure>", self._on_configure)
        self.after_idle(self._draw)

    def _on_configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _draw(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            return
        border = self.palette.accent if self._focused else self.palette.border
        draw_round_box(self.canvas, 0, 0, width, height, px(9),
                       self.palette.surface, border, self._bg)

    def _focus_in(self, _event=None):
        self._focused = True
        self._draw()

    def _focus_out(self, _event=None):
        self._focused = False
        self._draw()

    def _current(self):
        text = self.var.get().strip()
        try:
            return _dt.datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return _dt.date.today()

    def open(self):
        CalendarPopup(self, self.palette, initial=self._current(),
                      on_pick=self._picked,
                      anchor=(self.winfo_rootx(),
                              self.winfo_rooty() + self.winfo_height() + px(4)))

    def _picked(self, date):
        self.var.set(date.strftime("%Y-%m-%d"))
        if self.command is not None:
            self.command(date.strftime("%Y-%m-%d"))

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value or "")


# --------------------------------------------------------------------------- scroll
class ScrollFrame(tk.Frame):
    def __init__(self, master, palette, bg=None):
        outer = bg or _outer_bg(master)
        super().__init__(master, bg=outer, bd=0, highlightthickness=0)
        self.palette = palette
        self._bg = outer
        self._ledger_scroll = True
        self.canvas = tk.Canvas(self, bg=outer, bd=0, highlightthickness=0,
                                yscrollincrement=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       command=self.canvas.yview,
                                       style="Ledger.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=outer, bd=0, highlightthickness=0)
        self._window = self.canvas.create_window((0, 0), window=self.body,
                                                 anchor="nw")
        self._bar_visible = False
        self._region_job = None
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.body.bind("<MouseWheel>", self._wheel)

    def _on_scroll(self, first, last):
        self.canvas.yview("moveto", first)
        needs = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needs and not self._bar_visible:
            self.scrollbar.pack(side="right", fill="y")
            self._bar_visible = True
        elif not needs and self._bar_visible:
            self.scrollbar.pack_forget()
            self._bar_visible = False

    def _on_body(self, _event=None):
        if self._region_job is not None:
            return
        self._region_job = self.after_idle(self._update_region)

    def _update_region(self):
        self._region_job = None
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _wheel(self, event):
        self.canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"

    def bind_tree(self):
        self._on_body()

    def scroll_top(self):
        self.canvas.yview_moveto(0.0)


# --------------------------------------------------------------------------- toast
class Toast:
    def __init__(self, root, palette):
        self.root = root
        self.palette = palette
        self.window = None
        self._tween_in = None
        self._timer = None
        self._hide = None

    def show(self, message, kind="info", duration=2200):
        self._destroy()
        p = self.palette
        background = {"info": p.text, "success": p.success, "danger": p.danger}.get(
            kind, p.text)
        outer = p.bg
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.configure(bg=outer)
        window.attributes("-topmost", True)
        round_window(window)
        spec = font(10)
        font_obj = tkfont.Font(font=spec)
        width = font_obj.measure(message) + px(40)
        height = px(40)
        canvas = tk.Canvas(window, width=width, height=height, bg=outer,
                           bd=0, highlightthickness=0)
        canvas.pack()
        draw_round_box(canvas, 0, 0, width, height, height // 2, background,
                       background, outer)
        canvas.create_text(width / 2.0, height / 2.0, text=message, fill="#FFFFFF",
                           font=spec)
        self.window = window
        self.canvas = canvas
        self._place()
        self._fade_in()
        self._timer = self.root.after(duration, self._fade_out)

    def _place(self):
        if self.window is None:
            return
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + self.root.winfo_height() - height - px(36)
        self._target_x = x
        self._target_y = y
        self.window.geometry("+%d+%d" % (x, y + px(14)))

    def _fade_in(self):
        try:
            self.window.attributes("-alpha", 0.0)
        except tk.TclError:
            return
        offset = px(14)

        def frame(t):
            try:
                self.window.attributes("-alpha", min(1.0, 0.35 + t * 0.65))
                self.window.geometry("+%d+%d" % (
                    self._target_x, int(self._target_y + offset * (1 - t))))
            except tk.TclError:
                pass

        self._tween_in = Tween(self.root, 150, frame, interval_ms=16)
        self._tween_in.start()

    def _fade_out(self):
        if self.window is None:
            return
        try:
            self.window.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

        def frame(t):
            try:
                self.window.attributes("-alpha", max(0.0, 1.0 - t))
            except tk.TclError:
                pass

        def done():
            self._destroy()

        self._hide = Tween(self.root, 160, frame, interval_ms=16, on_done=done)
        self._hide.start()

    def _destroy(self):
        for tween in (self._tween_in, self._hide):
            if tween is not None:
                tween.cancel()
        self._tween_in = None
        self._hide = None
        if self._timer is not None:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None


# --------------------------------------------------------------------------- confirm
def confirm(parent, palette, title, message, ok_text="确定", cancel_text="取消",
            danger=False):
    window = tk.Toplevel(parent)
    window.title(title)
    window.configure(bg=palette.bg)
    window.resizable(False, False)
    window.transient(parent)
    body = tk.Frame(window, bg=palette.bg, padx=px(26), pady=px(22))
    body.pack(fill="both", expand=True)
    tk.Label(body, text=title, bg=palette.bg, fg=palette.text,
             font=font(12, "bold"), anchor="w").pack(fill="x")
    tk.Label(body, text=message, bg=palette.bg, fg=palette.text_muted,
             font=font(10), anchor="w", justify="left",
             wraplength=px(340)).pack(fill="x", pady=(px(10), px(18)))
    row = tk.Frame(body, bg=palette.bg)
    row.pack(fill="x")
    result = {"value": False}

    def close(value):
        result["value"] = value
        window.destroy()

    RoundButton(row, palette, cancel_text, variant="ghost", bg=palette.bg,
                command=lambda: close(False)).pack(side="right")
    RoundButton(row, palette, ok_text, variant="danger" if danger else "primary",
                bg=palette.bg, command=lambda: close(True)).pack(
        side="right", padx=(0, px(8)))
    window.bind("<Escape>", lambda e: close(False))
    window.update_idletasks()
    width = max(px(400), window.winfo_reqwidth())
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + max(px(80), (parent.winfo_height() - window.winfo_reqheight()) // 3)
    window.geometry("%dx%d+%d+%d" % (width, window.winfo_reqheight(), max(0, x), max(0, y)))
    round_window(window)
    window.grab_set()
    window.focus_force()
    parent.wait_window(window)
    return result["value"]
