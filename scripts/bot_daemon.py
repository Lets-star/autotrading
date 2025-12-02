"""
Legacy entry point for the trading bot daemon.

This script now simply delegates to the internal trading_bot.bot_daemon module
so that existing workflows that call scripts/bot_daemon.py continue to work.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from trading_bot.bot_daemon import run_daemon

if __name__ == "__main__":
    run_daemon()
