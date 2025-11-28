@echo off
echo Starting Trading Bot Dashboard...
call poetry run streamlit run src/trading_bot/app.py
if %errorlevel% neq 0 (
    echo Application failed to start.
    pause
)
