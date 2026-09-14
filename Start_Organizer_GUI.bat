@echo off
setlocal enabledelayedexpansion
title Automated Desktop File Organizer
cd /d "%~dp0"

REM 1. Check if virtual environment already exists
if exist "venv\Scripts\python.exe" goto :launch

echo ===================================================
echo [INFO] First time setup: Virtual environment not found.
echo Setting up environment on this machine...
echo ===================================================

REM Check if Python is installed
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on your system!
    echo Please download and install Python 3.10+ from https://www.python.org/
    echo NOTE: Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [INFO] Creating Python virtual environment (venv)...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing required dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip --quiet
venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install packages from requirements.txt.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Environment successfully created!
echo ===================================================

:launch
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "run_gui.py"
) else (
    start "" "venv\Scripts\python.exe" "run_gui.py"
)

exit /b 0
