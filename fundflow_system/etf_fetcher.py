"""
数据层 - ETF行情数据获取与行业映射模块
功能：ETF列表获取、历史行情、行业映射、低流动性过滤
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import logging
import time
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ETF 历史数据请求节流（避免触发东方财富 RemoteDisconnected）
ETF_HIST_THROTTLE = (0.8, 1.6)  # 每只 ETF 请求间随机 sleep 区间(秒)
ETF_LIST_THROTTLE = (1.0, 2.0)

# 请求头注入（复用 fundflow_fetcher 的反爬头）
try:
    from fundflow_fetcher import _inject_requests_headers
    _inject_requests_headers()
except Exception:
    pass

from config import INDUSTRY_ETF_MAPPING, DATA_DIR, SYS_CFG


class ETFFetcher:
    """ETF行情数据获取器"""

    def __init__(self):
        self._spot_cache: Optional[pd.DataFrame] = None
        self._cache_time = None

    def _retry(self, func, max_retries: int = 3, base_delay: float = 1.2):
        """通用重试（指数退避 + 节流）"""
        last_err = None
        for attempt in range(max_retries):
            try:
                result = func()
                if result is not None and (isinstance(result, pd.DataFrame) and not result.empty):
                    if attempt > 0:
                        logger.debug(f"第 {attempt + 1} 次尝试成功")
                    return result
                if isinstance(result, pd.DataFrame) and result.empty:
                    logger.warning(f"第 {attempt + 1} 次返回空数据")
            except (ConnectionError, TimeoutError) as ce:
                last_err = ce
                logger.warning(f"第 {attempt + 1} 次网络异常: {ce}")
            except Exception as e:
                last_err = e
                # 连接被远端断开是常见限流，降级为 warning 级别
                if "RemoteDisconnected" in str(type(e).__name__) or "closed connection" in str(e).lower():
                    logger.warning(f"第 {attempt + 1} 次远端断开连接: {e}")
                else:
                    logger.warning(f"第 {attempt + 1} 次失败 [{type(e).__name__}]: {e}")
            if attempt < max_retries - 1:
                wait = min(base_delay * (2 ** attempt) + random.uniform(0, 1.5), 20)
                time.sleep(wait)
        logger.error(f"重试 {max_retries} 次全部失败: {last_err}")
        return pd.DataFrame() if last_err else None

    def fetch_etf_list(self) -> pd.DataFrame:
        """获取全量ETF列表（带重试 + 备用接口）"""
        result = self._retry(lambda: ak.fund_etf_spot_em(), max_retries=2)
        if result is not None and not result.empty:
            return result
        logger.warning("东方财富ETF列表失败，尝试同花顺备用接口")
        return self._fetch_etf_list_fallback()

    def _fetch_etf_list_fallback(self) -> pd.DataFrame:
        """备用：从同花顺获取ETF列表"""
        result = self._retry(lambda: ak.fund_etf_spot_ths(), max_retries=2)
        if result is not None:
            return result
        logger.error("备用ETF列表也失败")
        return pd.DataFrame()

    def fetch_etf_hist(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取单只ETF历史日线数据（带重试 + 指数退避 + 新浪备用）"""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        def _do_fetch():
            return ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

        df = self._retry(_do_fetch, max_retries=3, base_delay=1.0)
        if df is None:
            df = pd.DataFrame()

        # 东方财富失败（如 push2his 被网络封禁）→ 新浪财经备用
        if df.empty:
            logger.info(f"ETF {code} 东方财富历史数据失败，切换新浪备用接口")
            try:
                df = self._fetch_etf_hist_sina(code, days)
            except Exception as e:
                logger.warning(f"ETF {code} 新浪备用接口也失败: {e}")
                df = pd.DataFrame()
        return df

    @staticmethod
    def _sina_symbol(code: str) -> str:
        """ETF 代码加交易所前缀：5/6 开头沪市(sh)，1/0 开头深市(sz)"""
        return ("sh" if code[0] in ("5", "6") else "sz") + code

    def _fetch_etf_hist_sina(self, code: str, days: int) -> pd.DataFrame:
        """新浪财经 ETF 历史日线（输出列名归一化为东方财富 schema）"""
        raw = ak.fund_etf_hist_sina(symbol=self._sina_symbol(code))
        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw.rename(columns={
            "date": "日期", "open": "开盘", "close": "收盘",
            "high": "最高", "low": "最低",
            "volume": "成交量", "amount": "成交额",
        })
        df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")

        start_dt = datetime.now() - timedelta(days=days)
        end_dt = datetime.now()
        df = df[
            (pd.to_datetime(df["日期"]) >= start_dt)
            & (pd.to_datetime(df["日期"]) <= end_dt)
        ].reset_index(drop=True)
        return df

    def fetch_multi_etf_hist(self, codes: List[str], days: int = 60) -> Dict[str, pd.DataFrame]:
        """批量获取多只ETF历史数据（请求间节流避免被封）"""
        results = {}
        total = len(codes)
        for idx, code in enumerate(codes):
            try:
                df = self.fetch_etf_hist(code, days)
                if not df.empty:
                    results[code] = df
                else:
                    logger.warning(f"[{idx + 1}/{total}] ETF {code} 历史数据为空")
            except Exception as e:
                logger.error(f"[{idx + 1}/{total}] ETF {code} 获取异常: {e}")
            # 请求间节流（最后一个不需要）
            if idx < total - 1:
                t = random.uniform(*ETF_HIST_THROTTLE)
                time.sleep(t)
        logger.info(f"批量获取完成: 成功 {len(results)}/{total}")
        return results

    def filter_low_liquidity(self, etf_df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤低流动性标的
        剔除：场内规模＜5000万、停牌、日成交量过低的ETF
        """
        if etf_df.empty:
            return etf_df

        min_scale = SYS_CFG.min_etf_scale

        df = etf_df.copy()

        if '规模' in df.columns:
            df['规模'] = pd.to_numeric(df['规模'], errors='coerce')
            df = df[df['规模'] >= min_scale]
            logger.info(f"按规模过滤后剩余 {len(df)} 只ETF")

        if '成交量' in df.columns:
            df['成交量'] = pd.to_numeric(df['成交量'], errors='coerce')
            df = df[df['成交量'] > 0]
            logger.info(f"按成交量过滤后剩余 {len(df)} 只ETF")

        if '最新价' in df.columns:
            df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')
            df = df[df['最新价'] > 0]
            logger.info(f"按价格过滤后剩余 {len(df)} 只ETF")

        return df

    def get_filtered_etf_list(self) -> pd.DataFrame:
        """获取过滤后的ETF列表"""
        df = self.fetch_etf_list()
        return self.filter_low_liquidity(df)


class IndustryETFMapper:
    """行业 → ETF 映射器"""

    def __init__(self):
        self.mapping = INDUSTRY_ETF_MAPPING

    def get_etf(self, industry: str) -> Optional[Tuple[str, str]]:
        """获取行业对应的ETF (code, name)"""
        return self.mapping.get(industry)

    def get_all_mapped_industries(self) -> List[str]:
        """获取所有已映射行业的列表"""
        return list(self.mapping.keys())

    def get_etf_universe(self) -> Dict[str, dict]:
        """
        获取ETF投资池（去重后的唯一ETF列表）
        Returns: {code: {name, industries}}
        """
        etf_dict = {}
        for industry, (code, name) in self.mapping.items():
            if code not in etf_dict:
                etf_dict[code] = {"name": name, "industries": []}
            etf_dict[code]["industries"].append(industry)
        return etf_dict

    def map_industry_flow_to_etf(self, flow_df: pd.DataFrame) -> pd.DataFrame:
        """
        将行业资金流数据映射到ETF维度
        一个ETF可能对应多个行业，取净额加权平均
        """
        if flow_df.empty:
            return pd.DataFrame()

        col_inflow = '流入资金' if '流入资金' in flow_df.columns else 'inflow'
        col_outflow = '流出资金' if '流出资金' in flow_df.columns else 'outflow'
        col_net = '净额' if '净额' in flow_df.columns else 'net_flow'
        col_change = '行业-涨跌幅' if '行业-涨跌幅' in flow_df.columns else 'change_pct'
        col_industry = '行业' if '行业' in flow_df.columns else 'industry'

        records = []
        for _, row in flow_df.iterrows():
            industry = row[col_industry]
            etf_info = self.get_etf(industry)
            if etf_info is None:
                continue

            code, name = etf_info
            records.append({
                'etf_code': code,
                'etf_name': name,
                'industry': industry,
                'net_flow': row[col_net],
                'inflow': row[col_inflow],
                'outflow': row[col_outflow],
                'change_pct': row[col_change],
            })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        agg = df.groupby(['etf_code', 'etf_name']).agg(
            net_flow=('net_flow', 'sum'),
            inflow=('inflow', 'sum'),
            outflow=('outflow', 'sum'),
            change_pct=('change_pct', 'mean'),
            industry_count=('industry', 'nunique'),
            industries=('industry', lambda x: '、'.join(x))
        ).reset_index()

        return agg.sort_values('net_flow', ascending=False)


if __name__ == "__main__":
    fetcher = ETFFetcher()
    filtered_df = fetcher.get_filtered_etf_list()
    print(f"过滤后的ETF数量: {len(filtered_df)}")

    mapper = IndustryETFMapper()
    etf_universe = mapper.get_etf_universe()
    print(f"ETF投资池: {len(etf_universe)} 只唯一ETF")
    for code, info in list(etf_universe.items())[:10]:
        print(f"  {code} {info['name']} → {', '.join(info['industries'])}")