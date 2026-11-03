"""应用外壳：窗口、侧栏导航与页面切换."""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from . import theme
from .db import Store
from .theme import font, px
from .views.record import RecordView
from .views.settings import SettingsView
from .views.stats import StatsView
from .views.transactions import TransactionsView
from .widgets import Toast

APP_NAME = "简账"
APP_NAME_EN = "ZhaoZhaoRecord"
APP_VERSION = "1.0.0"

NAV = [
    ("记账", "plus", RecordView),
    ("明细", "list", TransactionsView),
    ("统计", "chart", StatsView),
    ("设置", "sliders", SettingsView),
]

PAGE_ALIASES = {
    "record": 0, "记账": 0, "1": 0,
    "transactions": 1, "明细": 1, "2": 1,
    "stats": 2, "统计": 2, "3": 2,
    "settings": 3, "设置": 3, "4": 3,
}


def enable_dpi_awareness():
    """Make Tk render at real pixels on high-DPI Windows screens."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _set_tree_bg(widget, color):
    try:
        widget.configure(bg=color)
    except tk.TclError:
        pass


class NavItem(tk.Frame):
    def __init__(self, master, palette, label, icon, command, active=False):
        super().__init__(master, bg=palette.surface, height=px(42),
                         cursor="hand2")
        self.pack_propagate(False)
        self.palette = palette
        self.icon = icon
        self.command = command
        self.active = False
        self.bar = tk.Frame(self, width=px(3), bg=palette.surface)
        self.bar.pack(side="left", fill="y")
        self.canvas = tk.Canvas(self, width=px(20), height=px(20),
                                bg=palette.surface, bd=0, highlightthickness=0,
                                cursor="hand2")
        self.canvas.pack(side="left", padx=(px(16), px(12)))
        self.label = tk.Label(self, text=label, bg=palette.surface,
                              fg=palette.text_muted, font=font(10),
                              cursor="hand2")
        self.label.pack(side="left")
        for widget in (self, self.bar, self.canvas, self.label):
            widget.bind("<Button-1>", lambda e: self.command())
            widget.bind("<Enter>", lambda e: self._hover(True))
            widget.bind("<Leave>", lambda e: self._hover(False))
        self.set_active(active)
        self._draw_icon()

    def _hover(self, hovering):
        if self.active:
            return
        p = self.palette
        color = p.surface_alt if hovering else p.surface
        for widget in (self, self.bar, self.canvas, self.label):
            _set_tree_bg(widget, color)
        self.label.configure(fg=p.text if hovering else p.text_muted)

    def set_active(self, active):
        p = self.palette
        self.active = active
        if active:
            _set_tree_bg(self, p.accent_soft)
            _set_tree_bg(self.canvas, p.accent_soft)
            _set_tree_bg(self.bar, p.accent)
            self.label.configure(bg=p.accent_soft, fg=p.accent,
                                 font=font(10, "bold"))
        else:
            _set_tree_bg(self, p.surface)
            _set_tree_bg(self.canvas, p.surface)
            _set_tree_bg(self.bar, p.surface)
            self.label.configure(bg=p.surface, fg=p.text_muted, font=font(10))
        self._draw_icon()

    def _draw_icon(self):
        p = self.palette
        color = p.accent if self.active else p.text_muted
        s = px(20)
        c = self.canvas
        c.delete("all")
        width = max(1, int(px(1.6)))
        if self.icon == "plus":
            c.create_line(s * 0.5, s * 0.22, s * 0.5, s * 0.78, fill=color,
                          width=width, capstyle="round")
            c.create_line(s * 0.22, s * 0.5, s * 0.78, s * 0.5, fill=color,
                          width=width, capstyle="round")
        elif self.icon == "list":
            for i, ratio in enumerate((0.28, 0.5, 0.72)):
                y = s * ratio
                c.create_oval(s * 0.12, y - px(1.6), s * 0.12 + px(3.2),
                              y + px(1.6), fill=color, outline="")
                c.create_line(s * 0.36, y, s * 0.88, y, fill=color, width=width,
                              capstyle="round")
        elif self.icon == "chart":
            for ratio, height in ((0.24, 0.34), (0.5, 0.54), (0.76, 0.76)):
                x = s * ratio
                c.create_line(x, s * 0.82, x, s * (0.82 - height), fill=color,
                              width=max(2, int(px(3))), capstyle="round")
            c.create_line(s * 0.1, s * 0.84, s * 0.9, s * 0.84, fill=color,
                          width=1)
        else:
            for index, ratio in enumerate((0.28, 0.5, 0.72)):
                y = s * ratio
                c.create_line(s * 0.12, y, s * 0.88, y, fill=color, width=width,
                              capstyle="round")
                knob = 0.3 if index == 0 else (0.7 if index == 1 else 0.45)
                c.create_oval(s * knob - px(2.2), y - px(2.2),
                              s * knob + px(2.2), y + px(2.2),
                              fill=p.surface if self.active else p.surface,
                              outline=color, width=width)


class App:
    def __init__(self, db_path, demo=False):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.db_path)
        if demo:
            from . import demo as demo_module
            demo_module.ensure_seeded(self.store)
        self.palette = theme.resolve(self.store)

        self.root = tk.Tk()
        try:
            self.root.iconbitmap(str(_resource_path("assets/icon.ico")))
        except Exception:
            logging.exception("failed to set window icon")
        self.root.title("%s · 本地记账" % APP_NAME)
        self.root.configure(bg=self.palette.bg)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_scale()
        theme.apply_ttk(self.root, self.palette)
        self._setup_geometry()
        self._bind_keys()
        self.toast = Toast(self.root, self.palette)
        self.current = 0
        self.pages = []
        self.nav_items = []
        self._build_shell()
        self.show_page(0)

    # ------------------------------------------------------------------ setup
    def _setup_scale(self):
        try:
            self.scaling = float(self.root.tk.call("tk", "scaling"))
        except Exception:
            self.scaling = 96.0 / 72.0
        theme.set_scale(self.scaling / (96.0 / 72.0))

    def _setup_geometry(self):
        self.root.minsize(px(1000), px(640))
        saved = self.store.get_setting("window.geometry", "")
        if saved and re.match(r"^\d+x\d+\+-?\d+\+-?\d+$", saved):
            self.root.geometry(saved)
            return
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(px(1160), screen_w - px(80))
        height = min(px(740), screen_h - px(80))
        width = max(width, px(1000))
        height = max(height, px(640))
        x = (screen_w - width) // 2
        y = max(0, (screen_h - height) // 2 - px(20))
        self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))

    def _bind_keys(self):
        for index in range(len(NAV)):
            self.root.bind("<Control-Key-%d>" % (index + 1),
                           lambda e, i=index: self.show_page(i))

    def _build_shell(self):
        p = self.palette
        self.sidebar = tk.Frame(self.root, bg=p.surface, width=px(212))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo = tk.Frame(self.sidebar, bg=p.surface)
        logo.pack(fill="x", padx=px(24), pady=(px(28), px(26)))
        tk.Label(logo, text=APP_NAME, bg=p.surface, fg=p.text,
                 font=font(20, "bold"), anchor="w").pack(anchor="w")
        tk.Label(logo, text="轻量本地记账", bg=p.surface, fg=p.text_muted,
                 font=font(9), anchor="w").pack(anchor="w", pady=(px(2), 0))

        nav = tk.Frame(self.sidebar, bg=p.surface)
        nav.pack(fill="x")
        self.nav_items = []
        for index, (label, icon, _view) in enumerate(NAV):
            item = NavItem(nav, p, label, icon,
                           command=lambda i=index: self.show_page(i),
                           active=index == self.current)
            item.pack(fill="x", padx=px(10), pady=px(2))
            self.nav_items.append(item)

        bottom = tk.Frame(self.sidebar, bg=p.surface)
        bottom.pack(side="bottom", fill="x", padx=px(24), pady=(0, px(22)))
        tk.Label(bottom, text="数据保存在本机", bg=p.surface, fg=p.text_muted,
                 font=font(8), anchor="w").pack(anchor="w")
        tk.Label(bottom, text="v%s" % APP_VERSION, bg=p.surface,
                 fg=p.text_muted, font=font(8), anchor="w").pack(
                     anchor="w", pady=(px(2), 0))

        self.separator = tk.Frame(self.root, bg=p.border, width=1)
        self.separator.pack(side="left", fill="y")

        self.content = tk.Frame(self.root, bg=p.bg)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = [view(self.content, self) for _label, _icon, view in NAV]

    # ------------------------------------------------------------------ pages
    def show_page(self, index, refresh=True):
        if not self.pages:
            return
        index = max(0, min(index, len(self.pages) - 1))
        self.current = index
        for page in self.pages:
            page.pack_forget()
        page = self.pages[index]
        page.pack(fill="both", expand=True)
        for i, item in enumerate(self.nav_items):
            item.set_active(i == index)
        if refresh:
            hook = getattr(page, "on_show", None)
            try:
                if hook is not None:
                    hook()
                else:
                    page.refresh()
            except Exception:
                logging.exception("failed to refresh page %s", index)
        self.root.title("%s · %s" % (APP_NAME, NAV[index][0]))

    # ------------------------------------------------------------------ theme
    def set_theme(self, name, accent=None):
        self.store.set_setting("theme.preset", name)
        if accent:
            self.store.set_setting("theme.accent", accent)
        self.root.after(10, self._rebuild_theme)

    def _rebuild_theme(self):
        p = theme.resolve(self.store)
        self.palette = p
        theme.apply_ttk(self.root, p)
        self.root.configure(bg=p.bg)
        index = self.current
        if self.toast is not None and self.toast.window is not None:
            try:
                self.toast.window.destroy()
            except tk.TclError:
                pass
        self.sidebar.destroy()
        self.separator.destroy()
        self.content.destroy()
        self.pages = []
        self.nav_items = []
        self._build_shell()
        self.toast = Toast(self.root, p)
        self.show_page(index)
        self.toast.show("主题已切换", "success")

    # ------------------------------------------------------------------ close
    def _on_close(self):
        try:
            self.store.set_setting("window.geometry", self.root.geometry())
        except Exception:
            logging.exception("failed to save geometry")
        try:
            self.toast._destroy()
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            logging.exception("failed to close store")
        self.root.destroy()


def _resource_path(relative):
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / relative
    return Path(__file__).resolve().parent.parent / relative


def _data_home():
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME_EN
        return Path.home() / "AppData" / "Local" / APP_NAME_EN
    return Path(__file__).resolve().parent.parent


def _default_db():
    return _data_home() / "data" / "ledger.db"


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="简账 - 本地记账")
    parser.add_argument("--db", default=None, help="数据库文件路径")
    parser.add_argument("--demo", action="store_true", help="使用演示数据")
    parser.add_argument("--page", default="record", help="启动页面")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    db_path = Path(args.db) if args.db else _default_db()
    if args.demo and not args.db:
        db_path = db_path.with_name("demo.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(db_path.parent / "app.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    enable_dpi_awareness()
    try:
        app = App(str(db_path), demo=args.demo)
    except Exception:
        logging.exception("failed to start")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("简账", "启动失败，请查看日志：\n%s" % (db_path.parent / "app.log"))
            root.destroy()
        except Exception:
            pass
        raise
    index = PAGE_ALIASES.get(str(args.page).strip().lower(), 0)
    if index:
        app.show_page(index)
    try:
        app.root.mainloop()
    finally:
        logging.shutdown()
