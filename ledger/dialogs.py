"""Modal dialogs for adding transactions and managing categories."""
from __future__ import annotations

import datetime as dt
import tkinter as tk

from . import dates, money
from .db import CategoryInUse, StoreError
from .theme import CATEGORY_COLORS, font, px
from .widgets import (ChipGroup, DateEntry, EntryField, FieldLabel, RoundButton,
                      Segmented, confirm, draw_round_rect)


class _Modal(tk.Toplevel):
    """A borderless, draggable modal window with a custom header."""

    def __init__(self, parent, palette, title, width, height):
        super().__init__(parent)
        self.palette = palette
        self.result = None
        self._parent = parent
        self._drag = None
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=palette.border)
        self.transient(parent)
        self._width = px(width)
        self._height = px(height)
        parent.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self._width) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self._height) // 3)
        self.geometry("%dx%d+%d+%d" % (self._width, self._height, x, y))
        shell = tk.Frame(self, bg=palette.surface)
        shell.pack(fill="both", expand=True, padx=1, pady=1)
        self.header = tk.Frame(shell, bg=palette.surface)
        self.header.pack(fill="x", padx=px(24), pady=(px(16), 0))
        self.title_label = tk.Label(self.header, text=title, bg=palette.surface,
                                    fg=palette.text, font=font(13, "bold"))
        self.title_label.pack(side="left")
        close = tk.Label(self.header, text="×", bg=palette.surface,
                         fg=palette.text_muted, font=font(14), cursor="hand2",
                         padx=px(6))
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.close())
        tk.Frame(shell, bg=palette.border, height=1).pack(fill="x", padx=px(24),
                                                          pady=(px(12), 0))
        self.body = tk.Frame(shell, bg=palette.surface)
        self.body.pack(fill="both", expand=True, padx=px(24), pady=(px(16), 0))
        self.footer = tk.Frame(shell, bg=palette.surface)
        self.footer.pack(fill="x", padx=px(24), pady=(px(8), px(18)))
        for widget in (self.header, self.title_label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
        self.bind("<Escape>", lambda e: self.close())

    def _drag_start(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event):
        if self._drag:
            x = event.x_root - self._drag[0]
            y = event.y_root - self._drag[1]
            self.geometry("+%d+%d" % (x, y))

    def show(self):
        self.deiconify()
        self.lift()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()
        self.wait_window()
        return self.result

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        try:
            self._parent.focus_set()
        except tk.TclError:
            pass


def _section_label(master, palette, text):
    label = FieldLabel(master, palette, text)
    label.pack(anchor="w", pady=(px(12), px(6)))
    return label


class TxDialog(_Modal):
    def __init__(self, parent, palette, store, tx=None, default_kind="expense",
                 default_date=None):
        title = "编辑记录" if tx else "记一笔"
        super().__init__(parent, palette, title, 460, 520)
        self.store = store
        self.tx = tx or {}
        self.kind = self.tx.get("kind") or default_kind
        self._error_visible = False
        body = self.body

        self.segmented = Segmented(body, palette,
                                   [("expense", "支出"), ("income", "收入")],
                                   value=self.kind, command=self._kind_changed)
        self.segmented.pack(anchor="w")

        _section_label(body, palette, "金额")
        box = tk.Frame(body, bg=palette.surface, highlightthickness=1,
                       highlightbackground=palette.border,
                       highlightcolor=palette.accent)
        box.pack(fill="x")
        tk.Label(box, text="¥", bg=palette.surface, fg=palette.text_muted,
                 font=font(16, "bold")).pack(side="left", padx=(px(12), px(2)))
        self.amount = tk.StringVar()
        self.amount_entry = tk.Entry(box, textvariable=self.amount, bd=0,
                                     bg=palette.surface, fg=palette.text,
                                     insertbackground=palette.accent,
                                     font=font(20, "bold"), highlightthickness=0,
                                     relief="flat")
        self.amount_entry.pack(side="left", fill="both", expand=True,
                               padx=(0, px(12)), pady=px(8))
        self.amount_entry.bind("<FocusIn>", lambda e: box.configure(
            highlightbackground=palette.accent))
        self.amount_entry.bind("<FocusOut>", lambda e: box.configure(
            highlightbackground=palette.border))
        self.amount_entry.bind("<Return>", lambda e: self.save())

        _section_label(body, palette, "分类")
        self.chips = ChipGroup(body, palette, [], bg=palette.surface)
        self.chips.pack(fill="x")

        row = tk.Frame(body, bg=palette.surface)
        row.pack(fill="x", pady=(px(12), 0))
        left = tk.Frame(row, bg=palette.surface)
        left.pack(side="left", anchor="n")
        right = tk.Frame(row, bg=palette.surface)
        right.pack(side="left", fill="x", expand=True, padx=(px(16), 0))
        FieldLabel(left, palette, "日期").pack(anchor="w", pady=(0, px(6)))
        self.date = DateEntry(left, palette,
                              value=self.tx.get("date") or default_date or
                              dt.date.today().isoformat(), width=150)
        self.date.pack(anchor="w")
        FieldLabel(right, palette, "备注").pack(anchor="w", pady=(0, px(6)))
        self.note = EntryField(right, palette, width=18, size=10)
        self.note.pack(fill="x")
        self.note.bind("<Return>", lambda e: self.save())

        self.error = tk.Label(body, text="", bg=palette.surface, fg=palette.danger,
                              font=font(9), anchor="w", justify="left",
                              wraplength=px(400))
        self.error.pack(fill="x", pady=(px(8), 0))

        if tx:
            RoundButton(self.footer, palette, "删除", self._delete,
                        variant="link", size=9).pack(side="left")
        RoundButton(self.footer, palette, "保存", self.save).pack(side="right")
        RoundButton(self.footer, palette, "取消", self.close,
                      variant="ghost").pack(side="right", padx=(0, px(10)))

        if tx:
            self.amount.set(money.format_plain(tx["amount_cents"]))
            self.note.set(tx.get("note") or "")
        self._reload_categories()
        self.after_idle(self.amount_entry.focus_set)

    def _kind_changed(self, kind):
        self.kind = kind
        self._reload_categories()

    def _reload_categories(self):
        options = []
        for category in self.store.list_categories(self.kind):
            options.append({"value": category["id"], "label": category["name"],
                            "color": category["color"]})
        self.chips.set_options(options)
        current = self.tx.get("category_id") if self.tx.get("kind") == self.kind else None
        values = [option["value"] for option in options]
        if current not in values:
            current = values[0] if values else None
        if current is not None:
            self.chips.set(current)

    def _show_error(self, message):
        self.error.configure(text=message)
        self._error_visible = True

    def save(self):
        try:
            cents = money.parse_amount(self.amount.get())
        except ValueError as exc:
            self._show_error(str(exc))
            return
        date_s = self.date.get().strip()
        if not dates.is_valid_iso(date_s):
            self._show_error("日期格式应为 YYYY-MM-DD")
            return
        category_id = self.chips.get()
        if not category_id:
            self._show_error("请选择分类")
            return
        note = self.note.get()
        try:
            if self.tx:
                self.store.update_tx(self.tx["id"], date_s, cents, self.kind,
                                     category_id, note)
            else:
                self.store.add_tx(date_s, cents, self.kind, category_id, note)
        except StoreError as exc:
            self._show_error(str(exc))
            return
        self.result = "saved"
        self.close()

    def _delete(self):
        if not self.tx:
            return
        if not confirm(self, self.palette, "删除记录",
                       "删除后无法恢复，确定要删除这笔记录吗？",
                       ok_text="删除", danger=True):
            return
        self.store.delete_tx(self.tx["id"])
        self.result = "deleted"
        self.close()


class ColorPicker(tk.Frame):
    def __init__(self, master, palette, colors, value, columns=6):
        bg = master.cget("bg")
        super().__init__(master, bg=bg)
        self.palette = palette
        self.value = value or colors[0]
        self._cells = {}
        size = px(30)
        for index, color in enumerate(colors):
            cell = tk.Canvas(self, width=size + px(8), height=size + px(8),
                             bg=bg, bd=0, highlightthickness=0, cursor="hand2")
            cell.grid(row=index // columns, column=index % columns,
                      padx=(0, px(6)), pady=(0, px(6)))
            cell.bind("<Button-1>", lambda e, c=color: self.set(c))
            self._cells[color] = cell
        self._draw()

    def set(self, color):
        self.value = color
        self._draw()

    def get(self):
        return self.value

    def _draw(self):
        p = self.palette
        for color, cell in self._cells.items():
            cell.delete("all")
            size = px(30)
            pad = px(4)
            if color == self.value:
                cell.create_oval(0, 0, size + 2 * pad, size + 2 * pad,
                                 outline=p.text, width=2)
            cell.create_oval(pad, pad, size + pad, size + pad,
                             fill=color, outline=color)


class CategoryDialog(_Modal):
    def __init__(self, parent, palette, store, category=None):
        title = "编辑分类" if category else "新增分类"
        super().__init__(parent, palette, title, 400, 380)
        self.store = store
        self.category = category or {}
        body = self.body
        self.kind = self.category.get("kind") or "expense"

        FieldLabel(body, palette, "名称").pack(anchor="w", pady=(0, px(6)))
        self.name = EntryField(body, palette, width=18, size=11)
        self.name.pack(fill="x")
        if category:
            self.name.set(category["name"])
            self.name.bind("<Return>", lambda e: self.save())
        else:
            self.name.focus()

        if category:
            kind_label = "支出分类" if self.kind == "expense" else "收入分类"
            FieldLabel(body, palette, kind_label).pack(anchor="w",
                                                       pady=(px(14), px(4)))
        else:
            FieldLabel(body, palette, "类型").pack(anchor="w", pady=(px(14), px(6)))
            self.segmented = Segmented(body, palette,
                                       [("expense", "支出"), ("income", "收入")],
                                       value=self.kind,
                                       command=lambda v: setattr(self, "kind", v))
            self.segmented.pack(anchor="w")

        FieldLabel(body, palette, "颜色").pack(anchor="w", pady=(px(14), px(6)))
        self.colors = ColorPicker(body, palette, CATEGORY_COLORS,
                                  self.category.get("color"))
        self.colors.pack(anchor="w")

        self.error = tk.Label(body, text="", bg=palette.surface, fg=palette.danger,
                              font=font(9), anchor="w", justify="left",
                              wraplength=px(340))
        self.error.pack(fill="x", pady=(px(10), 0))

        if category:
            RoundButton(self.footer, palette, "删除", self._delete,
                        variant="link", size=9).pack(side="left")
        RoundButton(self.footer, palette, "保存", self.save).pack(side="right")
        RoundButton(self.footer, palette, "取消", self.close,
                      variant="ghost").pack(side="right", padx=(0, px(10)))

    def _show_error(self, message):
        self.error.configure(text=message)

    def save(self):
        name = self.name.get().strip()
        if not name:
            self._show_error("请输入分类名称")
            return
        color = self.colors.get()
        try:
            if self.category:
                self.store.update_category(self.category["id"], name=name, color=color)
            else:
                self.store.add_category(name, self.kind, color)
        except StoreError as exc:
            self._show_error(str(exc))
            return
        self.result = "saved"
        self.close()

    def _delete(self):
        if not self.category:
            return
        if not confirm(self, self.palette, "删除分类",
                       "确定要删除“%s”分类吗？" % self.category["name"],
                       ok_text="删除", danger=True):
            return
        try:
            self.store.delete_category(self.category["id"])
        except CategoryInUse as exc:
            self._show_error("该分类下还有 %d 笔记录，不能删除" % exc.count)
            return
        except StoreError as exc:
            self._show_error(str(exc))
            return
        self.result = "deleted"
        self.close()

