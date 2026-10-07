@echo off
chcp 65001 >nul
echo ============================================
echo    A股资金流动态检测与ETF交易系统
echo ============================================
echo.
echo 正在启动...
echo.

cd /d "%~dp0"
python start_app.py

pause