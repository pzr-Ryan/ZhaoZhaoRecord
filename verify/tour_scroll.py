"""Scroll to lower parts of stats/settings and capture."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledger.app import App, enable_dpi_awareness
from verify.capture import capture_client

def settle(root, wait=0.3):
    root.update_idletasks(); root.update(); time.sleep(wait); root.update()

def main():
    enable_dpi_awareness()
    db = os.path.join("data", "smoke.db")
    app = App(db, demo=True)
    app.animate_pages = False
    root = app.root
    settle(root)
    os.makedirs("verify/out", exist_ok=True)
    app.show_page(2); settle(root)
    app.pages[2].scroll.canvas.yview_moveto(1.0); settle(root)
    print("stats bottom", capture_client(root, "verify/out/page_stats_bottom.png"))
    app.show_page(3); settle(root)
    app.pages[3].scroll.canvas.yview_moveto(0.6); settle(root)
    print("settings mid", capture_client(root, "verify/out/page_settings_mid.png"))
    app.pages[3].scroll.canvas.yview_moveto(1.0); settle(root)
    print("settings bottom", capture_client(root, "verify/out/page_settings_bottom.png"))
    app.set_theme("青碧")
    for _ in range(6):
        settle(root, 0.15)
    print("theme", app.palette.accent, "page", app.current)
    print("settings teal", capture_client(root, "verify/out/page_settings_teal.png"))
    root.destroy()

if __name__ == "__main__":
    main()
