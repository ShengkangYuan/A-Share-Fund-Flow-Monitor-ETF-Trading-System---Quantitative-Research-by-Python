"""
独立调度器入口 - 在 Streamlit 关闭后仍能持续运行

使用方式：
1. 前台运行（调试用）：python scheduler_runner.py
2. 后台运行（推荐）：pythonw scheduler_runner.py
3. 通过 启动调度器.bat 一键启动（后台无窗口）

特性：
- 写入 PID 锁文件，避免与 Streamlit 内嵌线程冲突
- 接收 Ctrl+C / 关闭信号时优雅退出
- 进程意外终止时 PID 文件会被下次启动时检测到并清理
"""

import sys
import time
import logging
from datetime import datetime

from streamlit_scheduler import StreamlitScheduler, SCHEDULER_PID_FILE, SCHEDULER_LOG
from config import DATA_DIR

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "scheduler.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger("SchedulerRunner")


def cleanup_stale_pid():
    """清理失效的 PID 文件（进程已不存在时）"""
    try:
        if not SCHEDULER_PID_FILE.exists():
            return
        if not StreamlitScheduler.is_standalone_running():
            # 文件存在但进程已死，清理
            SCHEDULER_PID_FILE.unlink()
            logger.info("清理失效的 PID 文件")
    except Exception as e:
        logger.warning(f"清理 PID 文件失败: {e}")


def main():
    print("=" * 60)
    print("  A股资金流独立调度器")
    print("  - 交易时段每5分钟自动采集")
    print("  - 14:30 自动记录买入信号")
    print("  - 15:10 后自动运行回测")
    print("  - Ctrl+C 退出")
    print("=" * 60)

    cleanup_stale_pid()

    # 检查是否已有独立调度器在运行
    if StreamlitScheduler.is_standalone_running():
        print("⚠️ 已有独立调度器在运行，避免重复启动")
        print(f"   PID 文件: {SCHEDULER_PID_FILE}")
        sys.exit(1)

    sched = StreamlitScheduler()

    # 注册信号处理（优雅退出）
    def _on_exit(signum, frame):
        print(f"\n[{datetime.now():%H:%M:%S}] 收到退出信号，正在停止...")
        sched.stop()
        print("已停止")
        sys.exit(0)

    import signal as _signal
    _signal.signal(_signal.SIGINT, _on_exit)   # Ctrl+C
    _signal.signal(_signal.SIGTERM, _on_exit)  # kill

    # 以独立模式启动
    ok = sched.start(standalone=True)
    if not ok:
        print("❌ 调度器启动失败")
        sys.exit(1)

    print(f"\n[{datetime.now():%H:%M:%S}] ✅ 独立调度器已启动，PID={__import__('os').getpid()}")
    print(f"   日志文件: {DATA_DIR / 'scheduler.log'}")
    print(f"   状态文件: {SCHEDULER_LOG}")
    print(f"   PID 文件: {SCHEDULER_PID_FILE}")
    print(f"\n保持运行中...（Ctrl+C 退出）\n")

    # 主循环保持进程存活
    try:
        while True:
            time.sleep(60)
            # 每分钟打印一次状态
            status = sched.get_status()
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                  f"运行中 | 今日采集={status['today_fetch_count']} "
                  f"| 14:30信号={'已记录' if status['today_signal_recorded'] else '未记录'} "
                  f"| 自动回测={'已完成' if status['today_backtest_done'] else '待执行'}")
    except KeyboardInterrupt:
        _on_exit(None, None)


if __name__ == "__main__":
    main()
