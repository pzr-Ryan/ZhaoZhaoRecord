"""Launch the packaged entry point with pythonw and check it stays alive."""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "launch_test.db")


def main():
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(DB + suffix)
        except OSError:
            pass
    process = subprocess.Popen(
        ["pythonw.exe", "main.py", "--db", "data/launch_test.db"],
        cwd=ROOT,
    )
    time.sleep(4)
    alive = process.poll() is None
    print("alive=", alive, "pid=", process.pid)
    print("db=", os.path.exists(DB))
    if alive:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    time.sleep(0.5)
    log = os.path.join(ROOT, "data", "app.log")
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8", errors="replace") as handle:
            print("log tail:", handle.read()[-400:])
    assert alive, "app exited early"
    assert os.path.exists(DB), "database was not created"


if __name__ == "__main__":
    main()
