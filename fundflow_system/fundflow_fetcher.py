"""
数据层 - 资金流数据获取模块
功能：行业资金流采集、缓存管理、交易时段过滤、接口容错机制
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
import json
import time
import random
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fundflow.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== 全局反爬请求头注入（给 AKShare 底层 requests 使用）=====
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Referer": "https://data.eastmoney.com/",
}

def _inject_requests_headers():
    """给 AKShare 依赖的 requests 注入默认请求头，避免 403/空返回"""
    try:
        import requests
        from requests import utils as requests_utils
        # 方式一：修改 default_headers（最通用）
        sess_attr = requests.Session()
        for k, v in DEFAULT_HEADERS.items():
            sess_attr.headers[k] = v
        # 方式二：修改 requests 的默认头部
        try:
            requests.utils.default_headers = lambda: requests.structures.CaseInsensitiveDict(DEFAULT_HEADERS)
        except Exception:
            pass
        # 方式三：设置环境变量（部分 akshare 版本会读取）
        os.environ.setdefault("AKSHARE_USER_AGENT", DEFAULT_HEADERS["User-Agent"])
        logger.debug("已注入 requests 反爬请求头")
        return True
    except Exception as e:
        logger.warning(f"注入请求头失败（非致命）: {e}")
        return False

_inject_requests_headers()

from config import DATA_DIR, SYS_CFG

# ============================================================
# 我们使用的行业名（偏申万命名）→ 东方财富行业板块名 别名表
# 仅收录确认不一致的名称；一致的名称直接精确匹配。
# 未命中别名的会再走 difflib 模糊匹配兜底。
# ============================================================
_EM_INDUSTRY_ALIASES = {
    "软件": "软件开发",
    "白酒": "酿酒行业",
    "饮料制造": "酿酒行业",
    "食品加工": "食品饮料",
    "养殖业": "农牧饲渔",
    "农产品加工": "农牧饲渔",
    "小家电": "家电行业",
    "白色家电": "家电行业",
    "服装家纺": "纺织服装",
    "煤炭开采": "煤炭行业",
    "钢铁": "钢铁行业",
    "建筑材料": "水泥建材",
    "石油加工": "石油行业",
    "电力": "电力行业",
    "环境治理": "环保行业",
    "军工电子": "航天航空",
    "军工装备": "航天航空",
    "房地产": "房地产开发",
    "建筑装饰": "工程建设",
    "物流": "物流行业",
    "影视院线": "文化传媒",
    "旅游及酒店": "旅游酒店",
    "造纸": "造纸印刷",
    "零售": "商业百货",
}


class FundFlowFetcher:
    """资金流数据获取器"""

    def __init__(self):
        self.cache_dir = DATA_DIR / "fundflow_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_fetch_time = None
        self._board_map_file = DATA_DIR / "em_industry_board_map.json"

    def is_trading_hours(self) -> bool:
        """判断是否在交易时段"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()
        
        return (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end)

    def is_1430_window(self) -> bool:
        """判断是否在14:30截面快照窗口(14:28~14:32)"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        window_start = datetime.strptime("14:28", "%H:%M").time()
        window_end = datetime.strptime("14:32", "%H:%M").time()
        
        return window_start <= current_time <= window_end

    def _fetch_with_retry(self, func, max_retries: int = 3, base_delay: float = 1.5,
                          use_exponential: bool = True) -> Optional[pd.DataFrame]:
        """
        带重试机制的数据获取（改进版）
        - 指数退避: 第1次 1.5s, 第2次 3s, 第3次 6s（叠加随机抖动）
        - 对「空返回」和「异常」分类记录
        """
        last_err = None
        for attempt in range(max_retries):
            try:
                result = func()
                if result is not None and not result.empty:
                    if attempt > 0:
                        logger.info(f"第 {attempt + 1} 次尝试成功")
                    return result
                logger.warning(f"第 {attempt + 1} 次获取返回空 DataFrame")
            except AttributeError as ae:
                # AKShare 版本差异导致接口不存在 → 立即跳出，让上层换接口
                last_err = ae
                logger.error(f"第 {attempt + 1} 次获取: AKShare 接口不存在 {ae}")
                break
            except Exception as e:
                last_err = e
                logger.error(f"第 {attempt + 1} 次获取失败 [{type(e).__name__}]: {e}")

            if attempt < max_retries - 1:
                if use_exponential:
                    wait_time = (base_delay * (2 ** attempt)) + random.uniform(0, SYS_CFG.max_retries_delay)
                else:
                    wait_time = base_delay + random.uniform(0, SYS_CFG.max_retries_delay)
                wait_time = min(wait_time, 15)  # 最长不超过 15 秒
                logger.info(f"等待 {wait_time:.1f} 秒后第 {attempt + 2} 次尝试...")
                time.sleep(wait_time)

        logger.error(f"已重试 {max_retries} 次，全部失败。最后错误: {last_err}")
        return None

    def fetch_industry_flow(self) -> pd.DataFrame:
        """
        获取行业资金流数据（多重接口降级 + 缓存兜底）
        优先级：
          1. stock_fund_flow_industry（东方财富行业资金流）
          2. stock_sector_fund_flow_rank（东方财富板块资金流排名）
          3. 缓存兜底（如果以上都失败）
        """
        df = None

        # ===== 接口 1：stock_fund_flow_industry =====
        def fetch_v1():
            logger.debug("尝试接口1: stock_fund_flow_industry")
            return ak.stock_fund_flow_industry()
        df = self._fetch_with_retry(fetch_v1, max_retries=SYS_CFG.max_retries)
        if df is not None and not df.empty:
            return df

        # ===== 接口 2：stock_sector_fund_flow_rank =====
        def fetch_v2():
            logger.debug("尝试接口2: stock_sector_fund_flow_rank")
            return ak.stock_sector_fund_flow_rank()
        df = self._fetch_with_retry(fetch_v2, max_retries=SYS_CFG.max_retries)
        if df is not None and not df.empty:
            return df

        # ===== 接口 3：尝试其他已知变体（部分 AKShare 版本命名不同）=====
        alt_funcs = []
        for fname in [
            "stock_fund_flow_industry_em",
            "stock_fund_flow_industry_ths",
            "stock_board_fund_flow_ths",
            "stock_sector_fund_flow_ths",
        ]:
            if hasattr(ak, fname):
                alt_funcs.append((fname, getattr(ak, fname)))

        for fname, f in alt_funcs:
            def _make_fn(f_name, func):
                def _fn():
                    logger.debug(f"尝试备选接口 {f_name}")
                    return func()
                return _fn
            df = self._fetch_with_retry(_make_fn(fname, f), max_retries=2)
            if df is not None and not df.empty:
                logger.info(f"使用备选接口 {fname} 获取成功")
                return df

        # ===== 缓存兜底 =====
        logger.warning("所有在线接口均失败，尝试使用最新缓存兜底")
        cached_df = self.fetch_cached()
        if not cached_df.empty:
            logger.warning(f"已使用缓存兜底（共 {len(cached_df)} 条），请检查网络或 AKShare 版本")
            return cached_df

        raise RuntimeError(
            "所有资金流接口失败且无可用缓存，请检查网络连接或稍后再试。"
            " 可用接口: stock_fund_flow_industry / stock_sector_fund_flow_rank"
        )

    def normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化资金流数据格式"""
        if df.empty:
            return df

        df = df.copy()
        
        rename_map = {
            '行业': '行业',
            '行业名称': '行业',
            '流入资金': '流入资金',
            '主力净流入': '净额',
            '净流入': '净额',
            '净流入-主力': '净额',
            '流出资金': '流出资金',
            '净额': '净额',
            '行业-涨跌幅': '行业-涨跌幅',
            '涨跌幅': '行业-涨跌幅',
            '主力净流入占比': '主力净流入占比',
            '成交量': '成交量',
        }
        
        for old, new in rename_map.items():
            if old in df.columns and new not in df.columns:
                df = df.rename(columns={old: new})

        if '流入资金' not in df.columns and '净额' in df.columns and '流出资金' in df.columns:
            df['流入资金'] = df['净额'] + df['流出资金']

        for col in ['流入资金', '流出资金', '净额', '行业-涨跌幅', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def fetch_and_cache(self) -> pd.DataFrame:
        """获取数据并缓存"""
        try:
            df = self.fetch_industry_flow()
            df = self.normalize_data(df)
            
            timestamp = datetime.now()
            cache_file = self.cache_dir / f"{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            
            df.to_json(cache_file, orient='records', force_ascii=False)
            
            self.last_fetch_time = timestamp
            logger.info(f"数据缓存成功: {cache_file}")
            
            return df
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            raise

    def fetch_cached(self) -> pd.DataFrame:
        """获取最新缓存数据"""
        cache_files = list(self.cache_dir.glob("*.json"))
        if not cache_files:
            return pd.DataFrame()

        latest_file = sorted(cache_files, key=lambda x: x.stat().st_mtime)[-1]
        
        try:
            df = pd.read_json(latest_file)
            return df
        except Exception as e:
            logger.error(f"读取缓存文件失败: {e}")
            return pd.DataFrame()

    def fetch_history_for_backtest(self, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """获取回测用历史数据"""
        result = {}

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        cache_files = list(self.cache_dir.glob("*.json"))

        for f in cache_files:
            try:
                date_str = f.name[:8]
                file_date = pd.to_datetime(date_str)

                if start_dt <= file_date <= end_dt:
                    df = pd.read_json(f)
                    result[date_str] = df
            except Exception as e:
                logger.warning(f"读取历史文件 {f} 失败: {e}")

        return result

    def _load_em_board_map(self) -> Optional[dict]:
        """读取本地缓存的东财行业板块 {名称: 代码} 表。"""
        try:
            if self._board_map_file.exists():
                data = json.loads(self._board_map_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and len(data) >= 50:
                    return data
        except Exception as e:
            logger.warning(f"读取板块表缓存失败: {e}")
        return None

    def _fetch_em_board_map(self, max_rounds: int = 3):
        """
        用单次请求拉取东财全量行业板块表（pz=200 一页取完，
        避免多页期间触发限流拿到残缺表）。失败按 30s/60s 冷却重试。
        成功后落盘缓存。返回 {板块名: 板块代码}。
        """
        from curl_cffi import requests as cffi_requests

        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "fid": "f62", "po": "1", "pz": "200", "pn": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": "m:90 t:2",
            "fields": "f12,f14",
        }
        wait_schedule = [30, 60]
        for round_idx in range(max_rounds):
            try:
                r = cffi_requests.get(url, params=params,
                                      impersonate="chrome", timeout=15)
                diff = (r.json().get("data") or {}).get("diff") or []
                board_map = {x["f14"]: x["f12"] for x in diff if x.get("f14")}
                if len(board_map) >= 50:
                    self._board_map_file.write_text(
                        json.dumps(board_map, ensure_ascii=False),
                        encoding="utf-8")
                    return board_map
                logger.warning(f"板块表返回不完整（{len(board_map)} 个），将冷却重试")
            except Exception as e:
                logger.warning(f"拉取板块表失败: {str(e)[:100]}")
            if round_idx < max_rounds - 1:
                w = wait_schedule[min(round_idx, len(wait_schedule) - 1)]
                time.sleep(w)
        return None

    def _resolve_industry_board_names(self, industries: list):
        """
        把内部行业名解析为东财板块名。
        顺序：精确匹配 → 别名表 → difflib 模糊匹配(>0.6)。
        返回 (resolved: [(内部名, 东财名)], unresolved: [内部名])。
        """
        import difflib

        board_map = self._load_em_board_map()
        if board_map is None:
            board_map = self._fetch_em_board_map()
        if not board_map:
            # 在线也拿不到：无法解析，但仍允许直接用原名尝试（不阻塞流程）
            logger.warning("板块表不可用，行业名直接透传，缺失板块将逐个失败")
            return [(x, x) for x in industries], []

        # 用我们的完整板块表替换 akshare 的代码映射，防止其内部分页残缺
        try:
            from akshare.stock import stock_fund_em as _em_mod
            _em_mod._get_stock_sector_fund_flow_summary_code = lambda: board_map
        except Exception as e:
            logger.debug(f"替换 akshare 板块表失败（非致命）: {e}")

        em_names = list(board_map.keys())
        resolved, unresolved = [], []
        for name in industries:
            if name in board_map:
                resolved.append((name, name))
                continue
            alias = _EM_INDUSTRY_ALIASES.get(name)
            if alias and alias in board_map:
                resolved.append((name, alias))
                continue
            guess = difflib.get_close_matches(name, em_names, n=1, cutoff=0.6)
            if guess:
                resolved.append((name, guess[0]))
                logger.info(f"行业名模糊匹配: {name} → {guess[0]}")
            else:
                unresolved.append(name)
        return resolved, unresolved

    def _fetch_em_industry_chg(self, board_code: str, days: int) -> dict:
        """
        拉取东财行业板块日 K 的涨跌幅（资金流历史接口本身不含涨跌幅）。
        返回 {'YYYYMMDD': pct_float}；任何失败静默返回空 dict。
        """
        try:
            from curl_cffi import requests as cffi_requests
            beg = (datetime.now() - timedelta(days=days + 12)).strftime("%Y%m%d")
            params = {
                "secid": f"90.{board_code}",
                "klt": "101", "fqt": "0",
                "beg": beg, "end": "20500101",
                "lmt": str(days + 10),
                "fields1": "f1,f2,f3",
                "fields2": "f51,f59",  # 日期, 涨跌幅
            }
            r = cffi_requests.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params=params, impersonate="chrome", timeout=15)
            klines = ((r.json().get("data") or {}).get("klines")) or []
            out = {}
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        out[parts[0].replace("-", "")] = float(parts[1])
                    except (TypeError, ValueError):
                        continue
            return out
        except Exception as e:
            logger.debug(f"板块 {board_code} 日K涨跌幅拉取失败: {str(e)[:80]}")
            return {}

    def backfill_history_from_eastmoney(
        self,
        days: int = 30,
        industries: Optional[list] = None,
        progress_callback=None,
    ) -> Dict[str, pd.DataFrame]:
        """
        从东方财富自动补齐行业资金流历史数据，重建按日期的横截面缓存。

        原理：调用 ak.stock_sector_fund_flow_hist(symbol=行业名) 拉取每个行业
        的逐日历史资金流，然后按日期横截面合并为一份横截面表（schema 与
        fetch_industry_flow 输出一致：行业/流入资金/流出资金/净额/行业-涨跌幅）。

        缓存写入：data/fundflow_cache/YYYYMMDD_143000_snapshot.json
        （用 14:30 时间戳以兼容回测 14:30 信号选择逻辑）。

        Args:
            days: 需要补齐最近多少天的数据（默认 30 天）
            industries: 行业列表；为 None 时用当前最新快照的行业列表
            progress_callback: 可选回调 (current, total, message)

        Returns:
            Dict[date_str, DataFrame] — 与 fetch_history_for_backtest 同型
        """
        if industries is None:
            latest = self.fetch_cached()
            if latest.empty:
                raise RuntimeError("无法获取行业列表：无缓存数据且在线接口不可用")
            col = '行业' if '行业' in latest.columns else 'industry'
            industries = latest[col].dropna().unique().tolist()

        logger.info(f"开始从东方财富补齐 {len(industries)} 个行业最近 {days} 天历史")

        # 内部行业名 → 东财板块名（含别名/模糊匹配）；解析不到的直接跳过，
        # 避免对不存在的板块名做无意义的限流冷却
        resolved_pairs, unresolved = self._resolve_industry_board_names(industries)
        if unresolved:
            logger.warning(f"以下行业无匹配东财板块，已跳过: {unresolved}")
            if progress_callback:
                try:
                    progress_callback(0, len(industries),
                                      f"跳过无匹配板块 {len(unresolved)} 个: "
                                      + ",".join(unresolved[:5]))
                except Exception:
                    pass

        # 每个行业的历史 Series：{内部行业名: DataFrame(日期, 主力净流入-净额, 涨跌幅, ...)}
        per_industry: Dict[str, pd.DataFrame] = {}
        # 每个行业的逐日涨跌幅：{内部行业名: {YYYYMMDD: pct}}
        per_industry_chg: Dict[str, dict] = {}
        board_map = self._load_em_board_map() or {}
        success_count = 0
        fail_count = 0
        skipped_count = len(unresolved)
        consecutive_fails = 0   # 连续失败计数（触发限流冷却）
        cooldown_rounds = 0     # 已执行的冷却轮数
        total = len(resolved_pairs)

        for i, (industry, em_name) in enumerate(resolved_pairs):
            if progress_callback:
                try:
                    label = industry if em_name == industry else f"{industry}({em_name})"
                    progress_callback(i + 1, total, f"拉取 {label}")
                except Exception:
                    pass

            hist = None
            # 单行业最多 2 轮（首轮 + 限流冷却后 1 轮）
            for round_idx in range(2):
                try:
                    hist = ak.stock_sector_fund_flow_hist(symbol=em_name)
                    break
                except KeyError:
                    # 板块名在代码表中不存在：确定性错误，冷却无意义
                    logger.warning(f"[{i+1}/{total}] 板块 {em_name} 不存在，跳过")
                    break
                except Exception as e:
                    # 连续失败说明被限流：指数冷却 25s / 50s
                    if round_idx == 0:
                        wait_s = 25 if cooldown_rounds == 0 else 50
                        logger.warning(
                            f"[{i+1}/{total}] {industry}({em_name}) 失败，"
                            f"{wait_s}s 后冷却重试: {str(e)[:100]}"
                        )
                        if progress_callback:
                            try:
                                progress_callback(i + 1, total,
                                                  f"限流冷却 {wait_s}s ...")
                            except Exception:
                                pass
                        time.sleep(wait_s)
                        cooldown_rounds += 1
                    else:
                        logger.warning(f"[{i+1}/{total}] {industry}({em_name}) 冷却后仍失败: {str(e)[:100]}")

            if hist is not None and not hist.empty:
                per_industry[industry] = hist
                success_count += 1
                consecutive_fails = 0
                # 资金流接口不含涨跌幅，另拉板块日 K 补充（短暂间隔防风控）
                code = board_map.get(em_name)
                if code:
                    time.sleep(0.35 + random.uniform(0, 0.25))
                    per_industry_chg[industry] = self._fetch_em_industry_chg(code, days)
            else:
                fail_count += 1
                consecutive_fails += 1

            # 熔断：连续 8 个行业失败 → 长冷却一次；再失败则终止（返回已拿到的数据）
            if consecutive_fails >= 8:
                logger.warning("连续 8 个行业失败，长冷却 60s")
                time.sleep(60)
                consecutive_fails = 0
                if fail_count > success_count * 3 and success_count > 0:
                    logger.error("失败数远超成功数，终止补齐并保留部分结果")
                    break

            # 常规节流：东财对突发请求限流，保持 1.0~2.0s 随机间隔
            if i < total - 1:
                time.sleep(1.0 + random.uniform(0, 1.0))

        logger.info(f"历史拉取完成：成功 {success_count} 个，失败 {fail_count} 个，"
                    f"跳过 {skipped_count} 个")

        if not per_industry:
            raise RuntimeError("所有行业历史拉取均失败，无法补齐")

        # 计算日期范围
        end_dt = pd.to_datetime(datetime.now().date())
        start_dt = end_dt - pd.Timedelta(days=days - 1)

        # 按日期横截面重建
        rebuilt: Dict[str, pd.DataFrame] = {}
        date_index: set = set()
        for ind, hist in per_industry.items():
            if '日期' not in hist.columns:
                continue
            for d in hist['日期']:
                date_index.add(pd.to_datetime(d).strftime('%Y%m%d'))

        for date_str in sorted(date_index):
            rows = []
            for ind, hist in per_industry.items():
                if '日期' not in hist.columns:
                    continue
                match = hist[pd.to_datetime(hist['日期']).dt.strftime('%Y%m%d') == date_str]
                if match.empty:
                    continue
                r = match.iloc[0]
                # akshare stock_sector_fund_flow_hist 列：
                # 日期 / 主力净流入-净额 / 主力净流入-净占比 / 超大单净流入-净额 / ...
                # 无独立的"流入/流出"分解，也无涨跌幅；
                # 净额用主力净流入（流入/流出按正负拆分），涨跌幅取自板块日 K
                net = r.get('主力净流入-净额', 0) or 0
                chg = per_industry_chg.get(ind, {}).get(date_str, 0)
                rows.append({
                    '行业': ind,
                    '流入资金': max(net, 0),  # 简化处理
                    '流出资金': max(-net, 0),
                    '净额': net,
                    '行业-涨跌幅': chg,
                })
            if not rows:
                continue
            df = pd.DataFrame(rows)
            df = self.normalize_data(df)
            rebuilt[date_str] = df

            # 写缓存（14:30 快照，供回测识别为当日截面）
            cache_file = self.cache_dir / f"{date_str}_143000_snapshot.json"
            if not cache_file.exists():
                try:
                    df.to_json(cache_file, orient='records', force_ascii=False)
                except Exception as e:
                    logger.warning(f"写入补齐缓存 {cache_file} 失败: {e}")

        # 过滤到 [start_dt, end_dt] 范围
        in_range = {
            d: df for d, df in rebuilt.items()
            if start_dt <= pd.to_datetime(d) <= end_dt
        }
        logger.info(f"按日期横截面重建完成，共 {len(in_range)} 天 / 范围 {start_dt.date()} ~ {end_dt.date()}")
        return in_range



    def fetch_history_summary(self) -> pd.DataFrame:
        """获取历史数据摘要"""
        cache_files = sorted(list(self.cache_dir.glob("*.json")), key=lambda x: x.stat().st_mtime)
        
        records = []
        for f in cache_files[-60:]:
            try:
                df = pd.read_json(f)
                timestamp = datetime.strptime(f.name[:15], "%Y%m%d_%H%M%S")
                
                col_net = '净额' if '净额' in df.columns else 'net_flow'
                total_net = df[col_net].sum() if not df.empty else 0
                
                records.append({
                    'time': timestamp,
                    'total_net': total_net,
                    'industry_count': len(df),
                })
            except Exception as e:
                logger.warning(f"读取历史文件 {f} 失败: {e}")
        
        return pd.DataFrame(records)

    def clear_old_cache(self, days: int = 30):
        """清理过期缓存"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cache_files = list(self.cache_dir.glob("*.json"))
        deleted_count = 0
        
        for f in cache_files:
            try:
                file_date = datetime.fromtimestamp(f.stat().st_mtime)
                if file_date < cutoff_date:
                    f.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"删除缓存文件 {f} 失败: {e}")
        
        logger.info(f"清理了 {deleted_count} 个过期缓存文件")

    def get_snapshot_for_backtest(self) -> pd.DataFrame:
        """获取14:30截面快照数据（用于回测）"""
        cache_files = sorted(list(self.cache_dir.glob("*.json")), key=lambda x: x.stat().st_mtime, reverse=True)
        
        for f in cache_files[:10]:
            try:
                name = f.name
                time_str = name[9:15]
                if "1430" <= time_str <= "1432":
                    df = pd.read_json(f)
                    logger.info(f"找到14:30快照数据: {name}")
                    return df
            except:
                continue
        
        return self.fetch_cached()

    def fetch_and_save_with_mark(self) -> pd.DataFrame:
        """获取数据并保存，标记是否为14:30快照"""
        try:
            df = self.fetch_industry_flow()
            df = self.normalize_data(df)
            
            timestamp = datetime.now()
            is_1430 = self.is_1430_window()
            
            if is_1430:
                cache_file = self.cache_dir / f"{timestamp.strftime('%Y%m%d_%H%M%S')}_snapshot.json"
            else:
                cache_file = self.cache_dir / f"{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            
            df.to_json(cache_file, orient='records', force_ascii=False)
            
            df['fetch_time'] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            df['is_snapshot'] = is_1430
            
            self.last_fetch_time = timestamp
            logger.info(f"数据缓存成功{' [14:30快照]' if is_1430 else ''}: {cache_file}")
            
            return df
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            raise


if __name__ == "__main__":
    fetcher = FundFlowFetcher()
    
    print(f"当前是否交易时段: {fetcher.is_trading_hours()}")
    print(f"当前是否14:30窗口: {fetcher.is_1430_window()}")
    
    try:
        df = fetcher.fetch_and_cache()
        print(f"数据获取成功，共 {len(df)} 条行业数据")
        print(df.head())
    except Exception as e:
        print(f"数据获取失败: {e}")
    
    history_summary = fetcher.fetch_history_summary()
    print(f"历史数据摘要: {len(history_summary)} 条记录")