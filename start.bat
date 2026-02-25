@echo off
title AgelClaw Agent
cd /d "%~dp0"

:: Check if Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  =============================================
    echo    Python is not installed or not in PATH
    echo  =============================================
    echo.
    echo  AgelClaw requires Python 3.11 or newer.
    echo.
    echo  Download it from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, check the box
    echo  "Add Python to PATH" on the first screen.
    echo.
    echo  After installing Python, run this file again.
    echo.
    pause
    exit /b 1
)

:: Run the launcher
python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo  Something went wrong. See the error above.
    echo.
    pause
)
