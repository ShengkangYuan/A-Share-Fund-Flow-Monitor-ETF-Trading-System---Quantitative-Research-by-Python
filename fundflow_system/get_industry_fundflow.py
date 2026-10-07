"""
A股行业资金流向数据获取
数据来源：东方财富（AKShare）
日期：2026-07-16
"""

import akshare as ak
import pandas as pd
from datetime import datetime


def fetch_industry_fundflow() -> pd.DataFrame:
    """
    获取当日A股行业资金流向数据

    Returns:
        DataFrame 包含以下列：
        - 序号: 排名
        - 行业: 行业名称
        - 行业指数: 板块指数
        - 行业-涨跌幅: 板块涨跌幅(%)
        - 流入资金: 主力资金流入(亿)
        - 流出资金: 主力资金流出(亿)
        - 净额: 资金净流入(亿)
        - 公司家数: 板块内公司数量
        - 领涨股: 领涨股票名称
        - 领涨股-涨跌幅: 领涨股涨跌幅(%)
        - 当前价: 领涨股当前价格
    """
    df = ak.stock_fund_flow_industry()
    return df


def save_data(df: pd.DataFrame, filepath: str):
    """保存数据到CSV"""
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"✓ 数据已保存: {filepath}")
    print(f"  共 {len(df)} 个行业")


def print_summary(df: pd.DataFrame):
    """打印资金流向摘要"""

    # 按净流入排序
    df_sorted = df.sort_values('净额', ascending=False)

    print(f"\n{'='*60}")
    print(f"  A股行业资金流向日报 - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}")

    print(f"\n📈 TOP 10 资金净流入行业:")
    print(f"{'排名':<4} {'行业':<14} {'涨跌幅':>8} {'净流入(亿)':>10} {'流入(亿)':>10} {'流出(亿)':>10}")
    print("-" * 58)
    for i, row in df_sorted.head(10).iterrows():
        chg = f"{row['行业-涨跌幅']:+.2f}%"
        print(f" {row['序号']:<3} {row['行业']:<14} {chg:>8} {row['净额']:>8.2f}亿 {row['流入资金']:>8.2f}亿 {row['流出资金']:>8.2f}亿")

    print(f"\n📉 TOP 10 资金净流出行业:")
    print(f"{'排名':<4} {'行业':<14} {'涨跌幅':>8} {'净流出(亿)':>10} {'流入(亿)':>10} {'流出(亿)':>10}")
    print("-" * 58)
    for i, row in df_sorted.tail(10).iloc[::-1].iterrows():
        chg = f"{row['行业-涨跌幅']:+.2f}%"
        print(f" {row['序号']:<3} {row['行业']:<14} {chg:>8} {abs(row['净额']):>8.2f}亿 {row['流入资金']:>8.2f}亿 {row['流出资金']:>8.2f}亿")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    # 获取数据
    df = fetch_industry_fundflow()

    # 保存到CSV
    save_data(df, "industry_fundflow_20260716.csv")

    # 打印摘要
    print_summary(df)
