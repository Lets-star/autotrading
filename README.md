# Trading Bot Project

This project is a foundational Python scaffold for a trading bot.

## Project Structure

```
src/
└── trading_bot/
    ├── data_feeds/    # Data ingestion services
    ├── scoring/       # Strategy and scoring logic
    ├── execution/     # Order execution logic
    ├── risk/          # Risk management
    ├── ui/            # Streamlit dashboard
    ├── config.py      # Centralized configuration
    ├── main.py        # Bot runner entry point
    └── app.py         # Streamlit launcher
```

## Setup

This project uses [Poetry](https://python-poetry.org/) for dependency management.

### Prerequisites

- Python 3.10+
- Poetry

### Installation

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

The project uses `python-dotenv` and `pydantic-settings`. Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_KEY` | Exchange API Key | (Required if not set via secrets) |
| `API_SECRET` | Exchange API Secret | (Required if not set via secrets) |
| `EXCHANGE_ID` | Exchange ID (binance, bybit) | `binance` |
| `RISK_LIMIT_AMOUNT` | Max amount per trade | `100.0` |
| `ATR_MULTIPLIER` | Multiplier for ATR stop loss | `2.0` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Usage

### Run the Bot

```bash
poetry run python -m trading_bot.main
```

### Run the Dashboard

```bash
poetry run streamlit run src/trading_bot/app.py
```
