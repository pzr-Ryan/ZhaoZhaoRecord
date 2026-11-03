"""Smoke-test the frozen executable: startup, data path and first screenshot."""
import ctypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledger.app import enable_dpi_awareness  # noqa: E402
from verify.capture import capture_client  # noqa: E402

EXE = ROOT / "dist" / "ZhaoZhaoRecord.exe"
SANDBOX = ROOT / "dist" / "exe-check"


class FakeWindow:
    def __init__(self, hwnd):
        self._hwnd = hwnd

    def winfo_id(self):
        return self._hwnd


def main():
    if not EXE.exists():
        raise SystemExit("missing %s" % EXE)
    shutil.rmtree(str(SANDBOX), ignore_errors=True)
    state = SANDBOX / "ZhaoZhaoRecord" / "data"
    temp = ROOT / "dist" / "exe-temp"
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(SANDBOX)
    env["TEMP"] = str(temp)
    env["TMP"] = str(temp)

    enable_dpi_awareness()
    proc = subprocess.Popen([str(EXE)], cwd=str(ROOT), env=env)
    deadline = time.time() + 12
    db = state / "ledger.db"
    while time.time() < deadline and proc.poll() is None and not db.exists():
        time.sleep(0.5)

    alive = proc.poll() is None
    hwnd = 0
    window_deadline = time.time() + 10
    while alive and time.time() < window_deadline and not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "简账 · 记账")
        if not hwnd:
            time.sleep(0.5)
    shot = None
    if alive and hwnd:
        out = ROOT / "verify" / "out" / "exe_record.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        shot = capture_client(FakeWindow(hwnd), str(out))

    if alive and hwnd:
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
    if alive:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

    log = state / "app.log"
    if log.exists() and log.stat().st_size:
        print("LOG:", log.read_text(encoding="utf-8", errors="replace")[-2000:])
    print("exe alive:", alive, "rc:", proc.returncode, "db:", db.exists(), "hwnd:", bool(hwnd), "shot:", shot)
    if not alive or not db.exists() or not hwnd or not shot:
        raise SystemExit(1)


if __name__ == "__main__":
    main()