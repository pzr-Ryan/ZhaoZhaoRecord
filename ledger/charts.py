"""Canvas charts drawn without third-party dependencies."""
from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont

from .money import format_cents, format_compact
from .theme import FONT_FAMILY, font, mix, px
from .widgets import draw_round_rect


def nice_max(value):
    """Round an axis maximum up to 1/2/5 x 10^n."""
    value = float(value or 0)
    if value <= 0:
        return 1.0
    exponent = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 5, 10):
        candidate = step * exponent
        if value <= candidate:
            return float(candidate)
    return float(10 * exponent)


class BarChart(tk.Canvas):
    """A compact bar chart with grid lines and a hover tooltip."""

    def __init__(self, master, palette, height=220, bar_color=None, bg=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg, height=px(height), width=px(360), bd=0,
                         highlightthickness=0)
        self.palette = palette
        self.bar_color = bar_color or palette.accent
        self._data = []
        self._highlight = -1
        self._hover = None
        self._slots = []
        self._font_label = tkfont.Font(family=FONT_FAMILY, size=9)
        self._font_value = tkfont.Font(family=FONT_FAMILY, size=9, weight="bold")
        self._font_tip = tkfont.Font(family=FONT_FAMILY, size=9)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

    def set_data(self, data, highlight=-1):
        self._data = [(str(label), int(cents)) for label, cents in data]
        self._highlight = highlight
        self._hover = None
        self._draw()

    def _on_motion(self, event):
        index = None
        for i, (x1, x2, _label, _cents) in enumerate(self._slots):
            if x1 <= event.x <= x2:
                index = i
                break
        if index != self._hover:
            self._hover = index
            self._draw()

    def _on_leave(self, _event):
        if self._hover is not None:
            self._hover = None
            self._draw()

    def _draw(self):
        self.delete("all")
        self._slots = []
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width = int(self.cget("width"))
        if height <= 1:
            height = int(self.cget("height"))
        if width < px(120) or height < px(80) or not self._data:
            return
        p = self.palette
        pad_left, pad_right = px(54), px(10)
        pad_top, pad_bottom = px(16), px(28)
        plot_w = width - pad_left - pad_right
        plot_h = height - pad_top - pad_bottom
        if plot_w <= 10 or plot_h <= 10:
            return
        baseline = pad_top + plot_h
        max_cents = max(cents for _label, cents in self._data)
        if max_cents <= 0:
            self.create_line(pad_left, baseline, width - pad_right, baseline,
                             fill=p.border, width=1)
            self.create_text((pad_left + width - pad_right) / 2,
                             pad_top + plot_h / 2, text="这个区间还没有支出",
                             fill=p.text_muted, font=self._font_label)
            return
        top_value = max(100.0, nice_max(max_cents))
        steps = 4
        for i in range(steps + 1):
            value = top_value * i / steps
            y = baseline - plot_h * (value / top_value)
            self.create_line(pad_left, y, width - pad_right, y,
                             fill=p.chart_grid if i else p.border, width=1)
            label = "¥0" if i == 0 else format_compact(int(value))
            self.create_text(pad_left - px(8), y, text=label, anchor="e",
                             fill=p.text_muted, font=self._font_label)
        count = len(self._data)
        slot = plot_w / float(count)
        bar_w = max(px(3), min(px(32), slot * 0.56))
        label_w = max(self._font_label.measure(label) for label, _cents in self._data)
        label_every = max(1, int(math.ceil((label_w + px(14)) / max(1.0, slot))))
        shown = set(range(0, count, label_every))
        if count - 1 not in shown and (count - 1) - max(shown) >= label_every:
            shown.add(count - 1)
        for i, (label, cents) in enumerate(self._data):
            left = pad_left + slot * i + (slot - bar_w) / 2
            right = left + bar_w
            center = (left + right) / 2
            self._slots.append((pad_left + slot * i, pad_left + slot * (i + 1), label, cents))
            top = baseline - plot_h * (cents / top_value) if cents > 0 else baseline
            if cents > 0 and baseline - top < px(2):
                top = baseline - px(2)
            if i == self._hover:
                fill = p.accent_hover
            elif i == self._highlight:
                fill = self.bar_color
            else:
                fill = mix(self.bar_color, p.surface, 0.32)
            if cents > 0:
                draw_round_rect(self, left, top, right, baseline,
                                max(1, min(px(6), bar_w / 2)), fill=fill, outline="")
            else:
                self.create_line(left, baseline - 1, right, baseline - 1,
                                 fill=p.border, width=px(2))
            if i in shown:
                self.create_text(center, baseline + px(15), text=label, anchor="n",
                                 fill=p.text if i == self._highlight else p.text_muted,
                                 font=self._font_label)
        if self._hover is not None and self._hover < len(self._slots):
            x1, x2, label, cents = self._slots[self._hover]
            self._draw_tooltip((x1 + x2) / 2, label, cents, width, pad_top)

    def _draw_tooltip(self, center, label, cents, width, pad_top):
        p = self.palette
        text = "%s  %s" % (label, format_cents(cents))
        tip_w = self._font_tip.measure(text) + px(20)
        tip_h = px(26)
        x = center - tip_w / 2
        x = max(px(4), min(x, width - tip_w - px(4)))
        y = pad_top - px(4)
        draw_round_rect(self, x, y, x + tip_w, y + tip_h, px(7),
                        fill=p.text, outline="")
        self.create_text(x + tip_w / 2, y + tip_h / 2, text=text,
                         fill="#FFFFFF", font=self._font_tip)


