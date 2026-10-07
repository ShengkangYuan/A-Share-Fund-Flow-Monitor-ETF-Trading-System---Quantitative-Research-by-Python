@echo off
chcp 65001 >nul
title A股资金流独立调度器
cd /d "%~dp0"

echo ============================================================
echo   A股资金流独立调度器 - 后台运行模式
echo ============================================================
echo.
echo 启动中... 调度器将在后台运行
echo   - 交易时段每5分钟自动采集
echo   - 14:30 自动记录买入信号
echo   - 15:10 后自动运行回测
echo.
echo 关闭此窗口将停止调度器
echo.

REM 尝试用 pythonw 后台运行（无控制台窗口）
where pythonw >nul 2>&1
if %ERRORLEVEL% == 0 (
    start "FundFlowScheduler" /B pythonw scheduler_runner.py
    echo ✅ 调度器已在后台启动（无窗口）
) else (
    echo ⚠️ 未找到 pythonw，使用 python 启动...
    start "FundFlowScheduler" python scheduler_runner.py
    echo ✅ 调度器已启动
)

timeout /t 3 >nul
exit
