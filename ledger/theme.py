"""Theme palettes and ttk styling for 简账."""
from __future__ import annotations

from dataclasses import dataclass

from tkinter import ttk

FONT_FAMILY = "Microsoft YaHei UI"
FALLBACK_FAMILY = "Segoe UI"

SCALE = 1.0


def set_scale(value):
    global SCALE
    try:
        SCALE = max(1.0, min(3.0, float(value)))
    except (TypeError, ValueError):
        SCALE = 1.0


def px(value):
    return int(round(value * SCALE))


def font(size, weight="normal"):
    return (FONT_FAMILY, size, "bold" if weight == "bold" else "normal")


@dataclass(frozen=True)
class Palette:
    name: str
    accent: str
    accent_hover: str
    accent_soft: str
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    text_on_accent: str
    danger: str
    success: str
    chart_grid: str


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(color_a, color_b, weight_b):
    a = _hex_to_rgb(color_a)
    b = _hex_to_rgb(color_b)
    return _rgb_to_hex(tuple(a[i] * (1 - weight_b) + b[i] * weight_b for i in range(3)))


def darken(color, amount):
    return mix(color, "#000000", amount)


def lighten(color, amount):
    return mix(color, "#FFFFFF", amount)


def luminance(color):
    channels = []
    for value in _hex_to_rgb(color):
        c = value / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(color_a, color_b):
    lum_a = luminance(color_a)
    lum_b = luminance(color_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def build_palette(name, accent):
    accent = accent.upper()
    soft = mix(accent, "#FFFFFF", 0.90)
    hover = darken(accent, 0.14)
    on_accent = "#FFFFFF" if contrast_ratio(accent, "#FFFFFF") >= contrast_ratio(accent, "#1F2937") else "#1F2937"
    return Palette(
        name=name,
        accent=accent,
        accent_hover=hover,
        accent_soft=soft,
        bg="#F5F7FB",
        surface="#FFFFFF",
        surface_alt="#FAFBFE",
        border="#E6EAF2",
        text="#1F2937",
        text_muted="#6B7280",
        text_on_accent=on_accent,
        danger="#DC2626",
        success="#16A34A",
        chart_grid="#EDF1F7",
    )


PRESET_DEFS = [
    ("蓝白", "#2563EB"),
    ("青碧", "#0F766E"),
    ("紫罗兰", "#7C3AED"),
    ("暖橙", "#C2410C"),
    ("玫瑰", "#E11D48"),
    ("墨青", "#1E293B"),
]

PRESETS = [build_palette(name, accent) for name, accent in PRESET_DEFS]
PRESET_BY_NAME = {palette.name: palette for palette in PRESETS}
DEFAULT_PALETTE = PRESETS[0]

CATEGORY_COLORS = [
    "#F97316", "#3B82F6", "#EC4899", "#8B5CF6", "#14B8A6",
    "#EF4444", "#06B6D4", "#F59E0B", "#22C55E", "#6366F1",
    "#0EA5E9", "#94A3B8",
]


def resolve(store):
    name = store.get_setting("theme.preset", "蓝白")
    if name == "自定义":
        accent = store.get_setting("theme.accent", DEFAULT_PALETTE.accent)
        try:
            return build_palette("自定义", accent)
        except (ValueError, TypeError):
            return DEFAULT_PALETTE
    return PRESET_BY_NAME.get(name, DEFAULT_PALETTE)


def apply_ttk(root, palette):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Ledger.Treeview",
        background=palette.surface,
        fieldbackground=palette.surface,
        foreground=palette.text,
        rowheight=px(38),
        borderwidth=0,
        relief="flat",
        font=font(11),
    )
    style.map(
        "Ledger.Treeview",
        background=[("selected", palette.accent_soft)],
        foreground=[("selected", palette.text)],
    )
    style.configure(
        "Ledger.Treeview.Heading",
        background=palette.bg,
        foreground=palette.text_muted,
        relief="flat",
        borderwidth=0,
        font=font(10, "bold"),
        padding=(px(8), px(9)),
    )
    style.map(
        "Ledger.Treeview.Heading",
        background=[("active", palette.surface_alt)],
        foreground=[("active", palette.text)],
    )
    style.layout("Ledger.Treeview", [("Ledger.Treeview.treearea", {"sticky": "nswe"})])
    style.configure(
        "Ledger.Vertical.TScrollbar",
        background=palette.border,
        troughcolor=palette.bg,
        bordercolor=palette.bg,
        arrowcolor=palette.text_muted,
        relief="flat",
        borderwidth=0,
        width=px(10),
    )
    style.map("Ledger.Vertical.TScrollbar", background=[("active", palette.text_muted)])
