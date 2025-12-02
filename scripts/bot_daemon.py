#!/usr/bin/env python3
"""Entry point script to start the Bybit Bot Daemon as a background process.

This is used by the Streamlit UI (app.py) to spawn the daemon:
    subprocess.Popen([sys.executable, DAEMON_SCRIPT], cwd=root_dir)
"""

import os
import sys

# Add src to path so we can import trading_bot
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from trading_bot.bot_daemon import BybitBotDaemon


def main() -> None:
    daemon = BybitBotDaemon(base_dir=project_root)
    daemon.run_forever()


if __name__ == "__main__":
    main()
