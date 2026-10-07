"""
资金流动态检测与ETF交易系统 - 配置文件
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List
import os
import time
import logging

_logger = logging.getLogger(__name__)


# ============================================================
# 东方财富域名绕过系统代理
# 用户机器上的 Clash/v2ray 等系统代理会拦截 push2*.eastmoney.com，
# 导致 akshare 全部接口 ProxyError。东财是国内站点，直连最稳。
# 通过 NO_PROXY 让 requests/urllib 对这些域名直连。
# ============================================================
def _bypass_proxy_for_eastmoney():
    hosts = [
        "eastmoney.com", ".eastmoney.com",
        "push2.eastmoney.com", "push2his.eastmoney.com",
        "data.eastmoney.com", "quote.eastmoney.com",
        "fund.eastmoney.com", "82.push2.eastmoney.com",
        "48.push2.eastmoney.com", "17.push2.eastmoney.com",
    ]
    existing = os.environ.get("NO_PROXY", "") or os.environ.get("no_proxy", "")
    items = {x.strip() for x in existing.replace(";", ",").split(",") if x.strip()}
    changed = False
    for h in hosts:
        if h not in items:
            items.add(h)
            changed = True
    if changed:
        val = ",".join(sorted(items))
        os.environ["NO_PROXY"] = val
        os.environ["no_proxy"] = val

_bypass_proxy_for_eastmoney()


# ============================================================
# curl_cffi 浏览器指纹补丁
# 部分网络环境（Clash TUN / 安全网关）会按 TLS 指纹重置 Python
# urllib3 到东方财富的连接（curl 正常）。curl_cffi 模拟 Chrome 的
# TLS 指纹可稳定绕过。若环境未安装 curl_cffi 则静默跳过。
# ============================================================
def _patch_eastmoney_transport():
    try:
        from curl_cffi import requests as cffi_requests
    except Exception:
        return
    import requests

    _orig_session_request = requests.sessions.Session.request

    # 仅透传两边 API 都支持的参数
    _PASS_KEYS = {
        "params", "data", "json", "headers", "cookies", "files",
        "auth", "timeout", "allow_redirects", "proxies", "verify",
        "impersonate", "default_headers",
    }

    def _patched_request(self, method, url, **kwargs):
        if "eastmoney.com" in str(url):
            fwd = {k: v for k, v in kwargs.items() if k in _PASS_KEYS}
            fwd.setdefault("impersonate", "chrome")
            fwd.setdefault("timeout", 15)
            # 东财链路偶发连接重置，内部再试 1 次
            for attempt in range(2):
                try:
                    return cffi_requests.request(method, url, **fwd)
                except Exception:
                    if attempt == 0:
                        time.sleep(0.6)
            _logger.debug("curl_cffi 东财请求失败，回退标准 requests: %s", url)
        return _orig_session_request(self, method, url, **kwargs)

    requests.sessions.Session.request = _patched_request

_patch_eastmoney_transport()


def get_data_dir(name: str) -> Path:
    """获取数据目录，处理权限问题。云端/Docker 环境优先使用 /app/data"""
    import tempfile
    root_dir = Path(__file__).parent

    # 环境变量优先（云服务器可指定挂载卷路径）
    env_data_dir = os.environ.get("FUNDFLOW_DATA_DIR")
    if env_data_dir:
        p = Path(env_data_dir) / name if name else Path(env_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    candidates = [
        root_dir / "data" / name,
        Path(os.path.expanduser("~")) / "fundflow_data" / name,
        Path(os.path.expanduser("~")) / "fundflow" / name,
        Path(tempfile.gettempdir()) / "fundflow" / name,
        Path(os.getcwd()) / "data" / name,
    ]

    for path in candidates:
        try:
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)

            test_file = path / ".test_write"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return path
        except (PermissionError, OSError):
            continue

    return Path(tempfile.gettempdir()) / "fundflow" / name


ROOT_DIR = Path(__file__).parent
DATA_DIR = get_data_dir("")
DAILY_DIR = get_data_dir("daily")
SIGNALS_DIR = get_data_dir("signals")
REPORTS_DIR = get_data_dir("reports")
BACKTEST_DIR = get_data_dir("backtest")
VIDEOS_DIR = get_data_dir("videos")


@dataclass
class FlowAnalysisConfig:
    top_n_strong: int = 10
    top_n_weak: int = 10
    inflow_threshold: float = 5.0
    outflow_threshold: float = 3.0
    trend_days: int = 5
    min_change_for_long: float = 0.5
    max_change_for_short: float = -0.5


@dataclass
class TradingConfig:
    max_positions: int = 5
    position_size: float = 0.2
    stop_loss: float = -0.05
    take_profit: float = 0.15
    weight_net_flow: float = 0.4
    weight_change: float = 0.3
    weight_inflow_ratio: float = 0.3
    buy_threshold: float = 70.0
    sell_threshold: float = 30.0


@dataclass
class BacktestConfig:
    initial_capital: float = 100000
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0005
    start_date: str = "2024-01-01"
    end_date: str = "2026-07-31"
    rebalance_time: str = "14:30"
    max_positions: int = 5
    position_size: float = 0.2
    stop_loss: float = -0.05
    take_profit: float = 0.15
    # 策略模式: "next_day_rotation" 次日14:30强制换仓 / "continuous" 持续持仓至不再符合条件
    strategy_mode: str = "next_day_rotation"
    # 执行价位: "close" 用14:30近似收盘价 / "open" 次日开盘价
    execution_price: str = "close"


INDUSTRY_ETF_MAPPING: Dict[str, tuple] = {
    "半导体":      ("512480", "半导体ETF"),
    "消费电子":    ("159732", "消费电子ETF"),
    "软件":        ("159852", "软件ETF"),
    "计算机设备":  ("159998", "计算机ETF"),
    "通信设备":    ("515880", "通信ETF"),
    "元件":        ("159997", "电子ETF"),
    "光学光电子":  ("159997", "电子ETF"),
    "证券":        ("512880", "证券ETF"),
    "银行":        ("512800", "银行ETF"),
    "保险":        ("516730", "保险证券ETF"),
    "白酒":        ("512690", "酒ETF"),
    "食品加工":    ("515710", "食品ETF"),
    "养殖业":      ("159865", "养殖ETF"),
    "农产品加工":  ("159825", "农业ETF"),
    "饮料制造":    ("159736", "饮食ETF"),
    "小家电":      ("159996", "家电ETF"),
    "白色家电":    ("159996", "家电ETF"),
    "服装家纺":    ("159987", "纺织服装ETF"),
    "医疗器械":    ("512010", "医药ETF"),
    "医疗服务":    ("512010", "医药ETF"),
    "中药":        ("159647", "中药ETF"),
    "生物制品":    ("512010", "医药ETF"),
    "医药商业":    ("512010", "医药ETF"),
    "化学制药":    ("512010", "医药ETF"),
    "工业金属":    ("512400", "有色金属ETF"),
    "小金属":      ("512400", "有色金属ETF"),
    "贵金属":      ("518880", "黄金ETF"),
    "煤炭开采":    ("515220", "煤炭ETF"),
    "钢铁":        ("515210", "钢铁ETF"),
    "建筑材料":    ("516970", "基建ETF"),
    "化学制品":    ("516020", "化工ETF"),
    "化学原料":    ("516020", "化工ETF"),
    "农化制品":    ("516020", "化工ETF"),
    "石油加工":    ("159930", "石化ETF"),
    "汽车零部件":  ("516110", "汽车ETF"),
    "汽车整车":    ("516110", "汽车ETF"),
    "电力":        ("159611", "电力ETF"),
    "光伏设备":    ("515790", "光伏ETF"),
    "风电设备":    ("516160", "新能源ETF"),
    "电池":        ("561910", "电池ETF"),
    "环境治理":    ("159859", "环保ETF"),
    "军工电子":    ("512660", "军工ETF"),
    "军工装备":    ("512660", "军工ETF"),
    "房地产":      ("512200", "房地产ETF"),
    "建筑装饰":    ("516970", "基建ETF"),
    "铁路公路":    ("159965", "交通运输ETF"),
    "港口航运":    ("159965", "交通运输ETF"),
    "物流":        ("159965", "交通运输ETF"),
    "文化传媒":    ("159805", "传媒ETF"),
    "游戏":        ("159869", "游戏ETF"),
    "影视院线":    ("159805", "传媒ETF"),
    "旅游及酒店":  ("159766", "旅游ETF"),
    "造纸":        ("159987", "纺织服装ETF"),
    "零售":        ("159993", "零售消费ETF"),
    "综合":        ("159959", "央企ETF"),
}


@dataclass
class SystemConfig:
    max_retries: int = 3
    request_timeout: int = 30
    report_lang: str = "zh"
    send_report: bool = False
    auto_refresh_interval: int = 300
    frame_cache_days: int = 7
    video_auto_generate_time: str = "15:10"
    min_etf_scale: float = 5000
    max_retries_delay: int = 3


@dataclass
class TradingCostConfig:
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0005
    stamp_tax_rate: float = 0.001


FLOW_CFG = FlowAnalysisConfig()
TRADING_CFG = TradingConfig()
BACKTEST_CFG = BacktestConfig()
SYS_CFG = SystemConfig()
COST_CFG = TradingCostConfig()