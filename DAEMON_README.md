# Bybit Bot Daemon

## Overview

The Bybit Bot Daemon is a background process that manages trading positions on Bybit. It runs independently of the Streamlit UI and communicates through file-based signals.

## Architecture

### Components

1. **Daemon Module** (`src/trading_bot/bot_daemon.py`)
   - Core daemon implementation
   - Position management
   - Signal processing
   - Bybit API integration

2. **Entry Script** (`scripts/bot_daemon.py`)
   - Spawned by the Streamlit UI
   - Runs the daemon in the background

3. **UI Integration** (`src/trading_bot/app.py`)
   - Start/Stop daemon controls
   - Real-time status display
   - Command sending

### Communication

The daemon and UI communicate through files in the `signals/` directory:

- **`signals/status.json`**: Daemon writes its current state (PID, running status, positions, etc.)
- **`signals/command.txt`**: UI writes commands for the daemon to execute

### Daemon States

- **Not Running**: Process doesn't exist or is unresponsive
- **Idle**: Process is alive but not processing signals (`running=False`)
- **Running**: Process is alive and actively processing signals (`running=True`)

## Usage

### Starting the Daemon

From the Streamlit UI sidebar:
1. Click "Start Daemon" to launch the process
2. The daemon will initialize in Idle state
3. Click "Start Bot" to begin processing signals
4. Status will show as "✅ Running"

### Stopping the Daemon

1. Click "Stop Bot" to pause signal processing (daemon stays alive)
2. Or restart the app to terminate the process

### Simulation Mode

If API credentials are not configured, the daemon runs in **simulation mode**:
- No real trades are placed on Bybit
- Mock positions are created for testing
- Status displays "[SIM]" indicator

## Configuration

Daemon behavior is controlled by environment variables or `.streamlit/secrets.toml`:

```toml
[bybit]
api_key = "your_api_key"
api_secret = "your_api_secret"

[settings]
risk_limit_amount = 100.0  # USD per trade
log_level = "INFO"
```

## Position Management

The daemon automatically:
- Syncs positions from Bybit every 5 seconds
- Opens positions when receiving BUY/SELL signals (if risk checks pass)
- Tracks active positions in `data/positions.json`
- Closes positions on CLOSE_ALL command

## Monitoring

### Status File

The `signals/status.json` file contains:
```json
{
  "pid": 12345,
  "running": true,
  "state": "RUNNING",
  "last_update": "2024-01-01T12:00:00.123456",
  "simulation_mode": false,
  "position_count": 1,
  "last_command": "START",
  "last_error": null
}
```

### Logs

Daemon logs are written to `logs/bot.log` with rotation (max 1MB per file, 3 backups).

## Commands

The daemon responds to the following commands (written to `signals/command.txt`):

- **START**: Begin processing trading signals
- **STOP**: Pause signal processing (daemon stays alive)
- **BUY**: Open a long position (requires PAIR, SCORE)
- **SELL**: Open a short position (requires PAIR, SCORE)
- **CLOSE_ALL**: Close all open positions
- **SYNC**: Force position sync from Bybit
- **HEALTH_CHECK**: Log a health check message
- **SHUTDOWN**: Stop the daemon process

Example command format:
```
ACTION=BUY
PAIR=BTCUSDT
SCORE=0.75
TIMESTAMP=2024-01-01T12:00:00Z
```

## Testing

Run the daemon tests:
```bash
pytest tests/test_bot_daemon.py -v
```

Test coverage includes:
- Initialization (simulation and real client modes)
- Command processing
- Position management
- Risk checks
- File persistence
- Error handling

## Troubleshooting

### Daemon Status Shows "Stopped"

**Cause**: Process not running or status file is stale
**Solution**: Click "Start Daemon" in the UI

### Status Shows "Heartbeat Stale"

**Cause**: Daemon hasn't updated status file in 15+ seconds
**Solution**: Daemon may be frozen; restart it

### "SIMULATION MODE" Label

**Cause**: Missing or invalid API credentials
**Solution**: Configure `api_key` and `api_secret` in secrets

### Positions Not Updating

**Cause**: Risk checks failing or daemon in Idle state
**Solution**: 
1. Check daemon is in "Running" state
2. Review logs at `logs/bot.log`
3. Verify no duplicate positions exist

## Development

### Adding New Commands

1. Add command handling in `BybitBotDaemon.process_command()`
2. Update UI to send the command via `send_command()`
3. Add tests in `tests/test_bot_daemon.py`

### Extending Position Logic

The daemon supports dependency injection:
```python
daemon = BybitBotDaemon(
    base_dir="/path/to/project",
    client=custom_client,  # Mock for testing
    poll_interval=1.0,
    position_sync_interval=5.0,
)
```

## Security Notes

- API keys are never logged or displayed in the UI
- Simulation mode is automatically enabled if credentials are missing
- Position files contain only public market data (no keys)
- Daemon validates all commands before execution
