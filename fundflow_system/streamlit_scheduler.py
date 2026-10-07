"""
Streamlit 后台调度器
功能：
1. 交易时段每5分钟自动采集行业资金流数据，存档到本地
2. 14:30 窗口记录当日买入信号（前5 ETF）到 signals 目录
3. 通过 st.session_state 共享状态，与 Streamlit 主进程解耦
"""

import threading
import time
import json
import logging
import os
import signal as _signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

import pandas as pd

from config import ROOT_DIR, DATA_DIR, SYS_CFG, BACKTEST_CFG
from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import IndustryETFMapper
from flow_analyzer import SignalGenerator, FlowAnalyzer

logger = logging.getLogger(__name__)

# 信号目录
SIGNAL_DIR = ROOT_DIR / "signals"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

# 调度日志
SCHEDULER_LOG = DATA_DIR / "scheduler_status.json"
# PID 锁文件：标识是否有独立调度器进程在运行
SCHEDULER_PID_FILE = DATA_DIR / "scheduler.pid"


class StreamlitScheduler:
    """集成在 Streamlit 进程中的后台调度器（单例）"""

    _instance: Optional["StreamlitScheduler"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.fetcher = FundFlowFetcher()
        self.mapper = IndustryETFMapper()
        self.signal_gen = SignalGenerator(self.mapper)
        self.analyzer = FlowAnalyzer()

        self.thread: Optional[threading.Thread] = None
        self.watchdog_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.status_lock = threading.Lock()
        self._fetch_lock = threading.Lock()  # 防止并发重复采集
        self._backtest_lock = threading.Lock()  # 防止并发重复回测
        self._loop_crash_count = 0  # 主循环崩溃次数

        # 共享状态（与 Streamlit 读取）
        self.status: Dict = {
            "running": False,
            # 采集相关
            "last_fetch_time": None,
            "last_fetch_count": 0,
            "last_fetch_msg": "",
            "today_fetch_count": 0,
            # 14:30 信号相关
            "today_signal_recorded": False,
            "last_signal_time": None,
            "last_signal_top5": [],
            # 自动回测相关
            "today_backtest_done": False,
            "last_backtest_time": None,
            "last_backtest_status": "",  # success/failed/running
            "last_backtest_msg": "",
            "last_backtest_summary": {},  # 最近一次回测核心指标
            # 健康度/心跳
            "last_heartbeat": None,
            "heartbeat_count": 0,
            "thread_alive": False,
            "loop_crash_count": 0,  # 主循环崩溃次数
            "last_crash_time": None,
            "last_crash_msg": "",
            # 通用
            "history": [],  # 最近的操作记录
            "started_at": None,
            "last_update_time": None,  # 任何自动操作的最后更新时间
        }

    # ===== 状态访问 =====
    def get_status(self) -> Dict:
        with self.status_lock:
            return dict(self.status)

    def _push_history(self, record: Dict, max_len: int = 50):
        self.status["history"].append(record)
        if len(self.status["history"]) > max_len:
            self.status["history"] = self.status["history"][-max_len:]

    def _persist_status(self):
        """持久化调度状态到本地，便于重启后恢复"""
        try:
            with open(SCHEDULER_LOG, "w", encoding="utf-8") as f:
                json.dump({
                    "last_fetch_time": self.status["last_fetch_time"],
                    "today_fetch_count": self.status["today_fetch_count"],
                    "today_signal_recorded": self.status["today_signal_recorded"],
                    "last_signal_time": self.status["last_signal_time"],
                    "last_signal_top5": self.status["last_signal_top5"],
                    "today_backtest_done": self.status["today_backtest_done"],
                    "last_backtest_time": self.status["last_backtest_time"],
                    "last_backtest_status": self.status["last_backtest_status"],
                    "last_backtest_msg": self.status["last_backtest_msg"],
                    "last_backtest_summary": self.status["last_backtest_summary"],
                    "last_heartbeat": self.status["last_heartbeat"],
                    "heartbeat_count": self.status["heartbeat_count"],
                    "loop_crash_count": self.status["loop_crash_count"],
                    "last_crash_time": self.status["last_crash_time"],
                    "last_crash_msg": self.status["last_crash_msg"],
                    "history": self.status["history"][-20:],
                    "last_update_time": self.status["last_update_time"],
                }, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"持久化调度状态失败: {e}")

    def load_persisted_status(self):
        """加载持久化状态（仅在启动时调用一次）"""
        try:
            if SCHEDULER_LOG.exists():
                with open(SCHEDULER_LOG, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 只恢复当日的采集计数；跨日则重置
                last_str = data.get("last_fetch_time")
                if last_str:
                    last_dt = datetime.fromisoformat(last_str)
                    if last_dt.date() == datetime.now().date():
                        self.status["today_fetch_count"] = data.get("today_fetch_count", 0)
                        self.status["today_signal_recorded"] = data.get("today_signal_recorded", False)
                        self.status["today_backtest_done"] = data.get("today_backtest_done", False)
                    else:
                        self.status["today_fetch_count"] = 0
                        self.status["today_signal_recorded"] = False
                        self.status["today_backtest_done"] = False
                # 不区分日期的字段
                self.status["last_signal_time"] = data.get("last_signal_time")
                self.status["last_signal_top5"] = data.get("last_signal_top5", [])
                self.status["last_backtest_time"] = data.get("last_backtest_time")
                self.status["last_backtest_status"] = data.get("last_backtest_status", "")
                self.status["last_backtest_msg"] = data.get("last_backtest_msg", "")
                self.status["last_backtest_summary"] = data.get("last_backtest_summary", {})
                self.status["last_heartbeat"] = data.get("last_heartbeat")
                self.status["heartbeat_count"] = data.get("heartbeat_count", 0)
                self.status["loop_crash_count"] = data.get("loop_crash_count", 0)
                self.status["last_crash_time"] = data.get("last_crash_time")
                self.status["last_crash_msg"] = data.get("last_crash_msg", "")
                self.status["history"] = data.get("history", [])
                self.status["last_update_time"] = data.get("last_update_time")
                self._loop_crash_count = self.status["loop_crash_count"]
        except Exception as e:
            logger.warning(f"加载持久化调度状态失败: {e}")

    # ===== 调度控制 =====
    @staticmethod
    def is_standalone_running() -> bool:
        """检查是否有独立调度器进程在运行（通过 PID 文件）"""
        try:
            if not SCHEDULER_PID_FILE.exists():
                return False
            with open(SCHEDULER_PID_FILE, "r", encoding="utf-8") as f:
                pid_str = f.read().strip()
            if not pid_str:
                return False
            pid = int(pid_str)
            if pid == os.getpid():
                return False
            # 跨平台进程存活检测
            try:
                import psutil
                return psutil.pid_exists(pid)
            except ImportError:
                import sys as _sys
                if _sys.platform == "win32":
                    # Windows: tasklist 检查
                    import subprocess
                    result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}"],
                        capture_output=True, text=True, timeout=5
                    )
                    return str(pid) in result.stdout
                else:
                    # Linux/Unix: /proc 检查
                    import os as _os
                    return _os.path.exists(f"/proc/{pid}")
        except Exception as e:
            logger.warning(f"检查独立调度器状态失败: {e}")
            return False

    def _write_pid_file(self):
        """写入当前进程 PID 到锁文件"""
        try:
            with open(SCHEDULER_PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            logger.info(f"已写入 PID 文件: {os.getpid()}")
        except Exception as e:
            logger.warning(f"写入 PID 文件失败: {e}")

    def _clear_pid_file(self):
        """清除 PID 锁文件"""
        try:
            if SCHEDULER_PID_FILE.exists():
                # 仅当文件中的 PID 是当前进程时才清除
                with open(SCHEDULER_PID_FILE, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip() or "0")
                if pid == os.getpid():
                    SCHEDULER_PID_FILE.unlink()
                    logger.info("已清除 PID 文件")
        except Exception as e:
            logger.warning(f"清除 PID 文件失败: {e}")

    def start(self, standalone: bool = False):
        """
        启动后台采集线程 + Watchdog 保活线程
        - standalone=False: Streamlit 内嵌模式（默认，Streamlit 关闭时停止）
        - standalone=True: 独立进程模式（写入 PID 锁，避免与 Streamlit 内嵌线程冲突）
        """
        if self.status["running"]:
            return False
        # 若独立调度器已在运行，内嵌模式不再启动
        if not standalone and self.is_standalone_running():
            logger.info("检测到独立调度器在运行，跳过内嵌线程启动")
            self.status["last_fetch_msg"] = "独立调度器在运行中（无需启动内嵌线程）"
            return False
        self.stop_event.clear()
        self.load_persisted_status()
        # 启动主循环线程（可被 watchdog 自动重启）
        self._spawn_loop_thread()
        # 启动 watchdog 线程（仅启动一次）
        if not (self.watchdog_thread and self.watchdog_thread.is_alive()):
            self.watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="SchedulerWatchdog"
            )
            self.watchdog_thread.start()
        with self.status_lock:
            self.status["running"] = True
            self.status["started_at"] = datetime.now().isoformat()
            self.status["standalone"] = standalone
            self.status["thread_alive"] = True
        if standalone:
            self._write_pid_file()
        logger.info(f"Streamlit 后台调度器已启动 (standalone={standalone})")
        return True

    def _spawn_loop_thread(self):
        """（重新）生成主循环线程，崩溃后由 watchdog 调用"""
        self.thread = threading.Thread(target=self._run_loop_safe, daemon=True, name="FundFlowScheduler")
        self.thread.start()
        logger.info("主循环线程已启动/重启")

    def _watchdog_loop(self):
        """看门狗：监控主循环线程存活，异常退出则自动重启"""
        logger.info("Watchdog 线程已启动")
        consec_idle = 0
        while not self.stop_event.is_set():
            try:
                now = datetime.now()
                # 心跳：每 30 秒一次，哪怕没有采集也更新
                with self.status_lock:
                    self.status["last_heartbeat"] = now.isoformat()
                    self.status["heartbeat_count"] = self.status.get("heartbeat_count", 0) + 1
                    self.status["thread_alive"] = bool(self.thread and self.thread.is_alive())

                # 每 5 分钟也持久化一次心跳，确保状态文件是新的
                if self.status["heartbeat_count"] % 10 == 0:
                    self._persist_status()

                # 主循环线程存活检测
                if self.status["running"]:
                    if not (self.thread and self.thread.is_alive()):
                        consec_idle += 1
                        logger.warning(f"Watchdog 检测到主循环线程未存活 (连续第 {consec_idle} 次)，尝试重启...")
                        if consec_idle >= 1:
                            # 重启主循环
                            self._loop_crash_count += 1
                            with self.status_lock:
                                self.status["loop_crash_count"] = self._loop_crash_count
                                self.status["last_crash_time"] = now.isoformat()
                                self.status["last_crash_msg"] = "主循环线程退出，Watchdog 自动重启"
                                self._push_history({
                                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                                    "action": "watchdog_restart",
                                    "crash_count": self._loop_crash_count,
                                })
                            try:
                                self._spawn_loop_thread()
                                consec_idle = 0
                            except Exception as re:
                                logger.error(f"Watchdog 重启主循环失败: {re}")
                    else:
                        consec_idle = 0
            except Exception as e:
                logger.error(f"Watchdog 异常: {e}")
            # 30 秒检测周期
            self.stop_event.wait(timeout=30)
        logger.info("Watchdog 线程已退出")

    def stop(self):
        """停止后台采集线程 + Watchdog"""
        self.stop_event.set()
        with self.status_lock:
            self.status["running"] = False
            self.status["thread_alive"] = False
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=3)
            self.watchdog_thread = None
        # 清除 PID 文件（如果是独立模式）
        self._clear_pid_file()
        # 退出时持久化最终状态
        self._persist_status()
        logger.info("Streamlit 后台调度器已停止")
        return True

    def _run_loop_safe(self):
        """_run_loop 的安全包装：任何未捕获异常都写入日志并记录"""
        try:
            self._run_loop()
        except Exception as e:
            logger.critical(f"主循环未捕获异常（将由 Watchdog 重启）: {e}", exc_info=True)
            with self.status_lock:
                self.status["last_crash_time"] = datetime.now().isoformat()
                self.status["last_crash_msg"] = f"{type(e).__name__}: {e}"
                self.status["thread_alive"] = False
                self._push_history({
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "loop_crash",
                    "msg": f"{type(e).__name__}: {e}",
                })
            self._persist_status()

    # ===== 主循环 =====
    def _run_loop(self):
        """
        主循环（改进版 v2）：
        1. 交易日 交易时段：每 5 分钟采集一次
        2. 交易日 非交易时段（午间/盘前/盘后）：每 30 分钟采集一次
        3. 周末/节假日：每 60 分钟采集一次
        4. 最小采集间隔保护：任何情况下 60 秒内不得重复采集
        5. 基于日期的跨日重置
        6. _do_fetch 内部加去重锁
        """
        last_fetch = None
        last_cross_date = None  # 上一次跨日重置的日期
        # 最小采集间隔保护（秒）：避免接口1降级到接口2时 10 秒内连续写入缓存
        MIN_FETCH_GAP_SECONDS = 45

        # 启动时若 last_fetch_time 已存在则沿用
        if self.status["last_fetch_time"]:
            try:
                last_fetch = datetime.fromisoformat(self.status["last_fetch_time"])
                last_cross_date = last_fetch.date()
            except Exception:
                last_fetch = None
                last_cross_date = None

        logger.info(f"调度主循环启动 | 上次采集={last_fetch} | 跨日基准={last_cross_date}")

        while not self.stop_event.is_set():
            try:
                now = datetime.now()
                today = now.date()

                # ===== 跨日重置 =====
                if last_cross_date != today:
                    with self.status_lock:
                        self.status["today_fetch_count"] = 0
                        self.status["today_signal_recorded"] = False
                        self.status["today_backtest_done"] = False
                    logger.info(f"跨日重置: {last_cross_date} -> {today}")
                    last_cross_date = today

                # ===== 判断当前时间窗口 =====
                is_trading = self._is_trading_time(now)
                is_weekday = now.weekday() < 5
                is_1430_window = self._is_1430_window(now)

                # ===== 回测窗口：更严格的校验 =====
                # 条件：工作日 + 15:10之后 + 今日未回测 + 今日至少采集过1次（有快照数据）
                already_has_today_fetch = (
                    self.status["last_fetch_time"] is not None
                    and datetime.fromisoformat(self.status["last_fetch_time"]).date() == today
                )
                is_backtest_window = (
                    is_weekday
                    and self._is_post_close_backtest_window(now)
                    and not self.status["today_backtest_done"]
                    and already_has_today_fetch
                )

                # ===== 计算本轮是否采集 =====
                should_fetch = False
                seconds_since = (now - last_fetch).total_seconds() if last_fetch else float('inf')
                # 最小间隔强制保护
                min_gap_ok = seconds_since >= MIN_FETCH_GAP_SECONDS

                if is_trading:
                    if seconds_since >= SYS_CFG.auto_refresh_interval and min_gap_ok:
                        should_fetch = True
                    next_check = 10
                elif is_weekday:
                    if seconds_since >= 30 * 60 and min_gap_ok:
                        should_fetch = True
                    next_check = 30
                else:
                    if seconds_since >= 60 * 60 and min_gap_ok:
                        should_fetch = True
                    next_check = 60

                # ===== 执行采集（去重锁）=====
                if should_fetch:
                    # 使用 try-lock 跳过，不阻塞
                    got_lock = self._fetch_lock.acquire(blocking=False)
                    if got_lock:
                        try:
                            self._do_fetch(now)
                            last_fetch = now
                            if is_weekday and is_1430_window and not self.status["today_signal_recorded"]:
                                self._record_1430_signal(now)
                        except Exception as fe:
                            logger.error(f"执行采集失败: {fe}", exc_info=True)
                        finally:
                            self._fetch_lock.release()
                    else:
                        logger.debug("采集锁被占用，跳过本轮")

                # ===== 收盘后自动回测（防重入锁）=====
                if is_backtest_window:
                    got_bt = self._backtest_lock.acquire(blocking=False)
                    if got_bt:
                        try:
                            self._run_daily_backtest(now)
                        except Exception as be:
                            logger.error(f"自动回测失败: {be}", exc_info=True)
                        finally:
                            self._backtest_lock.release()

            except Exception as e:
                logger.error(f"调度循环异常: {e}", exc_info=True)
                with self.status_lock:
                    self.status["last_fetch_msg"] = f"调度器异常: {e}"
                    self.status["last_update_time"] = datetime.now().isoformat()

            self.stop_event.wait(timeout=next_check)

        logger.info("调度主循环已退出")

    def _is_post_close_backtest_window(self, now: datetime) -> bool:
        """是否处于收盘后回测窗口（工作日 15:10 - 23:59）"""
        if now.weekday() >= 5:
            return False
        t = now.time()
        return datetime.strptime("15:10", "%H:%M").time() <= t <= datetime.strptime("23:59", "%H:%M").time()

    def _is_trading_time(self, now: datetime) -> bool:
        """是否处于 A股交易时段（工作日 09:25-11:35 / 12:55-15:05）"""
        if now.weekday() >= 5:
            return False
        t = now.time()
        morning_start = datetime.strptime("09:25", "%H:%M").time()
        morning_end = datetime.strptime("11:35", "%H:%M").time()
        afternoon_start = datetime.strptime("12:55", "%H:%M").time()
        afternoon_end = datetime.strptime("15:05", "%H:%M").time()
        return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)

    def _is_1430_window(self, now: datetime) -> bool:
        """是否处于 14:30 买入信号记录窗口（工作日 14:28-14:33）"""
        if now.weekday() >= 5:
            return False
        t = now.time()
        w_start = datetime.strptime("14:28", "%H:%M").time()
        w_end = datetime.strptime("14:33", "%H:%M").time()
        return w_start <= t <= w_end

    # ===== 实际采集 =====
    def _do_fetch(self, now: datetime):
        """执行一次采集并存档"""
        try:
            df = self.fetcher.fetch_and_save_with_mark()
            is_snapshot = self.fetcher.is_1430_window()

            with self.status_lock:
                self.status["last_fetch_time"] = now.isoformat()
                self.status["last_fetch_count"] = len(df)
                self.status["last_fetch_msg"] = f"采集成功{' [14:30快照]' if is_snapshot else ''}，共 {len(df)} 条行业"
                self.status["today_fetch_count"] += 1
                self.status["last_update_time"] = now.isoformat()

                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "fetch",
                    "snapshot": is_snapshot,
                    "count": len(df),
                    "net_total": float(df['净额'].sum()) if '净额' in df.columns else 0,
                })

            self._persist_status()
            logger.info(f"[{now:%H:%M:%S}] 自动采集成功，行业数={len(df)}")

        except Exception as e:
            with self.status_lock:
                self.status["last_fetch_msg"] = f"采集失败: {e}"
                self.status["last_update_time"] = now.isoformat()
                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "fetch_error",
                    "msg": str(e),
                })
            logger.error(f"自动采集失败: {e}")

    def _record_1430_signal(self, now: datetime):
        """14:30 窗口：记录买入信号（前5 ETF），用于回测"""
        try:
            df = self.fetcher.get_snapshot_for_backtest()
            if df.empty:
                df = self.fetcher.fetch_cached()
            if df.empty:
                logger.warning("无可用资金流数据，跳过14:30信号记录")
                return

            df = self.analyzer.rank_industries(df)
            df = self.analyzer.calc_inflow_ratio(df)

            etf_df = self.mapper.map_industry_flow_to_etf(df)
            if etf_df.empty:
                logger.warning("ETF映射为空，跳过14:30信号记录")
                return

            etf_df['score'] = self.signal_gen.score_etf(etf_df)
            top5 = etf_df.sort_values('score', ascending=False).head(5).copy()

            record = {
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "top5_etfs": top5[['etf_code', 'etf_name', 'score', 'net_flow', 'change_pct']].to_dict('records'),
                "total_industry_count": len(df),
                "total_etf_count": len(etf_df),
            }

            signal_file = SIGNAL_DIR / f"{now.strftime('%Y%m%d')}_signal.json"
            with open(signal_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            with self.status_lock:
                self.status["today_signal_recorded"] = True
                self.status["last_signal_time"] = now.isoformat()
                self.status["last_signal_top5"] = [e["etf_name"] for e in record["top5_etfs"]]
                self.status["last_update_time"] = now.isoformat()
                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "record_1430_signal",
                    "top5": [e["etf_name"] for e in record["top5_etfs"]],
                    "file": str(signal_file),
                })

            self._persist_status()
            logger.info(f"14:30 买入信号已记录: {[e['etf_name'] for e in record['top5_etfs']]}")

        except Exception as e:
            logger.error(f"记录14:30信号失败: {e}", exc_info=True)
            with self.status_lock:
                self.status["last_update_time"] = now.isoformat()
                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "signal_error",
                    "msg": str(e),
                })

    # ===== 每日收盘后自动回测 =====
    def _run_daily_backtest(self, now: datetime):
        """
        每个交易日收盘后（15:10 触发）自动运行回测
        - 默认使用「次日14:30换仓」策略
        - 回测区间：最近 60 个交易日
        - 结果保存到 data/backtest/ 并更新调度状态
        """
        with self.status_lock:
            self.status["last_backtest_status"] = "running"
            self.status["last_backtest_msg"] = "回测进行中..."
            self.status["last_update_time"] = now.isoformat()

        self._push_history({
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "action": "backtest_start",
        })

        try:
            # 延迟导入避免循环依赖
            from backtester import ETFBacktester
            from config import BACKTEST_CFG

            bt = ETFBacktester()
            # 应用次日换仓策略
            bt.config.strategy_mode = getattr(BACKTEST_CFG, "strategy_mode", "next_day_rotation")
            bt.config.execution_price = getattr(BACKTEST_CFG, "execution_price", "close")
            bt.config.max_positions = BACKTEST_CFG.max_positions
            bt.config.stop_loss = BACKTEST_CFG.stop_loss
            bt.config.take_profit = BACKTEST_CFG.take_profit

            # 回测区间：最近 60 个交易日
            from datetime import timedelta
            end_date = now.strftime("%Y-%m-%d")
            start_dt = now - timedelta(days=90)  # 多预留 30 天确保有足够交易日
            start_date = start_dt.strftime("%Y-%m-%d")

            logger.info(f"开始每日自动回测: {start_date} ~ {end_date} 模式={bt.config.strategy_mode}")

            result = bt.run(start_date=start_date, end_date=end_date)

            # 保存结果
            filename = f"auto_{now.strftime('%Y%m%d_%H%M%S')}"
            save_path = bt.save_result(result, filename=filename)

            # 提取核心指标摘要
            summary = {
                "start_date": result.start_date,
                "end_date": result.end_date,
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "win_rate": result.win_rate,
                "total_trades": result.total_trades,
                "profit_factor": result.profit_factor if result.profit_factor != float('inf') else 999.99,
                "alpha": result.alpha,
                "beta": result.beta,
                "baseline_return": result.baseline_return,
                "excess_return": result.excess_return,
                "strategy_mode": bt.config.strategy_mode,
                "report_file": str(save_path),
            }

            with self.status_lock:
                self.status["today_backtest_done"] = True
                self.status["last_backtest_time"] = now.isoformat()
                self.status["last_backtest_status"] = "success"
                self.status["last_backtest_msg"] = (
                    f"自动回测成功: 总收益 {result.total_return:+.2f}%，"
                    f"夏普 {result.sharpe_ratio:.2f}，最大回撤 {result.max_drawdown:.2f}%，"
                    f"胜率 {result.win_rate:.1f}%"
                )
                self.status["last_backtest_summary"] = summary
                self.status["last_update_time"] = now.isoformat()
                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "backtest_done",
                    "total_return": result.total_return,
                    "sharpe": result.sharpe_ratio,
                    "report": str(save_path),
                })

            self._persist_status()
            logger.info(f"每日自动回测完成: {self.status['last_backtest_msg']}")

        except Exception as e:
            logger.error(f"每日自动回测失败: {e}", exc_info=True)
            with self.status_lock:
                self.status["today_backtest_done"] = True  # 标记完成避免反复失败重试
                self.status["last_backtest_time"] = now.isoformat()
                self.status["last_backtest_status"] = "failed"
                self.status["last_backtest_msg"] = f"自动回测失败: {e}"
                self.status["last_update_time"] = now.isoformat()
                self._push_history({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "backtest_error",
                    "msg": str(e),
                })
            self._persist_status()

    def run_backtest_manually(self, now: Optional[datetime] = None) -> Dict:
        """供 Streamlit 调用的手动触发回测入口"""
        if now is None:
            now = datetime.now()
        self._run_daily_backtest(now)
        return self.get_status()

    # ===== 历史数据访问 =====
    def list_today_snapshots(self) -> List[Dict]:
        """列出今日所有采集快照（按时间升序）"""
        cache_dir = DATA_DIR / "fundflow_cache"
        today_str = datetime.now().strftime("%Y%m%d")
        files = sorted(cache_dir.glob(f"{today_str}_*.json"))
        result = []
        for f in files:
            try:
                df = pd.read_json(f)
                if df.empty:
                    continue
                ts_str = f.name[:15]  # YYYYMMDD_HHMMSS
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                result.append({
                    "file": str(f),
                    "name": f.name,
                    "timestamp": ts,
                    "industry_count": len(df),
                    "net_total": float(df['净额'].sum()) if '净额' in df.columns else 0,
                    "is_snapshot": "_snapshot" in f.name,
                })
            except Exception:
                continue
        return result


# 模块级单例访问
def get_scheduler() -> StreamlitScheduler:
    return StreamlitScheduler()
