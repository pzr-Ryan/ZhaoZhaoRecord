"""SQLite storage layer for 简账."""
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import dates
from .money import format_plain

SCHEMA_VERSION = 1

DEFAULT_EXPENSE = [
    ("餐饮", "#F97316"),
    ("交通", "#3B82F6"),
    ("购物", "#EC4899"),
    ("居住", "#8B5CF6"),
    ("娱乐", "#14B8A6"),
    ("医疗", "#EF4444"),
    ("教育", "#06B6D4"),
    ("人情", "#F59E0B"),
    ("其他", "#94A3B8"),
]

DEFAULT_INCOME = [
    ("工资", "#22C55E"),
    ("奖金", "#10B981"),
    ("理财", "#0EA5E9"),
    ("兼职", "#6366F1"),
    ("其他", "#94A3B8"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('expense', 'income')),
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_builtin INTEGER NOT NULL DEFAULT 0,
    UNIQUE(name, kind)
);

CREATE TABLE IF NOT EXISTS transactions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL CHECK(length(date) = 10),
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    kind TEXT NOT NULL CHECK(kind IN ('expense', 'income')),
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_cat ON transactions(category_id);

CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_KINDS = ("expense", "income")


class StoreError(Exception):
    """Base class for friendly storage errors."""


class ValidationError(StoreError):
    pass


class DuplicateName(StoreError):
    pass


class CategoryInUse(StoreError):
    def __init__(self, count):
        super().__init__("该分类下已有 %d 笔记录，无法删除" % count)
        self.count = count


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _escape_like(value):
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _clean_name(name):
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValidationError("请输入分类名称")
    if len(cleaned) > 20:
        raise ValidationError("分类名称最多 20 个字")
    if "\n" in cleaned or "\r" in cleaned:
        raise ValidationError("分类名称不能换行")
    return cleaned


def _clean_color(color):
    color = (color or "").strip()
    if not _COLOR_RE.match(color):
        raise ValidationError("颜色值格式不正确")
    return color.upper()


