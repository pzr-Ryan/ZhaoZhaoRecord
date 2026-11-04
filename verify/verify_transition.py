"""Measure and sanity-check the staged page transition (manual UI check)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.app import App, enable_dpi_awareness  # noqa: E402


def overlay_alpha(app):
    if app._overlay is None:
        return None
    try:
        return float(app._overlay.attributes("-alpha"))
    except Exception:
        return None


def overlay_shift(app):
    canvas = app._overlay_canvas
    image = app._overlay_image
    if canvas is None or image is None:
        return None
    try:
        return int(canvas.coords(image)[1])
    except Exception:
        return None


def main():
    enable_dpi_awareness()
    db = os.path.join("data", "transition.db")
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db + suffix)
        except OSError:
            pass
    app = App(db, demo=True)
    app.animate_pages = True
    root = app.root
    root.update_idletasks()
    root.update()
    time.sleep(0.25)
    root.update()

    started = time.perf_counter()
    app.show_page(1, refresh=False, animate=True)
    anim_started = time.perf_counter()
    samples = []
    peak_alpha = 0.0

    def sample(elapsed):
        nonlocal peak_alpha
        page = app.pages[1]
        old_page = app.pages[0]
        try:
            page_y = int(page.winfo_y())
        except Exception:
            page_y = None
        alpha = overlay_alpha(app)
        shift = overlay_shift(app)
        if alpha is not None:
            peak_alpha = max(peak_alpha, alpha)
        samples.append((
            elapsed,
            app._overlay is not None,
            alpha,
            shift,
            old_page.winfo_ismapped(),
            page.winfo_ismapped(),
            page_y,
            app._backdrop is not None,
        ))

    sample(0.0)
    while app._transition is not None:
        root.update()
        elapsed = time.perf_counter() - anim_started
        sample(elapsed)
        if elapsed > 4.0:
            raise AssertionError("transition did not finish in 4s")
        time.sleep(0.005)
    root.update()
    total = time.perf_counter() - anim_started

    first = samples[0]
    reveal = next((item for item in samples if item[6] is not None and
                   first[6] is not None and item[6] < first[6]), None)
    destroyed = next((item for item in samples if item[1] is False), None)
    last = samples[-1]
    max_shift = max(item[3] for item in samples if item[3] is not None)
    final_y = last[6]

    assert first[1], "snapshot overlay missing at start"
    assert first[7] is True, "opaque backdrop missing at start"
    assert first[2] is not None and first[2] >= 0.98, first
    assert first[3] == 0, first
    assert first[6] == app._offset, first
    assert not first[4], "outgoing page should be replaced by its snapshot"
    assert first[5] and first[6] and first[6] >= 100, first
    assert reveal is not None, "incoming page never started moving"
    assert 0.70 <= reveal[0] <= 1.25, reveal
    assert reveal[1], "overlay should still be fading at reveal"
    assert not reveal[7], "backdrop should be removed at reveal"
    assert 0.15 <= reveal[2] <= 0.35, reveal
    assert reveal[6] < first[6], reveal
    assert destroyed is not None, "snapshot overlay never destroyed"
    assert destroyed[0] <= 1.30, destroyed
    assert max_shift >= 20, max_shift
    assert peak_alpha >= 0.98, peak_alpha
    assert final_y == 0, final_y
    assert last[1] is False and last[2] is None, last
    assert last[7] is False, last
    assert app._overlay is None and app._curtain is None
    assert app._backdrop is None
    assert app._transition is None and app._gap_cover is None
    assert 2.05 <= total <= 2.60, total
    assert 1.30 <= total - reveal[0] <= 1.55, total - reveal[0]
    print("capture %.3fs; duration %.3fs; overlay gone %.3fs; incoming start %.3fs" %
          (anim_started - started, total, destroyed[0], reveal[0]))
    print("start y %s; snapshot slide down %s; peak alpha %.3f; samples %s" %
          (first[6], max_shift, peak_alpha, len(samples)))
    print("at reveal", reveal)
    app.root.destroy()


if __name__ == "__main__":
    main()
