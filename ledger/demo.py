"""Generate a few months of believable demo data."""
from __future__ import annotations

import datetime as dt
import random

from . import dates

NOTES = {
    "餐饮": ["早餐", "午饭", "晚饭", "咖啡", "外卖", "水果", "面包"],
    "交通": ["地铁", "公交", "打车", "共享单车", "加油"],
    "购物": ["日用品", "衣服", "家居", "数码配件", "超市"],
    "居住": ["房租", "水电费", "物业费", "宽带"],
    "娱乐": ["电影", "音乐会员", "游戏", "周末出游"],
    "医疗": ["感冒药", "体检", "挂号"],
    "教育": ["买书", "网课", "文具"],
    "人情": ["红包", "请客", "礼物"],
    "其他": ["杂项", "临时支出"],
}


def _cats(store, kind):
    return {category["name"]: category["id"]
            for category in store.list_categories(kind)}


def ensure_seeded(store):
    """Populate an empty database with ~3 months of demo records."""
    if store.stats().get("tx", 0) > 0:
        return 0
    return seed(store)


def seed(store, days=90):
    rng = random.Random(20261103)
    expense = _cats(store, "expense")
    income = _cats(store, "income")
    today = dt.date.today()
    start = today - dt.timedelta(days=days - 1)
    count = 0

    def add(day, kind, category_name, cents, note):
        nonlocal count
        category_id = (expense if kind == "expense" else income).get(category_name)
        if category_id is None:
            return
        store.add_tx(dates.iso(day), int(cents), kind, category_id, note)
        count += 1

    def pick_note(name):
        return rng.choice(NOTES.get(name, [""]))

    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        # 餐饮：几乎每天 1-2 笔
        add(day, "expense", "餐饮", rng.randint(1200, 6800), pick_note("餐饮"))
        if rng.random() < 0.45:
            add(day, "expense", "餐饮", rng.randint(800, 3600), pick_note("餐饮"))
        # 交通
        if rng.random() < 0.55:
            add(day, "expense", "交通", rng.randint(300, 2800), pick_note("交通"))
        # 购物 / 娱乐 / 医疗 / 教育 / 人情
        if rng.random() < 0.22:
            add(day, "expense", "购物", rng.randint(3000, 48000), pick_note("购物"))
        if rng.random() < 0.12:
            add(day, "expense", "娱乐", rng.randint(2000, 18000), pick_note("娱乐"))
        if rng.random() < 0.04:
            add(day, "expense", "医疗", rng.randint(1500, 9000), pick_note("医疗"))
        if rng.random() < 0.05:
            add(day, "expense", "教育", rng.randint(3000, 20000), pick_note("教育"))
        if rng.random() < 0.05:
            add(day, "expense", "人情", rng.randint(5000, 30000), pick_note("人情"))
        # 固定支出
        if day.day == 1:
            add(day, "expense", "居住", 180000, "房租")
        if day.day == 5:
            add(day, "expense", "居住", rng.randint(8000, 16000), "水电费")
        # 收入
        if day.day == 10:
            add(day, "income", "工资", 880000, "月薪")
        if day.day == 15 and rng.random() < 0.8:
            add(day, "income", "兼职", rng.randint(30000, 90000), "兼职收入")
        if day.day == 20 and rng.random() < 0.7:
            add(day, "income", "理财", rng.randint(5000, 30000), "理财收益")
        if day.day == 28 and rng.random() < 0.3:
            add(day, "income", "奖金", rng.randint(20000, 60000), "项目奖金")

    return count


if __name__ == "__main__":
    import sys

    from .db import Store

    path = sys.argv[1] if len(sys.argv) > 1 else "data/demo.db"
    store = Store(path)
    print("seeded", seed(store), "records into", path)
    store.close()
