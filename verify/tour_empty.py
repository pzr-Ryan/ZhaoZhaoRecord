"""Capture all pages on a brand-new empty database."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.app import App, enable_dpi_awareness  # noqa: E402
from verify.capture import capture_client  # noqa: E402


def settle(root, wait=0.25):
    root.update_idletasks()
    root.update()
    time.sleep(wait)
    root.update()


def main():
    enable_dpi_awareness()
    db = os.path.join("data", "empty.db")
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db + suffix)
        except OSError:
            pass
    app = App(db, demo=False)
    root = app.root
    settle(root)
    for index, name in enumerate(("record", "transactions", "stats", "settings")):
        app.show_page(index)
        settle(root)
        print(name, capture_client(root, "verify/out/empty_%s.png" % name))
    app.show_page(2)
    settle(root)
    app.pages[2].scroll.canvas.yview_moveto(1.0)
    settle(root)
    print("stats-bottom", capture_client(root, "verify/out/empty_stats_bottom.png"))
    root.destroy()


if __name__ == "__main__":
    main()
