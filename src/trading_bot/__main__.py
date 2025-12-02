"""
Main entry point for running trading_bot.bot_daemon as a module.

Usage:
    python -m trading_bot.bot_daemon
"""

from trading_bot.bot_daemon import run_daemon

if __name__ == "__main__":
    run_daemon()
