@echo off
chcp 65001 >nul
echo ============================================
echo  资金流动态检测与ETF交易系统
echo ============================================
echo.
echo 请选择运行模式:
echo  1) CLI模式 - 单次运行，输出分析报告
echo  2) Dashboard模式 - Streamlit实时看板
echo  3) VS Code 模式 - 在VS Code中编辑代码
echo  4) 生成HTML报告 - 生成静态分析报告
echo.
set /p mode="请输入选项 (1/2/3/4): "

cd /d "%~dp0"

if "%mode%"=="1" (
    echo.
    echo 运行CLI分析...
    python main.py cli
    echo.
    pause
) else if "%mode%"=="2" (
    echo.
    echo 启动Streamlit实时看板...
    echo 浏览器将自动打开: http://localhost:8501
    echo 按 Ctrl+C 停止
    echo.
    python -m streamlit run dashboard.py --server.port 8501
) else if "%mode%"=="3" (
    code .
) else if "%mode%"=="4" (
    echo.
    echo 生成HTML报告...
    python -c "from fundflow_fetcher import FundFlowFetcher; from etf_fetcher import IndustryETFMapper; from flow_analyzer import SignalGenerator; from visualizer import Visualizer; f=FundFlowFetcher(); df=f.fetch_industry_flow(); m=IndustryETFMapper(); sg=SignalGenerator(m); s=sg.generate_etf_signals(df); Visualizer.create_full_report(df, s)"
    echo.
    echo 报告已生成到 data/reports/ 目录
    pause
) else (
    echo 无效选项！
    pause
)
