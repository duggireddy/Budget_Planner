"""
Budget Planner desktop launcher.
Starts the local server and opens the app in your default browser.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def main() -> None:
    from app.paths import is_frozen, user_data_dir

    root = user_data_dir()
    os.chdir(root)
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DB_BACKEND", "sqlite")
    os.environ.setdefault("SQLITE_PATH", str(data_dir / "budget.db"))

    if not is_frozen():
        sys.path.insert(0, str(root))

    from app.database import init_db
    from app.seed import ensure_sample_client

    init_db()
    ensure_sample_client()

    host = os.getenv("BUDGET_HOST", "127.0.0.1")
    port = int(os.getenv("BUDGET_PORT", "8765"))
    url = f"http://{host}:{port}"

    def run_server() -> None:
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            log_level="warning",
        )

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    for _ in range(30):
        time.sleep(0.2)
        try:
            import urllib.request

            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            continue

    webbrowser.open(url)
    print("=" * 50)
    print("  Budget Planner")
    print(f"  Running at: {url}")
    print(f"  Database:   {data_dir / 'budget.db'}")
    print("  Close this window to stop the app.")
    print("=" * 50)
    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping…")


if __name__ == "__main__":
    main()
