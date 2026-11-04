"""Timing helpers for smooth, low-cost UI motion."""
from __future__ import annotations


def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


TRANSITION_OUT_MS = 1000
TRANSITION_REVEAL = 0.75
TRANSITION_REVEAL_MS = int(TRANSITION_OUT_MS * TRANSITION_REVEAL)
TRANSITION_IN_MS = 1400
TRANSITION_MS = TRANSITION_REVEAL_MS + TRANSITION_IN_MS
TRANSITION_REVEAL_TIME = TRANSITION_REVEAL_MS / float(TRANSITION_MS)
TRANSITION_FADE_END = TRANSITION_OUT_MS / float(TRANSITION_MS)


def page_transition(t):
    """Return (old_opacity, incoming_offset, reveal_incoming).

    The outgoing page fades linearly from 1.0 to 0.0 over 1000 ms.  When the
    fade reaches 75% (750 ms, opacity 0.25) the incoming page starts sliding
    up from its offset and the outgoing page keeps fading for another 250 ms.
    The incoming page finishes settling at t == 1.0.
    """
    t = max(0.0, min(1.0, t))
    fade = min(1.0, t / TRANSITION_FADE_END) if TRANSITION_FADE_END else 1.0
    old_opacity = 1.0 - fade
    reveal = t >= TRANSITION_REVEAL_TIME
    if not reveal:
        return old_opacity, 1.0, False
    slide = ease_in_out_cubic(
        (t - TRANSITION_REVEAL_TIME) / (1.0 - TRANSITION_REVEAL_TIME))
    return old_opacity, 1.0 - slide, True


def lerp(a, b, t):
    return a + (b - a) * t


class Debouncer:
    """Collapse a burst of events into a single delayed callback."""

    def __init__(self, widget, delay_ms, callback):
        self.widget = widget
        self.delay_ms = max(1, int(delay_ms))
        self.callback = callback
        self._job = None
        self._args = ()
        self._cancelled = False

    @property
    def pending(self):
        return self._job is not None

    def schedule(self, *args):
        self._args = args
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.widget.after(self.delay_ms, self._fire)

    def _fire(self):
        self._job = None
        if self._cancelled:
            return
        self.callback(*self._args)

    def cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def flush(self):
        if self._job is not None:
            self.cancel()
            self.callback(*self._args)

    def destroy(self):
        self._cancelled = True
        self.cancel()


class Tween:
    """Frame-driven tween bound to a Tk widget."""

    def __init__(self, widget, duration_ms, on_frame, easing=ease_out_cubic,
                 interval_ms=15, on_done=None):
        self.widget = widget
        self.duration = max(1, int(duration_ms))
        self.on_frame = on_frame
        self.easing = easing
        self.interval = max(1, int(interval_ms))
        self.on_done = on_done
        self._job = None
        self._start = None
        self._running = False

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self._start = self.widget.tk.call("clock", "milliseconds")
        except Exception:
            self._start = None
        self._tick()

    def _now(self):
        try:
            return int(self.widget.tk.call("clock", "milliseconds"))
        except Exception:
            return None

    def _tick(self):
        if not self._running:
            return
        now = self._now()
        if self._start is None or now is None:
            progress = 1.0
        else:
            progress = (now - self._start) / float(self.duration)
        progress = max(0.0, min(1.0, progress))
        try:
            self.on_frame(self.easing(progress))
        except Exception:
            self.cancel()
            raise
        if progress >= 1.0:
            self._running = False
            self._job = None
            if self.on_done is not None:
                self.on_done()
            return
        self._job = self.widget.after(self.interval, self._tick)

    def cancel(self, complete=False):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        was_running = self._running
        self._running = False
        if complete and was_running:
            self.on_frame(1.0)
            if self.on_done is not None:
                self.on_done()