class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=3000")
        self._migrate()
        self._seed()

    # ------------------------------------------------------------------ schema
    def _migrate(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self.conn.executescript(SCHEMA)
            self.conn.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
            self.conn.commit()
        elif version > SCHEMA_VERSION:
            raise StoreError("数据文件版本高于程序版本，请升级程序后再打开")

    def _seed(self):
        count = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count:
            return
        with self.conn:
            order = 0
            for name, color in DEFAULT_EXPENSE:
                self.conn.execute(
                    "INSERT INTO categories(name, kind, color, sort_order, is_builtin) VALUES(?,?,?,?,1)",
                    (name, "expense", color, order),
                )
                order += 1
            order = 0
            for name, color in DEFAULT_INCOME:
                self.conn.execute(
                    "INSERT INTO categories(name, kind, color, sort_order, is_builtin) VALUES(?,?,?,?,1)",
                    (name, "income", color, order),
                )
                order += 1

    # -------------------------------------------------------------- categories
    def list_categories(self, kind=None):
        if kind:
            rows = self.conn.execute(
                "SELECT * FROM categories WHERE kind=? ORDER BY sort_order, id", (kind,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM categories ORDER BY kind, sort_order, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_category(self, category_id):
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (category_id,)
        ).fetchone()
        return dict(row) if row else None

    def add_category(self, name, kind, color):
        name = _clean_name(name)
        color = _clean_color(color)
        if kind not in _KINDS:
            raise ValidationError("分类类型不正确")
        exists = self.conn.execute(
            "SELECT id FROM categories WHERE name=? AND kind=?", (name, kind)
        ).fetchone()
        if exists:
            raise DuplicateName("已经有同名分类了")
        order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories WHERE kind=?", (kind,)
        ).fetchone()[0]
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO categories(name, kind, color, sort_order, is_builtin) VALUES(?,?,?,?,0)",
                (name, kind, color, order),
            )
        return cur.lastrowid

    def update_category(self, category_id, name=None, color=None, sort_order=None):
        current = self.get_category(category_id)
        if not current:
            raise ValidationError("分类不存在")
        name = _clean_name(current["name"] if name is None else name)
        color = _clean_color(current["color"] if color is None else color)
        sort_order = current["sort_order"] if sort_order is None else int(sort_order)
        exists = self.conn.execute(
            "SELECT id FROM categories WHERE name=? AND kind=? AND id<>?",
            (name, current["kind"], category_id),
        ).fetchone()
        if exists:
            raise DuplicateName("已经有同名分类了")
        with self.conn:
            self.conn.execute(
                "UPDATE categories SET name=?, color=?, sort_order=? WHERE id=?",
                (name, color, sort_order, category_id),
            )

    def delete_category(self, category_id):
        current = self.get_category(category_id)
        if not current:
            raise ValidationError("分类不存在")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE category_id=?", (category_id,)
        ).fetchone()[0]
        if count:
            raise CategoryInUse(count)
        same_kind = self.conn.execute(
            "SELECT COUNT(*) FROM categories WHERE kind=?", (current["kind"],)
        ).fetchone()[0]
        if same_kind <= 1:
            raise ValidationError("至少要保留一个%s分类" % ("支出" if current["kind"] == "expense" else "收入"))
        with self.conn:
            self.conn.execute("DELETE FROM categories WHERE id=?", (category_id,))

    def category_usage(self, category_id):
        return self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE category_id=?", (category_id,)
        ).fetchone()[0]

    # -------------------------------------------------------------- transactions
    def _validate_tx(self, date_s, amount_cents, kind, category_id, note):
        if not dates.is_valid_iso(date_s):
            raise ValidationError("日期格式应为 YYYY-MM-DD")
        if kind not in _KINDS:
            raise ValidationError("收支类型不正确")
        try:
            amount_cents = int(amount_cents)
        except (TypeError, ValueError):
            raise ValidationError("金额格式不正确") from None
        if amount_cents <= 0:
            raise ValidationError("金额必须大于 0")
        if amount_cents > 999_999_999:
            raise ValidationError("金额太大")
        category = self.get_category(category_id)
        if not category:
            raise ValidationError("请选择分类")
        if category["kind"] != kind:
            raise ValidationError("分类与收支类型不匹配")
        note = (note or "").strip()
        if len(note) > 200:
            raise ValidationError("备注最多 200 个字")
        return note

    def add_tx(self, date_s, amount_cents, kind, category_id, note=""):
        note = self._validate_tx(date_s, amount_cents, kind, category_id, note)
        now = _now()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO transactions(date, amount_cents, kind, category_id, note, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (date_s, int(amount_cents), kind, int(category_id), note, now, now),
            )
        return cur.lastrowid

    def update_tx(self, tx_id, date_s, amount_cents, kind, category_id, note=""):
        if not self.get_tx(tx_id):
            raise ValidationError("记录不存在")
        note = self._validate_tx(date_s, amount_cents, kind, category_id, note)
        with self.conn:
            self.conn.execute(
                "UPDATE transactions SET date=?, amount_cents=?, kind=?, category_id=?, note=?, updated_at=?"
                " WHERE id=?",
                (date_s, int(amount_cents), kind, int(category_id), note, _now(), tx_id),
            )

    def delete_tx(self, tx_id):
        with self.conn:
            cur = self.conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        return cur.rowcount > 0

    def get_tx(self, tx_id):
        row = self.conn.execute(
            "SELECT t.*, c.name AS category_name, c.color AS category_color"
            " FROM transactions t JOIN categories c ON c.id = t.category_id WHERE t.id=?",
            (tx_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_tx(self, start=None, end=None, kind=None, category_id=None, keyword=None,
                limit=None, order="date_desc"):
        clauses = []
        args = []
        if start:
            clauses.append("t.date >= ?")
            args.append(start)
        if end:
            clauses.append("t.date <= ?")
            args.append(end)
        if kind in _KINDS:
            clauses.append("t.kind = ?")
            args.append(kind)
        if category_id:
            clauses.append("t.category_id = ?")
            args.append(int(category_id))
        if keyword:
            clauses.append("t.note LIKE ? ESCAPE '\\'")
            args.append("%" + _escape_like(keyword.strip()) + "%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order_sql = {
            "date_desc": "t.date DESC, t.id DESC",
            "date_asc": "t.date ASC, t.id ASC",
            "amount_desc": "t.amount_cents DESC, t.id DESC",
            "amount_asc": "t.amount_cents ASC, t.id ASC",
        }.get(order, "t.date DESC, t.id DESC")
        sql = (
            "SELECT t.*, c.name AS category_name, c.color AS category_color"
            " FROM transactions t JOIN categories c ON c.id = t.category_id"
            + where
            + " ORDER BY "
            + order_sql
        )
        if limit:
            sql += " LIMIT ?"
            args.append(int(limit))
        return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    # ---------------------------------------------------------------- aggregates
    def summary(self, start, end):
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) AS c, COALESCE(SUM(amount_cents), 0) AS s"
            " FROM transactions WHERE date BETWEEN ? AND ? GROUP BY kind",
            (start, end),
        ).fetchall()
        result = {
            "expense_cents": 0,
            "income_cents": 0,
            "expense_count": 0,
            "income_count": 0,
            "count": 0,
        }
        for row in rows:
            if row["kind"] == "expense":
                result["expense_cents"] = int(row["s"])
                result["expense_count"] = int(row["c"])
            else:
                result["income_cents"] = int(row["s"])
                result["income_count"] = int(row["c"])
            result["count"] += int(row["c"])
        return result

    def daily_expense(self, start, end):
        rows = self.conn.execute(
            "SELECT date, SUM(amount_cents) AS s FROM transactions"
            " WHERE kind='expense' AND date BETWEEN ? AND ? GROUP BY date",
            (start, end),
        ).fetchall()
        found = {row["date"]: int(row["s"]) for row in rows}
        result = {}
        start_d = dates.parse_iso(start)
        end_d = dates.parse_iso(end)
        if not start_d or not end_d:
            return found
        for d in dates.date_range(start_d, end_d):
            key = dates.iso(d)
            result[key] = found.get(key, 0)
        return result

    def monthly_expense(self, year):
        rows = self.conn.execute(
            "SELECT substr(date, 1, 7) AS ym, SUM(amount_cents) AS s FROM transactions"
            " WHERE kind='expense' AND substr(date, 1, 4)=? GROUP BY ym",
            ("%04d" % year,),
        ).fetchall()
        found = {int(row["ym"][5:7]): int(row["s"]) for row in rows}
        return {month: found.get(month, 0) for month in range(1, 13)}

    def yearly_expense(self):
        rows = self.conn.execute(
            "SELECT substr(date, 1, 4) AS y, SUM(amount_cents) AS s FROM transactions"
            " WHERE kind='expense' GROUP BY y"
        ).fetchall()
        return {int(row["y"]): int(row["s"]) for row in rows}

    def max_expense(self, start, end):
        row = self.conn.execute(
            "SELECT t.date, t.amount_cents, t.note, c.name AS category_name"
            " FROM transactions t JOIN categories c ON c.id = t.category_id"
            " WHERE t.kind='expense' AND t.date BETWEEN ? AND ?"
            " ORDER BY t.amount_cents DESC, t.id DESC LIMIT 1",
            (start, end),
        ).fetchone()
        return dict(row) if row else None

    def category_breakdown(self, start, end, kind="expense"):
        rows = self.conn.execute(
            "SELECT c.id, c.name, c.color, SUM(t.amount_cents) AS s, COUNT(*) AS n"
            " FROM transactions t JOIN categories c ON c.id = t.category_id"
            " WHERE t.kind=? AND t.date BETWEEN ? AND ? GROUP BY c.id ORDER BY s DESC",
            (kind, start, end),
        ).fetchall()
        total = sum(int(row["s"]) for row in rows)
        items = []
        for row in rows:
            cents = int(row["s"])
            items.append({
                "name": row["name"],
                "color": row["color"],
                "cents": cents,
                "count": int(row["n"]),
                "pct": (cents / total) if total else 0.0,
            })
        if len(items) > 6:
            rest = items[6:]
            other_cents = sum(item["cents"] for item in rest)
            other_count = sum(item["count"] for item in rest)
            head = items[:6]
            existing = next((item for item in head if item["name"] == "其他"), None)
            if existing is not None:
                existing["cents"] += other_cents
                existing["count"] += other_count
                existing["pct"] = (existing["cents"] / total) if total else 0.0
            else:
                head.append({
                    "name": "其他",
                    "color": "#94A3B8",
                    "cents": other_cents,
                    "count": other_count,
                    "pct": (other_cents / total) if total else 0.0,
                })
            items = head
        return items

    # ----------------------------------------------------------------- settings
    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES(?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    # -------------------------------------------------------------- data tools
    def export_csv(self, path, start=None, end=None):
        rows = self.list_tx(start=start, end=end, order="date_asc")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["日期", "类型", "分类", "金额(元)", "备注"])
            for row in rows:
                note = row["note"] or ""
                if note[:1] in ("=", "+", "-", "@"):
                    note = "'" + note
                writer.writerow([
                    row["date"],
                    "支出" if row["kind"] == "expense" else "收入",
                    row["category_name"],
                    format_plain(row["amount_cents"]),
                    note,
                ])
        return len(rows)

    def backup(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        destination = sqlite3.connect(str(path))
        try:
            with destination:
                self.conn.backup(destination)
        finally:
            destination.close()
        return path

    def stats(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS tx, COALESCE(SUM(amount_cents), 0) AS total,"
            " MIN(date) AS first_date, MAX(date) AS last_date FROM transactions"
        ).fetchone()
        category_count = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        return {
            "tx": int(row["tx"]),
            "total_cents": int(row["total"]),
            "first_date": row["first_date"],
            "last_date": row["last_date"],
            "categories": int(category_count),
        }

    def close(self):
        if getattr(self, "conn", None) is not None:
            try:
                self.conn.commit()
            except sqlite3.Error:
                pass
            self.conn.close()
            self.conn = None
