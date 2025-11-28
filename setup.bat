@echo off
setlocal

echo Checking requirements...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    exit /b 1
)

call poetry --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Poetry not found. Installing via pip...
    pip install poetry
    if %errorlevel% neq 0 (
        echo Failed to install poetry.
        exit /b 1
    )
)

echo Installing dependencies...
call poetry install
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    exit /b 1
)

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
echo Please configure your API keys in the .env file.
echo To run the application, use: run.bat
echo.

endlocal
