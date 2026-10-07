@echo off
chcp 65001 >nul
title A-Share Fund Flow - Standalone Scheduler
cd /d "%~dp0"

echo ============================================================
echo   Standalone scheduler (keeps fetching after browser closes)
echo   - Fetches fund-flow snapshots every 5 min in market hours
echo   - Records 14:30 buy signals automatically
echo   - Close this window to stop
echo ============================================================
echo.

python scheduler_runner.py

pause
