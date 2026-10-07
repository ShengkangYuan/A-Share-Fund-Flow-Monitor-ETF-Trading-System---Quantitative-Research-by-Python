"""
全局数据格式化工具
- 金额统一保留2位小数带单位（亿）
- 涨跌幅保留2位小数
- 评分保留1-2位
- 日期统一 YYYY-MM-DD
"""

from datetime import datetime
from typing import Union, Optional
import pandas as pd
import numpy as np


def fmt_money(v: Union[float, int, None], unit: str = "亿", suffix: str = "") -> str:
    """金额格式化：保留2位小数 + 跟随界面语言（中文：亿 / 英文：B、M）"""
    if v is None or pd.isna(v):
        return "—"
    try:
        from i18n import fmt_flow_money, is_zh
        if is_zh():
            return f"{float(v):.2f}{unit}{suffix}"
        return fmt_flow_money(float(v), signed=False)
    except (TypeError, ValueError):
        return "—"


def fmt_signed_money(v: Union[float, int, None], unit: str = "亿") -> str:
    """带符号金额：+12.34亿 / +1.23B"""
    if v is None or pd.isna(v):
        return "—"
    try:
        from i18n import fmt_flow_money
        return fmt_flow_money(float(v), signed=True)
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v: Union[float, int, None], decimals: int = 2) -> str:
    """百分比格式化：保留2位小数"""
    if v is None or pd.isna(v):
        return "—"
    try:
        return f"{float(v):.{decimals}f}%"
    except (TypeError, ValueError):
        return "—"


def fmt_signed_pct(v: Union[float, int, None], decimals: int = 2) -> str:
    """带符号百分比"""
    if v is None or pd.isna(v):
        return "—"
    try:
        f = float(v)
        sign = "+" if f >= 0 else ""
        return f"{sign}{f:.{decimals}f}%"
    except (TypeError, ValueError):
        return "—"


def fmt_score(v: Union[float, int, None], decimals: int = 1) -> str:
    """评分格式化：保留1位小数"""
    if v is None or pd.isna(v):
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_date(d: Union[str, datetime, None], input_format: Optional[str] = None) -> str:
    """
    统一日期格式 YYYY-MM-DD
    支持：datetime对象、'YYYYMMDD'、'YYYY/MM/DD'、'YYYY-MM-DD'、ISO字符串
    """
    if d is None or (isinstance(d, str) and not d.strip()):
        return "—"

    # datetime 对象
    if isinstance(d, (datetime, pd.Timestamp)):
        return d.strftime("%Y-%m-%d")

    s = str(d).strip()

    # 已经是 YYYY-MM-DD
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return s

    # YYYYMMDD
    if len(s) == 8 and s.isdigit():
        try:
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        except Exception:
            pass

    # YYYY/MM/DD
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3:
            y, m, d_ = parts
            return f"{y.zfill(4)}-{m.zfill(2)}-{d_.zfill(2)}"

    # ISO datetime (e.g. 2026-08-23T15:30:00)
    if 'T' in s:
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m-%d")
        except Exception:
            return s[:10] if len(s) >= 10 else s

    # 尝试解析
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%Y%m%d"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue

    return s


def fmt_datetime(dt: Union[str, datetime, None]) -> str:
    """统一日期时间格式 YYYY-MM-DD HH:MM:SS"""
    if dt is None or (isinstance(dt, str) and not dt.strip()):
        return "—"
    if isinstance(dt, (datetime, pd.Timestamp)):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    s = str(dt).strip()
    # ISO 格式
    if 'T' in s:
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s[:19]

    # YYYYMMDD_HHMMSS
    if len(s) == 15 and s[8] == '_':
        try:
            return datetime.strptime(s, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    return s


def fmt_seconds_ago(seconds: Union[float, int, None]) -> str:
    """将秒数转为人类可读的相对时间（跟随界面语言）"""
    from i18n import fmt_lang_seconds_ago
    return fmt_lang_seconds_ago(seconds)


def fmt_time_ago(timestamp: Union[str, datetime, None]) -> str:
    """从时间戳计算'X秒前'"""
    if timestamp is None:
        return "—"
    try:
        if isinstance(timestamp, str):
            ts = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, (datetime, pd.Timestamp)):
            ts = timestamp
        else:
            return "—"
        delta = (datetime.now() - ts).total_seconds()
        return fmt_seconds_ago(delta)
    except Exception:
        return "—"


# ===== Pandas DataFrame 格式化辅助 =====
def format_flow_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """格式化资金流 DataFrame 用于展示"""
    if df is None or df.empty:
        return df
    out = df.copy()
    col_map = {
        '净额': '净流入',
        '流入资金': '流入',
        '流出资金': '流出',
        '行业-涨跌幅': '涨跌幅',
    }
    out = out.rename(columns={k: v for k, v in col_map.items() if k in out.columns})

    # 数值格式化（用于显示，保留原数据类型用于计算）
    for col in ['净流入', '流入', '流出']:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) else "—")
    if '涨跌幅' in out.columns:
        out['涨跌幅'] = out['涨跌幅'].apply(lambda x: f"{float(x):+.2f}%" if pd.notna(x) else "—")
    if '流入比' in out.columns:
        out['流入比'] = out['流入比'].apply(lambda x: f"{float(x)*100:.2f}%" if pd.notna(x) else "—")
    if 'score' in out.columns:
        out['score'] = out['score'].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    return out


def get_market_status_badge() -> str:
    """获取当前市场状态徽章 HTML（跟随界面语言）"""
    import i18n
    now = datetime.now()
    wd = now.weekday()
    t = now.time()
    from datetime import datetime as _dt
    if wd >= 5:
        return f'<span class="status-pill offline">⚫ {i18n.t("status_weekend")}</span>'
    if _dt.strptime("09:30", "%H:%M").time() <= t <= _dt.strptime("11:30", "%H:%M").time():
        return f'<span class="status-pill online">🟢 {i18n.t("status_trading")}</span>'
    if _dt.strptime("13:00", "%H:%M").time() <= t <= _dt.strptime("15:00", "%H:%M").time():
        return f'<span class="status-pill online">🟢 {i18n.t("status_trading")}</span>'
    if t < _dt.strptime("09:30", "%H:%M").time():
        return f'<span class="status-pill pending">⏳ {i18n.t("status_premarket")}</span>'
    return f'<span class="status-pill offline">⚫ {i18n.t("status_closed")}</span>'


if __name__ == "__main__":
    # 自测
    print(fmt_money(123.456789))  # 123.46亿
    print(fmt_signed_money(-12.345))  # -12.35亿
    print(fmt_pct(5.6789))  # 5.68%
    print(fmt_signed_pct(-2.345))  # -2.35%
    print(fmt_score(85.4567))  # 85.5
    print(fmt_date("20260823"))  # 2026-08-23
    print(fmt_date("2026/08/23"))  # 2026-08-23
    print(fmt_date("2026-08-23T15:30:00"))  # 2026-08-23
    print(fmt_datetime("2026-08-23T15:30:00"))  # 2026-08-23 15:30:00
    print(fmt_time_ago(datetime.now().isoformat()))  # 0秒前
    print(fmt_seconds_ago(125))  # 2分钟前
