"""
资金流动态检测与ETF交易系统 - 主入口
提供：CLI模式（单次运行）/ Dashboard模式（实时看板）
"""

import sys
import argparse
from datetime import datetime

from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import IndustryETFMapper, ETFFetcher
from flow_analyzer import FlowAnalyzer, SignalGenerator
from portfolio import Portfolio


def run_cli():
    """命令行模式：获取数据、分析、输出报告"""
    print("=" * 60)
    print(f"  A股资金流动态检测与ETF交易系统")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 获取数据
    print("\n📡 获取行业资金流向数据...")
    fetcher = FundFlowFetcher()
    flow_df = fetcher.fetch_industry_flow()
    fetcher.save_daily_snapshot(flow_df)
    print(f"   ✓ 获取到 {len(flow_df)} 个行业数据")

    # 2. 分析排名
    print("\n📊 行业资金流排名分析...")
    analyzer = FlowAnalyzer()
    ranked = analyzer.rank_industries(flow_df)

    # TOP 10 净流入
    top_in = analyzer.get_top_inflow(flow_df, 10)
    print(f"\n  📈 TOP 10 净流入行业:")
    print(f"  {'排名':<4} {'行业':<12} {'净流入(亿)':<10} {'涨跌幅':<8}")
    print(f"  {'-'*36}")
    for i, (_, row) in enumerate(top_in.iterrows(), 1):
        print(f"  {i:<4} {row['行业']:<12} {row['净额']:<+8.2f}亿 {row['行业-涨跌幅']:<+7.2f}%")

    # TOP 10 净流出
    top_out = analyzer.get_top_outflow(flow_df, 10)
    print(f"\n  📉 TOP 10 净流出行业:")
    print(f"  {'排名':<4} {'行业':<12} {'净流出(亿)':<10} {'涨跌幅':<8}")
    print(f"  {'-'*36}")
    for i, (_, row) in enumerate(top_out.iterrows(), 1):
        print(f"  {i:<4} {row['行业']:<12} {abs(row['净额']):<+8.2f}亿 {row['行业-涨跌幅']:<+7.2f}%")

    # 3. 生成ETF信号
    print("\n🎯 ETF交易信号...")
    mapper = IndustryETFMapper()
    signal_gen = SignalGenerator(mapper)
    signals = signal_gen.generate_etf_signals(flow_df)

    buy = [s for s in signals if s.signal == "buy"]
    sell = [s for s in signals if s.signal == "sell"]
    hold = [s for s in signals if s.signal == "hold"]

    if buy:
        print(f"\n  🟢 买入信号 ({len(buy)}):")
        for s in buy[:5]:
            print(f"    {s.etf_name}({s.etf_code}) 评分{s.score:.0f} 净流入{s.net_flow:+.1f}亿 - {s.reason}")

    if sell:
        print(f"\n  🔴 卖出信号 ({len(sell)}):")
        for s in sell[:5]:
            print(f"    {s.etf_name}({s.etf_code}) 评分{s.score:.0f} 净流入{s.net_flow:+.1f}亿 - {s.reason}")

    print(f"\n  🟡 持有/观望: {len(hold)} 只")

    # 4. 市场概览
    print(f"\n📋 市场概览:")
    print(f"  全市场净流入: {flow_df['净额'].sum():+.1f}亿")
    print(f"  上涨行业: {len(flow_df[flow_df['行业-涨跌幅'] > 0])}/{len(flow_df)}")
    print(f"  资金净流入行业: {len(flow_df[flow_df['净额'] > 0])}/{len(flow_df)}")

    print(f"\n{'=' * 60}")
    print(f"  分析完成！运行 dashboard.py 打开实时看板")
    print(f"{'=' * 60}")


def run_dashboard():
    """启动Streamlit看板"""
    import subprocess
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")
    print("🚀 启动实时看板...")
    print(f"  文件: {dashboard_path}")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        dashboard_path,
        "--server.port", "8501",
        "--server.headless", "false",
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="资金流动态检测与ETF交易系统")
    parser.add_argument("mode", nargs="?", default="cli",
                        choices=["cli", "dashboard", "dash"],
                        help="运行模式: cli(命令行) / dashboard(实时看板)")
    parser.add_argument("--port", type=int, default=8501,
                        help="Dashboard端口号")

    args = parser.parse_args()

    if args.mode == "cli":
        run_cli()
    elif args.mode in ("dashboard", "dash"):
        run_dashboard()
#streamlit run e:/jupyter/quant2026/资金流动态检测与ETF交易系统/dashboard.py