"""明细页：筛选、浏览、编辑与删除记录."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from .. import dates, money
from ..theme import font, px
from ..widgets import (DateEntry, Dropdown, EmptyState, EntryField, FieldLabel,
                       RoundButton, RoundedCard, SectionHeader, Segmented, confirm)
from .common import page_header, truncate


RANGES = [("today", "今日"), ("month", "本月"), ("year", "本年"),
          ("all", "全部"), ("custom", "自定义")]


class TransactionsView(tk.Frame):
    def __init__(self, master, app):
        self.app = app
        self.store = app.store
        self.palette = app.palette
        super().__init__(master, bg=self.palette.bg)
        self.range_value = "month"
        self.kind_value = "all"
        self.category_value = None
        self.rows = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        p = self.palette
        outer = tk.Frame(self, bg=p.bg)
        outer.pack(fill="both", expand=True, padx=px(28), pady=(px(24), px(22)))
        self.header = page_header(outer, p, "明细", "")
        self.header.pack(fill="x")
        self.subtitle = self.header.winfo_children()[1]
        self.subtitle.configure(text=self._subtitle())

        filters = RoundedCard(outer, p, padding=16)
        filters.pack(fill="x", pady=(px(16), px(14)))
        self._build_filters(filters.body)

        self.list_card = RoundedCard(outer, p, padding=16)
        self.list_card.pack(fill="both", expand=True)
        self._build_list(self.list_card.body)

    def _build_filters(self, body):
        p = self.palette
        top = tk.Frame(body, bg=p.surface)
        top.pack(fill="x")
        self.range_seg = Segmented(top, p, RANGES, value=self.range_value,
                                   command=self._on_range)
        self.range_seg.pack(side="left")
        RoundButton(top, p, "重置筛选", self._reset, variant="link", height=30,
                    size=9).pack(side="right")

        controls = tk.Frame(body, bg=p.surface)
        controls.pack(fill="x", pady=(px(14), 0))

        kind_box = tk.Frame(controls, bg=p.surface)
        kind_box.pack(side="left", padx=(0, px(14)))
        FieldLabel(kind_box, p, "类型").pack(anchor="w", pady=(0, px(5)))
        self.kind_dd = Dropdown(
            kind_box, p,
            [("all", "全部"), ("expense", "支出"), ("income", "收入")],
            value=self.kind_value, command=self._on_kind, width=104, size=9)
        self.kind_dd.pack(anchor="w")

        cat_box = tk.Frame(controls, bg=p.surface)
        cat_box.pack(side="left", padx=(0, px(14)))
        FieldLabel(cat_box, p, "分类").pack(anchor="w", pady=(0, px(5)))
        self.cat_dd = Dropdown(cat_box, p, [("", "全部分类")], value=None,
                               command=self._on_category, width=132, size=9)
        self.cat_dd.pack(anchor="w")

        kw_box = tk.Frame(controls, bg=p.surface)
        kw_box.pack(side="left", fill="x", expand=True, padx=(0, px(10)))
        FieldLabel(kw_box, p, "关键词").pack(anchor="w", pady=(0, px(5)))
        kw_row = tk.Frame(kw_box, bg=p.surface)
        kw_row.pack(fill="x")
        self.keyword = EntryField(kw_row, p, width=16, size=10)
        self.keyword.pack(side="left", fill="x", expand=True)
        self.keyword.bind("<Return>", lambda e: self._reload())
        RoundButton(kw_row, p, "查询", self._reload, height=34, width=64,
                    size=9).pack(side="left", padx=(px(8), 0))

        self.custom_row = tk.Frame(body, bg=p.surface)
        FieldLabel(self.custom_row, p, "起始日期").pack(side="left", padx=(0, px(8)))
        self.from_date = DateEntry(self.custom_row, p, width=130)
        self.from_date.pack(side="left")
        tk.Label(self.custom_row, text="至", bg=p.surface, fg=p.text_muted,
                 font=font(9)).pack(side="left", padx=px(8))
        self.to_date = DateEntry(self.custom_row, p, width=130)
        self.to_date.pack(side="left")
        RoundButton(self.custom_row, p, "应用", self._reload, height=34, width=64,
                    size=9).pack(side="left", padx=(px(10), 0))

    def _build_list(self, body):
        p = self.palette
        head = tk.Frame(body, bg=p.surface)
        head.pack(fill="x", pady=(0, px(10)))
        self.list_title = tk.Label(head, text="记录", bg=p.surface, fg=p.text,
                                   font=font(12, "bold"))
        self.list_title.pack(side="left")
        self.list_total = tk.Label(head, text="", bg=p.surface, fg=p.text_muted,
                                   font=font(9))
        self.list_total.pack(side="left", padx=(px(12), 0))
        RoundButton(head, p, "删除", self._delete_selected, variant="soft",
                    height=30, width=60, size=9).pack(side="right")
        RoundButton(head, p, "编辑", self._edit_selected, variant="soft",
                    height=30, width=60, size=9).pack(side="right", padx=(0, px(8)))

        self.tree_box = tk.Frame(body, bg=p.surface)
        self.tree_box.pack(fill="both", expand=True)
        self.tree_box.columnconfigure(0, weight=1)
        self.tree_box.rowconfigure(0, weight=1)

        columns = ("date", "kind", "category", "note", "amount")
        self.tree = ttk.Treeview(self.tree_box, columns=columns, show="headings",
                                 style="Ledger.Treeview", selectmode="browse")
        headings = {"date": "日期", "kind": "类型", "category": "分类",
                    "note": "备注", "amount": "金额"}
        widths = {"date": 104, "kind": 56, "category": 100, "note": 260,
                  "amount": 110}
        for name in columns:
            self.tree.heading(name, text=headings[name],
                              anchor="e" if name == "amount" else "w")
            self.tree.column(name, width=px(widths[name]),
                             minwidth=px(56),
                             anchor="e" if name == "amount" else "w",
                             stretch=(name == "note"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("expense", foreground=p.danger)
        self.tree.tag_configure("income", foreground=p.success)
        self.tree.tag_configure("even", background=p.surface_alt)
        scroll = ttk.Scrollbar(self.tree_box, orient="vertical",
                               command=self.tree.yview,
                               style="Ledger.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())
        self.tree.bind("<Return>", lambda e: self._edit_selected())
        self.tree.bind("<Delete>", lambda e: self._delete_selected())

        self.empty_box = tk.Frame(body, bg=p.surface)
        EmptyState(self.empty_box, p, "没有符合条件的记录",
                   "试试调整筛选条件，或先记一笔").pack(pady=(px(30), 0))

    # ------------------------------------------------------------------ helpers
    def _subtitle(self):
        return "查看、筛选并管理每一笔记录"

    def _bounds(self):
        today = dt.date.today()
        if self.range_value == "today":
            iso = dates.iso(today)
            return iso, iso
        if self.range_value == "month":
            return dates.month_bounds(today.year, today.month)
        if self.range_value == "year":
            return dates.year_bounds(today.year)
        if self.range_value == "all":
            return None, None
        start = self.from_date.get()
        end = self.to_date.get()
        if not dates.is_valid_iso(start) or not dates.is_valid_iso(end):
            return False
        if start > end:
            return False
        return start, end

    def _load_categories(self):
        cats = self.store.list_categories(None)
        if self.kind_value == "all":
            options = [(None, "全部分类")]
            for c in cats:
                suffix = "（支出）" if c["kind"] == "expense" else "（收入）"
                options.append((c["id"], c["name"] + suffix))
        else:
            options = [(None, "全部分类")]
            for c in cats:
                if c["kind"] == self.kind_value:
                    options.append((c["id"], c["name"]))
        values = [value for value, _ in options]
        if self.category_value not in values:
            self.category_value = None
        self.cat_dd.set_options(options)
        self.cat_dd.set(self.category_value)

    def refresh(self):
        self._load_categories()
        self._reload()

    def on_show(self):
        self.refresh()

    # ------------------------------------------------------------------ filters
    def _on_range(self, value):
        self.range_value = value
        if value == "custom":
            if not self.from_date.get() or not dates.is_valid_iso(self.from_date.get()):
                self.from_date.set(self._month_first())
            if not self.to_date.get() or not dates.is_valid_iso(self.to_date.get()):
                self.to_date.set(dates.iso(dt.date.today()))
            self.custom_row.pack(fill="x", pady=(px(12), 0))
        else:
            self.custom_row.pack_forget()
        self._reload()

    def _on_kind(self, value):
        self.kind_value = value
        self.category_value = None
        self._load_categories()
        self._reload()

    def _on_category(self, value):
        self.category_value = value
        self._reload()

    def _reset(self):
        self.range_value = "month"
        self.range_seg.set("month")
        self.custom_row.pack_forget()
        self.kind_value = "all"
        self.kind_dd.set("all")
        self.category_value = None
        self.keyword.set("")
        self._load_categories()
        self._reload()

    def _month_first(self):
        today = dt.date.today()
        return dates.iso(today.replace(day=1))

    # ------------------------------------------------------------------ data
    def _reload(self):
        bounds = self._bounds()
        if bounds is False:
            self.app.toast.show("请填写有效的日期范围", "error")
            return
        start, end = bounds
        kind = None if self.kind_value == "all" else self.kind_value
        keyword = self.keyword.get().strip() or None
        self.rows = self.store.list_tx(start, end, kind=kind,
                                       category_id=self.category_value,
                                       keyword=keyword)
        for item in self.tree.get_children():
            self.tree.delete(item)
        expense = income = 0
        for index, tx in enumerate(self.rows):
            if tx["kind"] == "expense":
                expense += tx["amount_cents"]
            else:
                income += tx["amount_cents"]
            tags = [tx["kind"]]
            if index % 2 == 1:
                tags.append("even")
            self.tree.insert("", "end", iid=str(tx["id"]), tags=tags, values=(
                tx["date"],
                "支出" if tx["kind"] == "expense" else "收入",
                tx["category_name"],
                truncate(tx.get("note") or "", 40),
                money.format_signed(tx["amount_cents"], tx["kind"]),
            ))
        self.list_title.configure(text="记录 %d 笔" % len(self.rows))
        self.list_total.configure(
            text="支出 %s · 收入 %s · 结余 %s" % (
                money.format_cents(expense), money.format_cents(income),
                money.format_cents(income - expense)))
        if self.rows:
            self.empty_box.pack_forget()
            self.tree_box.pack(fill="both", expand=True)
        else:
            self.tree_box.pack_forget()
            self.empty_box.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ actions
    def _selected_id(self):
        selection = self.tree.selection()
        if not selection:
            self.app.toast.show("请先选择一条记录", "error")
            return None
        return int(selection[0])

    def _edit_selected(self):
        tx_id = self._selected_id()
        if tx_id is None:
            return
        tx = self.store.get_tx(tx_id)
        if not tx:
            return
        from ..dialogs import TxDialog
        dialog = TxDialog(self.winfo_toplevel(), self.palette, self.store, tx=tx)
        result = dialog.show()
        if result:
            self.refresh()
            self.app.toast.show("记录已更新" if result == "saved" else "记录已删除",
                                "success")

    def _delete_selected(self):
        tx_id = self._selected_id()
        if tx_id is None:
            return
        if not confirm(self.winfo_toplevel(), self.palette, "删除记录",
                       "确定要删除这条记录吗？删除后无法恢复。",
                       ok_text="删除", danger=True):
            return
        if self.store.delete_tx(tx_id):
            self.refresh()
            self.app.toast.show("记录已删除", "success")
