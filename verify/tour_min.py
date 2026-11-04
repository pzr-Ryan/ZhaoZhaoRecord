"""Capture pages at the minimum window size and stress filter states."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.app import App, enable_dpi_awareness  # noqa: E402
from ledger.theme import px  # noqa: E402
from verify.capture import capture_client  # noqa: E402


def settle(root, wait=0.2):
    root.update_idletasks()
    root.update()
    time.sleep(wait)
    root.update()


def main():
    enable_dpi_awareness()
    app = App(os.path.join("data", "smoke.db"), demo=True)
    app.animate_pages = False
    root = app.root
    settle(root)
    width, height = px(1000), px(640)
    root.geometry("%dx%d+40+40" % (width, height))
    settle(root)
    print("window", root.winfo_width(), root.winfo_height())
    os.makedirs("verify/out", exist_ok=True)
    for index, name in enumerate(("record", "transactions", "stats", "settings")):
        app.show_page(index)
        settle(root)
        print(name, capture_client(root, "verify/out/min_%s.png" % name))

    tv = app.pages[1]
    app.show_page(1)
    settle(root)
    tv._on_range("custom")
    settle(root)
    print("custom", capture_client(root, "verify/out/min_custom.png"))
    tv.keyword.set("不存在的关键词")
    tv._reload()
    settle(root)
    print("empty", capture_client(root, "verify/out/min_empty.png"))
    root.destroy()


if __name__ == "__main__":
    main()
