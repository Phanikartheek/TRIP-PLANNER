"""
AI Trip Planner - 1-Click Unified Runner
Starts the FastAPI server on http://127.0.0.1:8000 (which serves both the backend API and frontend UI)
and automatically launches the application in your default web browser.
"""

import os
import sys
import threading
import time
import urllib.request
import webbrowser


def open_browser():
    """Wait for server to become responsive, then open browser."""
    url = "http://127.0.0.1:8000"
    for _ in range(25):
        time.sleep(0.4)
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            pass
    print(f"\n✨ Opening browser at {url} ...\n")
    webbrowser.open(url)

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    root_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(root_dir, "backend", "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    print("=" * 65)
    print(" 🇮🇳 AI Trip Planner — Launching Unified Frontend + Backend")
    print(" 🌐 Application URL : http://127.0.0.1:8000")
    print(" 📖 API Docs        : http://127.0.0.1:8000/docs")
    print("=" * 65)

    # Launch browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    print("Importing uvicorn and app...", flush=True)
    import uvicorn
    print("Importing FastAPI app from backend...", flush=True)
    from trip_planner.api.app import app
    print("Starting Uvicorn server on http://127.0.0.1:8000 ...", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
