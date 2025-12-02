"""Bybit bot daemon that manages a background trading process.

This module encapsulates the stateful daemon that:
- Listens for commands written by the Streamlit UI (start/stop/buy/sell/etc.)
- Talks to Bybit via pybit when API credentials are available
- Falls back to a simulation mode when credentials are missing (useful for local dev/tests)
- Persists lightweight status/position files that the UI can consume to display real-time
  daemon information without needing direct inter-process communication.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Callable, Dict, List, Optional

try:
    from pybit.unified_trading import HTTP
except ImportError:  # pragma: no cover - pybit is an optional runtime dependency in tests
    HTTP = None  # type: ignore

from trading_bot.config import settings

LOGGER_NAME = "trading_bot.bot_daemon"


def _default_base_dir() -> str:
    """Return the project root (two levels up from this file)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@dataclass
class PathRegistry:
    """Helper to manage daemon file-system paths."""

    base_dir: str
    signal_dir: Optional[str] = None
    data_dir: Optional[str] = None
    log_dir: Optional[str] = None

    def __post_init__(self) -> None:
        self.signal_dir = self.signal_dir or os.path.join(self.base_dir, "signals")
        self.data_dir = self.data_dir or os.path.join(self.base_dir, "data")
        self.log_dir = self.log_dir or os.path.join(self.base_dir, "logs")

        for path in (self.signal_dir, self.data_dir, self.log_dir):
            os.makedirs(path, exist_ok=True)

        self.command_file = os.path.join(self.signal_dir, "command.txt")
        self.status_file = os.path.join(self.signal_dir, "status.json")
        self.positions_file = os.path.join(self.data_dir, "positions.json")
        self.trades_file = os.path.join(self.data_dir, "trades.csv")
        self.log_file = os.path.join(self.log_dir, "bot.log")


