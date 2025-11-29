@echo off
setlocal

if not exist venv (
    echo Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting Trading Bot Dashboard...
set PYTHONPATH=%CD%\src
python -m streamlit run src/trading_bot/app.py
if %errorlevel% neq 0 (
    echo Application failed to start.
    pause
)

endlocal
