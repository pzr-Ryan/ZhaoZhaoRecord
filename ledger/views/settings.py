"""设置页：主题、分类管理、数据导出与备份."""
from __future__ import annotations

import datetime as dt
import os
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog

from ..db import CategoryInUse, ValidationError
from ..theme import CATEGORY_COLORS, PRESETS, font, px
from ..widgets import (RoundButton, RoundedCard, ScrollFrame, SectionHeader,
                       Segmented, confirm)
from .common import page_header

APP_VERSION = "1.0.0"


class _Swatch(tk.Frame):
    def __init__(self, master, palette, name, accent, selected, command):
        super().__init__(master, bg=palette.surface, cursor="hand2")
        self.palette = palette
        self.accent = accent
        self.selected = selected
        self.command = command
        size = px(44)
        self.canvas = tk.Canvas(self, width=size, height=size, bg=palette.surface,
                                bd=0, highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.label = tk.Label(self, text=name, bg=palette.surface, fg=palette.text_muted,
                              font=font(9), cursor="hand2")
        self.label.pack(pady=(px(4), 0))
        self._draw()
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", lambda e: self.command(name, accent))

    def _draw(self):
        self.canvas.delete("all")
        size = px(44)
        center = size / 2.0
        radius = size / 2.0 - px(5)
        if self.selected:
            self.canvas.create_oval(center - radius, center - radius,
                                    center + radius, center + radius,
                                    outline=self.accent, width=px(2))
            radius -= px(4)
        self.canvas.create_oval(center - radius, center - radius,
                                center + radius, center + radius,
                                fill=self.accent, outline="")
        self.label.configure(fg=self.palette.text if self.selected
                             else self.palette.text_muted,
                             font=font(9, "bold" if self.selected else "normal"))


class SettingsView(tk.Frame):
    def __init__(self, master, app):
        self.app = app
        self.store = app.store
        self.palette = app.palette
        super().__init__(master, bg=self.palette.bg)
        self.kind = "expense"
        self.swatches = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        p = self.palette
        outer = tk.Frame(self, bg=p.bg)
        outer.pack(fill="both", expand=True)
        head = tk.Frame(outer, bg=p.bg)
        head.pack(fill="x", padx=px(28), pady=(px(24), px(10)))
        self.header = page_header(head, p, "设置", "主题、分类与数据管理")
        self.header.pack(fill="x")
        self.scroll = ScrollFrame(outer, p, bg=p.bg)
        self.scroll.pack(fill="both", expand=True, padx=(px(28), px(14)),
                         pady=(0, px(18)))
        content = tk.Frame(self.scroll.body, bg=p.bg)
        content.pack(fill="both", expand=True)

        theme_card = RoundedCard(content, p, padding=18)
        theme_card.pack(fill="x")
        SectionHeader(theme_card.body, p, "主题颜色",
                      "默认蓝白，选择后立即生效").pack(fill="x")
        row = tk.Frame(theme_card.body, bg=p.surface)
        row.pack(anchor="w", pady=(px(12), 0))
        for preset in PRESETS:
            swatch = _Swatch(row, p, preset.name, preset.accent,
                             preset.name == p.name, self._pick_preset)
            swatch.pack(side="left", padx=(0, px(18)))
            self.swatches.append(swatch)

        custom_row = tk.Frame(theme_card.body, bg=p.surface)
        custom_row.pack(fill="x", pady=(px(12), 0))
        RoundButton(custom_row, p, "自定义颜色…", self._pick_custom,
                    variant="soft", height=32, size=9).pack(side="left")
        self.custom_label = tk.Label(custom_row, text="", bg=p.surface,
                                     fg=p.text_muted, font=font(9))
        self.custom_label.pack(side="left", padx=(px(12), 0))

        cat_card = RoundedCard(content, p, padding=18)
        cat_card.pack(fill="x", pady=(px(14), 0))
        cat_header = SectionHeader(cat_card.body, p, "分类管理",
                                   "删除分类前需要先清空该分类下的记录")
        cat_header.pack(fill="x")
        add_button = RoundButton(cat_header.action_area, p, "新增分类",
                                 self._add_category, height=30, size=9)
        add_button.pack(anchor="e")
        self.kind_seg = Segmented(cat_card.body, p,
                                  [("expense", "支出分类"), ("income", "收入分类")],
                                  value=self.kind, command=self._on_kind)
        self.kind_seg.pack(anchor="w", pady=(px(12), px(6)))
        self.cat_list = tk.Frame(cat_card.body, bg=p.surface)
        self.cat_list.pack(fill="x")

        data_card = RoundedCard(content, p, padding=18)
        data_card.pack(fill="x", pady=(px(14), 0))
        SectionHeader(data_card.body, p, "数据", "所有数据只保存在本机").pack(fill="x")
        actions = tk.Frame(data_card.body, bg=p.surface)
        actions.pack(fill="x", pady=(px(12), 0))
        RoundButton(actions, p, "导出 CSV", self._export_csv, variant="soft",
                    height=32, size=9).pack(side="left", padx=(0, px(10)))
        RoundButton(actions, p, "备份数据库", self._backup, variant="soft",
                    height=32, size=9).pack(side="left", padx=(0, px(10)))
        RoundButton(actions, p, "打开数据目录", self._open_folder, variant="soft",
                    height=32, size=9).pack(side="left")
        self.data_info = tk.Label(data_card.body, text="", bg=p.surface,
                                  fg=p.text_muted, font=font(8), anchor="w",
                                  justify="left")
        self.data_info.pack(fill="x", pady=(px(12), 0))

        about = RoundedCard(content, p, padding=18)
        about.pack(fill="x", pady=(px(14), 0))
        SectionHeader(about.body, p, "关于", "").pack(fill="x")
        tk.Label(about.body, text="简账 %s" % APP_VERSION, bg=p.surface,
                 fg=p.text, font=font(11, "bold"), anchor="w").pack(
                     fill="x", pady=(px(8), 0))
        tk.Label(about.body, text="一款轻量的本地记账工具 · Python + Tkinter 构建",
                 bg=p.surface, fg=p.text_muted, font=font(9), anchor="w").pack(
                     fill="x", pady=(px(2), 0))

    # ------------------------------------------------------------------ theme
    def _pick_preset(self, name, accent):
        self.app.set_theme(name)

    def _pick_custom(self):
        initial = self.palette.accent
        chosen = colorchooser.askcolor(color=initial, title="选择主题颜色",
                                       parent=self.winfo_toplevel())
        if chosen and chosen[1]:
            self.app.set_theme("自定义", chosen[1])

    # ------------------------------------------------------------------ categories
    def _on_kind(self, kind):
        self.kind = kind
        self._load_categories()

    def refresh(self):
        self._load_categories()
        self._load_data_info()
        if self.palette.name == "自定义":
            self.custom_label.configure(text="当前自定义 %s" % self.palette.accent)
        else:
            self.custom_label.configure(text="当前主题 %s" % self.palette.name)

    def on_show(self):
        self.refresh()

    def _load_categories(self):
        p = self.palette
        for child in self.cat_list.winfo_children():
            child.destroy()
        cats = self.store.list_categories(self.kind)
        for index, cat in enumerate(cats):
            if index:
                tk.Frame(self.cat_list, bg=p.border, height=1).pack(fill="x")
            row = tk.Frame(self.cat_list, bg=p.surface)
            row.pack(fill="x", pady=px(7))
            dot = tk.Canvas(row, width=px(11), height=px(11), bg=p.surface,
                            bd=0, highlightthickness=0)
            dot.pack(side="left", padx=(px(2), px(10)))
            dot.create_oval(1, 1, px(10), px(10), fill=cat["color"], outline="")
            tk.Label(row, text=cat["name"], bg=p.surface, fg=p.text,
                     font=font(10), anchor="w").pack(side="left")
            usage = self.store.category_usage(cat["id"])
            tk.Label(row, text="%d 笔" % usage, bg=p.surface, fg=p.text_muted,
                     font=font(8)).pack(side="left", padx=(px(10), 0))
            RoundButton(row, p, "删除", lambda c=cat: self._delete_category(c),
                        variant="link", height=26, size=9).pack(side="right")
            RoundButton(row, p, "编辑", lambda c=cat: self._edit_category(c),
                        variant="link", height=26, size=9).pack(side="right",
                                                              padx=(0, px(4)))

    def _add_category(self):
        from ..dialogs import CategoryDialog
        dialog = CategoryDialog(self.winfo_toplevel(), self.palette, self.store)
        if dialog.show() == "saved":
            self._load_categories()
            self.app.toast.show("分类已添加", "success")

    def _edit_category(self, category):
        from ..dialogs import CategoryDialog
        dialog = CategoryDialog(self.winfo_toplevel(), self.palette, self.store,
                                category=category)
        result = dialog.show()
        if result:
            self._load_categories()
            self.app.toast.show("分类已更新" if result == "saved" else "分类已删除",
                                "success")

    def _delete_category(self, category):
        if not confirm(self.winfo_toplevel(), self.palette, "删除分类",
                       "确定删除“%s”吗？" % category["name"], ok_text="删除",
                       danger=True):
            return
        try:
            self.store.delete_category(category["id"])
        except CategoryInUse as exc:
            self.app.toast.show(str(exc), "error")
            return
        except ValidationError as exc:
            self.app.toast.show(str(exc), "error")
            return
        self._load_categories()
        self.app.toast.show("分类已删除", "success")

    # ------------------------------------------------------------------ data
    def _load_data_info(self):
        stats = self.store.stats()
        size = 0
        try:
            size = Path(self.app.db_path).stat().st_size
        except OSError:
            pass
        if size >= 1024 * 1024:
            size_text = "%.1f MB" % (size / 1024.0 / 1024.0)
        else:
            size_text = "%.0f KB" % (size / 1024.0)
        self.data_info.configure(
            text="数据库：%s\n共 %d 笔记录 · %d 个分类 · %s" % (
                self.app.db_path, stats.get("tx", 0), stats.get("categories", 0),
                size_text))

    def _export_csv(self):
        stamp = dt.date.today().strftime("%Y%m%d")
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="导出 CSV",
            initialfile="简账-导出-%s.csv" % stamp, defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            count = self.store.export_csv(path)
        except OSError as exc:
            self.app.toast.show("导出失败：%s" % exc, "error")
            return
        self.app.toast.show("已导出 %d 笔记录" % count, "success")

    def _backup(self):
        stamp = dt.date.today().strftime("%Y%m%d")
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="备份数据库",
            initialfile="简账-备份-%s.db" % stamp, defaultextension=".db",
            filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.store.backup(path)
        except Exception as exc:
            self.app.toast.show("备份失败：%s" % exc, "error")
            return
        self.app.toast.show("备份已保存", "success")

    def _open_folder(self):
        folder = str(Path(self.app.db_path).resolve().parent)
        try:
            os.startfile(folder)
        except AttributeError:
            self.app.toast.show("当前系统不支持自动打开目录", "error")
        except OSError as exc:
            self.app.toast.show("打开目录失败：%s" % exc, "error")
