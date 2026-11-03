import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ledger.db import CategoryInUse, DuplicateName, Store, ValidationError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        self.store = Store(self.path)
        self.expense = {c["name"]: c for c in self.store.list_categories("expense")}
        self.income = {c["name"]: c for c in self.store.list_categories("income")}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def add(self, date_s, amount, category="餐饮", kind="expense", note=""):
        cats = self.expense if kind == "expense" else self.income
        return self.store.add_tx(date_s, amount, kind, cats[category]["id"], note)

    # ------------------------------------------------------------------ basics
    def test_seed_categories(self):
        self.assertEqual(len(self.expense), 9)
        self.assertEqual(len(self.income), 5)
        reopened = Store(self.path)
        try:
            self.assertEqual(len(reopened.list_categories()), 14)
        finally:
            reopened.close()

    def test_add_get_update_delete(self):
        tx_id = self.add("2026-11-03", 2550, note="午饭")
        row = self.store.get_tx(tx_id)
        self.assertEqual(row["category_name"], "餐饮")
        self.assertEqual(row["amount_cents"], 2550)
        self.store.update_tx(tx_id, "2026-11-04", 3000, "expense", self.expense["交通"]["id"], "打车")
        row = self.store.get_tx(tx_id)
        self.assertEqual(row["date"], "2026-11-04")
        self.assertEqual(row["category_name"], "交通")
        self.assertEqual(row["note"], "打车")
        self.assertTrue(self.store.delete_tx(tx_id))
        self.assertIsNone(self.store.get_tx(tx_id))

    def test_list_filters_and_keyword(self):
        self.add("2026-11-01", 1000, note="早餐")
        self.add("2026-11-02", 2000, note="100% 满足")
        self.add("2026-11-03", 3000, note="a_b")
        self.add("2026-11-03", 4000, category="工资", kind="income", note="axb")
        self.assertEqual(len(self.store.list_tx()), 4)
        self.assertEqual(len(self.store.list_tx(start="2026-11-02", end="2026-11-03")), 3)
        self.assertEqual(len(self.store.list_tx(kind="income")), 1)
        self.assertEqual(len(self.store.list_tx(category_id=self.expense["餐饮"]["id"])), 3)
        self.assertEqual(len(self.store.list_tx(keyword="早餐")), 1)
        self.assertEqual(len(self.store.list_tx(keyword="%")), 1)
        self.assertEqual(len(self.store.list_tx(keyword="_")), 1)
        self.assertEqual(len(self.store.list_tx(limit=2)), 2)

    def test_summary_and_series(self):
        self.add("2026-11-03", 1000)
        self.add("2026-11-03", 2500)
        self.add("2026-11-04", 3000, category="工资", kind="income")
        summary = self.store.summary("2026-11-01", "2026-11-30")
        self.assertEqual(summary["expense_cents"], 3500)
        self.assertEqual(summary["income_cents"], 3000)
        self.assertEqual(summary["count"], 3)
        daily = self.store.daily_expense("2026-11-03", "2026-11-05")
        self.assertEqual(daily, {"2026-11-03": 3500, "2026-11-04": 0, "2026-11-05": 0})
        monthly = self.store.monthly_expense(2026)
        self.assertEqual(len(monthly), 12)
        self.assertEqual(monthly[11], 3500)
        self.assertEqual(monthly[1], 0)
        yearly = self.store.yearly_expense()
        self.assertEqual(yearly[2026], 3500)

    def test_month_and_year_boundaries(self):
        self.add("2025-12-31", 1000)
        self.add("2026-01-01", 2000)
        self.assertEqual(self.store.summary("2026-01-01", "2026-12-31")["expense_cents"], 2000)
        self.assertEqual(self.store.monthly_expense(2026)[1], 2000)
        self.assertEqual(self.store.summary("2025-12-31", "2025-12-31")["expense_cents"], 1000)

    def test_max_expense(self):
        self.add("2026-11-03", 1000, note="small")
        self.add("2026-11-04", 9000, note="big")
        row = self.store.max_expense("2026-11-01", "2026-11-30")
        self.assertEqual(row["amount_cents"], 9000)
        self.assertEqual(row["note"], "big")

    def test_category_breakdown_merges_tail(self):
        amounts = [100, 200, 300, 400, 500, 600, 700, 800, 900]
        for (name, category), amount in zip(self.expense.items(), amounts):
            self.store.add_tx("2026-11-03", amount, "expense", category["id"], name)
        items = self.store.category_breakdown("2026-11-03", "2026-11-03")
        self.assertEqual(len(items), 6)
        self.assertEqual(items[0]["name"], "其他")
        self.assertEqual(items[0]["cents"], 1500)
        self.assertEqual(sum(item["cents"] for item in items), sum(amounts))
        self.assertAlmostEqual(sum(item["pct"] for item in items), 1.0, places=6)

    # ------------------------------------------------------------- categories
    def test_category_in_use_cannot_be_deleted(self):
        self.add("2026-11-03", 1000)
        with self.assertRaises(CategoryInUse):
            self.store.delete_category(self.expense["餐饮"]["id"])

    def test_last_category_cannot_be_deleted(self):
        categories = self.store.list_categories("income")
        for category in categories[:-1]:
            self.store.delete_category(category["id"])
        with self.assertRaises(ValidationError):
            self.store.delete_category(categories[-1]["id"])

    def test_duplicate_and_validation(self):
        with self.assertRaises(DuplicateName):
            self.store.add_category("餐饮", "expense", "#123456")
        with self.assertRaises(ValidationError):
            self.store.add_category("", "expense", "#123456")
        with self.assertRaises(ValidationError):
            self.store.add_category("测试", "expense", "red")
        with self.assertRaises(ValidationError):
            self.add("2026-13-01", 1000)
        with self.assertRaises(ValidationError):
            self.add("2026-11-03", 0)
        with self.assertRaises(ValidationError):
            self.store.add_tx("2026-11-03", 100, "expense", self.income["工资"]["id"], "")
        with self.assertRaises(ValidationError):
            self.add("2026-11-03", 100, note="x" * 201)

    def test_category_usage_and_update(self):
        self.add("2026-11-03", 1000)
        self.assertEqual(self.store.category_usage(self.expense["餐饮"]["id"]), 1)
        self.store.update_category(self.expense["餐饮"]["id"], name="吃饭", color="#111111")
        self.assertEqual(self.store.get_category(self.expense["餐饮"]["id"])["name"], "吃饭")

    # ---------------------------------------------------------------- settings
    def test_settings(self):
        self.assertEqual(self.store.get_setting("theme.preset", "蓝白"), "蓝白")
        self.store.set_setting("theme.preset", "青碧")
        self.store.set_setting("theme.preset", "玫瑰")
        self.assertEqual(self.store.get_setting("theme.preset"), "玫瑰")

    # ------------------------------------------------------------------- files
    def test_export_csv(self):
        self.add("2026-11-03", 123456, note='=1+1, "quoted"')
        path = Path(self.tmp.name) / "out" / "data.csv"
        count = self.store.export_csv(str(path))
        self.assertEqual(count, 1)
        raw = path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], ["日期", "类型", "分类", "金额(元)", "备注"])
        self.assertEqual(rows[1][0], "2026-11-03")
        self.assertEqual(rows[1][2], "餐饮")
        self.assertEqual(rows[1][3], "1234.56")
        self.assertEqual(rows[1][4], "'=1+1, \"quoted\"")

    def test_backup(self):
        self.add("2026-11-03", 1000)
        backup_path = Path(self.tmp.name) / "backups" / "copy.db"
        self.store.backup(str(backup_path))
        self.assertTrue(backup_path.exists())
        copy = Store(backup_path)
        try:
            self.assertEqual(copy.stats()["tx"], 1)
        finally:
            copy.close()

    def test_stats(self):
        self.add("2026-11-03", 1000)
        stats = self.store.stats()
        self.assertEqual(stats["tx"], 1)
        self.assertEqual(stats["categories"], 14)
        self.assertEqual(stats["first_date"], "2026-11-03")


if __name__ == "__main__":
    unittest.main()
