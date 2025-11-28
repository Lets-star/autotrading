#!/bin/bash

# Add user local bin to PATH just in case (standard location for poetry)
export PATH="$HOME/.local/bin:$PATH"

# Ensure poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Poetry not found. Please run ./setup.sh first."
    exit 1
fi

echo "Starting Trading Bot Dashboard..."
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
poetry run streamlit run src/trading_bot/app.py
