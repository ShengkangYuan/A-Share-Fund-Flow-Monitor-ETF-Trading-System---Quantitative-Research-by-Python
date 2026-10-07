"""
回测模块 - 基于下午2:30资金流的ETF交易回测系统
策略逻辑：
1. 每天下午2:30获取行业资金流数据
2. 基于资金流强度和趋势选择ETF
3. 次日以开盘价执行交易
4. 设置止损(-5%)和止盈(+15%)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from config import BACKTEST_CFG, INDUSTRY_ETF_MAPPING, BACKTEST_DIR
from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import ETFFetcher
from flow_analyzer import SignalGenerator, FlowAnalyzer


@dataclass
class BacktestPosition:
    etf_code: str
    etf_name: str
    entry_price: float
    current_price: float
    shares: int
    entry_date: str
    entry_signal_score: float
    stop_loss: float = 0.0
    take_profit: float = 0.0

    @property
    def pnl_pct(self) -> float:
        return (self.current_price - self.entry_price) / self.entry_price * 100

    @property
    def pnl_amount(self) -> float:
        return (self.current_price - self.entry_price) * self.shares

    @property
    def value(self) -> float:
        return self.current_price * self.shares


@dataclass
class BacktestTrade:
    etf_code: str
    etf_name: str
    direction: str
    price: float
    shares: int
    amount: float
    date: str
    reason: str
    pnl: float = 0.0
    signal_score: float = 0.0
    net_flow: float = 0.0
    holding_days: int = 0


@dataclass
class BacktestResult:
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    # 收益指标
    total_return: float
    annualized_return: float
    baseline_return: float = 0.0
    excess_return: float = 0.0
    # 风险指标
    max_drawdown: float = 0.0
    max_drawdown_start: str = ""
    max_drawdown_end: str = ""
    max_drawdown_duration: int = 0
    max_drawdown_recovery: int = 0
    volatility: float = 0.0
    downside_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    # 交易统计
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_win_pnl: float = 0.0
    avg_lose_pnl: float = 0.0
    max_win_pnl: float = 0.0
    max_lose_pnl: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_holding_days: float = 0.0
    max_holding_days: int = 0
    min_holding_days: int = 0
    # 基准对比
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    upside_capture: float = 0.0
    downside_capture: float = 0.0
    # 持仓统计
    max_open_positions: int = 0
    avg_open_positions: float = 0.0
    capital_utilization: float = 0.0
    # 数据
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades: List[BacktestTrade] = field(default_factory=list)
    daily_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    position_stats: Dict = field(default_factory=dict)


class ETFBacktester:
    """ETF资金流策略回测器 - 基于下午2:30资金流数据"""

    def __init__(self, config=None):
        self.config = config or BACKTEST_CFG
        self.fundflow_fetcher = FundFlowFetcher()
        self.etf_fetcher = ETFFetcher()
        self.mapping = INDUSTRY_ETF_MAPPING

        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[Dict] = []
        self.daily_signals: List[Dict] = []

        self.cash = self.config.initial_capital
        self.initial_capital = self.config.initial_capital
        self.current_date = None

        self.win_count = 0
        self.lose_count = 0
        self.total_pnl = 0
        self.total_win_pnl = 0
        self.total_lose_pnl = 0

    def _get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取回测期间的交易日列表"""
        dates = []
        current = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        while current <= end:
            if current.weekday() < 5:
                dates.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        return dates

    def _fetch_etf_prices(self, codes: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """批量获取ETF历史价格"""
        results = {}
        for code in codes:
            df = self.etf_fetcher.fetch_etf_hist(code, days=730)
            if not df.empty:
                results[code] = df
        return results

    def _fetch_baseline(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取沪深300基准数据"""
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol="sh000300")
            df = df[df['date'] >= start_date]
            df = df[df['date'] <= end_date]
            df = df.sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"获取沪深300基准失败: {e}")
            return pd.DataFrame()

    def _get_price_on_date(self, prices: Dict[str, pd.DataFrame], code: str, date_str: str) -> Optional[float]:
        """获取指定日期的ETF价格"""
        if code not in prices:
            return None

        df = prices[code]
        if '日期' in df.columns:
            mask = df['日期'] == date_str
        elif 'trade_date' in df.columns:
            mask = df['trade_date'] == date_str
        else:
            return None

        if mask.any():
            row = df[mask].iloc[0]
            if '收盘价' in row:
                return float(row['收盘价'])
            elif 'close' in row:
                return float(row['close'])
            elif '最新价' in row:
                return float(row['最新价'])
        return None

    def _get_open_price_on_date(self, prices: Dict[str, pd.DataFrame], code: str, date_str: str) -> Optional[float]:
        """获取指定日期的ETF开盘价"""
        if code not in prices:
            return None

        df = prices[code]
        if '日期' in df.columns:
            mask = df['日期'] == date_str
        elif 'trade_date' in df.columns:
            mask = df['trade_date'] == date_str
        else:
            return None

        if mask.any():
            row = df[mask].iloc[0]
            if '开盘价' in row:
                return float(row['开盘价'])
            elif 'open' in row:
                return float(row['open'])
            elif '收盘价' in row:
                return float(row['收盘价'])
        return None

    def _calculate_shares(self, price: float) -> int:
        """计算可买入数量"""
        max_amount = self.config.initial_capital * self.config.position_size
        shares = int(max_amount / price / 100) * 100
        actual_cost = shares * price

        if actual_cost > self.cash:
            shares = int(self.cash / price / 100) * 100

        return max(shares, 0)

    def _calculate_transaction_cost(self, amount: float, direction: str) -> float:
        """计算交易成本"""
        cost = 0
        
        cost += amount * self.config.commission_rate
        
        if hasattr(self.config, 'slippage_rate'):
            cost += amount * self.config.slippage_rate
        
        if direction == 'sell' and hasattr(self.config, 'stamp_tax_rate'):
            cost += amount * self.config.stamp_tax_rate
        
        return cost

    def _open_position(self, code: str, name: str, price: float, date_str: str, reason: str,
                       signal_score: float = 0, net_flow: float = 0):
        """开仓"""
        if len(self.positions) >= self.config.max_positions:
            return None

        shares = self._calculate_shares(price)
        if shares <= 0:
            return None

        cost = shares * price
        transaction_cost = self._calculate_transaction_cost(cost, 'buy')
        total_cost = cost + transaction_cost

        if total_cost > self.cash:
            return None

        position = BacktestPosition(
            etf_code=code,
            etf_name=name,
            entry_price=price,
            current_price=price,
            shares=shares,
            entry_date=date_str,
            entry_signal_score=signal_score,
            stop_loss=self.config.stop_loss,
            take_profit=self.config.take_profit,
        )

        self.positions[code] = position
        self.cash -= total_cost

        trade = BacktestTrade(
            etf_code=code, etf_name=name,
            direction="buy", price=price,
            shares=shares, amount=cost,
            date=date_str, reason=reason,
            signal_score=signal_score,
            net_flow=net_flow,
        )
        self.trades.append(trade)
        return position

    def _close_position(self, code: str, price: float, date_str: str, reason: str):
        """平仓"""
        position = self.positions.pop(code, None)
        if position is None:
            return None

        amount = price * position.shares
        transaction_cost = self._calculate_transaction_cost(amount, 'sell')
        net_amount = amount - transaction_cost

        pnl = net_amount - (position.entry_price * position.shares)

        self.cash += net_amount

        if pnl > 0:
            self.win_count += 1
            self.total_win_pnl += pnl
        else:
            self.lose_count += 1
            self.total_lose_pnl += pnl
        self.total_pnl += pnl

        holding_days = (pd.to_datetime(date_str) - pd.to_datetime(position.entry_date)).days

        trade = BacktestTrade(
            etf_code=code, etf_name=position.etf_name,
            direction="sell", price=price,
            shares=position.shares, amount=amount,
            date=date_str, reason=reason, pnl=pnl,
            signal_score=position.entry_signal_score,
            holding_days=holding_days,
        )
        self.trades.append(trade)
        return trade

    def _check_stop_loss_take_profit(self, prices: Dict[str, pd.DataFrame], date_str: str):
        """检查止损止盈"""
        closed = []
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            price = self._get_price_on_date(prices, code, date_str)
            if price is None:
                continue

            pos.current_price = price

            if pos.pnl_pct <= pos.stop_loss * 100:
                trade = self._close_position(code, price, date_str, f"止损 ({pos.pnl_pct:.1f}%)")
                if trade:
                    closed.append(trade)
            elif pos.pnl_pct >= pos.take_profit * 100:
                trade = self._close_position(code, price, date_str, f"止盈 ({pos.pnl_pct:.1f}%)")
                if trade:
                    closed.append(trade)
        return closed

    def _calculate_total_value(self, prices: Dict[str, pd.DataFrame], date_str: str) -> float:
        """计算总资产"""
        position_value = 0
        for code, pos in self.positions.items():
            price = self._get_price_on_date(prices, code, date_str)
            if price is not None:
                pos.current_price = price
                position_value += price * pos.shares
        return self.cash + position_value

    def _safe_quintile(self, s: pd.Series) -> pd.Series:
        """
        稳健五分位：先做无并列排名再 qcut，
        避免值大量相同（如补齐数据涨跌幅缺失为 0）时
        'Bin edges must be unique' 崩溃。
        """
        ranks = s.rank(method='first')
        n = len(ranks)
        if n == 0:
            return pd.Series(dtype=int)
        if n >= 5:
            return pd.qcut(ranks, q=5, labels=[1, 2, 3, 4, 5]).astype(int)
        # 行业不足 5 个时，按排名均匀映射到 1..n
        return ((ranks - 1) * 5 // n).clip(upper=4).astype(int) + 1

    def _analyze_flow_strength(self, flow_df: pd.DataFrame) -> pd.DataFrame:
        """分析资金流强度特征"""
        analyzer = FlowAnalyzer()
        df = analyzer.rank_industries(flow_df)
        df = analyzer.calc_inflow_ratio(df)
        df = analyzer.analyze_sector_momentum(df)

        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_change = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'

        df['flow_strength'] = self._safe_quintile(df[col_net])
        df['price_strength'] = self._safe_quintile(df[col_change])
        df['combined_strength'] = df['flow_strength'] + df['price_strength']

        return df

    def run(self, start_date: str = None, end_date: str = None, progress_callback=None) -> BacktestResult:
        """
        运行回测
        策略逻辑：每天下午2:30根据资金流选择ETF，次日以开盘价执行交易
        Args:
            progress_callback: 进度回调函数
        """
        start_date = start_date or self.config.start_date
        end_date = end_date or self.config.end_date

        if progress_callback:
            progress_callback(5, "初始化回测参数...")

        trading_dates = self._get_trading_dates(start_date, end_date)

        if progress_callback:
            progress_callback(10, "获取ETF价格数据...")

        all_etf_codes = list(set(code for _, (code, _) in self.mapping.items()))
        prices = self._fetch_etf_prices(all_etf_codes, start_date, end_date)

        if progress_callback:
            progress_callback(20, "获取沪深300基准...")

        baseline_df = self._fetch_baseline(start_date, end_date)

        if progress_callback:
            progress_callback(25, "获取资金流历史数据...")

        fundflow_history = self.fundflow_fetcher.fetch_history_for_backtest(start_date, end_date)

        # 如果缓存数据不足，自动从东方财富拉取历史数据补齐
        valid_dates = [d for d in trading_dates if d in fundflow_history]
        if len(valid_dates) < 10:
            if progress_callback:
                progress_callback(28, f"缓存数据不足({len(valid_dates)}天)，自动从东方财富补齐历史...")
            try:
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                days_needed = (end_dt - start_dt).days + 1
                # 只拉取有 ETF 映射的行业，减少请求数、降低被东财限流概率
                mapped_industries = list(dict.fromkeys(
                    ind for ind, (_, _) in INDUSTRY_ETF_MAPPING.items()
                ))
                backfilled = self.fundflow_fetcher.backfill_history_from_eastmoney(
                    days=min(days_needed + 5, 90),  # 多补 5 天冗余，最多 90 天
                    industries=mapped_industries,
                )
                # 合并到已有缓存（不覆盖现有更完整的数据）
                for d, df in backfilled.items():
                    if d not in fundflow_history:
                        fundflow_history[d] = df
                valid_dates = [d for d in trading_dates if d in fundflow_history]
            except Exception as e:
                logger.warning(f"自动补齐历史数据失败: {e}")

        if not fundflow_history:
            raise RuntimeError("没有找到资金流历史数据，请先积累数据")

        if len(valid_dates) < 10:
            raise RuntimeError(f"有效数据日期不足，仅找到 {len(valid_dates)} 天")

        from etf_fetcher import IndustryETFMapper
        mapper = IndustryETFMapper()
        signal_gen = SignalGenerator(mapper)

        # 策略模式分支
        mode = getattr(self.config, "strategy_mode", "continuous")
        if mode == "next_day_rotation":
            return self._run_next_day_rotation(
                start_date, end_date, valid_dates, fundflow_history,
                prices, baseline_df, mapper, signal_gen, progress_callback
            )

        total_steps = len(valid_dates)
        for i, date_str in enumerate(valid_dates):
            self.current_date = date_str

            flow_df = fundflow_history[date_str]

            flow_df = self._analyze_flow_strength(flow_df)

            signals = signal_gen.generate_backtest_signals(flow_df)

            top_buy = sorted(
                [(k, v) for k, v in signals.items() if v['signal'] == 'buy'],
                key=lambda x: x[1]['score'],
                reverse=True
            )[:self.config.max_positions]

            current_holdings = set(self.positions.keys())
            buy_codes = {code for code, _ in top_buy}

            for code in current_holdings - buy_codes:
                price = self._get_price_on_date(prices, code, date_str)
                if price is not None:
                    self._close_position(code, price, date_str, "不再符合买入条件")

            if i < len(valid_dates) - 1:
                next_date = valid_dates[i + 1]
                for code, info in top_buy:
                    if code not in self.positions:
                        open_price = self._get_open_price_on_date(prices, code, next_date)
                        if open_price is not None:
                            self._open_position(code, info['name'], open_price, next_date,
                                                f"下午2:30资金流信号 - {info['reason']}",
                                                signal_score=info['score'],
                                                net_flow=info.get('net_flow', 0))

            self._check_stop_loss_take_profit(prices, date_str)

            total_value = self._calculate_total_value(prices, date_str)
            position_pnl = total_value - self.initial_capital
            position_pnl_pct = position_pnl / self.initial_capital * 100

            baseline_pct = 0
            if not baseline_df.empty:
                baseline_mask = baseline_df['date'] == date_str
                if baseline_mask.any():
                    baseline_close = baseline_df.loc[baseline_mask, 'close'].iloc[0]
                    baseline_first = baseline_df['close'].iloc[0]
                    baseline_pct = (baseline_close - baseline_first) / baseline_first * 100

            self.equity_curve.append({
                'date': date_str,
                'total_value': total_value,
                'cash': self.cash,
                'position_value': total_value - self.cash,
                'pnl': position_pnl,
                'pnl_pct': position_pnl_pct,
                'positions': len(self.positions),
                'baseline_pct': baseline_pct,
            })

            self.daily_signals.append({
                'date': date_str,
                'buy_signals': len([s for s in signals.values() if s['signal'] == 'buy']),
                'sell_signals': len([s for s in signals.values() if s['signal'] == 'sell']),
                'hold_signals': len([s for s in signals.values() if s['signal'] == 'hold']),
                'total_flow': flow_df['净额'].sum() if '净额' in flow_df.columns else 0,
            })

            if progress_callback and i % max(1, total_steps // 20) == 0:
                progress_callback(25 + int((i + 1) / total_steps * 70), f"处理日期: {date_str}")

        if progress_callback:
            progress_callback(95, "处理收尾清仓...")

        for code in list(self.positions.keys()):
            price = self._get_price_on_date(prices, valid_dates[-1])
            if price is None:
                price = self._get_price_on_date(prices, code, valid_dates[-1])
            if price is not None:
                self._close_position(code, price, valid_dates[-1], "回测结束清仓")

        total_value = self._calculate_total_value(prices, valid_dates[-1])
        
        baseline_pct = 0
        if not baseline_df.empty:
            baseline_last = baseline_df['close'].iloc[-1]
            baseline_first = baseline_df['close'].iloc[0]
            baseline_pct = (baseline_last - baseline_first) / baseline_first * 100

        self.equity_curve.append({
            'date': valid_dates[-1],
            'total_value': total_value,
            'cash': self.cash,
            'position_value': total_value - self.cash,
            'pnl': total_value - self.initial_capital,
            'pnl_pct': (total_value - self.initial_capital) / self.initial_capital * 100,
            'positions': 0,
            'baseline_pct': baseline_pct,
        })

        if progress_callback:
            progress_callback(100, "生成回测结果...")

        return self._generate_result(start_date, end_date, valid_dates, baseline_df)

    def _run_next_day_rotation(self, start_date, end_date, valid_dates, fundflow_history,
                                prices, baseline_df, mapper, signal_gen, progress_callback=None) -> BacktestResult:
        """
        次日14:30强制换仓策略
        逻辑：
          - 每日14:30基于资金流选前5 ETF作为信号
          - 次日14:30（按收盘价近似）卖出所有持仓 + 买入新的5只 ETF
          - 持有到下一日14:30
        """
        if progress_callback:
            progress_callback(30, "运行次日14:30换仓策略...")

        # 预计算每个交易日的 top 信号
        daily_top: Dict[str, List] = {}
        daily_signals_meta: Dict[str, Dict] = {}
        for date_str in valid_dates:
            flow_df = fundflow_history[date_str]
            flow_df = self._analyze_flow_strength(flow_df)
            signals = signal_gen.generate_backtest_signals(flow_df)

            # 买入信号不足时用 hold 信号补足（保证每日都有 5 只候选）
            top_buy = sorted(
                [(k, v) for k, v in signals.items() if v['signal'] == 'buy'],
                key=lambda x: x[1]['score'], reverse=True
            )
            if len(top_buy) < self.config.max_positions:
                # 用其他信号补足
                others = sorted(
                    [(k, v) for k, v in signals.items() if v['signal'] != 'buy'],
                    key=lambda x: x[1]['score'], reverse=True
                )
                top_buy = (top_buy + others)[:self.config.max_positions]

            daily_top[date_str] = top_buy
            daily_signals_meta[date_str] = {
                'buy_signals': len([s for s in signals.values() if s['signal'] == 'buy']),
                'sell_signals': len([s for s in signals.values() if s['signal'] == 'sell']),
                'hold_signals': len([s for s in signals.values() if s['signal'] == 'hold']),
                'total_flow': float(flow_df['净额'].sum()) if '净额' in flow_df.columns else 0,
            }

        total_steps = len(valid_dates)
        exec_price_mode = getattr(self.config, "execution_price", "close")

        def _exec_price(code, date_str):
            if exec_price_mode == "open":
                p = self._get_open_price_on_date(prices, code, date_str)
                if p is not None:
                    return p
            # 默认用收盘价近似 14:30
            return self._get_price_on_date(prices, code, date_str)

        # 第一日：仅记录信号，不开仓
        for i, date_str in enumerate(valid_dates):
            self.current_date = date_str

            # 1) 换仓：在当日 14:30 卖出旧持仓 + 买入新信号
            if i > 0:
                new_top = daily_top.get(date_str, [])
                new_codes = {code for code, _ in new_top}

                # 卖出所有旧持仓（强制换仓）
                for code in list(self.positions.keys()):
                    price = _exec_price(code, date_str)
                    if price is not None:
                        self._close_position(code, price, date_str, "次日14:30强制换仓-卖出")

                # 买入新的5只
                for code, info in new_top:
                    if code not in self.positions:
                        buy_price = _exec_price(code, date_str)
                        if buy_price is not None:
                            self._open_position(
                                code, info['name'], buy_price, date_str,
                                f"14:30资金流信号-次日换仓买入 score={info['score']:.1f}",
                                signal_score=info['score'],
                                net_flow=info.get('net_flow', 0)
                            )

            # 2) 持仓期间止损止盈检查
            self._check_stop_loss_take_profit(prices, date_str)

            # 3) 记录权益
            total_value = self._calculate_total_value(prices, date_str)
            position_pnl = total_value - self.initial_capital
            position_pnl_pct = position_pnl / self.initial_capital * 100

            baseline_pct = 0
            if not baseline_df.empty:
                baseline_mask = baseline_df['date'] == date_str
                if baseline_mask.any():
                    baseline_close = baseline_df.loc[baseline_mask, 'close'].iloc[0]
                    baseline_first = baseline_df['close'].iloc[0]
                    baseline_pct = (baseline_close - baseline_first) / baseline_first * 100

            self.equity_curve.append({
                'date': date_str,
                'total_value': total_value,
                'cash': self.cash,
                'position_value': total_value - self.cash,
                'pnl': position_pnl,
                'pnl_pct': position_pnl_pct,
                'positions': len(self.positions),
                'baseline_pct': baseline_pct,
            })

            meta = daily_signals_meta.get(date_str, {})
            self.daily_signals.append({
                'date': date_str,
                'buy_signals': meta.get('buy_signals', 0),
                'sell_signals': meta.get('sell_signals', 0),
                'hold_signals': meta.get('hold_signals', 0),
                'total_flow': meta.get('total_flow', 0),
            })

            if progress_callback and i % max(1, total_steps // 20) == 0:
                progress_callback(30 + int((i + 1) / total_steps * 60), f"换仓处理: {date_str}")

        # 回测结束清仓
        if progress_callback:
            progress_callback(92, "回测结束清仓...")

        last_date = valid_dates[-1]
        for code in list(self.positions.keys()):
            price = _exec_price(code, last_date)
            if price is not None:
                self._close_position(code, price, last_date, "回测结束清仓")

        total_value = self._calculate_total_value(prices, last_date)
        baseline_pct = 0
        if not baseline_df.empty:
            baseline_last = baseline_df['close'].iloc[-1]
            baseline_first = baseline_df['close'].iloc[0]
            baseline_pct = (baseline_last - baseline_first) / baseline_first * 100

        self.equity_curve.append({
            'date': last_date,
            'total_value': total_value,
            'cash': self.cash,
            'position_value': total_value - self.cash,
            'pnl': total_value - self.initial_capital,
            'pnl_pct': (total_value - self.initial_capital) / self.initial_capital * 100,
            'positions': 0,
            'baseline_pct': baseline_pct,
        })

        if progress_callback:
            progress_callback(100, "生成回测结果...")

        return self._generate_result(start_date, end_date, valid_dates, baseline_df)

    def _generate_result(self, start_date: str, end_date: str, valid_dates: List[str], baseline_df=None) -> BacktestResult:
        """生成回测结果（含完整风险/交易/基准指标）"""
        equity_df = pd.DataFrame(self.equity_curve)

        if equity_df.empty:
            return BacktestResult(
                start_date=start_date, end_date=end_date,
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
                total_return=0, annualized_return=0,
                equity_curve=equity_df, trades=[],
            )

        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date').sort_index()

        # ===== 收益指标 =====
        total_return = (equity_df['total_value'].iloc[-1] - self.initial_capital) / self.initial_capital * 100

        days = (equity_df.index[-1] - equity_df.index[0]).days
        annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0

        # ===== 风险指标 =====
        running_max = equity_df['total_value'].cummax()
        drawdown = (equity_df['total_value'] - running_max) / running_max * 100
        max_drawdown = float(drawdown.min())

        # 最大回撤起止日期与持续期
        max_dd_end_idx = drawdown.idxmin()
        max_dd_end_str = max_dd_end_idx.strftime("%Y-%m-%d") if max_dd_end_idx is not None else ""
        # 回撤起点：从最大回撤终点往前找，最近的历史高点
        dd_series = drawdown.loc[:max_dd_end_idx]
        peak_idx = dd_series[dd_series >= 0].index
        max_dd_start_idx = peak_idx[-1] if len(peak_idx) > 0 else equity_df.index[0]
        max_dd_start_str = max_dd_start_idx.strftime("%Y-%m-%d")
        max_drawdown_duration = (max_dd_end_idx - max_dd_start_idx).days if max_dd_end_idx is not None else 0

        # 回撤恢复期：从回撤终点往后找到下一次创历史新高
        post_dd = equity_df.loc[max_dd_end_idx:]
        recovery_mask = post_dd['total_value'] >= running_max.loc[max_dd_end_idx]
        if recovery_mask.any():
            recovery_idx = post_dd[recovery_mask].index[0]
            max_drawdown_recovery = (recovery_idx - max_dd_end_idx).days
        else:
            max_drawdown_recovery = -1  # 未恢复

        # 日收益率
        daily_returns = equity_df['total_value'].pct_change().dropna()

        # 波动率（年化）
        volatility = float(daily_returns.std() * np.sqrt(252) * 100) if len(daily_returns) > 1 else 0
        # 下行波动率
        negative_returns = daily_returns[daily_returns < 0]
        downside_volatility = float(negative_returns.std() * np.sqrt(252) * 100) if len(negative_returns) > 1 else 0

        # 夏普比率
        sharpe_ratio = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
        # Sortino 比率
        sortino_ratio = float(daily_returns.mean() / negative_returns.std() * np.sqrt(252)) if len(negative_returns) > 1 and negative_returns.std() > 0 else 0
        # Calmar 比率
        calmar_ratio = float(annualized_return / abs(max_drawdown)) if max_drawdown != 0 else 0

        # VaR(95%) 与 CVaR(95%)
        var_95 = float(np.percentile(daily_returns, 5) * 100) if len(daily_returns) > 0 else 0
        cvar_95 = float(daily_returns[daily_returns <= np.percentile(daily_returns, 5)].mean() * 100) if len(daily_returns) > 0 else 0

        # ===== 交易统计 =====
        sell_trades = [t for t in self.trades if t.direction == 'sell']
        total_trades = len(sell_trades)
        win_trades = self.win_count
        lose_trades = self.lose_count
        win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0

        avg_trade_pnl = self.total_pnl / total_trades if total_trades > 0 else 0
        avg_win_pnl = self.total_win_pnl / win_trades if win_trades > 0 else 0
        avg_lose_pnl = self.total_lose_pnl / lose_trades if lose_trades > 0 else 0

        # 单笔最大盈亏
        sell_pnls = [t.pnl for t in sell_trades]
        max_win_pnl = max(sell_pnls) if sell_pnls else 0
        max_lose_pnl = min(sell_pnls) if sell_pnls else 0

        profit_factor = abs(self.total_win_pnl / self.total_lose_pnl) if self.total_lose_pnl != 0 else float('inf')

        # 连胜/连亏
        max_consec_wins, max_consec_losses = 0, 0
        cur_wins, cur_losses = 0, 0
        for t in sell_trades:
            if t.pnl > 0:
                cur_wins += 1
                cur_losses = 0
                max_consec_wins = max(max_consec_wins, cur_wins)
            elif t.pnl < 0:
                cur_losses += 1
                cur_wins = 0
                max_consec_losses = max(max_consec_losses, cur_losses)
            else:
                cur_wins, cur_losses = 0, 0

        # 持仓天数统计
        holding_days_list = [t.holding_days for t in sell_trades if t.holding_days > 0]
        avg_holding_days = float(np.mean(holding_days_list)) if holding_days_list else 0
        max_holding_days = max(holding_days_list) if holding_days_list else 0
        min_holding_days = min(holding_days_list) if holding_days_list else 0

        # ===== 基准对比 =====
        baseline_return = 0.0
        alpha = beta = information_ratio = tracking_error = 0.0
        upside_capture = downside_capture = 0.0

        if baseline_df is not None and not baseline_df.empty and len(baseline_df) >= 2:
            baseline_df = baseline_df.copy()
            baseline_df['date'] = pd.to_datetime(baseline_df['date'])
            baseline_df = baseline_df.set_index('date').sort_index()
            # 对齐到权益曲线日期
            aligned = equity_df[['total_value']].join(baseline_df[['close']], how='inner')
            if len(aligned) >= 2:
                baseline_first = aligned['close'].iloc[0]
                baseline_last = aligned['close'].iloc[-1]
                baseline_return = (baseline_last - baseline_first) / baseline_first * 100

                strat_ret = aligned['total_value'].pct_change().dropna()
                bench_ret = aligned['close'].pct_change().dropna()
                common = pd.concat([strat_ret, bench_ret], axis=1, keys=['strat', 'bench']).dropna()

                if len(common) > 1:
                    # Beta、Alpha（年化）
                    cov_matrix = np.cov(common['strat'], common['bench'])
                    var_bench = cov_matrix[1, 1]
                    beta = float(cov_matrix[0, 1] / var_bench) if var_bench != 0 else 0
                    alpha = float((common['strat'].mean() - beta * common['bench'].mean()) * 252 * 100)

                    # 跟踪误差与信息比率
                    active_ret = common['strat'] - common['bench']
                    tracking_error = float(active_ret.std() * np.sqrt(252) * 100)
                    information_ratio = float(active_ret.mean() / active_ret.std() * np.sqrt(252)) if active_ret.std() > 0 else 0

                    # 上下行捕获率
                    up_days = common[common['bench'] > 0]
                    down_days = common[common['bench'] < 0]
                    upside_capture = float(up_days['strat'].mean() / up_days['bench'].mean() * 100) if len(up_days) > 0 and up_days['bench'].mean() != 0 else 0
                    downside_capture = float(down_days['strat'].mean() / down_days['bench'].mean() * 100) if len(down_days) > 0 and down_days['bench'].mean() != 0 else 0

        excess_return = total_return - baseline_return

        # ===== 日度统计 =====
        daily_stats = equity_df.copy()
        daily_stats['daily_return'] = daily_stats['total_value'].pct_change() * 100
        daily_stats['drawdown'] = drawdown
        daily_stats['drawdown_duration'] = (drawdown < 0).astype(int).groupby((drawdown >= 0).cumsum()).cumsum()

        signal_df = pd.DataFrame(self.daily_signals)
        if not signal_df.empty:
            signal_df['date'] = pd.to_datetime(signal_df['date'])
            signal_df = signal_df.set_index('date')
            daily_stats = daily_stats.join(signal_df)

        # ===== 持仓统计 =====
        max_open_positions = int(equity_df['positions'].max())
        avg_open_positions = float(equity_df['positions'].mean())
        total_buys = len([t for t in self.trades if t.direction == 'buy'])
        total_sells = len([t for t in self.trades if t.direction == 'sell'])
        avg_position_value = float(equity_df['position_value'].mean())
        capital_utilization = float(avg_position_value / self.initial_capital * 100)

        position_stats = {
            'max_open_positions': max_open_positions,
            'avg_open_positions': avg_open_positions,
            'total_buys': total_buys,
            'total_sells': total_sells,
            'capital_utilization': capital_utilization,
        }

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=float(equity_df['total_value'].iloc[-1]),
            # 收益
            total_return=round(total_return, 2),
            annualized_return=round(annualized_return, 2),
            baseline_return=round(baseline_return, 2),
            excess_return=round(excess_return, 2),
            # 风险
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_start=max_dd_start_str,
            max_drawdown_end=max_dd_end_str,
            max_drawdown_duration=max_drawdown_duration,
            max_drawdown_recovery=max_drawdown_recovery,
            volatility=round(volatility, 2),
            downside_volatility=round(downside_volatility, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            sortino_ratio=round(sortino_ratio, 2),
            calmar_ratio=round(calmar_ratio, 2),
            var_95=round(var_95, 2),
            cvar_95=round(cvar_95, 2),
            # 交易
            total_trades=total_trades,
            win_trades=win_trades,
            lose_trades=lose_trades,
            win_rate=round(win_rate, 2),
            avg_trade_pnl=round(avg_trade_pnl, 2),
            avg_win_pnl=round(avg_win_pnl, 2),
            avg_lose_pnl=round(avg_lose_pnl, 2),
            max_win_pnl=round(max_win_pnl, 2),
            max_lose_pnl=round(max_lose_pnl, 2),
            profit_factor=round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            avg_holding_days=round(avg_holding_days, 1),
            max_holding_days=max_holding_days,
            min_holding_days=min_holding_days,
            # 基准
            alpha=round(alpha, 2),
            beta=round(beta, 2),
            information_ratio=round(information_ratio, 2),
            tracking_error=round(tracking_error, 2),
            upside_capture=round(upside_capture, 2),
            downside_capture=round(downside_capture, 2),
            # 持仓
            max_open_positions=max_open_positions,
            avg_open_positions=round(avg_open_positions, 2),
            capital_utilization=round(capital_utilization, 2),
            # 数据
            equity_curve=equity_df,
            trades=self.trades,
            daily_stats=daily_stats,
            position_stats=position_stats,
        )

    def save_result(self, result: BacktestResult, filename: str = None):
        """保存回测结果（权益曲线/交易明细/日度统计/完整摘要）"""
        if filename is None:
            filename = f"backtest_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

        # 权益曲线（含回撤）
        equity_out = result.equity_curve.copy()
        if 'drawdown' not in equity_out.columns and 'total_value' in equity_out.columns:
            running_max = equity_out['total_value'].cummax()
            equity_out['drawdown'] = (equity_out['total_value'] - running_max) / running_max * 100
        equity_out.to_csv(BACKTEST_DIR / f"{filename}_equity.csv", encoding='utf-8-sig')

        # 交易明细
        if result.trades:
            trades_df = pd.DataFrame([{
                '日期': t.date,
                '方向': t.direction,
                '代码': t.etf_code,
                '名称': t.etf_name,
                '价格': t.price,
                '股数': t.shares,
                '金额': round(t.amount, 2),
                '原因': t.reason,
                '盈亏': round(t.pnl, 2),
                '信号评分': t.signal_score,
                '净流入': t.net_flow,
                '持仓天数': t.holding_days,
            } for t in result.trades])
            trades_df.to_csv(BACKTEST_DIR / f"{filename}_trades.csv", index=False, encoding='utf-8-sig')

        # 日度统计
        if not result.daily_stats.empty:
            result.daily_stats.to_csv(BACKTEST_DIR / f"{filename}_daily.csv", encoding='utf-8-sig')

        # 完整摘要（一维键值表，便于查看）
        recovery_str = f"{result.max_drawdown_recovery}天" if result.max_drawdown_recovery >= 0 else "未恢复"
        summary_rows = [
            ('起始日期', result.start_date),
            ('结束日期', result.end_date),
            ('初始资金', f"{result.initial_capital:,.2f}"),
            ('最终资金', f"{result.final_capital:,.2f}"),
            ('—— 收益指标 ——', ''),
            ('总收益率(%)', result.total_return),
            ('年化收益率(%)', result.annualized_return),
            ('沪深300收益率(%)', result.baseline_return),
            ('超额收益(%)', result.excess_return),
            ('—— 风险指标 ——', ''),
            ('最大回撤(%)', result.max_drawdown),
            ('最大回撤起始', result.max_drawdown_start),
            ('最大回撤谷底', result.max_drawdown_end),
            ('回撤持续天数', result.max_drawdown_duration),
            ('回撤恢复天数', recovery_str),
            ('年化波动率(%)', result.volatility),
            ('下行波动率(%)', result.downside_volatility),
            ('夏普比率', result.sharpe_ratio),
            ('Sortino比率', result.sortino_ratio),
            ('Calmar比率', result.calmar_ratio),
            ('VaR(95%)(%)', result.var_95),
            ('CVaR(95%)(%)', result.cvar_95),
            ('—— 交易统计 ——', ''),
            ('总交易次数', result.total_trades),
            ('盈利次数', result.win_trades),
            ('亏损次数', result.lose_trades),
            ('胜率(%)', result.win_rate),
            ('平均盈亏', result.avg_trade_pnl),
            ('平均盈利', result.avg_win_pnl),
            ('平均亏损', result.avg_lose_pnl),
            ('最大单笔盈利', result.max_win_pnl),
            ('最大单笔亏损', result.max_lose_pnl),
            ('盈亏比', result.profit_factor),
            ('最大连胜次数', result.max_consecutive_wins),
            ('最大连亏次数', result.max_consecutive_losses),
            ('平均持仓天数', result.avg_holding_days),
            ('最长持仓天数', result.max_holding_days),
            ('最短持仓天数', result.min_holding_days),
            ('—— 基准对比 ——', ''),
            ('Alpha(年化%)', result.alpha),
            ('Beta', result.beta),
            ('信息比率', result.information_ratio),
            ('跟踪误差(%)', result.tracking_error),
            ('上行捕获率(%)', result.upside_capture),
            ('下行捕获率(%)', result.downside_capture),
            ('—— 持仓统计 ——', ''),
            ('最大持仓数', result.max_open_positions),
            ('平均持仓数', result.avg_open_positions),
            ('资金利用率(%)', result.capital_utilization),
        ]
        summary_df = pd.DataFrame(summary_rows, columns=['指标', '值'])
        summary_df.to_csv(BACKTEST_DIR / f"{filename}_summary.csv", index=False, encoding='utf-8-sig')

        # JSON 摘要（便于程序读取）
        try:
            import json
            json_path = BACKTEST_DIR / f"{filename}_summary.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({k: (str(v) if isinstance(v, (pd.Timestamp,)) else v)
                           for k, v in zip(summary_df['指标'], summary_df['值'])},
                          f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"保存JSON摘要失败: {e}")

        return BACKTEST_DIR / f"{filename}_summary.csv"


if __name__ == "__main__":
    backtester = ETFBacktester()
    result = backtester.run("2025-01-01", "2026-07-31")

    print(f"回测结果:")
    print(f"总收益率: {result.total_return:.2f}%")
    print(f"年化收益率: {result.annualized_return:.2f}%")
    print(f"最大回撤: {result.max_drawdown:.2f}%")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"胜率: {result.win_rate:.2f}%")
    print(f"交易次数: {result.total_trades}")
    print(f"平均盈亏: {result.avg_trade_pnl:.2f}")
    print(f"盈亏比: {result.profit_factor:.2f}")

    backtester.save_result(result)