"""统计页：日/月/年额度、趋势与分类构成."""
from __future__ import annotations

import datetime as dt
import tkinter as tk

from .. import dates, money
from ..charts import BarChart, DonutChart
from ..theme import font, px
from ..widgets import (RoundButton, RoundedCard, ScrollFrame, SectionHeader,
                       Segmented, StatCard)
from .common import page_header


class StatsView(tk.Frame):
    def __init__(self, master, app):
        self.app = app
        self.store = app.store
        self.palette = app.palette
        super().__init__(master, bg=self.palette.bg)
        self.period = "days"
        self._bar_sig = None
        self._donut_sig = None
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        p = self.palette
        outer = tk.Frame(self, bg=p.bg)
        outer.pack(fill="both", expand=True)
        head = tk.Frame(outer, bg=p.bg)
        head.pack(fill="x", padx=px(28), pady=(px(24), px(10)))
        self.header = page_header(head, p, "统计", "")
        self.header.pack(fill="x")
        self.subtitle = self.header.winfo_children()[1]

        self.scroll = ScrollFrame(outer, p, bg=p.bg)
        self.scroll.pack(fill="both", expand=True, padx=(px(28), px(14)),
                         pady=(0, px(18)))
        content = tk.Frame(self.scroll.body, bg=p.bg)
        content.pack(fill="both", expand=True)

        stats = tk.Frame(content, bg=p.bg)
        stats.pack(fill="x")
        for column in range(3):
            stats.columnconfigure(column, weight=1, uniform="stat")
        self.today_card = StatCard(stats, p, "今日支出")
        self.today_card.grid(row=0, column=0, sticky="nsew", padx=(0, px(12)))
        self.month_card = StatCard(stats, p, "本月支出",
                                   accent="#F97316")
        self.month_card.grid(row=0, column=1, sticky="nsew", padx=(0, px(12)))
        self.year_card = StatCard(stats, p, "本年支出", accent="#7C3AED")
        self.year_card.grid(row=0, column=2, sticky="nsew")

        bar_card = RoundedCard(content, p, padding=18)
        bar_card.pack(fill="x", pady=(px(14), 0))
        trend_header = SectionHeader(bar_card.body, p, "支出趋势",
                                     "柱形为每个周期的支出合计")
        trend_header.pack(fill="x")
        self.period_seg = Segmented(
            trend_header.action_area, p,
            [("days", "近14天"), ("months", "近12月"), ("years", "近5年")],
            value=self.period, command=self._on_period)
        self.period_seg.pack(anchor="e")
        self.bar = BarChart(bar_card.body, p, height=230, bg=p.surface)
        self.bar.pack(fill="x", expand=True, pady=(px(10), 0))

        bottom = tk.Frame(content, bg=p.bg)
        bottom.pack(fill="both", expand=True, pady=(px(14), 0))
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=2)
        bottom.rowconfigure(0, weight=1)

        donut_card = RoundedCard(bottom, p, padding=18)
        donut_card.grid(row=0, column=0, sticky="nsew", padx=(0, px(12)))
        SectionHeader(donut_card.body, p, "本月分类", "按支出分类的占比").pack(fill="x")
        self.donut = DonutChart(donut_card.body, p, height=250, bg=p.surface)
        self.donut.pack(fill="both", expand=True, pady=(px(6), 0))

        overview = RoundedCard(bottom, p, padding=18)
        overview.grid(row=0, column=1, sticky="nsew")
        SectionHeader(overview.body, p, "本月概览", "").pack(fill="x")
        self.metrics = {}
        rows = [("income", "收入"), ("expense", "支出"), ("balance", "结余"),
                ("avg", "日均支出"), ("max", "最大单笔")]
        for index, (key, label) in enumerate(rows):
            if index:
                tk.Frame(overview.body, bg=p.border, height=1).pack(
                    fill="x", pady=px(10))
            self._metric_row(overview.body, key, label)

    def _metric_row(self, body, key, label):
        p = self.palette
        row = tk.Frame(body, bg=p.surface)
        row.pack(fill="x", pady=(px(12), 0))
        left = tk.Frame(row, bg=p.surface)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=label, bg=p.surface, fg=p.text_muted,
                 font=font(9), anchor="w").pack(anchor="w")
        sub = tk.Label(left, text="", bg=p.surface, fg=p.text_muted,
                       font=font(8), anchor="w")
        sub.pack(anchor="w", pady=(px(2), 0))
        value = tk.Label(row, text="¥0.00", bg=p.surface, fg=p.text,
                         font=font(11, "bold"), anchor="e")
        value.pack(side="right", anchor="n", padx=(px(8), 0))
        self.metrics[key] = (value, sub)

    # ------------------------------------------------------------------ data
    def refresh(self):
        today = dt.date.today()
        self.subtitle.configure(text="截至 %d年%d月%d日 · 周%s" % (
            today.year, today.month, today.day, dates.weekday_cn(today)))
        month_start, month_end = dates.month_bounds(today.year, today.month)
        year_start, year_end = dates.year_bounds(today.year)
        iso_today = dates.iso(today)

        day_sum = self.store.summary(iso_today, iso_today)
        month_sum = self.store.summary(month_start, month_end)
        year_sum = self.store.summary(year_start, year_end)
        p = self.palette
        self.today_card.set_value(
            money.format_cents(day_sum["expense_cents"]),
            "共 %d 笔 · 收入 %s" % (day_sum["expense_count"],
                                    money.format_cents(day_sum["income_cents"])))
        self.month_card.set_value(
            money.format_cents(month_sum["expense_cents"]),
            "共 %d 笔 · 结余 %s" % (month_sum["expense_count"],
                                    money.format_cents(month_sum["income_cents"] -
                                                       month_sum["expense_cents"])))
        self.year_card.set_value(
            money.format_cents(year_sum["expense_cents"]),
            "共 %d 笔 · 结余 %s" % (year_sum["expense_count"],
                                    money.format_cents(year_sum["income_cents"] -
                                                       year_sum["expense_cents"])))

        self._load_bars(today)
        self._load_donut(month_start, month_end)
        self._load_overview(today, month_start, month_end, month_sum)

    def on_show(self):
        self.refresh()

    def _on_period(self, value):
        self.period = value
        self._load_bars(dt.date.today())

    def _load_bars(self, today):
        if self.period == "days":
            start = today - dt.timedelta(days=13)
            values = self.store.daily_expense(dates.iso(start), dates.iso(today))
            data = [("%02d-%02d" % (day.month, day.day), values.get(dates.iso(day), 0))
                    for day in dates.date_range(start, today)]
        elif self.period == "months":
            first = today.replace(day=1)
            months = [dates.add_months(first, -offset) for offset in range(11, -1, -1)]
            cache = {}
            data = []
            for month in months:
                if month.year not in cache:
                    cache[month.year] = self.store.monthly_expense(month.year)
                cents = cache[month.year].get(month.month, 0)
                data.append(("%02d-%02d" % (month.year % 100, month.month), cents))
        else:
            values = self.store.yearly_expense()
            data = [("%d年" % year, values.get(year, 0))
                    for year in range(today.year - 4, today.year + 1)]
        signature = (self.period, tuple(data))
        if signature == self._bar_sig and self.bar._drawn:
            return
        self._bar_sig = signature
        self.bar.set_data(data, highlight=len(data) - 1)

    def _load_donut(self, start, end):
        items = self.store.category_breakdown(start, end, kind="expense")
        signature = tuple((item.get("name"), item.get("color"),
                           int(item.get("cents", 0)), int(item.get("count", 0)))
                          for item in items)
        if signature == self._donut_sig and self.donut._drawn:
            return
        self._donut_sig = signature
        self.donut.set_data(items, center_label="本月支出")

    def _load_overview(self, today, start, end, summary):
        p = self.palette
        income = summary["income_cents"]
        expense = summary["expense_cents"]
        balance = income - expense
        avg = expense // max(1, today.day)
        self.metrics["income"][0].configure(text=money.format_cents(income),
                                            fg=p.success)
        self.metrics["income"][1].configure(text="本月累计收入")
        self.metrics["expense"][0].configure(text=money.format_cents(expense),
                                             fg=p.text)
        self.metrics["expense"][1].configure(text="共 %d 笔" % summary["expense_count"])
        self.metrics["balance"][0].configure(
            text=money.format_cents(balance),
            fg=p.success if balance >= 0 else p.danger)
        self.metrics["balance"][1].configure(text="收入减去支出")
        self.metrics["avg"][0].configure(text=money.format_cents(avg), fg=p.text)
        self.metrics["avg"][1].configure(text="按本月已过 %d 天计算" % today.day)
        top = self.store.max_expense(start, end)
        if top:
            self.metrics["max"][0].configure(
                text=money.format_cents(top["amount_cents"]), fg=p.text)
            caption = top["category_name"]
            if top.get("date"):
                caption += " · " + top["date"][5:]
            self.metrics["max"][1].configure(text=caption)
        else:
            self.metrics["max"][0].configure(text="¥0.00", fg=p.text)
            self.metrics["max"][1].configure(text="本月还没有支出")
