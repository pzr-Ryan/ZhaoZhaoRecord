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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from capture import capture_client
from ledger import theme
from ledger import widgets as w
from ledger.theme import DEFAULT_PALETTE as P

root = tk.Tk()
root.update_idletasks()
scale = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
theme.set_scale(scale)
s = theme.px
root.geometry("%dx%d+40+40" % (s(1000), s(800)))
root.configure(bg=P.bg)
theme.apply_ttk(root, P)

card = w.RoundedCard(root, P, padding=18)
card.place(x=s(30), y=s(30), width=s(400), height=s(250))
tk.Label(card.body, text="卡片标题", bg=P.surface, fg=P.text,
         font=theme.font(12, "bold")).pack(anchor="w")
tk.Label(card.body, text="副标题说明文字", bg=P.surface, fg=P.text_muted,
         font=theme.font(9)).pack(anchor="w", pady=(s(2), s(10)))
row = tk.Frame(card.body, bg=P.surface)
row.pack(anchor="w")
w.RoundButton(row, P, "主要按钮", lambda: None).pack(side="left", padx=(0, s(10)))
w.RoundButton(row, P, "次要按钮", None, variant="soft").pack(side="left")

flow = w.FlowFrame(root, P)
flow.place(x=s(30), y=s(310), width=s(400), height=s(120))
for name, color in [("餐饮", "#F97316"), ("交通", "#3B82F6"), ("购物", "#EC4899"),
                    ("居住", "#8B5CF6"), ("娱乐", "#14B8A6")]:
    flow.add(w.Chip(flow, P, name, color=color, selected=(name == "餐饮"),
                   command=lambda v: None))

seg = w.Segmented(root, P, [("expense", "支出"), ("income", "收入")],
                  value="expense")
seg.place(x=s(30), y=s(450))

entry = w.EntryField(root, P, width=14)
entry.place(x=s(30), y=s(510))
entry.set("12.50")

date = w.DateEntry(root, P, "2026-11-03")
date.place(x=s(230), y=s(506), width=s(160))

w.RoundButton(root, P, "幽灵按钮", None, variant="ghost").place(x=s(30), y=s(580))
w.RoundButton(root, P, "危险按钮", None, variant="danger").place(x=s(170), y=s(580))
w.RoundButton(root, P, "链接按钮", None, variant="link").place(x=s(310), y=s(585))

stat = w.StatCard(root, P, "本月支出", "¥1,234.56", "共 12 笔")
stat.place(x=s(470), y=s(30), width=s(480), height=s(150))

scroll = w.ScrollFrame(root, P)
scroll.place(x=s(470), y=s(210), width=s(480), height=s(250))
for i in range(30):
    tk.Label(scroll.body, text="第 %d 行记录" % (i + 1), bg=P.bg,
             fg=P.text, font=theme.font(10)).pack(anchor="w", pady=s(3))

empty = w.EmptyState(root, P, "还没有记录", "点击左侧开始你的第一笔记账吧")
empty.place(x=s(470), y=s(500), width=s(480), height=s(240))

root.update()
root.attributes("-topmost", True)
root.lift()
root.update()
time.sleep(0.5)
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
size = capture_client(root, os.path.join(HERE, "out", "widgets.png"))
print("widgets ok", root.winfo_width(), root.winfo_height(), size, "scale", scale)
root.attributes("-topmost", False)
root.after(200, root.destroy)
root.mainloop()
