@echo off
title NOC360 VOS Launcher

set "ANTI_HACK_URL=%~1"
set "VOS_SHORTCUT_PATH=%~2"

echo ====================================
echo NOC360 VOS Desktop Launcher
echo ====================================
echo Anti-Hack URL: %ANTI_HACK_URL%
echo VOS Shortcut: %VOS_SHORTCUT_PATH%
echo.

if "%VOS_SHORTCUT_PATH%"=="" (
  echo ERROR: VOS shortcut/app path was not provided.
  timeout /t 6
  exit /b 1
)

if not "%ANTI_HACK_URL%"=="" (
  echo Opening Anti-Hack whitelist page...
  start "" "%ANTI_HACK_URL%"
  timeout /t 3 /nobreak >nul
)

echo Launching selected VOS client...
start "" "%VOS_SHORTCUT_PATH%"

echo.
echo If VOS does not open, check the selected shortcut/app path in NOC360.
timeout /t 5
