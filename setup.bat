@echo off
setlocal

echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python (3.10 or 3.13 recommended^) and add it to PATH.
    exit /b 1
)

echo.
echo Creating virtual environment (venv)...
if not exist venv (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment.
    exit /b 1
)

echo.
echo Installing dependencies from requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    exit /b 1
)

echo.
echo Setting up configuration...
if not exist .env (
    if exist .env.example (
        echo Creating .env file from .env.example...
        copy .env.example .env
    ) else (
        echo .env.example not found. Creating empty .env...
        type nul > .env
    )
) else (
    echo .env file already exists.
)

echo.
echo Setup complete!
echo.
echo IMPORTANT:
echo 1. Edit .env file to add your API keys.
echo 2. To start the application, run: run.bat
echo.

endlocal
