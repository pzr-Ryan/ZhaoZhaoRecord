import ctypes
import os
import random
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from capture import capture_client
from ledger import theme
from ledger.charts import BarChart, DonutChart
from ledger.theme import DEFAULT_PALETTE as P
from ledger.widgets import RoundedCard
from ledger.money import format_cents

root = tk.Tk()
root.update_idletasks()
theme.set_scale(float(root.tk.call("tk", "scaling")) / (96.0 / 72.0))
s = theme.px
root.geometry("%dx%d+40+40" % (s(1300), s(900)))
root.configure(bg=P.bg)
theme.apply_ttk(root, P)

random.seed(7)
days = ["11-%02d" % d for d in range(1, 15)]
bar = BarChart(root, P)
bar.set_data([(label, random.randint(1800, 42000)) for label in days], highlight=13)
bar.place(x=s(30), y=s(60), width=s(760), height=s(330))

months = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
bar2 = BarChart(root, P)
bar2.set_data([(label, random.randint(350000, 1500000)) for label in months],
              highlight=11)
bar2.place(x=s(820), y=s(60), width=s(450), height=s(330))

items = [
    {"name": "餐饮", "cents": 128600, "color": "#F97316"},
    {"name": "购物", "cents": 86200, "color": "#EC4899"},
    {"name": "交通", "cents": 45200, "color": "#3B82F6"},
    {"name": "居住", "cents": 320000, "color": "#8B5CF6"},
    {"name": "娱乐", "cents": 28600, "color": "#14B8A6"},
    {"name": "其他", "cents": 12800, "color": "#94A3B8"},
]
donut = DonutChart(root, P)
donut.set_data(items, "本月支出")
donut.place(x=s(30), y=s(430), width=s(1240), height=s(400))

root.update()
root.attributes("-topmost", True)
root.lift()
root.update()
time.sleep(0.4)
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
size = capture_client(root, os.path.join(HERE, "out", "charts.png"))
print("charts ok", size, "scale", theme.SCALE)
root.attributes("-topmost", False)
root.after(200, root.destroy)
root.mainloop()