class BybitBotDaemon:
    """Background daemon responsible for managing Bybit positions."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        signal_dir: Optional[str] = None,
        data_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        poll_interval: float = 1.0,
        position_sync_interval: float = 5.0,
        client: Optional[Any] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.paths = PathRegistry(
            base_dir=base_dir or _default_base_dir(),
            signal_dir=signal_dir,
            data_dir=data_dir,
            log_dir=log_dir,
        )
        self.poll_interval = poll_interval
        self.position_sync_interval = position_sync_interval
        self.now_fn = now_fn or datetime.utcnow

        self.logger = self._configure_logger()
        self.logger.debug("Initializing BybitBotDaemon with base_dir=%s", self.paths.base_dir)

        self.client = client or self._create_client()
        self.simulation_mode = self.client is None

        self.running = False
        self.positions: List[Dict[str, Any]] = []
        self.last_command: Optional[str] = None
        self.last_signal_meta: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None
        self.started_at = self.now_fn().isoformat() + "Z"
        self._stop_requested = False
        self._last_position_sync = 0.0

        self._load_positions()
        self.update_status(force=True)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(LOGGER_NAME)
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        existing = [
            handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
        ]
        if not existing:
            handler = RotatingFileHandler(
                self.paths.log_file,
                maxBytes=1_048_576,
                backupCount=3,
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            console = logging.StreamHandler()
            console.setFormatter(formatter)
            logger.addHandler(console)

        return logger

    def _create_client(self) -> Optional[Any]:
        if HTTP is None:
            self.logger.warning("pybit not available. Running in simulation mode.")
            return None

        api_key = settings.api_key
        api_secret = settings.api_secret
        if not api_key or not api_secret:
            self.logger.warning(
                "Bybit API credentials missing. Running daemon in simulation mode."
            )
            return None

        try:
            client = HTTP(
                testnet=False,
                api_key=api_key,
                api_secret=api_secret,
            )
            self.logger.info("Bybit client initialized successfully.")
            return client
        except Exception as exc:  # pragma: no cover - network failure path
            self.last_error = str(exc)
            self.logger.error("Failed to initialize Bybit client: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load_positions(self) -> None:
        if not os.path.exists(self.paths.positions_file):
            self.positions = []
            self.save_positions()
            return

        try:
            with open(self.paths.positions_file, "r", encoding="utf-8") as fp:
                self.positions = json.load(fp)
                if not isinstance(self.positions, list):  # legacy format guard
                    self.positions = []
        except Exception as exc:  # pragma: no cover - corruption path
            self.positions = []
            self.last_error = str(exc)
            self.logger.error("Failed to load positions: %s", exc)

    def save_positions(self) -> None:
        try:
            with open(self.paths.positions_file, "w", encoding="utf-8") as fp:
                json.dump(self.positions, fp, indent=2)
        except Exception as exc:  # pragma: no cover - IO failure path
            self.last_error = str(exc)
            self.logger.error("Failed to save positions: %s", exc)

    def update_status(self, force: bool = False) -> None:
        status = {
            "pid": os.getpid(),
            "running": self.running,
            "state": "RUNNING" if self.running else "IDLE",
            "last_update": self.now_fn().isoformat(),
            "simulation_mode": self.simulation_mode,
            "position_count": len(self.positions),
            "last_command": self.last_command,
            "last_signal": self.last_signal_meta,
            "last_error": self.last_error,
            "started_at": self.started_at,
            "poll_interval": self.poll_interval,
            "position_sync_interval": self.position_sync_interval,
        }

        try:
            with open(self.paths.status_file, "w", encoding="utf-8") as fp:
                json.dump(status, fp, indent=2)
        except Exception as exc:  # pragma: no cover - IO failure path
            if force:
                raise
            self.last_error = str(exc)
            self.logger.error("Failed to write status file: %s", exc)

    # ------------------------------------------------------------------
    # Exchange helpers
    # ------------------------------------------------------------------
    def _sync_positions(self) -> None:
        if self.simulation_mode or not self.client:
            # In simulation mode, positions are driven by local state only.
            return

        try:
            response = self.client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") != 0:
                self.logger.error("Bybit get_positions error: %s", response.get("retMsg"))
                return

            all_positions = response["result"].get("list", [])
            active_positions = [
                pos for pos in all_positions if float(pos.get("size", 0)) > 0
            ]
            self.positions = active_positions
            self.save_positions()
            self.logger.debug("Synced %s active positions", len(active_positions))
        except Exception as exc:  # pragma: no cover - network failure path
            self.last_error = str(exc)
            self.logger.error("Failed to sync positions: %s", exc)

    def _place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
    ) -> bool:
        if self.simulation_mode or not self.client:
            return True

        try:
            order = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(qty),
            )
            if order.get("retCode") != 0:
                self.logger.error("Order failed: %s", order.get("retMsg"))
                self.last_error = order.get("retMsg")
                return False
            return True
        except Exception as exc:  # pragma: no cover - network failure path
            self.last_error = str(exc)
            self.logger.error("Bybit order error: %s", exc)
            return False

    def close_all_positions(self) -> None:
        if self.simulation_mode or not self.client:
            self.positions = []
            self.save_positions()
            return

        for pos in list(self.positions):
            symbol = pos.get("symbol")
            if not symbol:
                continue
            size = pos.get("size", "0")
            opposite = "Sell" if pos.get("side") == "Buy" else "Buy"
            try:
                order = self.client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=opposite,
                    orderType="Market",
                    qty=size,
                    reduceOnly=True,
                )
                if order.get("retCode") != 0:
                    self.logger.error(
                        "Failed to close position %s: %s", symbol, order.get("retMsg")
                    )
            except Exception as exc:  # pragma: no cover - network failure path
                self.last_error = str(exc)
                self.logger.error("Close position error for %s: %s", symbol, exc)

        time.sleep(1)
        self._sync_positions()

    # ------------------------------------------------------------------
    # Command processing
    # ------------------------------------------------------------------
    def read_signal(self) -> Optional[Dict[str, str]]:
        if not os.path.exists(self.paths.command_file):
            return None

        try:
            with open(self.paths.command_file, "r", encoding="utf-8") as fp:
                content = fp.read()
            os.remove(self.paths.command_file)
        except Exception as exc:  # pragma: no cover - IO failure path
            self.last_error = str(exc)
            self.logger.error("Failed to read command file: %s", exc)
            return None

        data: Dict[str, str] = {}
        for line in content.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip().upper()] = value.strip()

        return data if data else None

    def check_risk(self, signal: Dict[str, str]) -> bool:
        pair = signal.get("PAIR")
        action = signal.get("ACTION")
        if not pair or action not in {"BUY", "SELL"}:
            self.logger.warning("Invalid signal: %s", signal)
            return False

        for pos in self.positions:
            if pos.get("symbol") == pair and float(pos.get("size", 0)) > 0:
                self.logger.warning("Existing position detected for %s; ignoring signal.", pair)
                return False

        return True

    def open_position(self, signal: Dict[str, str]) -> bool:
        pair = signal.get("PAIR")
        action = signal.get("ACTION")
        self.logger.info("Opening position: %s %s", action, pair)

        if not self.check_risk(signal):
            return False

        if self.simulation_mode or not self.client:
            mock_position = {
                "symbol": pair,
                "side": "Buy" if action == "BUY" else "Sell",
                "size": "0.001",
                "avgPrice": "45000",
                "markPrice": "45000",
                "unrealisedPnl": "0",
                "stopLoss": "44000",
                "takeProfit": "46000",
                "simulated": True,
                "opened_at": self.now_fn().isoformat() + "Z",
            }
            self.positions.append(mock_position)
            self.save_positions()
            return True

        try:
            ticker = self.client.get_tickers(category="linear", symbol=pair)
            price = float(ticker["result"]["list"][0]["lastPrice"])
        except Exception as exc:  # pragma: no cover - network failure path
            self.last_error = str(exc)
            self.logger.error("Failed to fetch ticker: %s", exc)
            return False

        if price <= 0:
            self.logger.error("Received invalid price for %s", pair)
            return False

        size_usd = getattr(settings, "risk_limit_amount", 100.0)
        qty = round(size_usd / price, 4)
        side = "Buy" if action == "BUY" else "Sell"

        if not self._place_order(pair, side, qty):
            return False

        time.sleep(1)  # wait for fills
        self._sync_positions()
        return True

    def process_command(self, command: Dict[str, str]) -> None:
        action = command.get("ACTION", "").upper()
        if not action:
            return

        self.last_command = action
        self.logger.info("Processing command: %s", command)

        if action == "START":
            self.running = True
            self.logger.info("Daemon marked as RUNNING")
        elif action == "STOP":
            self.running = False
            self.logger.info("Daemon marked as IDLE")
        elif action == "CLOSE_ALL":
            self.close_all_positions()
        elif action in {"BUY", "SELL"}:
            if self.running:
                success = self.open_position(command)
                self.last_signal_meta = {
                    "action": action,
                    "pair": command.get("PAIR"),
                    "received_at": self.now_fn().isoformat() + "Z",
                    "success": success,
                }
            else:
                self.logger.info("Signal ignored because daemon is not running")
        elif action in {"SHUTDOWN", "EXIT"}:
            self.logger.info("Shutdown requested")
            self.running = False
            self._stop_requested = True
        elif action == "SYNC":
            self._sync_positions()
        elif action == "HEALTH_CHECK":
            self.logger.info("Health check received: OK")

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------
    def tick(self) -> None:
        self.update_status()

        now = time.time()
        if now - self._last_position_sync >= self.position_sync_interval:
            self._sync_positions()
            self._last_position_sync = now

        command = self.read_signal()
        if command:
            self.process_command(command)

    def run_forever(self) -> None:
        self.logger.info("Bybit Bot Daemon started with PID %s", os.getpid())
        try:
            while not self._stop_requested:
                try:
                    self.tick()
                except Exception as exc:  # pragma: no cover - defensive guard
                    self.last_error = str(exc)
                    self.logger.exception("Unhandled daemon error: %s", exc)
                time.sleep(max(self.poll_interval, 0))
        except KeyboardInterrupt:  # pragma: no cover - CLI convenience
            self.logger.info("Keyboard interrupt received. Stopping daemon...")
        finally:
            self.running = False
            self.update_status()
            self.logger.info("Daemon stopped cleanly.")

    def request_stop(self) -> None:
        self._stop_requested = True


__all__ = ["BybitBotDaemon"]
