"""
分析层 - 资金流分析与信号评分模块
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass

from config import FLOW_CFG, TRADING_CFG


@dataclass
class TradeSignal:
    etf_code: str
    etf_name: str
    industries: str
    score: float
    signal: str
    net_flow: float
    change_pct: float
    inflow_outflow_ratio: float
    reason: str
    rank: int = 0


class FlowAnalyzer:
    """资金流分析器"""

    @staticmethod
    def get_top_inflow(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        return df.nlargest(n, col_net)

    @staticmethod
    def get_top_outflow(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        return df.nsmallest(n, col_net)

    @staticmethod
    def calc_inflow_ratio(df: pd.DataFrame) -> pd.DataFrame:
        col_in = '流入资金' if '流入资金' in df.columns else 'inflow'
        col_out = '流出资金' if '流出资金' in df.columns else 'outflow'
        col_net = '净额' if '净额' in df.columns else 'net_flow'

        df = df.copy()
        df['流入流出比'] = df[col_in] / df[col_out].replace(0, np.nan)
        df.loc[df[col_net] < 0, '流入流出比'] = -df['流入流出比']
        return df

    @staticmethod
    def rank_industries(df: pd.DataFrame) -> pd.DataFrame:
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_change = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'
        col_in = '流入资金' if '流入资金' in df.columns else 'inflow'
        col_out = '流出资金' if '流出资金' in df.columns else 'outflow'

        df = df.copy()

        df['net_flow_rank'] = df[col_net].rank(ascending=False, method='min')
        df['change_rank'] = df[col_change].rank(ascending=False, method='min')

        ratio = df[col_in] / df[col_out].replace(0, np.nan)
        df['ratio_rank'] = ratio.rank(ascending=False, method='min')

        max_rank = len(df)
        w_net = TRADING_CFG.weight_net_flow
        w_change = TRADING_CFG.weight_change
        w_ratio = TRADING_CFG.weight_inflow_ratio

        df['composite_score'] = (
            w_net * (1 - df['net_flow_rank'] / max_rank) +
            w_change * (1 - df['change_rank'] / max_rank) +
            w_ratio * (1 - df['ratio_rank'] / max_rank)
        ) * 100

        df['rank'] = df['composite_score'].rank(ascending=False, method='min').astype(int)
        return df.sort_values('composite_score', ascending=False)

    @staticmethod
    def analyze_sector_momentum(df: pd.DataFrame) -> pd.DataFrame:
        """分析行业动量特征"""
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_change = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'

        df = df.copy()

        df['momentum_score'] = df[col_net] * (1 + df[col_change] / 100)

        df['flow_strength'] = pd.qcut(df[col_net], q=5, labels=[1, 2, 3, 4, 5])
        df['price_strength'] = pd.qcut(df[col_change], q=5, labels=[1, 2, 3, 4, 5])

        df['strength_combined'] = df['flow_strength'].astype(int) + df['price_strength'].astype(int)

        conditions = [
            (df['strength_combined'] >= 8),
            (df['strength_combined'] >= 6) & (df['strength_combined'] < 8),
            (df['strength_combined'] >= 4) & (df['strength_combined'] < 6),
            (df['strength_combined'] >= 2) & (df['strength_combined'] < 4),
        ]
        labels = ['强势', '偏强', '中性', '偏弱']
        df['momentum_label'] = np.select(conditions, labels, default='弱势')

        return df


class SignalGenerator:
    """信号生成器"""

    def __init__(self, mapper):
        self.mapper = mapper

    def generate_etf_signals(self, flow_df: pd.DataFrame) -> List[TradeSignal]:
        analyzer = FlowAnalyzer()
        ranked = analyzer.rank_industries(flow_df)
        ranked = analyzer.calc_inflow_ratio(ranked)
        ranked = analyzer.analyze_sector_momentum(ranked)

        signals = []
        etf_signals = {}

        col_industry = '行业' if '行业' in ranked.columns else 'industry'
        col_net = '净额' if '净额' in ranked.columns else 'net_flow'
        col_change = '行业-涨跌幅' if '行业-涨跌幅' in ranked.columns else 'change_pct'
        col_in = '流入资金' if '流入资金' in ranked.columns else 'inflow'
        col_out = '流出资金' if '流出资金' in ranked.columns else 'outflow'

        for _, row in ranked.iterrows():
            industry = row[col_industry]
            etf_info = self.mapper.get_etf(industry)
            if etf_info is None:
                continue

            code, name = etf_info
            net = row[col_net]
            chg = row[col_change]
            score = row['composite_score']
            ratio = row.get('流入流出比', net / (row[col_out] if row[col_out] > 0 else 1))
            momentum = row.get('momentum_label', '中性')

            if code not in etf_signals:
                etf_signals[code] = {
                    'name': name,
                    'industries': [],
                    'scores': [],
                    'net_flows': [],
                    'changes': [],
                    'ratios': [],
                    'momentums': [],
                }

            etf_signals[code]['industries'].append(industry)
            etf_signals[code]['scores'].append(score)
            etf_signals[code]['net_flows'].append(net)
            etf_signals[code]['changes'].append(chg)
            etf_signals[code]['ratios'].append(ratio)
            etf_signals[code]['momentums'].append(momentum)

        for code, data in etf_signals.items():
            avg_score = np.mean(data['scores'])
            total_net = sum(data['net_flows'])
            avg_change = np.mean(data['changes'])
            avg_ratio = np.mean(data['ratios'])

            strong_count = sum(1 for m in data['momentums'] if m == '强势')
            weak_count = sum(1 for m in data['momentums'] if m == '弱势')

            if avg_score >= TRADING_CFG.buy_threshold and total_net > FLOW_CFG.inflow_threshold:
                signal_type = "buy"
                reason = f"资金净流入{total_net:.1f}亿, 评分{avg_score:.0f}, {strong_count}个强势行业"
            elif avg_score <= TRADING_CFG.sell_threshold and total_net < -FLOW_CFG.outflow_threshold:
                signal_type = "sell"
                reason = f"资金净流出{abs(total_net):.1f}亿, 评分{avg_score:.0f}, {weak_count}个弱势行业"
            else:
                signal_type = "hold"
                reason = f"资金净流{total_net:.1f}亿, 评分{avg_score:.0f}, 等待明确信号"

            signals.append(TradeSignal(
                etf_code=code,
                etf_name=data['name'],
                industries='、'.join(data['industries']),
                score=round(avg_score, 1),
                signal=signal_type,
                net_flow=round(total_net, 2),
                change_pct=round(avg_change, 2),
                inflow_outflow_ratio=round(avg_ratio, 2),
                reason=reason
            ))

        signals.sort(key=lambda s: s.score, reverse=True)
        for i, s in enumerate(signals):
            s.rank = i + 1

        return signals

    def generate_backtest_signals(self, flow_df: pd.DataFrame) -> Dict[str, dict]:
        """生成回测用信号（返回ETF维度的字典）"""
        signals = self.generate_etf_signals(flow_df)
        result = {}
        for s in signals:
            result[s.etf_code] = {
                'name': s.etf_name,
                'score': s.score,
                'signal': s.signal,
                'net_flow': s.net_flow,
                'change_pct': s.change_pct,
                'reason': s.reason,
            }
        return result

    def get_top_buy_signals(self, signals: List[TradeSignal], n: int = 5) -> List[TradeSignal]:
        buys = [s for s in signals if s.signal == "buy"]
        return buys[:n]

    def get_top_sell_signals(self, signals: List[TradeSignal], n: int = 5) -> List[TradeSignal]:
        sells = [s for s in signals if s.signal == "sell"]
        return sells[:n]

    def score_etf(self, etf_df: pd.DataFrame) -> pd.Series:
        """为ETF评分，返回评分Series"""
        if etf_df.empty:
            return pd.Series([], dtype=float)
        
        df = etf_df.copy()

        col_net = 'net_flow' if 'net_flow' in df.columns else ('净额' if '净额' in df.columns else '净流入')
        col_change = 'change_pct' if 'change_pct' in df.columns else ('行业-涨跌幅' if '行业-涨跌幅' in df.columns else '涨跌幅')
        col_in = 'inflow' if 'inflow' in df.columns else ('流入资金' if '流入资金' in df.columns else '流入')
        col_out = 'outflow' if 'outflow' in df.columns else ('流出资金' if '流出资金' in df.columns else '流出')

        max_rank = len(df)
        if max_rank == 0:
            return pd.Series([], dtype=float)
        
        if col_net not in df.columns:
            raise ValueError(f"缺少必要列: {col_net}")
        if col_change not in df.columns:
            raise ValueError(f"缺少必要列: {col_change}")
        
        df['net_flow_rank'] = df[col_net].rank(ascending=False, method='min')
        df['change_rank'] = df[col_change].rank(ascending=False, method='min')
        
        if col_in in df.columns and col_out in df.columns:
            ratio = df[col_in] / df[col_out].replace(0, np.nan)
            df['ratio_rank'] = ratio.rank(ascending=False, method='min')
            w_ratio = TRADING_CFG.weight_inflow_ratio
        else:
            df['ratio_rank'] = df['net_flow_rank']
            w_ratio = 0
        
        w_net = TRADING_CFG.weight_net_flow
        w_change = TRADING_CFG.weight_change

        scores = (
            w_net * (1 - df['net_flow_rank'] / max_rank) +
            w_change * (1 - df['change_rank'] / max_rank) +
            w_ratio * (1 - df['ratio_rank'] / max_rank)
        ) * 100
        
        scores = scores.fillna(0)
        
        return scores