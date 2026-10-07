"""
定时采集服务 - 每5分钟采集行业资金流数据，14:30记录买入信号
"""

import time
import schedule
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import IndustryETFMapper
from flow_analyzer import SignalGenerator, FlowAnalyzer


class FundFlowScheduler:
    """资金流定时采集调度器"""
    
    def __init__(self):
        self.fetcher = FundFlowFetcher()
        self.mapper = IndustryETFMapper()
        self.signal_gen = SignalGenerator(self.mapper)
        self.analyzer = FlowAnalyzer()
        
        self.signal_dir = Path(__file__).parent / "signals"
        self.signal_dir.mkdir(parents=True, exist_ok=True)
        
        self.daily_signal_recorded = False
        self.last_fetch_time = None
    
    def is_trading_day(self) -> bool:
        """判断是否为交易日"""
        now = datetime.now()
        return now.weekday() < 5
    
    def is_trading_hours(self) -> bool:
        """判断是否在交易时段"""
        return self.fetcher.is_trading_hours()
    
    def fetch_and_record(self):
        """执行一次采集并记录"""
        try:
            df = self.fetcher.fetch_and_save_with_mark()
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] 采集成功，共 {len(df)} 条行业数据")
            
            self.last_fetch_time = datetime.now()
            
            return df
        except Exception as e:
            logger.error(f"[{datetime.now().strftime('%H:%M:%S')}] 采集失败: {e}")
            return None
    
    def record_1430_signal(self):
        """记录14:30买入信号（前五ETF）"""
        try:
            df = self.fetcher.get_snapshot_for_backtest()
            
            if df.empty:
                df = self.fetcher.fetch_cached()
            
            if df.empty:
                logger.warning("没有可用的资金流数据，无法生成买入信号")
                return
            
            df = self.analyzer.rank_industries(df)
            df = self.analyzer.calc_inflow_ratio(df)
            
            etf_df = self.mapper.map_industry_flow_to_etf(df)
            
            if etf_df.empty:
                logger.warning("没有找到映射的ETF")
                return
            
            etf_df['score'] = self.signal_gen.score_etf(etf_df)
            
            top5 = etf_df.sort_values('score', ascending=False).head(5).copy()
            
            signal_record = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'top5_etfs': top5[['etf_code', 'etf_name', 'score', 'net_flow', 'change_pct']].to_dict('records'),
                'total_industry_count': len(df),
                'total_etf_count': len(etf_df),
            }
            
            signal_file = self.signal_dir / f"{datetime.now().strftime('%Y%m%d')}_signal.json"
            with open(signal_file, 'w', encoding='utf-8') as f:
                json.dump(signal_record, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 14:30买入信号已记录，选中5只ETF: {[e['etf_name'] for e in signal_record['top5_etfs']]}")
            
            return signal_record
            
        except Exception as e:
            logger.error(f"记录14:30信号失败: {e}")
            return None
    
    def run_daily(self):
        """每日执行流程"""
        logger.info(f"========== 开始新一天采集 [{datetime.now().strftime('%Y-%m-%d')}] ==========")
        
        self.daily_signal_recorded = False
        
        while self.is_trading_day():
            now = datetime.now()
            
            if self.is_trading_hours():
                self.fetch_and_record()
                
                if self.fetcher.is_1430_window() and not self.daily_signal_recorded:
                    self.record_1430_signal()
                    self.daily_signal_recorded = True
            
            time.sleep(300)
    
    def start(self):
        """启动调度器"""
        logger.info("🚀 资金流定时采集服务启动")
        logger.info("📋 采集计划: 交易时段每5分钟采集一次")
        logger.info("🎯 14:30自动记录买入信号（前五ETF）")
        
        while True:
            now = datetime.now()
            
            if self.is_trading_day():
                self.run_daily()
            else:
                logger.info(f"周末休息，下一个交易日: {self.get_next_trading_day()}")
                time.sleep(3600)
    
    def get_next_trading_day(self) -> str:
        """获取下一个交易日"""
        next_day = datetime.now() + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")


if __name__ == "__main__":
    scheduler = FundFlowScheduler()
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("⏹️ 采集服务已停止")