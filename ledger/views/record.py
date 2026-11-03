"""记账页：快速记一笔 + 今日清单."""
from __future__ import annotations

import datetime as dt
import tkinter as tk

from .. import dates, money
from ..theme import font, px
from ..widgets import (ChipGroup, DateEntry, EmptyState, EntryField, FieldLabel,
                       RoundButton, RoundedCard, ScrollFrame, SectionHeader,
                       Segmented, StatCard)
from .common import (amount_field, bind_click, hover_row, page_header, truncate)


class RecordView(tk.Frame):
    def __init__(self, master, app):
        self.app = app
        self.store = app.store
        self.palette = app.palette
        super().__init__(master, bg=self.palette.bg)
        self.kind = "expense"
        self._rows = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        p = self.palette
        outer = tk.Frame(self, bg=p.bg)
        outer.pack(fill="both", expand=True, padx=px(28), pady=(px(24), px(22)))
        self.header = page_header(outer, p, "记账", "")
        self.header.pack(fill="x")
        self.subtitle = self.header.winfo_children()[1]
        self.subtitle.configure(text=self._date_line())

        columns = tk.Frame(outer, bg=p.bg)
        columns.pack(fill="both", expand=True, pady=(px(16), 0))
        columns.columnconfigure(0, weight=0, minsize=px(412))
        columns.columnconfigure(1, weight=1)
        columns.rowconfigure(0, weight=1)

        form_card = RoundedCard(columns, p, padding=22)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        self._build_form(form_card.body)

        list_card = RoundedCard(columns, p, padding=20)
        list_card.grid(row=0, column=1, sticky="nsew")
        self._build_today(list_card.body)

    def _build_form(self, body):
        p = self.palette
        SectionHeader(body, p, "快速记账", "按 Enter 即可保存").pack(fill="x")
        self.segmented = Segmented(body, p, [("expense", "支出"), ("income", "收入")],
                                   value=self.kind, command=self._kind_changed)
        self.segmented.pack(anchor="w", pady=(px(16), 0))

        FieldLabel(body, p, "金额").pack(anchor="w", pady=(px(16), px(6)))
        self.amount_var = tk.StringVar()
        box, self.amount_entry = amount_field(body, p, self.amount_var, size=20)
        box.pack(fill="x")
        self.amount_entry.bind("<Return>", lambda e: self._save())

        FieldLabel(body, p, "分类").pack(anchor="w", pady=(px(14), px(6)))
        self.chips = ChipGroup(body, p, [], bg=p.surface)
        self.chips.pack(fill="x")

        row = tk.Frame(body, bg=p.surface)
        row.pack(fill="x", pady=(px(14), 0))
        left = tk.Frame(row, bg=p.surface)
        left.pack(side="left", anchor="n")
        right = tk.Frame(row, bg=p.surface)
        right.pack(side="left", fill="x", expand=True, padx=(px(14), 0))
        FieldLabel(left, p, "日期").pack(anchor="w", pady=(0, px(6)))
        self.date = DateEntry(left, p, value=dates.iso(dt.date.today()), width=140)
        self.date.pack(anchor="w")
        FieldLabel(right, p, "备注").pack(anchor="w", pady=(0, px(6)))
        self.note = EntryField(right, p, width=14, size=10)
        self.note.pack(fill="x")
        self.note.bind("<Return>", lambda e: self._save())

        self.save_button = RoundButton(body, p, "保存这一笔", self._save, height=40,
                                       size=11, bold=True)
        self.save_button.pack(fill="x", pady=(px(20), 0))

    def _build_today(self, body):
        p = self.palette
        head = tk.Frame(body, bg=p.surface)
        head.pack(fill="x")
        tk.Label(head, text="今日清单", bg=p.surface, fg=p.text,
                 font=font(13, "bold")).pack(side="left")
        self.today_total = tk.Label(head, text="", bg=p.surface, fg=p.text_muted,
                                    font=font(9))
        self.today_total.pack(side="right")
        tk.Label(body, text="点击一条记录可以修改或删除", bg=p.surface,
                 fg=p.text_muted, font=font(9)).pack(
                     anchor="w", pady=(px(2), px(12)))
        self.today_scroll = ScrollFrame(body, p, bg=p.surface)
        self.today_scroll.pack(fill="both", expand=True)
        self._rows = []

    # ------------------------------------------------------------------ content
    def _date_line(self):
        today = dt.date.today()
        return "%d年%d月%d日 · 周%s" % (today.year, today.month, today.day,
                                       dates.weekday_cn(today))

    def _load_categories(self, preferred=None):
        self.categories = self.store.list_categories(self.kind)
        options = [{"value": c["id"], "label": c["name"], "color": c["color"]}
                   for c in self.categories]
        previous = preferred if preferred is not None else self.chips.get()
        self.chips.set_options(options)
        values = [c["id"] for c in self.categories]
        if previous not in values:
            previous = values[0] if values else None
        if previous is not None:
            self.chips.set(previous)

    def _kind_changed(self, kind):
        self.kind = kind
        self._load_categories(preferred=None)

    def refresh(self):
        self.subtitle.configure(text=self._date_line())
        self._load_categories()
        self._refresh_today()

    def on_show(self):
        self.refresh()
        try:
            self.amount_entry.focus_set()
        except tk.TclError:
            pass

    def _refresh_today(self):
        p = self.palette
        body = self.today_scroll.body
        for child in body.winfo_children():
            child.destroy()
        self._rows = []
        today = dates.iso(dt.date.today())
        summary = self.store.summary(today, today)
        self.today_total.configure(
            text="支出 %s · 收入 %s" % (money.format_cents(summary["expense_cents"]),
                                        money.format_cents(summary["income_cents"])))
        rows = self.store.list_tx(today, today, order="date_desc")
        if not rows:
            EmptyState(body, p, "今天还没有记账", "在上方表单记下第一笔吧").pack(
                pady=(px(28), 0))
        else:
            for index, tx in enumerate(rows):
                self._add_row(body, tx)
                if index < len(rows) - 1:
                    tk.Frame(body, bg=p.border, height=1).pack(fill="x", padx=px(2))
        self.today_scroll.bind_tree()

    def _add_row(self, body, tx):
        p = self.palette
        row = tk.Frame(body, bg=p.surface)
        row.pack(fill="x")
        inner = tk.Frame(row, bg=p.surface)
        inner.pack(fill="x", padx=px(2), pady=px(11))
        dot = tk.Canvas(inner, width=px(10), height=px(10), bg=p.surface, bd=0,
                        highlightthickness=0)
        dot.pack(side="left", padx=(px(2), px(10)))
        dot.create_oval(0, 0, px(9), px(9), fill=tx["category_color"],
                        outline=tx["category_color"])
        text = tk.Frame(inner, bg=p.surface)
        text.pack(side="left", fill="x", expand=True)
        title = tx["category_name"]
        if tx.get("note"):
            title += " · " + truncate(tx["note"], 14)
        tk.Label(text, text=title, bg=p.surface, fg=p.text, font=font(10),
                 anchor="w").pack(anchor="w")
        tk.Label(text, text=tx["date"], bg=p.surface,
                 fg=p.text_muted, font=font(8),
                 anchor="w").pack(anchor="w", pady=(px(2), 0))
        color = p.danger if tx["kind"] == "expense" else p.success
        tk.Label(inner, text=money.format_signed(tx["amount_cents"], tx["kind"]),
                 bg=p.surface, fg=color, font=font(11, "bold"),
                 anchor="e").pack(side="right")
        hover_row(row, p.surface, p.surface_alt)
        bind_click(row, lambda e, tx_id=tx["id"]: self._edit(tx_id))
        self._rows.append(row)

    # ------------------------------------------------------------------ actions
    def _edit(self, tx_id):
        from ..dialogs import TxDialog
        tx = self.store.get_tx(tx_id)
        if not tx:
            return
        dialog = TxDialog(self.winfo_toplevel(), self.palette, self.store, tx=tx)
        result = dialog.show()
        if result:
            self.refresh()
            self.app.toast.show("记录已更新" if result == "saved" else "记录已删除",
                                "success")

    def _save(self):
        p = self.palette
        try:
            cents = money.parse_amount(self.amount_var.get())
        except ValueError as exc:
            self.app.toast.show(str(exc), "error")
            return
        date_s = self.date.get()
        if not dates.is_valid_iso(date_s):
            self.app.toast.show("日期格式应为 YYYY-MM-DD", "error")
            return
        category_id = self.chips.get()
        if not category_id:
            self.app.toast.show("请选择分类", "error")
            return
        try:
            self.store.add_tx(date_s, cents, self.kind, category_id, self.note.get())
        except Exception as exc:
            self.app.toast.show(str(exc), "error")
            return
        self.amount_var.set("")
        self.note.set("")
        self._refresh_today()
        self.app.toast.show("已记一笔 %s" % money.format_cents(cents), "success")
        self.amount_entry.focus_set()
