"""Entry point for SiliconTree Computer Architecture & Hardware Security Suite (Flask Web GUI)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web_gui import create_flask_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch SiliconTree Flask GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    app = create_flask_app()
    url = f"http://{args.host}:{args.port}"
    print(f"SiliconTree running at {url}")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
