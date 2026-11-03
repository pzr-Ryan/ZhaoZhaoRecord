"""Smoke-test the modal transaction and category dialogs with screenshots."""
import ctypes
import os
import sys
import time
import tkinter as tk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "verify"))

from capture import capture_client  # noqa: E402
from ledger import theme  # noqa: E402
from ledger.db import Store  # noqa: E402
from ledger.dialogs import CategoryDialog, TxDialog  # noqa: E402

OUT = os.path.join(ROOT, "verify", "out")
os.makedirs(OUT, exist_ok=True)
DB = os.path.join(ROOT, "data", "dialog_demo.db")
if os.path.exists(DB):
    os.remove(DB)
for suffix in ("-wal", "-shm"):
    path = DB + suffix
    if os.path.exists(path):
        os.remove(path)

store = Store(DB)
root = tk.Tk()
root.update_idletasks()
scale = root.tk.call("tk", "scaling") / (96.0 / 72.0)
theme.set_scale(scale)
palette = theme.resolve(store)
theme.apply_ttk(root, palette)
root.title("dialog smoke")
root.geometry("%dx%d+60+60" % (theme.px(1000), theme.px(760)))
root.configure(bg=palette.bg)

expense = store.list_categories("expense")
income = store.list_categories("income")
today = "2026-11-03"
store.add_tx(today, 2560, "expense", expense[0]["id"], "午饭 · 牛肉面")
store.add_tx(today, 1800, "expense", expense[1]["id"], "地铁充值")
store.add_tx(today, 880000, "income", income[0]["id"], "月薪")
rows = store.list_tx(None, None, None, None, None)
print("rows", len(rows), "scale", scale)

# --- edit dialog screenshot -------------------------------------------------
tx = store.get_tx(rows[0]["id"])
edit = TxDialog(root, palette, store, tx=tx)
edit.update_idletasks()
edit.deiconify()
edit.update()
root.update()
time.sleep(0.4)
w, h = capture_client(edit, os.path.join(OUT, "dialog_tx.png"))
print("tx dialog captured", w, h, "chips", len(edit.chips.items))
edit.close()

# --- create dialog: fill and save ------------------------------------------
before = store.stats()["tx"]
create = TxDialog(root, palette, store, default_date=today)
create.update_idletasks()
create.deiconify()
create.update()
root.update()
create.segmented.set("income")
create.update_idletasks()
create.amount.set("123.45")
create.note.set("测试收入")
create.segmented.set("expense")
create.amount.set("23.45")
create.note.set("测试支出")
create.update()
time.sleep(0.2)
w, h = capture_client(create, os.path.join(OUT, "dialog_tx_new.png"))
create.save()
after = store.stats()["tx"]
last = store.list_tx(None, None, None, None, None)[0]
print("create saved:", create.result, "count", before, "->", after, "capture", w, h,
      "last", last["amount_cents"], last["kind"], last["note"])

# invalid amount should not close
bad = TxDialog(root, palette, store, default_date=today)
bad.deiconify()
bad.update()
bad.amount.set("abc")
bad.save()
print("bad amount error:", repr(bad.error.cget("text")), "alive", bool(bad.winfo_exists()))
bad.close()

# --- category dialog screenshot + create -----------------------------------
cat = CategoryDialog(root, palette, store, category=expense[0])
cat.update_idletasks()
cat.deiconify()
cat.update()
root.update()
time.sleep(0.3)
w, h = capture_client(cat, os.path.join(OUT, "dialog_category.png"))
cat.name.set("餐饮")
cat.save()
print("category edit saved:", cat.result, "capture", w, h)

new_cat = CategoryDialog(root, palette, store)
new_cat.deiconify()
new_cat.update()
new_cat.name.set("宠物")
new_cat.colors.set("#F97316")
new_cat.save()
print("category create:", new_cat.result)
names = [c["name"] for c in store.list_categories("expense")]
print("expense categories:", names)

store.close()
root.destroy()
print("dialogs ok")
