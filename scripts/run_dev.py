"""Run the FastAPI backend and Next.js frontend dev servers together.

Stopping this script (Ctrl+C) stops both.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"

_venv_python = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable


def _popen(args: list[str], cwd: Path) -> subprocess.Popen:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(args, cwd=cwd, creationflags=creationflags)


def _stop(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    print(f"stopping {name} (pid {proc.pid})...")
    if os.name == "nt":
        # npm/uvicorn spawn child processes (node, reload workers); a plain
        # terminate() only kills the top-level pid and leaves the port bound.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc.terminate()
    proc.wait(timeout=10)


def main() -> None:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm not found on PATH")

    backend = _popen([PYTHON, "-m", "uvicorn", "memedb.api.app:app", "--reload"], cwd=ROOT)
    frontend = _popen([npm, "run", "dev"], cwd=FRONTEND_DIR)

    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                print("backend exited unexpectedly")
                break
            if frontend.poll() is not None:
                print("frontend exited unexpectedly")
                break
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        _stop(frontend, "frontend")
        _stop(backend, "backend")


if __name__ == "__main__":
    main()
