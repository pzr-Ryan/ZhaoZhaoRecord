"""Small helpers shared by the page views."""
from __future__ import annotations

import tkinter as tk

from ..theme import font, px
from ..widgets import draw_round_box


def page_header(parent, palette, title, subtitle=""):
    box = tk.Frame(parent, bg=palette.bg)
    tk.Label(box, text=title, bg=palette.bg, fg=palette.text,
             font=font(19, "bold"), anchor="w").pack(anchor="w")
    tk.Label(box, text=subtitle, bg=palette.bg, fg=palette.text_muted,
             font=font(10), anchor="w").pack(anchor="w", pady=(px(4), 0))
    return box


def divider(parent, color, pady=0, padx=0):
    line = tk.Frame(parent, bg=color, height=1)
    line.pack(fill="x", pady=pady, padx=padx)
    return line


def amount_field(master, palette, textvariable, size=20, height=58):
    outer = master.cget("bg")
    box = tk.Frame(master, bg=outer, height=px(height))
    box.pack_propagate(False)
    canvas = tk.Canvas(box, bg=outer, bd=0, highlightthickness=0)
    canvas.place(x=0, y=0, relwidth=1, relheight=1)
    state = {"focus": False}

    def redraw(_event=None):
        width = box.winfo_width()
        actual = box.winfo_height()
        if width <= 1 or actual <= 1:
            return
        border = palette.accent if state["focus"] else palette.border
        draw_round_box(canvas, 0, 0, width, actual, px(10),
                       palette.surface, border, outer)

    tk.Label(box, text="¥", bg=palette.surface, fg=palette.text_muted,
             font=font(size - 3, "bold")).pack(side="left",
                                              padx=(px(16), px(2)))
    entry = tk.Entry(box, textvariable=textvariable, bd=0, bg=palette.surface,
                     fg=palette.text, insertbackground=palette.accent,
                     font=font(size, "bold"), highlightthickness=0, relief="flat")
    entry.pack(side="left", fill="both", expand=True, padx=(0, px(16)),
               pady=px(10))

    def focus_in(_event):
        state["focus"] = True
        redraw()

    def focus_out(_event):
        state["focus"] = False
        redraw()

    entry.bind("<FocusIn>", focus_in)
    entry.bind("<FocusOut>", focus_out)
    box.bind("<Configure>", redraw)
    box.after_idle(redraw)
    return box, entry


def truncate(text, limit=18):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def set_tree_bg(widget, color):
    try:
        widget.configure(bg=color)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        set_tree_bg(child, color)


def hover_row(row, normal, hover):
    """Change the background of a row and its children on hover."""
    def enter(_event):
        set_tree_bg(row, hover)

    def leave(_event):
        set_tree_bg(row, normal)

    stack = [row]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        try:
            widget.bind("<Enter>", enter, add="+")
            widget.bind("<Leave>", leave, add="+")
        except tk.TclError:
            pass


def bind_click(widget, callback):
    stack = [widget]
    while stack:
        node = stack.pop()
        stack.extend(node.winfo_children())
        try:
            node.bind("<Button-1>", callback, add="+")
            node.configure(cursor="hand2")
        except tk.TclError:
            pass
