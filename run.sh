#!/bin/bash

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

echo "Starting Trading Bot Dashboard..."
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
python -m streamlit run src/trading_bot/app.py
