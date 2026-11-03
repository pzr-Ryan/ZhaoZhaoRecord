"""Reusable Tk widgets drawn with Canvas for a clean, dependency-free look."""
from __future__ import annotations

import calendar
import datetime as dt
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .theme import FONT_FAMILY, font, px


# --------------------------------------------------------------------------- helpers
def rounded_points(x1, y1, x2, y2, radius):
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    if radius <= 0:
        return [x1, y1, x2, y1, x2, y2, x1, y2]
    return [
        x1 + radius, y1,
        x2 - radius, y1, x2, y1,
        x2, y1 + radius,
        x2, y2 - radius, x2, y2,
        x2 - radius, y2,
        x1 + radius, y2, x1, y2,
        x1, y2 - radius,
        x1, y1 + radius, x1, y1,
    ]


def draw_round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    kwargs.setdefault("smooth", True)
    kwargs.setdefault("splinesteps", 24)
    return canvas.create_polygon(rounded_points(x1, y1, x2, y2, radius), **kwargs)


def is_descendant(widget, ancestor):
    while widget is not None:
        if widget == ancestor:
            return True
        try:
            widget = widget.master
        except Exception:
            return False
    return False


def bind_wheel_tree(widget, canvas):
    def handler(event):
        if not canvas.winfo_exists():
            return "break"
        delta = int(-event.delta / 120) if event.delta else 0
        if delta:
            canvas.yview_scroll(delta, "units")
        return "break"

    def walk(node):
        node.bind("<MouseWheel>", handler)
        for child in node.winfo_children():
            walk(child)

    walk(widget)


