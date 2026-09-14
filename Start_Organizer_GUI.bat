@echo off
title Automated Desktop File Organizer
cd /d "%~dp0"

:: Check if virtual environment exists
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "run_gui.py"
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "run_gui.py"
) else (
    python "run_gui.py"
)
