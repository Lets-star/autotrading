# Trading Bot Project

This project is a foundational Python scaffold for a trading bot.

## Project Structure

```
src/
└── trading_bot/
    ├── backtesting/   # Backtesting engine
    ├── data_feeds/    # Data ingestion services (Binance, Bybit)
    ├── scoring/       # Strategy and scoring logic
    ├── execution/     # Order execution logic
    ├── risk/          # Risk management
    ├── ui/            # Streamlit dashboard resources
    ├── config.py      # Centralized configuration
    ├── main.py        # Bot runner entry point
    └── app.py         # Streamlit dashboard
```

## Setup and Installation

### Prerequisites

- Python 3.10+
- Poetry (optional, the setup script can install it)

### Quick Start (Recommended)

**Linux/macOS:**
```bash
./setup.sh
```

**Windows:**
```batch
setup.bat
```

These scripts will:
1. Check for Python and Poetry.
2. Install Poetry if missing.
3. Install project dependencies.
4. Create a `.env` file from `.env.example`.

### Manual Installation

1.  Clone the repository.
2.  Install dependencies:

    ```bash
    poetry install
    ```

    **Note on TA-Lib**: This project optionally uses TA-Lib. If you need it, you must first install the underlying C library.
    - Ubuntu/Debian: `sudo apt-get install libta-lib0` (or compile from source)
    - macOS: `brew install ta-lib`
    - Then uncomment `TA-Lib` in `pyproject.toml` and run `poetry install` again.

## Configuration

The project uses `python-dotenv` and `pydantic-settings`.

### Environment Variables

Edit the `.env` file created by the setup script.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_KEY` | Exchange API Key | (Required if not set via secrets) |
| `API_SECRET` | Exchange API Secret | (Required if not set via secrets) |
| `EXCHANGE_ID` | Exchange ID (binance, bybit) | `binance` |
| `RISK_LIMIT_AMOUNT` | Max amount per trade | `100.0` |
| `ATR_MULTIPLIER` | Multiplier for ATR stop loss | `2.0` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Secrets Management

For the Streamlit dashboard, you can configure secrets in `.streamlit/secrets.toml`:

```toml
[bybit]
api_key = "YOUR_API_KEY"
api_secret = "YOUR_API_SECRET"
```

The application will fall back to environment variables (`API_KEY`, `API_SECRET`) if secrets are not found.

## Usage

### Run the Dashboard

**Linux/macOS:**
```bash
./run.sh
```
or with Make:
```bash
make run
```

**Windows:**
```batch
run.bat
```

**Manual:**
```bash
poetry run streamlit run src/trading_bot/app.py
```

### Run the Bot (Headless)

```bash
poetry run python -m trading_bot.main
```

## Backtesting

The dashboard now includes a "Backtest Lab" mode.
- Connects to Bybit to fetch historical data.
- Simulates trades using `ScoringService` and `RiskService`.
- Displays PnL, Win Rate, and Equity Curve.

## Testing

To run the integration tests:

**Linux/macOS (Make):**
```bash
make test
```

**Manual:**
```bash
poetry run pytest
```
