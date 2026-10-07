@echo off
chcp 65001 >nul
echo ============================================
echo   A-Share Fund Flow Monitor and ETF System
echo ============================================
echo.
echo Starting dashboard...
echo.

cd /d "%~dp0"
python start_app.py

pause