# --------------------------------------------------------------------------- surfaces
class RoundedCard(tk.Frame):
    """A card with a real rounded background and a padded content body."""

    def __init__(self, master, palette, padding=18, radius=14, bg=None, fill=None, **kwargs):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg, bd=0, highlightthickness=0, **kwargs)
        self.palette = palette
        self.padding = px(padding)
        self.radius = px(radius)
        self._bg = bg
        self.fill = fill or palette.surface
        self.border = palette.border
        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=self.fill)
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)
        self._masks = {}
        for corner in ("nw", "ne", "sw", "se"):
            mask = tk.Canvas(self, width=self.radius, height=self.radius, bg=bg,
                             bd=0, highlightthickness=0)
            self._masks[corner] = mask
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event):
        self._redraw(event.width, event.height)

    def _redraw(self, width, height):
        if width < 8 or height < 8:
            return
        radius = max(0, min(self.radius, width // 2, height // 2))
        self.canvas.delete("all")
        draw_round_rect(
            self.canvas, 0.5, 0.5, width - 1, height - 1, radius,
            fill=self.fill, outline=self.border, width=1,
        )
        specs = {
            "nw": (0, 0, 0, 0, 2 * radius, 2 * radius, 90),
            "ne": (width - radius, 0, -radius, 0, radius, 2 * radius, 0),
            "sw": (0, height - radius, 0, -radius, 2 * radius, radius, 180),
            "se": (width - radius, height - radius, -radius, -radius, radius, radius, 270),
        }
        current = self.cget("bg")
        for corner, (x, y, bx1, by1, bx2, by2, start) in specs.items():
            mask = self._masks[corner]
            if not mask.winfo_exists():
                continue
            mask.configure(bg=current, width=radius, height=radius)
            mask.place(x=x, y=y, width=radius, height=radius)
            mask.delete("all")
            if radius <= 0:
                continue
            bbox = (bx1, by1, bx2, by2)
            mask.create_arc(*bbox, start=start, extent=90, style="pieslice",
                            fill=self.fill, outline="")
            mask.create_arc(*bbox, start=start, extent=90, style="arc",
                            outline=self.border, width=1)
            self.tk.call("raise", mask._w)
        self.body.configure(bg=self.fill)
        self.body.lift()
        for mask in self._masks.values():
            self.tk.call("raise", mask._w)

    def set_fill(self, fill):
        self.fill = fill
        self._redraw(self.winfo_width(), self.winfo_height())


class SectionHeader(tk.Frame):
    def __init__(self, master, palette, title, subtitle=""):
        super().__init__(master, bg=master.cget("bg"))
        self.action_area = tk.Frame(self, bg=self.cget("bg"))
        self.action_area.pack(side="right", anchor="e")
        left = tk.Frame(self, bg=self.cget("bg"))
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=title, bg=self.cget("bg"), fg=palette.text,
                 font=font(13, "bold"), anchor="w").pack(anchor="w")
        if subtitle:
            tk.Label(left, text=subtitle, bg=self.cget("bg"), fg=palette.text_muted,
                     font=font(9), anchor="w").pack(anchor="w", pady=(2, 0))


class StatCard(RoundedCard):
    def __init__(self, master, palette, title, value="¥0.00", sub="", accent=None, padding=16):
        super().__init__(master, palette, padding=padding, radius=13)
        bg = self.fill
        self.accent = accent or palette.accent
        top = tk.Frame(self.body, bg=bg)
        top.pack(fill="x")
        dot_size = px(9)
        self.dot = tk.Canvas(top, width=dot_size, height=dot_size, bg=bg, bd=0,
                             highlightthickness=0)
        self.dot.pack(side="left", padx=(0, px(7)))
        self.dot.create_oval(1, 1, dot_size - 1, dot_size - 1,
                             fill=self.accent, outline="")
        tk.Label(top, text=title, bg=bg, fg=palette.text_muted, font=font(10),
                 anchor="w").pack(side="left")
        self.value_label = tk.Label(self.body, text=value, bg=bg, fg=palette.text,
                                    font=font(22, "bold"), anchor="w")
        self.value_label.pack(anchor="w", pady=(px(8), 0))
        self.sub_label = tk.Label(self.body, text=sub, bg=bg, fg=palette.text_muted,
                                  font=font(9), anchor="w")
        self.sub_label.pack(anchor="w", pady=(px(4), 0))

    def set_value(self, value, sub=None):
        self.value_label.configure(text=value)
        if sub is not None:
            self.sub_label.configure(text=sub)


class EmptyState(tk.Frame):
    def __init__(self, master, palette, title="还没有记录", hint="", padding=20):
        bg = master.cget("bg")
        super().__init__(master, bg=bg)
        s = px
        art = tk.Canvas(self, width=s(96), height=s(76), bg=bg, bd=0,
                        highlightthickness=0)
        art.pack(pady=(s(padding), s(6)))
        art.create_oval(s(10), s(8), s(86), s(68), fill=palette.surface_alt,
                        outline=palette.border)
        art.create_rectangle(s(30), s(24), s(66), s(56), fill=palette.surface,
                             outline=palette.text_muted, width=1)
        for y in (s(32), s(39), s(46)):
            art.create_line(s(36), y, s(60), y, fill=palette.border, width=2)
        tk.Label(self, text=title, bg=bg, fg=palette.text, font=font(11, "bold")).pack()
        if hint:
            tk.Label(self, text=hint, bg=bg, fg=palette.text_muted, font=font(9),
                     justify="center", wraplength=px(320)).pack(
                         pady=(px(4), px(padding)))


# --------------------------------------------------------------------------- buttons
class RoundButton(tk.Canvas):
    def __init__(self, master, palette, text, command=None, variant="primary",
                 width=None, height=34, radius=9, padx=16, size=10, bold=None,
                 bg=None):
        self.palette = palette
        self.variant = variant
        self.command = command
        self.enabled = True
        self._hover = False
        self._pressed = False
        self._radius = px(radius)
        bg = bg or master.cget("bg")
        self._font = tkfont.Font(family=FONT_FAMILY, size=size,
                                 weight="bold" if (bold if bold is not None else
                                                   variant in ("primary", "danger")) else "normal")
        text_width = self._font.measure(text)
        self._text = text
        self._padx = padx
        width = px(width) if width else max(px(74), text_width + 2 * px(padx))
        super().__init__(master, width=width, height=px(height), bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key-space>", lambda e: self._activate())
        self.bind("<Return>", lambda e: self._activate())
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _colors(self):
        p = self.palette
        if not self.enabled:
            return p.border, p.border, p.text_muted, None
        if self.variant == "primary":
            fill = p.accent_hover if (self._hover or self._pressed) else p.accent
            return fill, fill, p.text_on_accent, None
        if self.variant == "danger":
            from .theme import darken
            fill = darken(p.danger, 0.12) if (self._hover or self._pressed) else p.danger
            return fill, fill, "#FFFFFF", None
        if self.variant == "soft":
            from .theme import mix
            fill = mix(p.accent_soft, p.accent, 0.10 if self._hover else 0.0)
            return fill, fill, p.accent, None
        if self.variant == "ghost":
            fill = p.bg if (self._hover or self._pressed) else p.surface
            return fill, p.border, p.text, None
        return None, None, p.accent, None  # link

    def _draw(self):
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        fill, outline, fg, _ = self._colors()
        if self.variant == "link":
            self.create_text(width / 2, height / 2, text=self._text, fill=fg,
                             font=self._font)
        else:
            draw_round_rect(self, 0.5, 0.5, width - 0.5, height - 0.5, self._radius,
                            fill=fill, outline=outline or fill, width=1)
            self.create_text(width / 2, height / 2, text=self._text, fill=fg,
                             font=self._font)
        if self.enabled:
            self.configure(cursor="hand2")
        else:
            self.configure(cursor="arrow")

    def _on_enter(self, _event):
        self._hover = True
        self._draw()

    def _on_leave(self, _event):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event):
        if self.enabled:
            self._pressed = True
            self.focus_set()
            self._draw()

    def _on_release(self, event):
        if not self.enabled:
            return
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._pressed = False
        self._draw()
        if inside:
            self._activate()

    def _activate(self):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self._draw()

    def set_text(self, text):
        self._text = text
        self._draw()


# --------------------------------------------------------------------------- chips
class Chip(tk.Canvas):
    def __init__(self, master, palette, text, value=None, color=None,
                 selected=False, command=None, height=30, size=9, bg=None):
        self.palette = palette
        self.value = value if value is not None else text
        self.color = color
        self.text = text
        self.selected = selected
        self.command = command
        self._font = tkfont.Font(family=FONT_FAMILY, size=size,
                                 weight="bold" if selected else "normal")
        dot_space = px(16) if color else 0
        width = self._font.measure(text) + px(26) + dot_space
        bg = bg or master.cget("bg")
        super().__init__(master, width=width, height=px(height), bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._bg = bg
        self._height = px(height)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", self._on_configure)
        self._draw()

    def _on_configure(self, event):
        self._draw(event.width)

    def _draw(self, width=None):
        self.delete("all")
        p = self.palette
        w = width or self.winfo_width()
        if w <= 1:
            w = int(self.cget("width"))
        w = max(1, w)
        h = self._height
        fill = p.accent_soft if self.selected else p.surface
        outline = p.accent if self.selected else p.border
        draw_round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, h // 2,
                        fill=fill, outline=outline, width=1)
        fg = p.accent if self.selected else p.text
        self._font.configure(weight="bold" if self.selected else "normal")
        x = px(12)
        if self.color:
            dot = px(4)
            self.create_oval(x, h / 2 - dot, x + 2 * dot, h / 2 + dot,
                             fill=self.color, outline=self.color)
            x += px(14)
        self.create_text(x, h / 2, text=self.text, anchor="w", fill=fg,
                         font=self._font)

    def set_selected(self, selected):
        self.selected = bool(selected)
        self._draw()

    def _click(self, _event):
        if self.command:
            self.command(self.value)


class FlowFrame(tk.Frame):
    def __init__(self, master, palette, hgap=8, vgap=8, bg=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.palette = palette
        self.hgap = px(hgap)
        self.vgap = px(vgap)
        self.items = []
        self._last_width = 0
        self._last_height = 0
        self.bind("<Configure>", self._on_configure)

    def add(self, widget):
        widget.place(x=0, y=0)
        self.items.append(widget)
        self._reflow()
        return widget

    def clear(self):
        for widget in self.items:
            widget.destroy()
        self.items = []
        self.configure(height=1)
        self._last_height = 1

    def _on_configure(self, event):
        if abs(event.width - self._last_width) > 1:
            self._last_width = event.width
            self._reflow()

    def _reflow(self):
        width = self._last_width or self.winfo_width()
        if width <= 1:
            return
        x = y = row_height = 0
        for widget in self.items:
            ww = widget.winfo_reqwidth()
            hh = widget.winfo_reqheight()
            if x and x + ww > width:
                x = 0
                y += row_height + self.vgap
                row_height = 0
            widget.place(x=x, y=y, width=ww, height=hh)
            x += ww + self.hgap
            row_height = max(row_height, hh)
        height = y + row_height
        if height != self._last_height:
            self._last_height = height
            self.configure(height=max(1, height))


class ChipGroup(FlowFrame):
    def __init__(self, master, palette, options, value=None, command=None,
                 multi=False, hgap=8, vgap=8, bg=None):
        super().__init__(master, palette, hgap=hgap, vgap=vgap, bg=bg)
        self.command = command
        self.multi = multi
        self.selected = set(value) if multi and isinstance(value, (list, tuple, set)) else (
            set() if multi else {value})
        self._option_items = []
        self.set_options(options)

    def set_options(self, options):
        self.clear()
        self._option_items = list(options)
        for option in self._option_items:
            if isinstance(option, dict):
                value = option["value"]
                label = option.get("label", str(value))
                color = option.get("color")
            else:
                value = label = str(option)
                color = None
            chip = Chip(self, self.palette, label, value=value, color=color,
                        selected=value in self.selected, command=self._click,
                        bg=self.cget("bg"))
            self.add(chip)

    def _click(self, value):
        if self.multi:
            if value in self.selected:
                self.selected.discard(value)
            else:
                self.selected.add(value)
        else:
            self.selected = {value}
        for widget in self.items:
            if isinstance(widget, Chip):
                widget.set_selected(widget.value in self.selected)
        if self.command:
            self.command(self.get())

    def get(self):
        if self.multi:
            return [value for value in self.selected]
        return next(iter(self.selected), None)

    def set(self, value):
        self.selected = set(value) if self.multi and isinstance(value, (list, tuple, set)) else (
            set() if self.multi else {value})
        for widget in self.items:
            if isinstance(widget, Chip):
                widget.set_selected(widget.value in self.selected)


# --------------------------------------------------------------------------- segmented
class Segmented(tk.Canvas):
    def __init__(self, master, palette, options, value=None, command=None,
                 height=32, radius=8, pad=3, size=9, bg=None):
        self.palette = palette
        self.options = [(option, option) if not isinstance(option, (tuple, list)) else
                        (option[0], option[1]) for option in options]
        self.value = value if value is not None else (self.options[0][0] if self.options else None)
        self.command = command
        self._pad = px(pad)
        self._radius = px(radius)
        self._height = px(height)
        self._font = tkfont.Font(family=FONT_FAMILY, size=size, weight="bold")
        seg_width = max(max(self._font.measure(label) for _, label in self.options)
                        + px(30), px(58))
        width = seg_width * len(self.options) + 2 * self._pad
        bg = bg or master.cget("bg")
        super().__init__(master, width=width, height=self._height, bg=bg, bd=0,
                         highlightthickness=0, cursor="hand2")
        self._bg = bg
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        p = self.palette
        w = max(1, self.winfo_width() or int(self.cget("width")))
        h = self._height
        draw_round_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, self._radius,
                        fill=p.surface_alt, outline=p.border, width=1)
        count = max(1, len(self.options))
        seg = (w - 2 * self._pad) / count
        for index, (value, label) in enumerate(self.options):
            x = self._pad + index * seg
            if value == self.value:
                draw_round_rect(self, x + 0.5, self._pad + 0.5,
                                x + seg - 0.5, h - self._pad - 0.5,
                                max(4, self._radius - 2),
                                fill=p.accent, outline=p.accent)
                fg = p.text_on_accent
            else:
                fg = p.text_muted
            self.create_text(x + seg / 2, h / 2, text=label, fill=fg,
                             font=self._font)

    def _click(self, event):
        count = max(1, len(self.options))
        seg = (max(1, self.winfo_width()) - 2 * self._pad) / count
        index = int((event.x - self._pad) // seg)
        index = max(0, min(count - 1, index))
        value = self.options[index][0]
        if value != self.value:
            self.value = value
            self._draw()
            if self.command:
                self.command(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._draw()


# --------------------------------------------------------------------------- fields
class EntryField(tk.Frame):
    def __init__(self, master, palette, textvariable=None, width=18, justify="left",
                 size=11, bg=None):
        bg = bg or palette.surface
        super().__init__(master, bg=bg, highlightthickness=1,
                         highlightbackground=palette.border,
                         highlightcolor=palette.accent)
        self.palette = palette
        self.entry = tk.Entry(
            self, textvariable=textvariable, width=width, bd=0,
            bg=bg, fg=palette.text, insertbackground=palette.accent,
            disabledbackground=palette.surface_alt, disabledforeground=palette.text_muted,
            font=font(size), justify=justify, highlightthickness=0, relief="flat",
        )
        self.entry.pack(fill="both", expand=True, padx=px(10), pady=px(6))
        self.entry.bind("<FocusIn>", lambda e: self.configure(highlightbackground=palette.accent))
        self.entry.bind("<FocusOut>", lambda e: self.configure(highlightbackground=palette.border))

    def get(self):
        return self.entry.get()

    def set(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def focus(self):
        self.entry.focus_set()

    def bind(self, sequence, func, add=None):
        return self.entry.bind(sequence, func, add)


class FieldLabel(tk.Label):
    def __init__(self, master, palette, text):
        super().__init__(master, text=text, bg=master.cget("bg"),
                         fg=palette.text_muted, font=font(9), anchor="w")


# --------------------------------------------------------------------------- dropdown
class Dropdown(tk.Frame):
    def __init__(self, master, palette, options, value=None, command=None,
                 width=150, height=34, size=10):
        bg = master.cget("bg")
        super().__init__(master, bg=bg)
        self.palette = palette
        self.options = []
        self.value = value
        self.command = command
        self._width = px(width)
        self._height = px(height)
        self._font = tkfont.Font(family=FONT_FAMILY, size=size)
        self.canvas = tk.Canvas(self, width=self._width, height=self._height,
                                bg=bg, bd=0, highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self._open())
        self.popup = None
        self._outside_id = None
        self.set_options(options, value)

    def set_options(self, options, value=None):
        self.options = list(options)
        values = [option[0] for option in self.options]
        if value is not None:
            self.value = value
        elif self.value not in values:
            self.value = values[0] if values else None
        self._draw()

    def _label(self):
        for value, label in self.options:
            if value == self.value:
                return label
        return ""

    def _draw(self):
        p = self.palette
        self.canvas.delete("all")
        w, h = self._width, self._height
        draw_round_rect(self.canvas, 0.5, 0.5, w - 0.5, h - 0.5, px(8),
                        fill=p.surface, outline=p.border, width=1)
        self.canvas.create_text(px(11), h / 2, text=self._label(), anchor="w",
                                fill=p.text, font=self._font)
        x = w - px(15)
        y = h / 2 - px(1)
        arrow = px(4)
        self.canvas.create_line(x - arrow, y, x, y + arrow, fill=p.text_muted,
                                width=1.5)
        self.canvas.create_line(x, y + arrow, x + arrow, y, fill=p.text_muted,
                                width=1.5)

    def _open(self):
        if self.popup is not None and self.popup.winfo_exists():
            self._close()
            return
        if not self.options:
            return
        p = self.palette
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg=p.border)
        popup.attributes("-topmost", True)
        self.popup = popup
        rows = min(len(self.options), 8)
        row_height = px(32)
        height = rows * row_height + px(8)
        frame = tk.Frame(popup, bg=p.surface)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        listbox = tk.Listbox(
            frame, bd=0, highlightthickness=0, activestyle="none",
            bg=p.surface, fg=p.text, selectbackground=p.accent_soft,
            selectforeground=p.text, font=self._font, height=rows,
            exportselection=False,
        )
        listbox.pack(fill="both", expand=True, padx=px(3), pady=px(4))
        values = []
        for value, label in self.options:
            listbox.insert("end", label)
            values.append(value)
        try:
            listbox.selection_set(values.index(self.value))
            listbox.see(values.index(self.value))
        except ValueError:
            pass
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self._height + px(4)
        screen_h = self.winfo_screenheight()
        if y + height > screen_h - px(12):
            y = self.winfo_rooty() - height - px(4)
        popup.geometry("%dx%d+%d+%d" % (self._width, height, x, y))

        def choose(_event=None):
            selection = listbox.curselection()
            if selection:
                value = values[selection[0]]
                self.value = value
                self._draw()
                self._close()
                if self.command:
                    self.command(value)

        listbox.bind("<ButtonRelease-1>", choose)
        listbox.bind("<Return>", choose)
        listbox.bind("<Escape>", lambda e: self._close())
        popup.bind("<FocusOut>", self._on_focus_out)
        listbox.focus_set()

        def outside(event):
            if not is_descendant(event.widget, popup) and event.widget is not self.canvas:
                self._close()

        self._outside_id = self.winfo_toplevel().bind("<Button-1>", outside, add="+")

    def _on_focus_out(self, _event):
        self.after(80, self._close)

    def _close(self):
        if self.popup is not None:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        if self._outside_id is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._outside_id)
            except Exception:
                pass
            self._outside_id = None

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._draw()


# --------------------------------------------------------------------------- calendar
class CalendarPopup(tk.Toplevel):
    def __init__(self, master, palette, initial, on_pick=None):
        super().__init__(master)
        self.palette = palette
        self.on_pick = on_pick
        self.overrideredirect(True)
        self.configure(bg=palette.border)
        self._font = tkfont.Font(family=FONT_FAMILY, size=10)
        self._font_bold = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")
        today = dt.date.today()
        self.view = initial or today
        self.selected = initial
        self.body = tk.Frame(self, bg=palette.surface)
        self.body.pack(fill="both", expand=True, padx=1, pady=1)
        self._build()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, _event):
        self.after(80, self._maybe_close)

    def _maybe_close(self):
        try:
            focused = self.focus_get()
        except Exception:
            focused = None
        if focused is None or not is_descendant(focused, self):
            self.destroy()

    def _build(self):
        for child in self.body.winfo_children():
            child.destroy()
        p = self.palette
        header = tk.Frame(self.body, bg=p.surface)
        header.pack(fill="x", padx=px(12), pady=(px(10), px(4)))
        nav = px(26)
        prev = tk.Canvas(header, width=nav, height=nav, bg=p.surface, bd=0,
                         highlightthickness=0, cursor="hand2")
        prev.pack(side="left")
        prev.create_text(nav / 2, nav / 2, text="‹", fill=p.text_muted, font=font(14))
        prev.bind("<Button-1>", lambda e: self._shift(-1))
        nxt = tk.Canvas(header, width=nav, height=nav, bg=p.surface, bd=0,
                        highlightthickness=0, cursor="hand2")
        nxt.pack(side="right")
        nxt.create_text(nav / 2, nav / 2, text="›", fill=p.text_muted, font=font(14))
        nxt.bind("<Button-1>", lambda e: self._shift(1))
        tk.Label(header, text="%d 年 %d 月" % (self.view.year, self.view.month),
                 bg=p.surface, fg=p.text, font=self._font_bold).pack(side="left",
                                                                     expand=True)
        grid = tk.Frame(self.body, bg=p.surface)
        grid.pack(padx=px(10), pady=(px(2), px(4)))
        names = ["一", "二", "三", "四", "五", "六", "日"]
        for index, name in enumerate(names):
            tk.Label(grid, text=name, bg=p.surface, fg=p.text_muted,
                     font=font(8), width=4).grid(row=0, column=index, pady=(0, 2))
        cal = calendar.Calendar(firstweekday=0)
        today = dt.date.today()
        weeks = cal.monthdatescalendar(self.view.year, self.view.month)
        while len(weeks) < 6:
            weeks.append([day + dt.timedelta(days=7) for day in weeks[-1]])
        for row, week in enumerate(weeks[:6], start=1):
            for column, day in enumerate(week):
                cell = tk.Frame(grid, bg=p.surface, width=px(32), height=px(30))
                cell.grid(row=row, column=column, padx=1, pady=1)
                cell.grid_propagate(False)
                label = tk.Label(cell, text=str(day.day), bg=p.surface,
                                 fg=p.text if day.month == self.view.month else p.border,
                                 font=self._font, cursor="hand2")
                label.pack(fill="both", expand=True)
                if day == self.selected:
                    label.configure(bg=p.accent, fg=p.text_on_accent)
                elif day == today:
                    label.configure(fg=p.accent)
                label.bind("<Button-1>", lambda e, d=day: self._pick(d))
                label.bind("<Enter>", lambda e, w=label, d=day: self._hover(w, d))
                label.bind("<Leave>", lambda e, w=label, d=day: self._unhover(w, d))
        footer = tk.Frame(self.body, bg=p.surface)
        footer.pack(fill="x", padx=px(12), pady=(0, px(10)))
        today_link = tk.Label(footer, text="今天", bg=p.surface, fg=p.accent,
                              font=self._font_bold, cursor="hand2")
        today_link.pack(side="left")
        today_link.bind("<Button-1>", lambda e: self._pick(dt.date.today()))
        cancel = tk.Label(footer, text="取消", bg=p.surface, fg=p.text_muted,
                          font=self._font, cursor="hand2")
        cancel.pack(side="right")
        cancel.bind("<Button-1>", lambda e: self.destroy())

    def _hover(self, widget, day):
        if day != self.selected:
            widget.configure(bg=self.palette.accent_soft)

    def _unhover(self, widget, day):
        if day != self.selected:
            widget.configure(bg=self.palette.surface)

    def _shift(self, delta):
        month = self.view.month + delta
        year = self.view.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        self.view = dt.date(year, month, 1)
        self._build()

    def _pick(self, day):
        if self.on_pick:
            self.on_pick(day)
        self.destroy()


class DateEntry(tk.Frame):
    def __init__(self, master, palette, value=None, width=120, height=34, command=None):
        bg = master.cget("bg")
        super().__init__(master, bg=bg)
        self.palette = palette
        self.command = command
        self.var = tk.StringVar(value=value or dt.date.today().isoformat())
        self.field = tk.Frame(self, bg=palette.surface, highlightthickness=1,
                              highlightbackground=palette.border,
                              highlightcolor=palette.accent,
                              width=px(width), height=px(height))
        self.field.pack(fill="both", expand=True)
        self.field.pack_propagate(False)
        button = tk.Canvas(self.field, width=px(26), height=px(height),
                           bg=palette.surface, bd=0, highlightthickness=0,
                           cursor="hand2")
        button.pack(side="right", padx=(0, px(4)))
        self.entry = tk.Entry(self.field, textvariable=self.var, bd=0,
                              bg=palette.surface, fg=palette.text,
                              insertbackground=palette.accent, font=font(10),
                              highlightthickness=0, relief="flat")
        self.entry.pack(side="left", fill="both", expand=True,
                        padx=(px(10), px(2)))
        self.entry.bind("<FocusIn>", lambda e: self.field.configure(
            highlightbackground=palette.accent))
        self.entry.bind("<FocusOut>", lambda e: self.field.configure(
            highlightbackground=palette.border))
        self._draw_icon(button)
        button.bind("<Button-1>", lambda e: self.open())
        self._width = width

    def _draw_icon(self, canvas):
        p = self.palette
        s = px
        canvas.create_rectangle(s(7), s(7), s(21), s(21),
                                outline=p.text_muted, width=1.2)
        canvas.create_line(s(7), s(11), s(21), s(11), fill=p.text_muted, width=1.2)
        canvas.create_line(s(10), s(5), s(10), s(8), fill=p.text_muted, width=1.4)
        canvas.create_line(s(18), s(5), s(18), s(8), fill=p.text_muted, width=1.4)
        for x in (11, 15, 18):
            canvas.create_oval(s(x) - px(1), s(14), s(x) + px(1), s(16),
                               fill=p.accent, outline="")

    def open(self):
        initial = None
        try:
            initial = dt.date.fromisoformat(self.var.get().strip())
        except ValueError:
            initial = dt.date.today()
        popup = CalendarPopup(self.winfo_toplevel(), self.palette, initial, self._picked)
        popup.update_idletasks()
        width = popup.winfo_reqwidth()
        height = popup.winfo_reqheight()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + px(4)
        if y + height > self.winfo_screenheight() - px(12):
            y = self.winfo_rooty() - height - px(4)
        x = max(0, min(x, self.winfo_screenwidth() - width - px(12)))
        popup.geometry("+%d+%d" % (x, y))
        popup.lift()
        popup.focus_set()

    def _picked(self, day):
        self.var.set(day.isoformat())
        if self.command:
            self.command(day.isoformat())

    def get(self):
        return self.var.get().strip()

    def set(self, value):
        self.var.set(value)


# --------------------------------------------------------------------------- scroll
class ScrollFrame(tk.Frame):
    def __init__(self, master, palette, bg=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg)
        self.palette = palette
        self.canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, style="Ledger.Vertical.TScrollbar",
                                       orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self._visible_scrollbar = False

    def _wheel(self, event):
        if self.canvas.winfo_exists():
            delta = int(-event.delta / 120) if event.delta else 0
            if delta:
                self.canvas.yview_scroll(delta, "units")
        return "break"

    def _on_scroll(self, first, last):
        first, last = float(first), float(last)
        if first <= 0.0 and last >= 1.0:
            if self._visible_scrollbar:
                self.scrollbar.pack_forget()
                self._visible_scrollbar = False
        else:
            if not self._visible_scrollbar:
                self.scrollbar.pack(side="right", fill="y")
                self._visible_scrollbar = True
        self.scrollbar.set(first, last)

    def _on_body(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.bind_tree()

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def bind_tree(self):
        bind_wheel_tree(self.body, self.canvas)

    def scroll_top(self):
        self.canvas.yview_moveto(0)


# --------------------------------------------------------------------------- toast
class Toast:
    def __init__(self, root, palette):
        self.root = root
        self.palette = palette
        self.window = None
        self.timer = None

    def show(self, message, kind="info", duration=2200):
        p = self.palette
        colors = {"info": "#1F2937", "success": p.success, "error": p.danger}
        bg = colors.get(kind, "#1F2937")
        self._destroy()
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.configure(bg=bg)
        try:
            window.attributes("-topmost", True)
        except Exception:
            pass
        label = tk.Label(window, text=message, bg=bg, fg="#FFFFFF", font=font(10),
                         padx=px(20), pady=px(10))
        label.pack()
        window.update_idletasks()
        width = window.winfo_reqwidth()
        height = window.winfo_reqheight()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        x = root_x + (root_w - width) // 2
        y = root_y + root_h - height - px(36)
        window.geometry("%dx%d+%d+%d" % (width, height, x, y))
        window.lift()
        self.window = window
        self.timer = self.root.after(duration, self._destroy)

    def _destroy(self):
        if self.timer is not None:
            try:
                self.root.after_cancel(self.timer)
            except Exception:
                pass
            self.timer = None
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


def confirm(parent, palette, title, message, ok_text="确定", cancel_text="取消",
            danger=False):
    """Modal confirm dialog; returns True when confirmed."""
    result = {"value": False}
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.configure(bg=palette.surface)
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()
    wrap = tk.Frame(dialog, bg=palette.surface, padx=px(26), pady=px(22))
    wrap.pack(fill="both", expand=True)
    tk.Label(wrap, text=title, bg=palette.surface, fg=palette.text,
             font=font(12, "bold"), anchor="w").pack(anchor="w")
    tk.Label(wrap, text=message, bg=palette.surface, fg=palette.text_muted,
             font=font(10), justify="left", wraplength=px(340),
             anchor="w").pack(anchor="w", pady=(px(10), px(18)))
    buttons = tk.Frame(wrap, bg=palette.surface)
    buttons.pack(anchor="e")

    def close(value):
        result["value"] = value
        dialog.destroy()

    RoundButton(buttons, palette, cancel_text, lambda: close(False), variant="ghost",
                height=32).pack(side="left", padx=(0, px(8)))
    RoundButton(buttons, palette, ok_text, lambda: close(True),
                variant="danger" if danger else "primary", height=32).pack(side="left")
    dialog.bind("<Escape>", lambda e: close(False))
    dialog.update_idletasks()
    width = max(px(400), dialog.winfo_reqwidth())
    height = dialog.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
    dialog.geometry("%dx%d+%d+%d" % (width, height, max(0, x), max(0, y)))
    dialog.wait_window()
    return result["value"]
