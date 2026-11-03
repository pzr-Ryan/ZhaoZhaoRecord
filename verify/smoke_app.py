"""Launch the real app with demo data and capture the first screen."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.app import App, enable_dpi_awareness  # noqa: E402
from verify.capture import capture_client  # noqa: E402


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
    root = app.root
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    out = os.path.join("verify", "out", "app_record.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    size = capture_client(root, out)
    print("captured", size, app.store.stats())


if __name__ == "__main__":
    main()
