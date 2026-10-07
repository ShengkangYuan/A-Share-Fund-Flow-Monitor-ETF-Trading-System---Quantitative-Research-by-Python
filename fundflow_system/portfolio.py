"""
投资组合管理模块 - 仓位管理、交易记录、风险评估
"""

import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from config import TRADING_CFG, REPORTS_DIR


@dataclass
class Position:
    """持仓记录"""
    etf_code: str
    etf_name: str
    entry_price: float
    current_price: float
    shares: int
    entry_date: str
    entry_reason: str
    stop_loss: float = 0.0
    take_profit: float = 0.0

    @property
    def pnl_pct(self) -> float:
        """盈亏百分比"""
        return (self.current_price - self.entry_price) / self.entry_price * 100

    @property
    def pnl_amount(self) -> float:
        """盈亏金额"""
        return (self.current_price - self.entry_price) * self.shares

    @property
    def should_stop_loss(self) -> bool:
        """是否触发止损"""
        return self.pnl_pct <= self.stop_loss * 100

    @property
    def should_take_profit(self) -> bool:
        """是否触发止盈"""
        return self.pnl_pct >= self.take_profit * 100


@dataclass
class TradeRecord:
    """交易记录"""
    etf_code: str
    etf_name: str
    direction: str          # buy / sell
    price: float
    shares: int
    amount: float
    date: str
    reason: str
    pnl: float = 0.0        # 该笔盈亏


class Portfolio:
    """投资组合管理"""

    def __init__(self, initial_capital: float = 0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, Position] = {}       # code -> Position
        self.trades: List[TradeRecord] = []
        self.cash = initial_capital

    @property
    def total_value(self) -> float:
        """总资产"""
        position_value = sum(
            p.current_price * p.shares for p in self.positions.values()
        )
        return self.cash + position_value

    @property
    def position_pnl(self) -> float:
        """持仓盈亏"""
        return sum(p.pnl_amount for p in self.positions.values())

    @property
    def position_pnl_pct(self) -> float:
        """持仓盈亏百分比"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.total_value - self.initial_capital) / self.initial_capital * 100

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def used_capital_ratio(self) -> float:
        """仓位使用率"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.initial_capital - self.cash) / self.initial_capital * 100

    def can_open_position(self) -> bool:
        """是否可以开新仓"""
        return self.position_count < TRADING_CFG.max_positions

    def calculate_buy_shares(self, price: float) -> int:
        """计算可买入股数（按单只ETF仓位比例）"""
        max_amount = self.initial_capital * TRADING_CFG.position_size
        # 取整到100股
        shares = int(max_amount / price / 100) * 100
        actual_cost = shares * price
        if actual_cost > self.cash:
            shares = int(self.cash / price / 100) * 100
        return max(shares, 0)

    def open_position(self, code: str, name: str, price: float,
                       date: str, reason: str) -> Optional[Position]:
        """开仓"""
        if not self.can_open_position():
            return None

        shares = self.calculate_buy_shares(price)
        if shares <= 0:
            return None

        cost = shares * price
        if cost > self.cash:
            return None

        position = Position(
            etf_code=code,
            etf_name=name,
            entry_price=price,
            current_price=price,
            shares=shares,
            entry_date=date,
            entry_reason=reason,
            stop_loss=TRADING_CFG.stop_loss,
            take_profit=TRADING_CFG.take_profit,
        )

        self.positions[code] = position
        self.cash -= cost

        trade = TradeRecord(
            etf_code=code, etf_name=name,
            direction="buy", price=price,
            shares=shares, amount=cost,
            date=date, reason=reason,
        )
        self.trades.append(trade)

        return position

    def close_position(self, code: str, price: float,
                        date: str, reason: str) -> Optional[Position]:
        """平仓"""
        position = self.positions.pop(code, None)
        if position is None:
            return None

        amount = price * position.shares
        pnl = amount - (position.entry_price * position.shares)

        self.cash += amount
        trade = TradeRecord(
            etf_code=code, etf_name=position.etf_name,
            direction="sell", price=price,
            shares=position.shares, amount=amount,
            date=date, reason=reason, pnl=pnl,
        )
        self.trades.append(trade)

        position.current_price = price
        return position

    def update_prices(self, prices: Dict[str, float]):
        """更新持仓市价"""
        for code, price in prices.items():
            if code in self.positions:
                self.positions[code].current_price = price

    def check_stop_loss_take_profit(self, date: str) -> List[TradeRecord]:
        """检查止损止盈"""
        closed = []
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            if pos.should_stop_loss:
                result = self.close_position(code, pos.current_price, date,
                                              f"止损触发 ({pos.pnl_pct:.1f}%)")
                if result:
                    closed.append(self.trades[-1])
            elif pos.should_take_profit:
                result = self.close_position(code, pos.current_price, date,
                                              f"止盈触发 ({pos.pnl_pct:.1f}%)")
                if result:
                    closed.append(self.trades[-1])
        return closed

    def get_positions_df(self) -> pd.DataFrame:
        """持仓列表转DataFrame"""
        if not self.positions:
            return pd.DataFrame()
        records = []
        for p in self.positions.values():
            records.append({
                '代码': p.etf_code,
                '名称': p.etf_name,
                '买入价': p.entry_price,
                '现价': p.current_price,
                '持股': p.shares,
                '盈亏%': round(p.pnl_pct, 2),
                '盈亏额': round(p.pnl_amount, 2),
                '买入日': p.entry_date,
                '止损价': round(p.entry_price * (1 + p.stop_loss), 3) if p.stop_loss else 0,
                '止盈价': round(p.entry_price * (1 + p.take_profit), 3) if p.take_profit else 0,
            })
        return pd.DataFrame(records)

    def get_trades_df(self) -> pd.DataFrame:
        """交易记录转DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        records = []
        for t in self.trades:
            records.append({
                '方向': '买入' if t.direction == 'buy' else '卖出',
                '代码': t.etf_code,
                '名称': t.etf_name,
                '价格': t.price,
                '股数': t.shares,
                '金额': round(t.amount, 2),
                '日期': t.date,
                '原因': t.reason,
                '盈亏': round(t.pnl, 2),
            })
        return pd.DataFrame(records)

    def save_report(self):
        """保存持仓报告"""
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        pos_df = self.get_positions_df()
        trades_df = self.get_trades_df()

        if not pos_df.empty:
            pos_df.to_csv(REPORTS_DIR / f"positions_{date_str}.csv",
                         index=False, encoding='utf-8-sig')
        if not trades_df.empty:
            trades_df.to_csv(REPORTS_DIR / f"trades_{date_str}.csv",
                           index=False, encoding='utf-8-sig')

        # 汇总报告
        summary = {
            '日期': date_str,
            '初始资金': self.initial_capital,
            '总资产': round(self.total_value, 2),
            '现金': round(self.cash, 2),
            '持仓市值': round(self.total_value - self.cash, 2),
            '总盈亏': round(self.total_value - self.initial_capital, 2),
            '总盈亏%': round(self.position_pnl_pct, 2),
            '持仓数': self.position_count,
            '仓位使用率%': round(self.used_capital_ratio, 1),
        }
        pd.DataFrame([summary]).to_csv(
            REPORTS_DIR / f"summary_{date_str}.csv",
            index=False, encoding='utf-8-sig'
        )
        return summary


if __name__ == "__main__":
    # 测试
    pf = Portfolio(initial_capital=100000)
    pf.open_position("512480", "半导体ETF", 1.5, "2026-07-16", "测试开仓")
    print(f"总资产: {pf.total_value:.2f}, 现金: {pf.cash:.2f}")
    print(pf.get_positions_df())
