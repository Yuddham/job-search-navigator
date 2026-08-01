"""Desktop entry point for the packaged Windows app (PyInstaller + pywebview).
Not used by the plain `uvicorn app.main:app --reload` dev workflow -- this is
the entry point PyInstaller freezes (see packaging/navigrad.spec).

Starts the existing FastAPI app (unchanged, no duplicated routes/logic) via
uvicorn in a background thread, waits for it to answer, then opens a native
window pointed at it. The window's own icon comes from the exe's embedded
icon resource (set at PyInstaller build time) -- pywebview's `icon` param to
webview.start() only applies to the GTK/QT backends, not Windows.
"""
import logging
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import requests
import uvicorn
import webview

from app import config
from app.main import app as fastapi_app

log = logging.getLogger("navigrad.desktop")


def _crash_log_path() -> Path:
    base = Path(os.environ["APPDATA"]) / "Navigrad" if getattr(sys, "frozen", False) else config.BASE_DIR
    return base / "crash.log"


def _run_server(port: int) -> None:
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            requests.get(url, timeout=0.5)
            return True
        except requests.exceptions.RequestException:
            time.sleep(0.1)
    return False


def main() -> None:
    port = config.PORT

    import socket

    port_in_use = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            port_in_use = True
    if port_in_use:
        port = _find_free_port()

    thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    if not _wait_until_ready(url):
        raise RuntimeError(f"Navigrad's local server never became ready on {url}")

    window = webview.create_window("Navigrad", url, width=1280, height=860, min_size=(900, 600))
    window.events.closed += lambda: os._exit(0)
    webview.start()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            log_path = _crash_log_path()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {time.ctime()} ---\n")
                f.write(traceback.format_exc())
        finally:
            raise
