@echo off
title Automated Desktop File Organizer
cd /d "%~dp0"

:: 1. Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Setting up on this machine...
    
    :: Check if Python is installed on the system
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python was not found on this system.
        echo Please install Python 3.10+ from https://www.python.org and make sure to check "Add Python to PATH".
        pause
        exit /b 1
    )

    echo [INFO] Creating virtual environment (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo [INFO] Installing required dependencies...
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\pip.exe install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies from requirements.txt.
        pause
        exit /b 1
    )
    echo [SUCCESS] Setup completed successfully!
)

:: 2. Launch the Application
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "run_gui.py"
) else (
    "venv\Scripts\python.exe" "run_gui.py"
)

