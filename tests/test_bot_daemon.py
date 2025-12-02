"""Tests for the Bybit bot daemon."""

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from trading_bot.bot_daemon import BybitBotDaemon


@pytest.fixture
def temp_dir():
    """Create a temporary directory for daemon files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_client():
    """Create a mock Bybit client."""
    client = MagicMock()
    client.get_positions.return_value = {
        "retCode": 0,
        "result": {"list": []},
    }
    client.get_tickers.return_value = {
        "retCode": 0,
        "result": {"list": [{"lastPrice": "50000"}]},
    }
    client.place_order.return_value = {
        "retCode": 0,
        "result": {"orderId": "12345"},
    }
    return client


def test_daemon_init_simulation_mode(temp_dir):
    """Test daemon initialization in simulation mode."""
    daemon = BybitBotDaemon(base_dir=temp_dir, client=None)
    
    assert daemon.simulation_mode is True
    assert daemon.running is False
    assert isinstance(daemon.positions, list)
    assert os.path.exists(daemon.paths.status_file)
    assert os.path.exists(daemon.paths.positions_file)


def test_daemon_init_with_client(temp_dir, mock_client):
    """Test daemon initialization with a real client."""
    daemon = BybitBotDaemon(base_dir=temp_dir, client=mock_client)
    
    assert daemon.simulation_mode is False
    assert daemon.client is mock_client


def test_daemon_status_update(temp_dir):
    """Test that status file is updated correctly."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    daemon.running = True
    daemon.update_status()
    
    with open(daemon.paths.status_file, "r") as f:
        status = json.load(f)
    
    assert status["pid"] == os.getpid()
    assert status["running"] is True
    assert status["simulation_mode"] is True
    assert "last_update" in status


def test_daemon_process_start_command(temp_dir):
    """Test processing START command."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    assert daemon.running is False
    daemon.process_command({"ACTION": "START"})
    assert daemon.running is True


def test_daemon_process_stop_command(temp_dir):
    """Test processing STOP command."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    daemon.running = True
    
    daemon.process_command({"ACTION": "STOP"})
    assert daemon.running is False


def test_daemon_process_shutdown_command(temp_dir):
    """Test processing SHUTDOWN command."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    daemon.process_command({"ACTION": "SHUTDOWN"})
    assert daemon._stop_requested is True


def test_daemon_read_signal(temp_dir):
    """Test reading a command file."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    # Write a command file
    with open(daemon.paths.command_file, "w") as f:
        f.write("ACTION=START\nPAIR=BTCUSDT\n")
    
    signal = daemon.read_signal()
    assert signal is not None
    assert signal["ACTION"] == "START"
    assert signal["PAIR"] == "BTCUSDT"
    
    # File should be removed after reading
    assert not os.path.exists(daemon.paths.command_file)


def test_daemon_open_position_simulation(temp_dir):
    """Test opening a position in simulation mode."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    daemon.running = True
    
    signal = {"ACTION": "BUY", "PAIR": "BTCUSDT", "SCORE": "0.75"}
    result = daemon.open_position(signal)
    
    assert result is True
    assert len(daemon.positions) == 1
    assert daemon.positions[0]["symbol"] == "BTCUSDT"
    assert daemon.positions[0]["side"] == "Buy"


def test_daemon_open_position_with_client(temp_dir, mock_client):
    """Test opening a position with a real client."""
    daemon = BybitBotDaemon(base_dir=temp_dir, client=mock_client)
    daemon.running = True
    
    signal = {"ACTION": "BUY", "PAIR": "BTCUSDT", "SCORE": "0.75"}
    result = daemon.open_position(signal)
    
    assert result is True
    mock_client.get_tickers.assert_called_once()
    mock_client.place_order.assert_called_once()


def test_daemon_check_risk_duplicate_position(temp_dir):
    """Test risk check rejects duplicate positions."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    # Add an existing position
    daemon.positions = [{"symbol": "BTCUSDT", "size": "0.001"}]
    
    signal = {"ACTION": "BUY", "PAIR": "BTCUSDT"}
    assert daemon.check_risk(signal) is False


def test_daemon_check_risk_new_position(temp_dir):
    """Test risk check allows new positions."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    daemon.positions = []
    
    signal = {"ACTION": "BUY", "PAIR": "BTCUSDT"}
    assert daemon.check_risk(signal) is True


def test_daemon_close_all_positions_simulation(temp_dir):
    """Test closing all positions in simulation mode."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    daemon.positions = [
        {"symbol": "BTCUSDT", "size": "0.001", "side": "Buy"},
        {"symbol": "ETHUSDT", "size": "0.01", "side": "Sell"},
    ]
    
    daemon.close_all_positions()
    assert len(daemon.positions) == 0


def test_daemon_close_all_positions_with_client(temp_dir, mock_client):
    """Test closing all positions with a real client."""
    daemon = BybitBotDaemon(base_dir=temp_dir, client=mock_client)
    daemon.positions = [
        {"symbol": "BTCUSDT", "size": "0.001", "side": "Buy"},
    ]
    
    daemon.close_all_positions()
    mock_client.place_order.assert_called()


def test_daemon_tick(temp_dir):
    """Test a single daemon tick cycle."""
    daemon = BybitBotDaemon(base_dir=temp_dir, poll_interval=0.1)
    
    # Write a START command
    with open(daemon.paths.command_file, "w") as f:
        f.write("ACTION=START\n")
    
    daemon.tick()
    
    # Command should be processed
    assert daemon.running is True
    assert not os.path.exists(daemon.paths.command_file)
    
    # Status file should be updated
    with open(daemon.paths.status_file, "r") as f:
        status = json.load(f)
    assert status["running"] is True


def test_daemon_position_persistence(temp_dir):
    """Test that positions are persisted to file."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    daemon.positions = [{"symbol": "BTCUSDT", "size": "0.001"}]
    daemon.save_positions()
    
    # Create a new daemon instance
    daemon2 = BybitBotDaemon(base_dir=temp_dir)
    
    # Positions should be loaded (in simulation mode)
    assert len(daemon2.positions) == 1
    assert daemon2.positions[0]["symbol"] == "BTCUSDT"


def test_daemon_handles_invalid_command(temp_dir):
    """Test daemon handles invalid commands gracefully."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    
    # Invalid command should not crash
    daemon.process_command({"ACTION": "INVALID_ACTION"})
    daemon.process_command({})
    daemon.process_command({"INVALID": "NO_ACTION"})
    
    # Daemon should still be operational
    assert daemon.running is False


def test_daemon_sync_positions_with_client(temp_dir, mock_client):
    """Test syncing positions from Bybit."""
    mock_client.get_positions.return_value = {
        "retCode": 0,
        "result": {
            "list": [
                {"symbol": "BTCUSDT", "size": "0.001", "side": "Buy"},
                {"symbol": "ETHUSDT", "size": "0", "side": "Buy"},  # Inactive
            ]
        },
    }
    
    daemon = BybitBotDaemon(base_dir=temp_dir, client=mock_client)
    daemon._sync_positions()
    
    # Only active positions should be synced
    assert len(daemon.positions) == 1
    assert daemon.positions[0]["symbol"] == "BTCUSDT"


def test_daemon_ignores_signals_when_stopped(temp_dir):
    """Test daemon ignores BUY/SELL signals when not running."""
    daemon = BybitBotDaemon(base_dir=temp_dir)
    daemon.running = False
    
    signal = {"ACTION": "BUY", "PAIR": "BTCUSDT", "SCORE": "0.75"}
    daemon.process_command(signal)
    
    # No position should be opened
    assert len(daemon.positions) == 0
