from __future__ import annotations

import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

from config.settings import PORT
from panel.server import app


HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{PORT}"


def _start_server():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False, threaded=True)


def _wait_for_server(timeout_seconds: int = 45) -> bool:
    health_url = f"{BASE_URL}/api/health"
    deadline = time.time() + max(timeout_seconds, 5)
    while time.time() < deadline:
        try:
            with urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except URLError:
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return False


def main():
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    if _wait_for_server():
        webbrowser.open(BASE_URL)
    else:
        webbrowser.open(BASE_URL)

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
