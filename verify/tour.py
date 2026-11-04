"""Capture every page of the real app with demo data."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.app import App, enable_dpi_awareness  # noqa: E402
from verify.capture import capture_client  # noqa: E402

NAMES = ["record", "transactions", "stats", "settings"]


def main():
    enable_dpi_awareness()
    db = os.path.join("data", "smoke.db")
    if os.path.exists(db):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(db + suffix)
            except OSError:
                pass
    app = App(db, demo=True)
    app.animate_pages = False
    root = app.root
    root.update_idletasks()
    root.update()
    time.sleep(0.3)
    root.update()
    os.makedirs(os.path.join("verify", "out"), exist_ok=True)
    for index, name in enumerate(NAMES):
        app.show_page(index)
        root.update_idletasks()
        root.update()
        time.sleep(0.25)
        root.update()
        size = capture_client(root, os.path.join("verify", "out", "page_%s.png" % name))
        print(name, size)


if __name__ == "__main__":
    main()
