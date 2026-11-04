"""End-to-end flow checks for 简账 (save, filter, delete, export, backup, themes)."""
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger import money  # noqa: E402
from ledger.app import App, enable_dpi_awareness  # noqa: E402
from ledger.theme import PRESETS  # noqa: E402


def settle(root, wait=0.15):
    root.update_idletasks()
    root.update()
    time.sleep(wait)
    root.update()


def clean(path):
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except OSError:
            pass


def main():
    enable_dpi_awareness()
    db = os.path.join("data", "flow.db")
    clean(db)
    app = App(db, demo=False)
    app.animate_pages = False
    root = app.root
    settle(root)
    store = app.store

    # ---- record: expense then income
    record = app.pages[0]
    assert record.chips.get(), "category chip should default to first category"
    record.amount_var.set("12.34")
    record.note.set("流程测试")
    record._save()
    settle(root)
    assert store.stats()["tx"] == 1
    tx = store.list_tx(None, None)[0]
    assert tx["amount_cents"] == 1234 and tx["note"] == "流程测试"
    assert len(record._rows) == 1

    record.amount_var.set("abc")
    record._save()
    settle(root)
    assert store.stats()["tx"] == 1, "invalid amount must not save"

    record._kind_changed("income")
    settle(root)
    record.amount_var.set("100")
    record.note.set("工资测试")
    record._save()
    settle(root)
    assert store.stats()["tx"] == 2

    # ---- transactions: filters, keyword, delete
    tv = app.pages[1]
    app.show_page(1)
    settle(root)
    tv.range_value = "month"
    tv._reload()
    assert len(tv.rows) == 2
    tv._on_kind("income")
    assert len(tv.rows) == 1 and tv.rows[0]["amount_cents"] == 10000
    tv._on_kind("all")
    tv.keyword.set("流程")
    tv._reload()
    assert len(tv.rows) == 1 and tv.rows[0]["note"] == "流程测试"
    tv.keyword.set("")
    tv.range_value = "custom"
    tv.from_date.set("2026-13-01")
    tv._reload()
    assert len(tv.rows) == 1, "invalid custom range should keep previous rows"
    tv._reset()
    assert tv.range_value == "month" and len(tv.rows) == 2

    first = tv.tree.get_children()[0]
    tv.tree.selection_set(first)
    import ledger.views.transactions as tv_module
    tv_module.confirm = lambda *a, **k: True
    tv._delete_selected()
    settle(root)
    assert store.stats()["tx"] == 1

    # ---- stats page refresh
    app.show_page(2)
    settle(root)
    assert app.pages[2].metrics["expense"][0].cget("text").startswith("¥")

    # ---- settings: export + backup + themes
    app.show_page(3)
    settle(root)
    settings = app.pages[3]
    import ledger.views.settings as settings_module
    csv_path = os.path.join("data", "flow-export.csv")
    db_backup = os.path.join("data", "flow-backup.db")
    for path in (csv_path, db_backup):
        try:
            os.remove(path)
        except OSError:
            pass
    settings_module.filedialog.asksaveasfilename = lambda **k: csv_path
    settings._export_csv()
    settle(root)
    with open(csv_path, "rb") as handle:
        raw = handle.read()
    assert raw.startswith(b"\xef\xbb\xbf"), "CSV must use UTF-8 BOM"
    assert raw.count(b"\n") >= 2, "CSV should contain header and rows"
    settings_module.filedialog.asksaveasfilename = lambda **k: db_backup
    settings._backup()
    settle(root)
    connection = sqlite3.connect(db_backup)
    try:
        backed_up = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        connection.close()
    assert backed_up == 1

    for preset in PRESETS:
        app.set_theme(preset.name)
        for _ in range(5):
            settle(root, 0.05)
        assert app.palette.accent.lower() == preset.accent.lower(), preset.name
        assert store.get_setting("theme.preset") == preset.name
        assert app.current == 3
    app.set_theme("自定义", "#123456")
    for _ in range(5):
        settle(root, 0.05)
    assert app.palette.name == "自定义"
    assert app.palette.accent.lower() == "#123456"
    assert store.get_setting("theme.accent") == "#123456"

    # ---- geometry persistence
    root.geometry("2100x1300+60+40")
    settle(root)
    app._on_close()
    app2 = App(db, demo=False)
    settle(app2.root)
    assert app2.root.geometry().startswith("2100x1300"), app2.root.geometry()
    theme_saved = app2.store.get_setting("theme.preset", "")
    app2._on_close()

    print("flows ok: tx=1, export rows=%d, backup rows=%d, theme=%s"
          % (raw.count(b"\n") - 1, backed_up, theme_saved))


if __name__ == "__main__":
    main()
