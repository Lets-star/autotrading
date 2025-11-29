import pytest
from unittest.mock import MagicMock, patch
from trading_bot.backtesting.engine import BacktestEngine
from trading_bot.data_feeds.binance_fetcher import BinanceDataFetcher
from trading_bot.data_feeds.bybit_fetcher import BybitDataFetcher

def test_backtest_engine_defaults_to_binance():
    engine = BacktestEngine(api_key="key", api_secret="secret")
    assert isinstance(engine.fetcher, BinanceDataFetcher)
    assert engine.data_source == "binance"

def test_backtest_engine_uses_bybit():
    engine = BacktestEngine(api_key="key", api_secret="secret", data_source="Bybit")
    assert isinstance(engine.fetcher, BybitDataFetcher)
    assert engine.data_source == "bybit"

def test_backtest_engine_uses_binance_explicitly():
    engine = BacktestEngine(api_key="key", api_secret="secret", data_source="Binance")
    assert isinstance(engine.fetcher, BinanceDataFetcher)
    assert engine.data_source == "binance"
