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

from . import raster, snapshot, theme
from .db import Store
from .motion import TRANSITION_MS, TRANSITION_REVEAL, Tween, page_transition
from .theme import font, px
from .views.record import RecordView
from .views.settings import SettingsView
from .views.stats import StatsView
from .views.transactions import TransactionsView
from .widgets import Toast, draw_round_box, round_window

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


class NavItem(tk.Canvas):
    """A rounded, anti-aliased sidebar entry."""

    def __init__(self, master, palette, label, icon, command, active=False,
                 height=40):
        super().__init__(master, height=px(height), bg=palette.surface, bd=0,
                         highlightthickness=0, cursor="hand2", takefocus=0)
        self.palette = palette
        self.icon = icon
        self.label = label
        self.command = command
        self.active = bool(active)
        self._hover = False
        self._last = (0, 0)
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Configure>", self._configure)
        self.after_idle(self._draw)

    def _enter(self, _event=None):
        self._hover = True
        self._draw()

    def _leave(self, _event=None):
        self._hover = False
        self._draw()

    def _configure(self, event=None):
        size = (self.winfo_width(), self.winfo_height())
        if size == self._last:
            return
        self._last = size
        self._draw()

    def _draw(self):
        p = self.palette
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width, height = px(196), px(40)
        self.delete("all")
        if self.active:
            fill, fg, spec = p.accent_soft, p.accent, font(10, "bold")
        elif self._hover:
            fill, fg, spec = p.surface_alt, p.text, font(10)
        else:
            fill, fg, spec = p.surface, p.text_muted, font(10)
        draw_round_box(self, 0, 0, width, height, px(10), fill, fill,
                       p.surface)
        self.create_image(px(16), height / 2.0, anchor="w",
                          image=raster.icon(self, self.icon, px(18), fg))
        self.create_text(px(44), height / 2.0, anchor="w", text=self.label,
                         fill=fg, font=spec)

    def set_active(self, active):
        self.active = bool(active)
        self._draw()

    def _hover_set(self, hovering):
        self._hover = hovering
        self._draw()


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
        self.animate_pages = True
        self._first_show = False
        self._transition = None
        self._transition_page = None
        self._transition_old = None
        self._transition_size = None
        self._transition_swapped = False
        self._transition_revealed = False
        self._curtain = None
        self._gap_cover = None
        self._overlay = None
        self._overlay_canvas = None
        self._overlay_image = None
        self._overlay_photo = None
        self._backdrop = None
        self._offset = px(120)
        self._old_offset = px(48)
        round_window(self.root)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.bind("<Destroy>", self._on_destroy, add="+")
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
        self.sidebar = tk.Frame(self.root, bg=p.surface, width=px(224))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo = tk.Frame(self.sidebar, bg=p.surface)
        logo.pack(fill="x", padx=px(20), pady=(px(24), px(20)))
        badge = tk.Canvas(logo, width=px(38), height=px(38), bg=p.surface,
                          bd=0, highlightthickness=0)
        badge.pack(side="left", padx=(0, px(11)))
        draw_round_box(badge, 0, 0, px(38), px(38), px(12), p.accent,
                       p.accent, p.surface)
        badge.create_text(px(19), px(19), text="简", fill=p.text_on_accent,
                          font=font(16, "bold"))
        brand_text = tk.Frame(logo, bg=p.surface)
        brand_text.pack(side="left")
        tk.Label(brand_text, text=APP_NAME, bg=p.surface, fg=p.text,
                 font=font(18, "bold"), anchor="w").pack(anchor="w")
        tk.Label(brand_text, text="本地记账", bg=p.surface, fg=p.text_muted,
                 font=font(9), anchor="w").pack(anchor="w", pady=(px(1), 0))

        tk.Label(self.sidebar, text="页面", bg=p.surface, fg=p.text_muted,
                 font=font(8), anchor="w").pack(fill="x", padx=px(24),
                                                pady=(0, px(6)))

        nav = tk.Frame(self.sidebar, bg=p.surface)
        nav.pack(fill="x")
        self.nav_items = []
        for index, (label, icon, _view) in enumerate(NAV):
            item = NavItem(nav, p, label, icon,
                           command=lambda i=index: self.show_page(i),
                           active=index == self.current)
            item.pack(fill="x", padx=px(12), pady=px(2))
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
    def show_page(self, index, refresh=True, animate=None):
        if not self.pages:
            return
        index = max(0, min(index, len(self.pages) - 1))
        old = self.current
        page = self.pages[index]
        if animate is None:
            animate = bool(
                self.animate_pages and self._first_show and old != index and
                self.content.winfo_ismapped() and
                self.content.winfo_width() > 1
            )
        self._finish_transition()
        self.current = index
        self._first_show = True
        for i, item in enumerate(self.nav_items):
            item.set_active(i == index)
        self.root.title("%s · %s" % (APP_NAME, NAV[index][0]))
        tween = None
        if animate:
            tween = self._start_transition(self.pages[old], page)
        if tween is None:
            for other in self.pages:
                if other is not page:
                    other.place_forget()
            page.place(x=0, y=0, relwidth=1, relheight=1)
            page.lift()
        if refresh:
            hook = getattr(page, "on_show", None)
            try:
                if hook is not None:
                    hook()
                else:
                    page.refresh()
            except Exception:
                logging.exception("failed to refresh page %s", index)
        if old != index:
            try:
                self.root.focus_set()
            except tk.TclError:
                pass
        if tween is not None and self._transition is tween:
            try:
                self.content.update_idletasks()
            except tk.TclError:
                pass
            tween.start()
        elif tween is None:
            self._notify_reveal(page)

    def _start_transition(self, old_page, new_page):
        self._transition_old = old_page
        self._transition_page = new_page
        self._transition_swapped = False
        self._transition_revealed = False
        try:
            self._transition_size = (
                self.root.winfo_x(), self.root.winfo_y(),
                self.root.winfo_width(), self.root.winfo_height())
        except tk.TclError:
            self._transition_size = None
        self._destroy_gap_cover()
        self._destroy_curtain()
        self._destroy_overlay()
        self._destroy_backdrop()

        photo = None
        try:
            old_page.place(x=0, y=0, relwidth=1, relheight=1)
            old_page.lift()
            self.content.update_idletasks()
            photo = snapshot.capture_page(old_page, self.root)
        except tk.TclError:
            photo = None

        if photo is not None:
            backdrop = self._make_backdrop()
            overlay = self._make_overlay(photo) if backdrop else None
            if overlay is not None:
                try:
                    old_page.place_forget()
                    new_page.place(
                        x=0, y=self._offset, relwidth=1, relheight=1)
                    new_page.lift()
                    backdrop.lift()
                    overlay.lift()
                    self.content.update_idletasks()
                except tk.TclError:
                    self._destroy_overlay()
                    self._destroy_backdrop()
                    try:
                        old_page.place(x=0, y=0, relwidth=1, relheight=1)
                        old_page.lift()
                    except tk.TclError:
                        pass
                else:
                    self._transition_swapped = True
                    self._transition = Tween(
                        self.root, TRANSITION_MS, self._transition_frame,
                        easing=lambda value: max(0.0, min(1.0, value)),
                        on_done=lambda: self._end_transition(new_page),
                    )
                    return self._transition
            else:
                self._destroy_overlay()
                self._destroy_backdrop()

        # Fallback when the snapshot is unavailable: show the incoming page
        # behind an opaque curtain and reveal it at the 75% mark.
        try:
            old_page.place(x=0, y=0, relwidth=1, relheight=1)
            new_page.place(
                x=0, y=self._offset, relwidth=1, relheight=1)
            self._make_gap_cover()
            old_page.lift()
            self.content.update_idletasks()
        except tk.TclError:
            pass
        curtain = self._make_curtain()
        if curtain is None:
            self._destroy_gap_cover()
            self._transition_old = None
            self._transition_page = None
            self._transition_size = None
            return None
        self._curtain = curtain
        self._transition = Tween(
            self.root, TRANSITION_MS, self._transition_frame,
            easing=lambda value: max(0.0, min(1.0, value)),
            on_done=lambda: self._end_transition(new_page),
        )
        return self._transition

    def _make_backdrop(self):
        backdrop = None
        try:
            x = int(self.content.winfo_rootx())
            y = int(self.content.winfo_rooty())
            width = int(self.content.winfo_width())
            height = int(self.content.winfo_height())
            if width <= 1 or height <= 1:
                return None
            backdrop = tk.Toplevel(self.root)
            backdrop.withdraw()
            backdrop.overrideredirect(True)
            backdrop.configure(bg=self.palette.bg)
            backdrop.transient(self.root)
            backdrop.geometry("%dx%d+%d+%d" % (width, height, x, y))
            try:
                if self.root.attributes("-topmost"):
                    backdrop.attributes("-topmost", True)
            except tk.TclError:
                pass
            backdrop.attributes("-alpha", 1.0)
            backdrop.update_idletasks()
            backdrop.deiconify()
            backdrop.lift()
            self._backdrop = backdrop
            return backdrop
        except tk.TclError:
            if backdrop is not None:
                try:
                    backdrop.destroy()
                except tk.TclError:
                    pass
            self._backdrop = None
            return None

    def _destroy_backdrop(self):
        backdrop = self._backdrop
        self._backdrop = None
        if backdrop is not None:
            try:
                backdrop.destroy()
            except tk.TclError:
                pass

    def _make_overlay(self, photo):
        overlay = canvas = image = None
        try:
            x = int(self.content.winfo_rootx())
            y = int(self.content.winfo_rooty())
            width = int(self.content.winfo_width())
            height = int(self.content.winfo_height())
            if width <= 1 or height <= 1:
                return None
            overlay = tk.Toplevel(self.root)
            overlay.withdraw()
            overlay.overrideredirect(True)
            overlay.configure(bg=self.palette.bg)
            overlay.transient(self.root)
            try:
                if self.root.attributes("-topmost"):
                    overlay.attributes("-topmost", True)
            except tk.TclError:
                pass
            overlay.geometry("%dx%d+%d+%d" % (width, height, x, y))
            canvas = tk.Canvas(
                overlay, bg=self.palette.bg, bd=0, highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            image = canvas.create_image(0, 0, anchor="nw", image=photo)
            overlay.attributes("-alpha", 1.0)
            overlay.update_idletasks()
            overlay.deiconify()
            overlay.lift()
            self._overlay = overlay
            self._overlay_canvas = canvas
            self._overlay_image = image
            self._overlay_photo = photo
            return overlay
        except tk.TclError:
            if overlay is not None:
                try:
                    overlay.destroy()
                except tk.TclError:
                    pass
            self._overlay = None
            self._overlay_canvas = None
            self._overlay_image = None
            self._overlay_photo = None
            return None

    def _set_overlay_alpha(self, alpha):
        if self._overlay is None:
            return
        try:
            self._overlay.attributes(
                "-alpha", max(0.0, min(1.0, float(alpha))))
        except tk.TclError:
            pass

    def _move_overlay(self, progress):
        if self._overlay_canvas is None or self._overlay_image is None:
            return
        try:
            progress = max(0.0, min(1.0, float(progress)))
            self._overlay_canvas.coords(
                self._overlay_image, 0, int(self._old_offset * progress))
        except tk.TclError:
            pass

    def _destroy_overlay(self):
        overlay = self._overlay
        self._overlay = None
        self._overlay_canvas = None
        self._overlay_image = None
        self._overlay_photo = None
        if overlay is not None:
            try:
                overlay.destroy()
            except tk.TclError:
                pass

    def _make_gap_cover(self):
        """Opaque strip above the outgoing page, hiding the incoming page."""
        self._destroy_gap_cover()
        try:
            cover = tk.Frame(self.content, bg=self.palette.bg, bd=0,
                             highlightthickness=0)
            cover.place(x=0, y=0, relwidth=1, height=0)
            cover.lift()
            self._gap_cover = cover
        except tk.TclError:
            self._gap_cover = None

    def _make_curtain(self):
        curtain = None
        try:
            x = int(self.content.winfo_rootx())
            y = int(self.content.winfo_rooty())
            width = int(self.content.winfo_width())
            height = int(self.content.winfo_height())
            if width <= 1 or height <= 1:
                return None
            curtain = tk.Toplevel(self.root)
            curtain.withdraw()
            curtain.overrideredirect(True)
            curtain.configure(bg=self.palette.bg)
            curtain.transient(self.root)
            curtain.geometry("%dx%d+%d+%d" % (width, height, x, y))
            curtain.attributes("-alpha", 0.0)
            curtain.update_idletasks()
            curtain.deiconify()
            curtain.lift()
            return curtain
        except tk.TclError:
            if curtain is not None:
                try:
                    curtain.destroy()
                except tk.TclError:
                    pass
            return None

    def _transition_frame(self, t):
        page = self._transition_page
        if page is None:
            return
        opacity, offset_ratio, reveal = page_transition(t)
        if self._overlay is not None:
            self._set_overlay_alpha(opacity)
            self._move_overlay(1.0 - opacity)
            if reveal and self._backdrop is not None:
                self._destroy_backdrop()
            if reveal:
                self._notify_reveal(page)
                try:
                    page.place_configure(
                        y=int(self._offset * offset_ratio))
                except tk.TclError:
                    pass
            if opacity <= 0.001:
                self._destroy_overlay()
            return
        if not self._transition_swapped:
            self._move_outgoing(1.0 - opacity)
        if reveal and not self._transition_swapped:
            self._reveal_page()
        if self._transition_swapped:
            try:
                page.place_configure(y=int(self._offset * offset_ratio))
            except tk.TclError:
                pass
        if self._transition_swapped:
            self._set_curtain_alpha(TRANSITION_REVEAL * offset_ratio)
        else:
            self._set_curtain_alpha(1.0 - opacity)

    def _move_outgoing(self, progress):
        old = self._transition_old
        if old is None or old is self._transition_page:
            return
        if self._gap_cover is None:
            return
        try:
            progress = max(0.0, min(1.0, float(progress)))
            distance = int(self._old_offset * progress)
            old.place_configure(y=distance)
            self._gap_cover.place_configure(height=distance)
        except tk.TclError:
            pass

    def _reveal_page(self):
        page = self._transition_page
        old = self._transition_old
        if page is None:
            return
        try:
            if old is not None and old is not page:
                old.place_forget()
            self._destroy_gap_cover()
            page.lift()
        except tk.TclError:
            pass
        self._transition_swapped = True
        self._notify_reveal(page)

    def _notify_reveal(self, page):
        if page is None or self._transition_revealed:
            return
        self._transition_revealed = True
        hook = getattr(page, "on_reveal", None)
        if hook is None:
            return
        try:
            hook()
        except Exception:
            logging.exception("page reveal hook failed")

    def _set_curtain_alpha(self, alpha):
        if self._curtain is None:
            return
        try:
            self._curtain.attributes(
                "-alpha", max(0.0, min(1.0, float(alpha))))
        except tk.TclError:
            pass

    def _destroy_curtain(self):
        if self._curtain is not None:
            try:
                self._curtain.destroy()
            except tk.TclError:
                pass
        self._curtain = None

    def _destroy_gap_cover(self):
        cover = self._gap_cover
        self._gap_cover = None
        if cover is not None:
            try:
                cover.destroy()
            except tk.TclError:
                pass

    def _end_transition(self, page):
        if self._transition_page is not page:
            return
        try:
            page.place_configure(x=0, y=0)
        except tk.TclError:
            pass
        self._destroy_curtain()
        self._destroy_gap_cover()
        self._destroy_overlay()
        self._destroy_backdrop()
        for other in self.pages:
            if other is not page:
                other.place_forget()
        self._transition = None
        self._transition_page = None
        self._transition_old = None
        self._transition_size = None
        self._transition_swapped = False
        self._transition_revealed = False

    def _finish_transition(self):
        tween = self._transition
        page = self._transition_page
        old = self._transition_old
        self._transition = None
        self._transition_page = None
        self._transition_old = None
        self._transition_size = None
        self._transition_swapped = False
        self._transition_revealed = False
        if tween is not None:
            tween.cancel()
        self._destroy_curtain()
        self._destroy_gap_cover()
        self._destroy_overlay()
        self._destroy_backdrop()
        if page is not None:
            try:
                page.place_configure(x=0, y=0)
            except tk.TclError:
                pass
            for other in self.pages:
                if other is not page:
                    other.place_forget()
        elif old is not None:
            try:
                old.place_configure(x=0, y=0)
            except tk.TclError:
                pass

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        try:
            self._finish_transition()
        except Exception:
            self._transition = None

    def _on_root_configure(self, event):
        if self._transition_page is None:
            return
        try:
            geometry = (
                self.root.winfo_x(), self.root.winfo_y(),
                self.root.winfo_width(), self.root.winfo_height())
        except tk.TclError:
            return
        if self._transition_size and geometry != self._transition_size:
            self._finish_transition()

    def _on_mousewheel(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None
        if widget is None:
            return None
        try:
            widget_class = widget.winfo_class()
        except tk.TclError:
            return None
        if widget_class in ("Treeview", "Listbox", "TCombobox", "Text", "Entry"):
            return None
        current = widget
        while current is not None:
            if getattr(current, "_ledger_scroll", False):
                try:
                    current.canvas.yview_scroll(
                        -3 if event.delta > 0 else 3, "units")
                except Exception:
                    pass
                return "break"
            current = getattr(current, "master", None)
        return None

    # ------------------------------------------------------------------ theme
    def set_theme(self, name, accent=None):
        self.store.set_setting("theme.preset", name)
        if accent:
            self.store.set_setting("theme.accent", accent)
        self.root.after(10, self._rebuild_theme)

    def _rebuild_theme(self):
        self._finish_transition()
        raster.clear_cache()
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
        self._first_show = False
        self.show_page(index)
        self.toast.show("主题已切换", "success")

    # ------------------------------------------------------------------ close
    def _on_close(self):
        try:
            self._finish_transition()
        except Exception:
            pass
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
