@echo off
title NOC360 Local Launcher
cd /d "%~dp0"

echo ====================================
echo NOC360 Local VOS Launcher
echo ====================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Please install Python 3 first.
  pause
  exit /b 1
)

echo Installing/updating launcher dependency...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install requirements.
  pause
  exit /b 1
)

echo.
echo Starting NOC360 Launcher on http://127.0.0.1:5055
python launcher.py
pause