class DonutChart(tk.Canvas):
    """A donut chart with a centered total and a right-hand legend."""

    def __init__(self, master, palette, height=230, bg=None):
        bg = bg or master.cget("bg")
        super().__init__(master, bg=bg, height=px(height), width=px(420), bd=0,
                         highlightthickness=0)
        self.palette = palette
        self._items = []
        self.center_label = "合计"
        self._font_center = tkfont.Font(family=FONT_FAMILY, size=15, weight="bold")
        self._font_center_label = tkfont.Font(family=FONT_FAMILY, size=9)
        self._font_name = tkfont.Font(family=FONT_FAMILY, size=9)
        self._font_amount = tkfont.Font(family=FONT_FAMILY, size=9, weight="bold")
        self.bind("<Configure>", lambda e: self._draw())

    def set_data(self, items, center_label="合计"):
        self._items = [dict(item) for item in items]
        self.center_label = center_label
        self._draw()

    def _draw(self):
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width = int(self.cget("width"))
        if height <= 1:
            height = int(self.cget("height"))
        if width < px(160) or height < px(100):
            return
        p = self.palette
        total = sum(max(0, int(item.get("cents", 0))) for item in self._items)
        pad = px(10)
        legend_min = px(180)
        diameter = min(height - 2 * pad, px(300),
                       width - 2 * pad - px(36) - legend_min)
        diameter = max(px(120), diameter)
        ring = max(px(10), diameter * 0.14)
        legend_x_guess = pad + diameter + px(36)
        legend_w = min(px(340), width - legend_x_guess - px(16))
        group_w = diameter + px(36) + legend_w
        x0 = max(pad, (width - group_w) / 2)
        y0 = (height - diameter) / 2
        cx, cy = x0 + diameter / 2, y0 + diameter / 2
        radius = (diameter - ring) / 2
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        legend_x = x0 + diameter + px(36)
        if total <= 0:
            self.create_oval(*box, outline=p.border, width=ring)
            self.create_text(cx, cy - px(8), text=format_cents(0),
                             fill=p.text, font=self._font_center)
            self.create_text(cx, cy + px(16), text=self.center_label,
                             fill=p.text_muted, font=self._font_center_label)
            if legend_w >= px(120):
                self.create_text(legend_x, cy, text="本月还没有支出记录",
                                 anchor="w", fill=p.text_muted,
                                 font=self._font_name)
            return
        self.create_oval(*box, outline=p.surface_alt, width=ring)
        start = 90.0
        for item in self._items:
            cents = max(0, int(item.get("cents", 0)))
            if cents <= 0:
                continue
            extent = -360.0 * cents / total
            color = item.get("color") or p.accent
            if extent <= -359.5:
                self.create_oval(*box, outline=color, width=ring)
            else:
                self.create_arc(*box, start=start, extent=extent, style="arc",
                                outline=color, width=ring)
            start += extent
        self.create_text(cx, cy - px(8), text=format_cents(total),
                         fill=p.text, font=self._font_center)
        self.create_text(cx, cy + px(16), text=self.center_label,
                         fill=p.text_muted, font=self._font_center_label)
        if legend_w < px(120):
            return
        rows = self._items
        row_h = min(px(34), max(px(20), (height - px(8)) / max(1, len(rows))))
        top = (height - row_h * len(rows)) / 2
        for i, item in enumerate(rows):
            y = top + row_h * i
            cents = max(0, int(item.get("cents", 0)))
            color = item.get("color") or p.accent
            name = str(item.get("name", ""))
            dot = px(4)
            self.create_oval(legend_x, y + row_h / 2 - dot, legend_x + 2 * dot,
                             y + row_h / 2 + dot, fill=color, outline=color)
            percent = cents * 100.0 / total
            percent_text = ("%.1f%%" if percent < 10 else "%.0f%%") % percent
            self.create_text(legend_x + px(18), y + row_h / 2, text=name,
                             anchor="w", fill=p.text, font=self._font_name)
            self.create_text(legend_x + legend_w, y + row_h / 2,
                             text=format_cents(cents), anchor="e", fill=p.text,
                             font=self._font_amount)
            amount_w = self._font_amount.measure(format_cents(cents))
            self.create_text(legend_x + legend_w - amount_w - px(10),
                             y + row_h / 2, text=percent_text, anchor="e",
                             fill=p.text_muted, font=self._font_name)
