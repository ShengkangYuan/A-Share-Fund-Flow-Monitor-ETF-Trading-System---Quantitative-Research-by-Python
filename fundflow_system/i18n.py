"""
中英双语文案字典 / Bilingual (English / 中文) text dictionary

- 默认语言：英文 (en)，可在侧边栏切换中文 (zh)
- 界面层所有静态文案统一通过 t("key") 读取
- 金额（亿）、相对时间、月份、交易原因等带数据层中文的内容，
  通过本模块的辅助函数在展示层翻译，不改动底层数据
"""

import re

# ============================================================
# 语言状态 / language state（每次 Streamlit rerun 由 dashboard 设置）
# ============================================================
_current_lang = "en"


def set_lang(lang: str) -> None:
    global _current_lang
    _current_lang = "zh" if lang == "zh" else "en"


def get_lang() -> str:
    return _current_lang


# ============================================================
# 文案字典 / string table
# ============================================================
STRINGS = {
    "en": {
        # ---- 通用 / generic ----
        "app_title": "A-Share Fund Flow Monitor & ETF Trading System",
        "app_subtitle": "Real-time fund-flow selection · Forced rotation at 14:30 the next trading day · Bar Chart Race visualization",
        "footer": "A-Share Fund Flow Monitor & ETF Trading System · Data source: Eastmoney · For educational purposes only, not investment advice",
        "lang_label": "Language",
        "refresh": "Refresh",
        "download": "Download",
        "export": "Export",
        "none_dash": "—",
        "seconds_short": "s",
        "minutes_short": "m",
        "hours_short": "h",
        "days_word": "d",
        "days_full": "days",

        # ---- 市场状态 / market status ----
        "status_trading": "Trading",
        "status_premarket": "Pre-market",
        "status_closed": "Closed",
        "status_weekend": "Market closed",

        # ---- Hero 顶部 / header badges ----
        "sched_standalone_badge": "Standalone scheduler running",
        "sched_embedded_badge": "Embedded mode",
        "data_updated": "Updated {ago}",
        "last_update": "Last update {time}",

        # ---- 侧边栏 / sidebar ----
        "sidebar_title": "Settings",
        "sidebar_subtitle": "Backtest & data fetching",
        "theme_caption_dark": "Dark mode (Ctrl+Shift+D to toggle)",
        "theme_caption_light": "Light mode (Ctrl+Shift+D to toggle)",
        "grp_cost": "Transaction costs",
        "commission": "Commission (%)",
        "slippage": "Slippage (%)",
        "stamp_tax": "Stamp duty (%)",
        "grp_risk": "Risk controls",
        "stop_loss": "Stop loss (%)",
        "take_profit": "Take profit (%)",
        "grp_strategy": "Strategy parameters",
        "max_positions": "Max positions",
        "position_size": "Position size",
        "buy_threshold": "Buy score threshold",
        "rebalance_time": "Rebalance time",
        "strategy_mode": "Strategy mode",
        "mode_next_day": "Next-day 14:30 forced rotation",
        "mode_continuous": "Continuous holding (legacy)",
        "execution_price": "Execution price",
        "exec_close": "Close price (~14:30)",
        "exec_open": "Next-day open price",
        "grp_fetch": "Fetching",
        "refresh_interval": "Auto-refresh interval (s)",
        "reset_defaults": "Reset to defaults",
        "toast_reset": "Default parameters restored",
        "grp_shortcuts": "Keyboard shortcuts",
        "shortcut_fetch": "Fetch once now",
        "shortcut_backtest": "Run backtest",
        "shortcut_dark": "Toggle dark mode",
        "shortcut_f5": "Refresh the page",
        "data_dirs": "Data directories",
        "root_dir": "Root",
        "data_dir": "Data",

        # ---- Tabs ----
        "tab_realtime": "Live Fund Flow",
        "tab_visual": "Dynamic Visualization",
        "tab_video": "Video Library",
        "tab_backtest": "ETF Backtest",

        # ---- 实时页 / real-time tab ----
        "rt_title": "A-Share Fund Flow Monitor",
        "rt_scheduler": "Live fetch scheduler",
        "rt_standalone_on": "**Standalone scheduler running** — data fetching continues even after this page is closed",
        "rt_standalone_off": "**Embedded mode** — closing this page stops automatic fetching. Run `python scheduler_runner.py` (or double-click `start_scheduler.bat` on Windows) for standalone mode",
        "health_healthy": "Healthy",
        "health_hb_stale_main": "Heartbeat OK, main loop unresponsive",
        "health_hb_timeout": "Heartbeat timeout (scheduler may be hung)",
        "health_normal": "Normal",
        "health_running_no_main": "Running, main loop unresponsive",
        "health_not_started": "Not started",
        "m_sched_mode": "Scheduler mode",
        "m_mode_standalone": "Standalone process",
        "m_mode_embedded": "Embedded thread",
        "m_mode_help": "Standalone: keeps running after the page closes / Embedded: stops with the page",
        "m_health": "Health",
        "m_health_help": "Heartbeat freshness + thread liveness",
        "m_today_fetches": "Fetches today",
        "m_signal_1430": "14:30 signal",
        "m_signal_yes": "Recorded",
        "m_signal_no": "Not recorded",
        "m_signal_help": "Auto-records the day's buy signals (top 5 ETFs) in the 14:28-14:33 window",
        "m_last_fetch": "Last fetch",
        "m_last_fetch_n": "Industries fetched",
        "diag_title": "Scheduler diagnostics (heartbeat / crashes / history)",
        "diag_last_hb": "Last heartbeat",
        "diag_fresh": "fresh",
        "diag_timeout": "timeout",
        "diag_no_hb": "no heartbeat",
        "diag_thread": "Main-loop thread",
        "diag_alive": "Alive",
        "diag_dead": "Not alive",
        "diag_watchdog": "Watchdog restarts",
        "diag_watchdog_help": "Auto-restarts after the main loop crashes",
        "diag_hb_total": "Total heartbeats",
        "diag_last_crash": "Last crash ({time}): {msg}",
        "diag_history_title": "Recent activity (latest 10)",
        "col_time": "Time",
        "col_action": "Action",
        "col_detail": "Detail",
        "no_history": "No history yet",
        "signal_today_title": "Today's 14:30 buy signals – Top 5 ETFs (recorded at {time})",
        "last_auto_update": "Last automatic update: {time}",
        "btn_pause_fetch": "Pause auto-fetch",
        "btn_start_fetch": "Start auto-fetch",
        "btn_pause_fetch_help": "In standalone mode, press Ctrl+C in the scheduler console (or stop the background process in Task Manager)",
        "toast_fetch_paused": "Auto-fetch paused",
        "toast_fetch_started": "Auto-fetch started",
        "btn_manual_fetch": "Fetch now",
        "spinner_fetching": "Fetching data...",
        "toast_fetch_ok": "Manual fetch succeeded",
        "manual_fetch_failed": "Manual fetch failed: {err}",
        "btn_refresh_page": "Refresh page",
        "sched_failed_warn": "Could not read scheduler status (automatic fetching may still run in the background): {err}",
        "auto_refresh": "Auto-refresh page",
        "auto_refresh_help": "Refresh automatically every {n} s to see the latest data",
        "spinner_loading_flow": "Loading fund flow data...",
        "rt_no_data": "No cached data yet. Click \"Fetch now\" above, or wait for the background scheduler during trading hours.",
        "kpi_net": "Market-wide net inflow",
        "kpi_inflow": "Inflow",
        "kpi_outflow": "Outflow",
        "kpi_inflow_ratio": "Industries with net inflow",
        "btn_show_top20": "Show TOP 20",
        "btn_collapse_top10": "Collapse to TOP 10",
        "showing_top": "Showing TOP{n} ({total} industries)",
        "industry_top_title": "Industry fund flow ranking – TOP{n}",
        "chart_net_flow": "Net inflow ({unit})",
        "chart_industry": "Industry",
        "chart_rank_title": "Industry fund flow ranking – TOP{n}",
        "etf_alert_title": "ETF score alerts",
        "no_etf_mapping": "No ETF mapping data, please check the industry-ETF mapping config",
        "found_buy": "{n} ETF(s) meet the buy condition (score ≥ {threshold})",
        "found_near": "{n} ETF(s) are close to the threshold (60–{threshold})",
        "found_below": "{n} ETF(s) below the buy threshold (score < 60), highlighted in yellow",
        "st_buy": "Meets buy threshold",
        "st_near": "Below buy threshold",
        "st_low": "Low score",
        "col_code": "Code",
        "col_name": "Name",
        "col_netflow": "Net inflow ({unit})",
        "col_change": "Change (%)",
        "col_score": "Score",
        "col_status": "Status",
        "export_etf_scores": "Export ETF scores (CSV)",
        "btn_record_signal": "Record 14:30 buy signal",
        "signal_saved": "14:30 buy signal saved to {path}",
        "signal_picked": "Selected 5 ETFs: {names}",
        "signal_save_failed": "Failed to record signal: {err}",
        "etf_score_failed": "ETF scoring failed: {err}",
        "hist_signals_title": "Historical 14:30 stock-pick signals",
        "select_date": "Select date",
        "record_time": "Recorded at",
        "total_industries": "Industries",
        "total_etfs": "ETFs",
        "no_signals": "No 14:30 signal records yet",
        "no_signal_dir": "Signal directory does not exist; record a 14:30 signal first",
        "flow_detail_title": "Industry fund flow details",
        "col_inflow_amt": "Inflow ({unit})",
        "col_outflow_amt": "Outflow ({unit})",
        "col_net_amt": "Net ({unit})",
        "col_change_pct": "Change (%)",
        "sort_by": "Sort by",
        "sort_net": "Net",
        "sort_inflow": "Inflow",
        "sort_outflow": "Outflow",
        "ascending": "Ascending",
        "export_detail": "Export details (CSV)",
        "trend_title": "Fund flow trend",
        "trace_net_inflow": "Net inflow",
        "chart_trend_title": "Real-time fund flow trend",
        "axis_time": "Time",
        "axis_netflow_yi": "Net inflow (¥100M)",
        "data_fetch_failed": "Failed to load data: {err}",

        # ---- 回测页 / backtest tab ----
        "bt_title": "ETF Fund Flow Backtester",
        "bt_daily_title": "Daily automatic backtest",
        "bt_today": "Auto backtest today",
        "bt_done": "Done",
        "bt_pending": "Pending",
        "bt_today_help": "Runs automatically after 15:10 on trading days (last 60 trading days, next-day 14:30 rotation)",
        "bt_last_time": "Last backtest",
        "bt_last_update": "Latest automatic update",
        "bt_last_update_help": "Latest update across all automatic jobs (fetch / signal / backtest)",
        "bt_total_return": "Total return",
        "bt_sharpe": "Sharpe ratio",
        "bt_full_metrics": "Show full metrics of the latest automatic backtest",
        "bt_strategy_mode": "Strategy mode",
        "bt_period": "Period",
        "bt_annualized": "Annualized return",
        "bt_max_dd": "Max drawdown",
        "bt_win_rate": "Win rate",
        "bt_profit_factor": "Profit factor",
        "bt_baseline": "Baseline return",
        "bt_excess": "Excess return",
        "bt_report_path": "Report path: {path}",
        "btn_run_auto_bt": "Run automatic backtest now",
        "btn_run_auto_bt_help": "Triggers the same backtest as the scheduler (last 60 trading days)",
        "spinner_auto_bt": "Running automatic backtest, please wait (1–3 minutes)...",
        "toast_auto_bt_done": "Automatic backtest finished",
        "auto_bt_failed": "Automatic backtest failed: {err}",
        "auto_bt_ok_msg": "Auto backtest succeeded: total return {total}%, Sharpe {sharpe}, max drawdown {dd}%, win rate {win}%",
        "err_not_enough_days": "not enough valid data days: only {n} found",
        "fetch_standalone": "Standalone scheduler is running (no embedded thread needed)",
        "sched_error_msg": "Scheduler error: {err}",
        "fetch_ok_msg": "Fetch succeeded{shot}, {n} industries total",
        "snapshot_tag": " [14:30 snapshot]",
        "fetch_failed_msg": "Fetch failed: {err}",
        "btn_reset_bt_flag": "Reset today's backtest flag",
        "btn_reset_bt_help": "Sets today_backtest_done to False so the scheduler runs again after 15:10",
        "toast_reset_bt": "Reset; it will run again automatically after 15:10",
        "bt_sched_failed": "Could not read scheduler status: {err}",
        "bt_manual_title": "Manual backtest",
        "bt_start_date": "Start date",
        "bt_start_help": "Backtest start date; historical fund-flow data must exist",
        "bt_end_date": "End date",
        "bt_end_help": "Backtest end date",
        "bt_backfill_title": "Backfill historical data from Eastmoney",
        "bt_backfill_desc": "If the backtest reports \"not enough valid dates\", click below to pull per-industry fund-flow history from Eastmoney and rebuild the daily cross-section cache.",
        "bt_backfill_days": "Days to backfill",
        "btn_backfill": "Backfill now",
        "bt_backfill_ok": "Backfill complete: {n} trading days rebuilt",
        "bt_backfill_failed": "Backfill failed: {err}",
        "bt_status_preparing": "Preparing backtest...",
        "btn_start_bt": "Start backtest",
        "log_read_signals": "1) Reading historical fund-flow signals...",
        "log_no_history": "No historical fund-flow data found; run data fetching first to build up history",
        "log_not_enough_dates": "Not enough valid dates: only {n} day(s); adjust the date range",
        "log_got_days": "Loaded {n} day(s) of fund-flow data",
        "log_download_etf": "2) Downloading ETF daily data...",
        "log_downloaded_n": "Downloaded {i}/{n} ETFs",
        "log_bt_timeout": "Backtest timed out (>120 s); shorten the date range",
        "log_no_prices": "No ETF price data was retrieved",
        "log_got_prices": "Price data for {n} ETF(s) retrieved",
        "log_running": "3) Running strategy backtest...",
        "log_strategy_done": "Strategy backtest finished",
        "log_metrics": "4) Computing performance metrics and charts...",
        "log_done": "Backtest complete!",
        "log_failed": "Backtest failed: {err}",
        "bt_status_running": "Backtest running...",
        "bt_status_failed": "Backtest failed",
        "bt_status_done": "Backtest complete",
        "perf_title": "Performance overview",
        "pm_final_capital": "Final capital",
        "pm_total_return": "Total return",
        "pm_annualized": "Annualized",
        "pm_sharpe": "Sharpe",
        "pm_max_dd": "Max drawdown",
        "pm_win_rate": "Win rate",
        "pm_total_trades": "Total trades",
        "grp_return": "Return metrics",
        "pm_excess_csi300": "Excess return vs CSI 300",
        "pm_csi300": "CSI 300 return",
        "pm_final_funds": "Final equity",
        "grp_risk": "Risk metrics",
        "pm_sortino": "Sortino ratio",
        "pm_calmar": "Calmar ratio",
        "pm_vol": "Annualized volatility",
        "pm_down_vol": "Downside volatility",
        "grp_trade_stats": "Trade statistics",
        "pm_avg_win": "Average win",
        "pm_avg_loss": "Average loss",
        "pm_max_win": "Largest single win",
        "pm_max_loss": "Largest single loss",
        "pm_streaks": "Max win/loss streak",
        "pm_avg_holding": "Avg holding period",
        "grp_benchmark": "Benchmark comparison",
        "pm_alpha": "Alpha (annualized)",
        "pm_beta": "Beta",
        "pm_info_ratio": "Information ratio",
        "pm_tracking_error": "Tracking error",
        "pm_upside_capture": "Upside capture",
        "pm_downside_capture": "Downside capture",
        "pm_capital_util": "Capital utilization",
        "dd_start": "Drawdown start",
        "dd_trough": "Drawdown trough",
        "dd_duration": "Drawdown duration",
        "dd_recovery": "Recovery period",
        "dd_not_recovered": "Not recovered",
        "dd_longest_hold": "Longest holding period",
        "btn_save_report": "Save full report",
        "report_saved": "Report saved: {path}",
        "save_failed": "Save failed: {err}",
        "export_equity": "Export equity curve (CSV)",
        "export_daily_stats": "Export daily stats (CSV)",
        "compare_title": "Comparison with historical backtests",
        "cmp_file": "Run",
        "cmp_current": "Current",
        "cmp_time": "Time",
        "cmp_period": "Period",
        "cmp_strategy": "Strategy",
        "cmp_total": "Total (%)",
        "cmp_annual": "Annual. (%)",
        "cmp_sharpe": "Sharpe",
        "cmp_dd": "DD (%)",
        "cmp_win": "Win (%)",
        "cmp_caption": "Red bold = best value for that metric (in A-shares red = up, so red = better) | Blue = current run",
        "cmp_chart_title": "Total return of historical backtests",
        "axis_bt_time": "Backtest time",
        "axis_total_return": "Total return (%)",
        "cmp_render_failed": "Comparison chart failed to render: {err}",
        "cmp_not_enough": "Not enough historical backtests to compare yet. Run more backtests and the comparison table appears automatically.",
        "cmp_load_failed": "Failed to load historical comparison: {err}",
        "equity_title": "Strategy equity curve vs CSI 300 benchmark",
        "trace_equity": "Strategy equity",
        "trace_baseline": "CSI 300 benchmark",
        "trace_dd_start": "Drawdown start",
        "trace_peak": "Peak",
        "trace_dd_trough": "Drawdown trough",
        "trace_low": "Trough",
        "anno_dd_zone": "Max-drawdown zone {pct}%",
        "chart_equity_title": "Strategy return curve comparison",
        "axis_date": "Date",
        "axis_total_assets": "Total assets",
        "dd_analysis_title": "Drawdown analysis",
        "trace_drawdown": "Drawdown",
        "chart_dd_title": "Drawdown curve (underwater plot)",
        "axis_dd_pct": "Drawdown (%)",
        "hover_date": "Date: {x}",
        "rolling_title": "Rolling return and volatility",
        "trace_rolling_ret": "20-day rolling return (%)",
        "trace_rolling_vol": "20-day rolling annualized volatility (%)",
        "chart_rolling_title": "20-day rolling return and volatility",
        "axis_rolling_ret": "Rolling return (%)",
        "axis_rolling_vol": "Annualized volatility (%)",
        "yearly_title": "Annual returns",
        "trace_yearly": "Annual return",
        "chart_yearly_title": "Annual returns",
        "axis_year": "Year",
        "axis_return_pct": "Return (%)",
        "heatmap_title": "Monthly return heatmap",
        "axis_month": "Month",
        "axis_year_only": "Year",
        "color_monthly_ret": "Monthly return (%)",
        "monthly_win_title": "Monthly win-rate statistics",
        "m_profit_months": "Profitable months",
        "m_loss_months": "Losing months",
        "m_best_month": "Best month",
        "m_worst_month": "Worst month",
        "trades_title": "Trade details",
        "tr_col_date": "Date",
        "tr_col_dir": "Side",
        "tr_col_code": "ETF code",
        "tr_col_name": "ETF name",
        "tr_col_price": "Price",
        "tr_col_shares": "Shares",
        "tr_col_amount": "Amount",
        "tr_col_pnl": "P&L",
        "tr_col_pnl_pct": "P&L (%)",
        "tr_col_reason": "Reason",
        "tr_col_hold_days": "Holding days",
        "side_buy": "Buy",
        "side_sell": "Sell",
        "export_trades": "Export trade details (CSV)",
        "batch_title": "Batch grid backtest",
        "btn_run_batch": "Run batch backtest",
        "batch_timeout": "Batch backtest timed out (>300 s)",
        "batch_running": "Backtesting: {pos} positions / {score} score ({i}/{n})",
        "batch_combo_name": "{pos} pos / {score}",
        "batch_combo_failed": "Combination [{pos} pos / {score}] failed: {err}",
        "batch_done": "Batch backtest complete!",
        "batch_chart_title": "Batch backtest comparison (normalized)",
        "batch_col_combo": "Parameter set",
        "batch_col_total": "Total return (%)",
        "batch_col_annual": "Annualized (%)",
        "batch_col_dd": "Max drawdown (%)",
        "batch_col_sharpe": "Sharpe",
        "batch_col_win": "Win rate (%)",
        "batch_col_trades": "Trades",
        "batch_table_title": "Batch backtest performance table",
        "export_batch": "Export batch results (CSV)",

        # ---- 视频页 / video tab ----
        "vid_title": "Fund Flow Video Manager",
        "btn_make_video": "Generate video",
        "vid_few_frames": "Not enough frames; at least 2 are required",
        "vid_generating": "Generating video… {pct}%",
        "vid_done": "Video generated: {path}",
        "vid_failed": "Generation failed: {err}",
        "btn_clear_frames": "Clear frame cache",
        "vid_clear_warn": "{n} frame(s) cached today will be lost if you clear!",
        "btn_confirm_clear": "Confirm clear",
        "vid_frames_cleared": "Frame cache cleared",
        "vid_list_title": "Video files",
        "vid_filter_date": "Filter by date",
        "batch_ops": "Batch actions",
        "btn_select_all": "Select all",
        "btn_deselect_all": "Deselect all",
        "btn_batch_delete": "Delete selected ({n})",
        "vid_deleted_n": "Deleted {n} video file(s)",
        "vid_selected_n": "{n} file(s) selected",
        "vid_none_selected": "No file selected",
        "vid_table_title": "Video files",
        "col_select": "Select",
        "col_filename": "Filename",
        "col_size": "Size",
        "col_type": "Type",
        "col_modified": "Modified",
        "single_preview": "Single video preview",
        "select_video_preview": "Select a video to preview",
        "vid_preview_title": "Video preview",
        "vid_cannot_load": "Could not load the video",
        "vid_info_title": "File information",
        "vid_file_name": "Filename",
        "vid_size": "Size",
        "vid_type": "Type",
        "vid_modified": "Modified",
        "btn_download_video": "Download this video",
        "vid_read_failed": "Failed to read video: {err}",
        "btn_delete_file": "Delete this file",
        "vid_file_deleted": "File deleted",
        "vid_delete_failed": "Deletion failed",
        "batch_download_title": "Batch download",
        "btn_zip_download": "Download {n} video(s) as ZIP",
        "btn_download_zip": "Download ZIP",
        "vid_zip_hint": "No file selected; tick videos in the table above first",
        "btn_clear_all_videos": "Delete all videos",
        "btn_confirm_clear_all": "Confirm delete everything",
        "vid_no_files": "No video files yet; generate one first",
        "vid_frame_status": "Current frame cache",
        "vid_total_frames": "Total cached frames",
        "vid_today_frames": "Frames cached today",

        # ---- 动态可视化页 / dynamic visualization tab ----
        "dv_title": "Dynamic Visualization (Bar Chart Race)",
        "dv_caption": "Built from 5-minute snapshots; shows how industry fund-flow rankings and ETF scores evolve in real time",
        "dv_bg_scheduler": "Background scheduler",
        "dv_standalone_on": "**Standalone process mode** — keeps running after the page is closed",
        "m_run_status": "Status",
        "st_running": "Running",
        "st_stopped": "Stopped",
        "m_health2": "Health",
        "hb_ago": "Heartbeat {n} s ago",
        "hb_none": "No heartbeat",
        "m_watchdog": "Watchdog restarts",
        "dv_last_crash": "Last crash: {time} {msg}",
        "btn_pause_collect": "Pause fetching",
        "btn_start_collect": "Start fetching",
        "btn_collect_help": "In standalone mode, use the scheduler start/stop scripts",
        "btn_fetch_once": "Fetch once now",
        "btn_clear_preview": "Clear preview cache",
        "fetch_history_title": "Fetch history (latest {n})",
        "dv_sched_failed": "Could not read scheduler status: {err}",
        "dv_viz_load_failed": "Failed to load visualization module: {err}",
        "dv_no_cache": "No fund-flow cache data yet. Fetch data on the Live Fund Flow tab first.",
        "dv_select_date": "Select date",
        "dv_snap_limit": "Snapshots to load",
        "dv_top_n": "Rows to show",
        "btn_generate": "Generate charts",
        "dv_loading_snaps": "Loading snapshots...",
        "dv_loaded": "Loaded: {rows} industry rows, {points} time point(s), {scores} ETF score record(s)",
        "dv_click_hint": "Click \"Generate charts\" to load and play the Bar Chart Race animation",
        "dv_no_snaps_date": "No snapshots available for this date",
        "m_snapshots": "Snapshots",
        "m_time_span": "Time span",
        "m_industries": "Industries",
        "m_latest_net": "Latest net inflow",
        "dv_industry_race": "Industry fund flow Bar Chart Race",
        "dv_etf_race": "ETF score Bar Chart Race",
        "dv_close_line_title": "Intraday cumulative fund flow line chart",
        "dv_close_line_caption": "Each fetch adds one timestamp; cumulative net inflow of the TOP N industries extends over time (like a live ECG)",
        "dv_line_n": "Industries in line chart",
        "dv_mainflow_title": "Intraday main-fund-flow animated bar chart",
        "dv_mainflow_caption": "Filtered by trading session; TOP N industries by main net inflow, animated over time",
        "dv_session": "Trading session",
        "sess_afternoon": "Afternoon 13:00–15:00",
        "sess_morning": "Morning 09:30–11:30",
        "sess_all": "All day",
        "dv_bar_n": "Industries in bar chart",
        "dv_net_trend": "Market-wide net inflow trend",
        "dv_up_down": "Advancing vs declining industries",
        "dv_in_out": "Inflow vs outflow",
        "dv_make_video_title": "Generate an animated video",
        "dv_fps": "Frame rate",
        "btn_gen_race_video": "Generate Bar Chart Race video",
        "spinner_gen_video": "Generating animated video...",
        "vid_generated": "Video generated",
        "btn_download_video2": "Download video",
        "vid_gen_failed": "Video generation failed: {err}",

        # ---- 动态图表（dynamic_visualizer）/ chart strings ----
        "chg_netflow_yi": "Net inflow (¥100M)",
        "chg_score": "Score",
        "chg_etf": "ETF",
        "chg_time": "Time",
        "race_industry_title": "Industry fund flow Bar Chart Race – TOP{n}",
        "race_etf_title": "ETF score Bar Chart Race – TOP{n}",
        "trend_live_title": "Market-wide net inflow live trend",
        "up": "Advancing",
        "down": "Declining",
        "chart_updown_title": "Advancing vs declining industries",
        "axis_count": "Count",
        "inflow_word": "Inflow",
        "outflow_word": "Outflow",
        "chart_inout_title": "Fund inflow vs outflow",
        "axis_amount_yi": "Amount (¥100M)",
        "close_line_title": "Intraday cumulative fund flow – TOP{n} industries",
        "axis_fetch_time": "Fetch time",
        "axis_cum_net": "Cumulative net inflow (¥100M)",
        "mainflow_empty_title": "Intraday {sess} main fund flow – no data",
        "mainflow_title": "Intraday {sess} main fund flow – TOP{n}",
        "colorbar_net": "Net (¥100M)",
        "colorbar_score": "Score",
        "netflow_trace": "Net inflow",
        "btn_play": "Play",
        "btn_pause_anim": "Pause",
        "slider_time_prefix": "Time: ",
        "hover_cum_net": "Time: %{x}<br>Cum net inflow: %{y:.1f} (¥100M)",
        "no_snap_in_session": "No snapshots in the selected session",

        # ---- 主题 / theme ----
        "theme_dark": "Dark",
        "theme_light": "Light",

        # ---- 快捷键触发 / shortcut toasts ----
        "spinner_shortcut_fetch": "Running manual fetch...",
        "toast_sc_fetch_ok": "Shortcut: manual fetch succeeded",
        "sc_fetch_failed": "Shortcut fetch failed: {err}",
        "toast_sc_theme": "Switched to {mode} mode",
        "spinner_sc_bt": "Running backtest, please wait...",
        "toast_sc_bt_ok": "Shortcut: automatic backtest finished",
        "sc_bt_failed": "Shortcut backtest failed: {err}",
        "sched_start_failed": "Failed to start scheduler: {err}",
    },

    "zh": {
        # ---- 通用 ----
        "app_title": "A股资金流动态检测与ETF交易系统",
        "app_subtitle": "基于实时资金流的智能选股 · 次日14:30强制换仓策略 · Bar Chart Race 可视化",
        "footer": "A股资金流动态检测与ETF交易系统 · 数据来源：东方财富 · 仅供学习研究，不构成投资建议",
        "lang_label": "语言",
        "refresh": "刷新",
        "download": "下载",
        "export": "导出",
        "none_dash": "—",
        "seconds_short": "秒",
        "minutes_short": "分钟",
        "hours_short": "小时",
        "days_word": "天",
        "days_full": "天",

        # ---- 市场状态 ----
        "status_trading": "交易中",
        "status_premarket": "盘前",
        "status_closed": "已收盘",
        "status_weekend": "休市",

        # ---- Hero ----
        "sched_standalone_badge": "独立调度器运行中",
        "sched_embedded_badge": "内嵌模式",
        "data_updated": "数据更新于 {ago}",
        "last_update": "最近更新 {time}",

        # ---- 侧边栏 ----
        "sidebar_title": "系统配置",
        "sidebar_subtitle": "回测与采集参数",
        "theme_caption_dark": "当前：暗黑模式（Ctrl+Shift+D 切换）",
        "theme_caption_light": "当前：明亮模式（Ctrl+Shift+D 切换）",
        "grp_cost": "交易成本",
        "commission": "佣金费率 (%)",
        "slippage": "滑点率 (%)",
        "stamp_tax": "印花税率 (%)",
        "grp_risk": "风控参数",
        "stop_loss": "止损 (%)",
        "take_profit": "止盈 (%)",
        "grp_strategy": "策略参数",
        "max_positions": "最大持仓数",
        "position_size": "单仓位占比",
        "buy_threshold": "买入阈值",
        "rebalance_time": "调仓时间",
        "strategy_mode": "策略模式",
        "mode_next_day": "次日14:30强制换仓",
        "mode_continuous": "持续持仓（旧版）",
        "execution_price": "执行价位",
        "exec_close": "收盘价（≈14:30）",
        "exec_open": "次日开盘价",
        "grp_fetch": "采集设置",
        "refresh_interval": "自动刷新间隔 (秒)",
        "reset_defaults": "恢复默认参数",
        "toast_reset": "已恢复默认参数",
        "grp_shortcuts": "键盘快捷键",
        "shortcut_fetch": "手动采集一次",
        "shortcut_backtest": "运行回测",
        "shortcut_dark": "切换暗黑模式",
        "shortcut_f5": "刷新页面",
        "data_dirs": "数据目录",
        "root_dir": "根目录",
        "data_dir": "数据目录",

        # ---- Tabs ----
        "tab_realtime": "实时资金流",
        "tab_visual": "动态可视化",
        "tab_video": "视频管理",
        "tab_backtest": "ETF回测",

        # ---- 实时页 ----
        "rt_title": "A股资金流动态监控",
        "rt_scheduler": "实时采集调度器",
        "rt_standalone_on": "**独立调度器运行中** — 即使关闭本网页，自动采集仍会持续",
        "rt_standalone_off": "**内嵌模式** — 关闭本网页将停止自动采集。建议运行 `启动调度器.bat` 启用独立模式",
        "health_healthy": "健康",
        "health_hb_stale_main": "心跳正常，主循环未响应",
        "health_hb_timeout": "心跳超时（调度器可能挂死）",
        "health_normal": "正常",
        "health_running_no_main": "运行中，主循环未响应",
        "health_not_started": "未启动",
        "m_sched_mode": "调度模式",
        "m_mode_standalone": "独立进程",
        "m_mode_embedded": "内嵌线程",
        "m_mode_help": "独立进程：关闭网页仍持续运行 / 内嵌线程：关闭网页即停止",
        "m_health": "健康状态",
        "m_health_help": "心跳新鲜度 + 线程存活双维度判断",
        "m_today_fetches": "今日采集次数",
        "m_signal_1430": "14:30信号",
        "m_signal_yes": "已记录",
        "m_signal_no": "未记录",
        "m_signal_help": "14:28-14:33窗口自动记录当日买入信号（前5 ETF）",
        "m_last_fetch": "最近采集",
        "m_last_fetch_n": "最近采集行业数",
        "diag_title": "调度器诊断详情（心跳/崩溃/历史记录）",
        "diag_last_hb": "最近心跳",
        "diag_fresh": "新鲜",
        "diag_timeout": "超时",
        "diag_no_hb": "无心跳",
        "diag_thread": "主循环线程",
        "diag_alive": "存活",
        "diag_dead": "未存活",
        "diag_watchdog": "Watchdog重启次数",
        "diag_watchdog_help": "主循环异常退出后被看门狗自动重启的次数",
        "diag_hb_total": "累计心跳数",
        "diag_last_crash": "最近一次崩溃（{time}）：{msg}",
        "diag_history_title": "最近操作历史（最近10条）",
        "col_time": "时间",
        "col_action": "操作",
        "col_detail": "详情",
        "no_history": "暂无历史记录",
        "signal_today_title": "今日14:30买入信号 - TOP5 ETF（记录时间: {time}）",
        "last_auto_update": "最新自动操作更新时间: {time}",
        "btn_pause_fetch": "暂停自动采集",
        "btn_start_fetch": "启动自动采集",
        "btn_pause_fetch_help": "独立进程模式下请通过停止调度器.bat 或任务管理器停止",
        "toast_fetch_paused": "已暂停自动采集",
        "toast_fetch_started": "已启动自动采集",
        "btn_manual_fetch": "手动采集一次",
        "spinner_fetching": "正在手动采集...",
        "toast_fetch_ok": "手动采集成功",
        "manual_fetch_failed": "手动采集失败: {err}",
        "btn_refresh_page": "刷新页面",
        "sched_failed_warn": "调度器状态读取失败（自动采集可能仍在后台运行）: {err}",
        "auto_refresh": "自动刷新页面",
        "auto_refresh_help": "每 {n} 秒自动刷新页面查看最新数据",
        "spinner_loading_flow": "正在加载资金流数据...",
        "rt_no_data": "暂无缓存数据。请点击上方「手动采集一次」按钮，或等待后台调度器在交易时段自动采集。",
        "kpi_net": "全市场净流入",
        "kpi_inflow": "流入资金",
        "kpi_outflow": "流出资金",
        "kpi_inflow_ratio": "流入行业占比",
        "btn_show_top20": "显示 TOP20",
        "btn_collapse_top10": "收起到 TOP10",
        "showing_top": "当前显示 TOP{n}（共 {total} 个行业）",
        "industry_top_title": "行业资金流向 TOP{n}",
        "chart_net_flow": "净流入（{unit}）",
        "chart_industry": "行业名称",
        "chart_rank_title": "行业资金流向排行 TOP{n}",
        "etf_alert_title": "ETF评分预警",
        "no_etf_mapping": "暂无ETF映射数据，请检查行业-ETF映射配置",
        "found_buy": "发现 {n} 只满足买入条件的ETF（评分≥{threshold}）",
        "found_near": "发现 {n} 只评分接近阈值的ETF（60-{threshold}）",
        "found_below": "发现 {n} 只未达买入阈值的ETF（评分<60），表格中以黄色标注",
        "st_buy": "达买入阈值",
        "st_near": "未达买入阈值",
        "st_low": "评分偏低",
        "col_code": "代码",
        "col_name": "名称",
        "col_netflow": "净流入（{unit}）",
        "col_change": "涨跌幅（%）",
        "col_score": "评分",
        "col_status": "状态",
        "export_etf_scores": "导出ETF评分",
        "btn_record_signal": "记录14:30买入信号",
        "signal_saved": "14:30买入信号已记录到 {path}",
        "signal_picked": "选中5只ETF: {names}",
        "signal_save_failed": "记录信号失败: {err}",
        "etf_score_failed": "ETF评分计算失败: {err}",
        "hist_signals_title": "历史14:30选股信号",
        "select_date": "选择日期",
        "record_time": "记录时间",
        "total_industries": "行业总数",
        "total_etfs": "ETF总数",
        "no_signals": "暂无14:30信号记录",
        "no_signal_dir": "信号目录不存在，请先记录一次14:30信号",
        "flow_detail_title": "行业资金流向明细",
        "col_inflow_amt": "流入资金（{unit}）",
        "col_outflow_amt": "流出资金（{unit}）",
        "col_net_amt": "净额（{unit}）",
        "col_change_pct": "涨跌幅（%）",
        "sort_by": "排序方式",
        "sort_net": "净额",
        "sort_inflow": "流入资金",
        "sort_outflow": "流出资金",
        "ascending": "升序排列",
        "export_detail": "导出明细",
        "trend_title": "资金流趋势图",
        "trace_net_inflow": "净流入",
        "chart_trend_title": "资金流实时趋势",
        "axis_time": "时间",
        "axis_netflow_yi": "净流入（亿元）",
        "data_fetch_failed": "数据获取失败: {err}",

        # ---- 回测页 ----
        "bt_title": "ETF资金流回测系统",
        "bt_daily_title": "每日自动回测",
        "bt_today": "今日自动回测",
        "bt_done": "已完成",
        "bt_pending": "待执行",
        "bt_today_help": "每个交易日15:10后自动运行回测（最近60交易日，次日14:30换仓策略）",
        "bt_last_time": "最近回测时间",
        "bt_last_update": "最新自动操作更新",
        "bt_last_update_help": "所有自动操作（采集/信号/回测）的最近更新时间",
        "bt_total_return": "总收益",
        "bt_sharpe": "夏普比率",
        "bt_full_metrics": "查看最近一次自动回测完整指标",
        "bt_strategy_mode": "策略模式",
        "bt_period": "回测区间",
        "bt_annualized": "年化收益",
        "bt_max_dd": "最大回撤",
        "bt_win_rate": "胜率",
        "bt_profit_factor": "盈亏比",
        "bt_baseline": "基准收益",
        "bt_excess": "超额收益",
        "bt_report_path": "报告路径: {path}",
        "btn_run_auto_bt": "立即运行自动回测",
        "btn_run_auto_bt_help": "触发一次与自动调度相同的回测（最近60交易日）",
        "spinner_auto_bt": "正在运行自动回测，请稍候（可能需要1-3分钟）...",
        "toast_auto_bt_done": "自动回测完成",
        "auto_bt_failed": "自动回测失败: {err}",
        "auto_bt_ok_msg": "自动回测成功: 总收益 {total}%，夏普 {sharpe}，最大回撤 {dd}%，胜率 {win}%",
        "err_not_enough_days": "有效数据日期不足，仅找到 {n} 天",
        "fetch_standalone": "独立调度器在运行中（无需启动内嵌线程）",
        "sched_error_msg": "调度器异常: {err}",
        "fetch_ok_msg": "采集成功{shot}，共 {n} 条行业",
        "snapshot_tag": " [14:30快照]",
        "fetch_failed_msg": "采集失败: {err}",
        "btn_reset_bt_flag": "重置今日回测标记",
        "btn_reset_bt_help": "将 today_backtest_done 重置为 False，让调度器在15:10后再次触发",
        "toast_reset_bt": "已重置，将在15:10后再次自动回测",
        "bt_sched_failed": "调度器状态读取失败: {err}",
        "bt_manual_title": "手动回测",
        "bt_start_date": "开始日期",
        "bt_start_help": "回测起始日期，需有历史资金流数据",
        "bt_end_date": "结束日期",
        "bt_end_help": "回测结束日期",
        "bt_backfill_title": "从东方财富补齐历史数据",
        "bt_backfill_desc": "如果回测报\"有效数据日期不足\"，点击下方按钮从东方财富逐行业拉取历史资金流并重建按日期的横截面缓存。",
        "bt_backfill_days": "补齐天数",
        "btn_backfill": "立即补齐",
        "bt_backfill_ok": "补齐完成：重建了 {n} 个交易日",
        "bt_backfill_failed": "补齐失败: {err}",
        "bt_status_preparing": "准备回测...",
        "btn_start_bt": "开始回测",
        "log_read_signals": "① 读取历史资金信号...",
        "log_no_history": "没有找到资金流历史数据，请先点击'采集并缓存'积累数据",
        "log_not_enough_dates": "有效数据日期不足，仅找到 {n} 天，请调整日期范围",
        "log_got_days": "读取到 {n} 天资金流数据",
        "log_download_etf": "② 批量下载ETF日线数据...",
        "log_downloaded_n": "已下载 {i}/{n} 只ETF",
        "log_bt_timeout": "回测超时（超过120秒），请缩小回测时间范围",
        "log_no_prices": "未获取到任何ETF价格数据",
        "log_got_prices": "成功获取 {n} 只ETF价格数据",
        "log_running": "③ 运行策略回测...",
        "log_strategy_done": "回测策略运行完成",
        "log_metrics": "④ 计算绩效指标并绘图...",
        "log_done": "回测完成!",
        "log_failed": "回测失败: {err}",
        "bt_status_running": "回测运行中...",
        "bt_status_failed": "回测失败",
        "bt_status_done": "回测完成",
        "perf_title": "绩效指标概览",
        "pm_final_capital": "期末总资产",
        "pm_total_return": "总收益率",
        "pm_annualized": "年化收益",
        "pm_sharpe": "夏普比率",
        "pm_max_dd": "最大回撤",
        "pm_win_rate": "交易胜率",
        "pm_total_trades": "总交易次数",
        "grp_return": "收益指标",
        "pm_excess_csi300": "超额收益(沪深300)",
        "pm_csi300": "沪深300收益率",
        "pm_final_funds": "最终资金",
        "grp_risk": "风险指标",
        "pm_sortino": "Sortino比率",
        "pm_calmar": "Calmar比率",
        "pm_vol": "年化波动率",
        "pm_down_vol": "下行波动率",
        "grp_trade_stats": "交易统计",
        "pm_avg_win": "平均盈利",
        "pm_avg_loss": "平均亏损",
        "pm_max_win": "最大单笔盈利",
        "pm_max_loss": "最大单笔亏损",
        "pm_streaks": "最大连胜/连亏",
        "pm_avg_holding": "平均持仓天数",
        "grp_benchmark": "基准对比",
        "pm_alpha": "Alpha(年化)",
        "pm_beta": "Beta",
        "pm_info_ratio": "信息比率",
        "pm_tracking_error": "跟踪误差",
        "pm_upside_capture": "上行捕获率",
        "pm_downside_capture": "下行捕获率",
        "pm_capital_util": "资金利用率",
        "dd_start": "最大回撤起始",
        "dd_trough": "最大回撤谷底",
        "dd_duration": "回撤持续天数",
        "dd_recovery": "回撤恢复天数",
        "dd_not_recovered": "未恢复",
        "dd_longest_hold": "最长持仓天数",
        "btn_save_report": "保存完整报告",
        "report_saved": "报告已保存: {path}",
        "save_failed": "保存失败: {err}",
        "export_equity": "导出权益曲线",
        "export_daily_stats": "导出日度统计",
        "compare_title": "与历史回测对比",
        "cmp_file": "文件",
        "cmp_current": "本次",
        "cmp_time": "时间",
        "cmp_period": "区间",
        "cmp_strategy": "策略",
        "cmp_total": "总收益(%)",
        "cmp_annual": "年化(%)",
        "cmp_sharpe": "夏普",
        "cmp_dd": "回撤(%)",
        "cmp_win": "胜率(%)",
        "cmp_caption": "红色加粗 = 该指标最优值（A股红涨绿跌，红色=更好） | 蓝色 = 本次回测",
        "cmp_chart_title": "历史回测总收益对比",
        "axis_bt_time": "回测时间",
        "axis_total_return": "总收益率(%)",
        "cmp_render_failed": "对比图渲染失败: {err}",
        "cmp_not_enough": "暂无足够的历史回测数据用于对比。完成更多次回测后会自动展示对比表。",
        "cmp_load_failed": "历史对比加载失败: {err}",
        "equity_title": "策略权益曲线 vs 沪深300基准",
        "trace_equity": "策略权益",
        "trace_baseline": "沪深300基准",
        "trace_dd_start": "回撤起点",
        "trace_peak": "高点",
        "trace_dd_trough": "回撤谷底",
        "trace_low": "低点",
        "anno_dd_zone": "最大回撤区间 {pct}%",
        "chart_equity_title": "策略收益曲线对比",
        "axis_date": "日期",
        "axis_total_assets": "总资产",
        "dd_analysis_title": "回撤分析",
        "trace_drawdown": "回撤",
        "chart_dd_title": "回撤曲线（水下图）",
        "axis_dd_pct": "回撤(%)",
        "hover_date": "日期: {x}",
        "rolling_title": "滚动收益与波动率",
        "trace_rolling_ret": "20日滚动收益(%)",
        "trace_rolling_vol": "20日滚动年化波动率(%)",
        "chart_rolling_title": "20日滚动收益与波动率",
        "axis_rolling_ret": "滚动收益(%)",
        "axis_rolling_vol": "年化波动率(%)",
        "yearly_title": "年度收益分布",
        "trace_yearly": "年度收益",
        "chart_yearly_title": "年度收益率",
        "axis_year": "年份",
        "axis_return_pct": "收益率(%)",
        "heatmap_title": "月度收益热力图",
        "axis_month": "月份",
        "axis_year_only": "年份",
        "color_monthly_ret": "月度收益(%)",
        "monthly_win_title": "月度胜率统计",
        "m_profit_months": "盈利月数",
        "m_loss_months": "亏损月数",
        "m_best_month": "最佳月份",
        "m_worst_month": "最差月份",
        "trades_title": "交易明细",
        "tr_col_date": "日期",
        "tr_col_dir": "方向",
        "tr_col_code": "ETF代码",
        "tr_col_name": "ETF名称",
        "tr_col_price": "价格",
        "tr_col_shares": "股数",
        "tr_col_amount": "金额",
        "tr_col_pnl": "盈亏",
        "tr_col_pnl_pct": "盈亏(%)",
        "tr_col_reason": "原因",
        "tr_col_hold_days": "持仓天数",
        "side_buy": "买入",
        "side_sell": "卖出",
        "export_trades": "导出交易明细",
        "batch_title": "批量网格回测",
        "btn_run_batch": "运行批量回测",
        "batch_timeout": "批量回测超时（超过300秒）",
        "batch_running": "正在回测: {pos}只-{score}分 ({i}/{n})",
        "batch_combo_name": "{pos}只-{score}分",
        "batch_combo_failed": "参数组合 [{pos}只-{score}分] 回测失败: {err}",
        "batch_done": "批量回测完成!",
        "batch_chart_title": "批量回测对比曲线（归一化）",
        "batch_col_combo": "参数组合",
        "batch_col_total": "总收益率(%)",
        "batch_col_annual": "年化收益率(%)",
        "batch_col_dd": "最大回撤(%)",
        "batch_col_sharpe": "夏普比率",
        "batch_col_win": "胜率(%)",
        "batch_col_trades": "交易次数",
        "batch_table_title": "批量回测绩效表",
        "export_batch": "导出批量回测结果",

        # ---- 视频页 ----
        "vid_title": "资金流动态视频管理",
        "btn_make_video": "手动合成视频",
        "vid_few_frames": "帧数据不足，至少需要2帧",
        "vid_generating": "视频生成中… {pct}%",
        "vid_done": "视频生成完成: {path}",
        "vid_failed": "生成失败: {err}",
        "btn_clear_frames": "清空帧缓存",
        "vid_clear_warn": "当前有 {n} 条今日缓存帧，清空将丢失今日数据！",
        "btn_confirm_clear": "确认清空",
        "vid_frames_cleared": "帧缓存已清空",
        "vid_list_title": "视频文件列表",
        "vid_filter_date": "按日期筛选",
        "batch_ops": "批量操作",
        "btn_select_all": "全选",
        "btn_deselect_all": "取消全选",
        "btn_batch_delete": "批量删除 ({n})",
        "vid_deleted_n": "已删除 {n} 个视频文件",
        "vid_selected_n": "已选 {n} 个文件",
        "vid_none_selected": "未选择文件",
        "vid_table_title": "视频文件列表",
        "col_select": "选择",
        "col_filename": "文件名",
        "col_size": "大小",
        "col_type": "类型",
        "col_modified": "修改时间",
        "single_preview": "单个视频预览",
        "select_video_preview": "选择视频文件预览",
        "vid_preview_title": "视频预览",
        "vid_cannot_load": "无法加载视频",
        "vid_info_title": "文件信息",
        "vid_file_name": "文件名",
        "vid_size": "大小",
        "vid_type": "类型",
        "vid_modified": "修改时间",
        "btn_download_video": "下载此视频",
        "vid_read_failed": "读取视频失败: {err}",
        "btn_delete_file": "删除此文件",
        "vid_file_deleted": "文件已删除",
        "vid_delete_failed": "删除失败",
        "batch_download_title": "批量下载",
        "btn_zip_download": "打包下载 {n} 个视频 (ZIP)",
        "btn_download_zip": "下载 ZIP 文件",
        "vid_zip_hint": "未选择文件，请先在上方表格中勾选要下载的视频",
        "btn_clear_all_videos": "批量清理所有视频",
        "btn_confirm_clear_all": "确认批量删除全部",
        "vid_no_files": "暂无视频文件，请先生成视频",
        "vid_frame_status": "当前帧缓存状态",
        "vid_total_frames": "总缓存帧数",
        "vid_today_frames": "今日缓存帧数",

        # ---- 动态可视化页 ----
        "dv_title": "动态可视化（Bar Chart Race）",
        "dv_caption": "基于5分钟采集快照，实时呈现行业资金排名与 ETF 评分动态变化",
        "dv_bg_scheduler": "后台调度器",
        "dv_standalone_on": "**独立进程模式** - 关闭网页仍持续运行",
        "m_run_status": "运行状态",
        "st_running": "运行中",
        "st_stopped": "已停止",
        "m_health2": "健康度",
        "hb_ago": "心跳 {n} 秒前",
        "hb_none": "无心跳",
        "m_watchdog": "Watchdog重启",
        "dv_last_crash": "最近崩溃: {time} {msg}",
        "btn_pause_collect": "暂停采集",
        "btn_start_collect": "启动采集",
        "btn_collect_help": "独立进程模式下请通过启动/停止调度器脚本操作",
        "btn_fetch_once": "立即采集一次",
        "btn_clear_preview": "清理历史预览",
        "fetch_history_title": "采集历史（最近{n}条）",
        "dv_sched_failed": "调度器状态读取失败: {err}",
        "dv_viz_load_failed": "可视化模块加载失败: {err}",
        "dv_no_cache": "暂无资金流缓存数据。请先在「实时资金流」页面采集数据。",
        "dv_select_date": "选择日期",
        "dv_snap_limit": "加载快照数",
        "dv_top_n": "显示条数",
        "btn_generate": "生成动态图表",
        "dv_loading_snaps": "加载快照数据...",
        "dv_loaded": "加载完成：{rows} 条行业数据，{points} 个时间点，{scores} 条 ETF 评分",
        "dv_click_hint": "点击「生成动态图表」按钮加载并播放 Bar Chart Race 动画",
        "dv_no_snaps_date": "该日期无可用快照数据",
        "m_snapshots": "快照数",
        "m_time_span": "时间跨度",
        "m_industries": "行业数",
        "m_latest_net": "最新净流入",
        "dv_industry_race": "行业资金流向 Bar Chart Race",
        "dv_etf_race": "ETF 评分 Bar Chart Race",
        "dv_close_line_title": "单日收盘资金流向动态线图",
        "dv_close_line_caption": "每帧添加一个采集时间点，TOP N 行业累计净流入随时间延伸（类似实时心电图）",
        "dv_line_n": "线图行业数",
        "dv_mainflow_title": "单日午盘主力资金流向动态柱状图",
        "dv_mainflow_caption": "按交易时段筛选，主力净流入 TOP N 行业柱状图，按时间推进动画",
        "dv_session": "交易时段",
        "sess_afternoon": "下午盘 13:00-15:00",
        "sess_morning": "上午盘 9:30-11:30",
        "sess_all": "全天",
        "dv_bar_n": "柱状图行业数",
        "dv_net_trend": "全市场净流入趋势",
        "dv_up_down": "涨跌家数对比",
        "dv_in_out": "流入流出对比",
        "dv_make_video_title": "一键生成动态视频",
        "dv_fps": "帧率",
        "btn_gen_race_video": "生成 Bar Chart Race 视频",
        "spinner_gen_video": "正在生成动态视频...",
        "vid_generated": "视频已生成",
        "btn_download_video2": "下载视频",
        "vid_gen_failed": "视频生成失败: {err}",

        # ---- 动态图表 ----
        "chg_netflow_yi": "净流入(亿元)",
        "chg_score": "评分",
        "chg_etf": "ETF",
        "chg_time": "时间",
        "race_industry_title": "行业资金流向 Bar Chart Race - TOP{n}",
        "race_etf_title": "ETF 评分 Bar Chart Race - TOP{n}",
        "trend_live_title": "全市场净流入实时趋势",
        "up": "上涨",
        "down": "下跌",
        "chart_updown_title": "行业涨跌家数对比",
        "axis_count": "家数",
        "inflow_word": "流入",
        "outflow_word": "流出",
        "chart_inout_title": "资金流入流出对比",
        "axis_amount_yi": "金额(亿元)",
        "close_line_title": "单日收盘资金流向动态线图 - TOP{n} 行业累计净流入",
        "axis_fetch_time": "采集时间",
        "axis_cum_net": "累计净流入(亿元)",
        "mainflow_empty_title": "单日{sess}主力资金流向动态柱状图（无数据）",
        "mainflow_title": "单日{sess}主力资金流向动态柱状图 - TOP{n}",
        "colorbar_net": "净流入(亿)",
        "colorbar_score": "评分",
        "netflow_trace": "净流入",
        "btn_play": "播放",
        "btn_pause_anim": "暂停",
        "slider_time_prefix": "时间: ",
        "hover_cum_net": "时间: %{x}<br>累计净流入: %{y:.1f}亿",
        "no_snap_in_session": "所选时段无快照数据",

        # ---- 主题 ----
        "theme_dark": "暗黑",
        "theme_light": "明亮",

        # ---- 快捷键 ----
        "spinner_shortcut_fetch": "正在执行手动采集...",
        "toast_sc_fetch_ok": "快捷键触发：手动采集成功",
        "sc_fetch_failed": "快捷键采集失败: {err}",
        "toast_sc_theme": "已切换至{mode}模式",
        "spinner_sc_bt": "正在运行回测，请稍候...",
        "toast_sc_bt_ok": "快捷键触发：自动回测完成",
        "sc_bt_failed": "快捷键回测失败: {err}",
        "sched_start_failed": "调度器启动失败: {err}",
    },
}


# ============================================================
# 取值 / lookup
# ============================================================
def t(key: str, **kwargs) -> str:
    table = STRINGS.get(_current_lang) or STRINGS["en"]
    s = table.get(key)
    if s is None:
        s = STRINGS["en"].get(key, key)
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


def is_zh() -> bool:
    return _current_lang == "zh"


def unit_100m() -> str:
    """资金流单位：中文用「亿」，英文用 ¥100M"""
    return "亿" if is_zh() else "¥100M"


# ============================================================
# 金额（输入单位：亿元）/ money formatting (input unit: 100M CNY)
# ============================================================
def fmt_flow_money(v, signed: bool = True, decimals: int = 2) -> str:
    if v is None:
        return t("none_dash")
    try:
        f = float(v)
    except (TypeError, ValueError):
        return t("none_dash")
    sign = "+" if signed and f >= 0 else ""
    if is_zh():
        return f"{sign}{f:.{decimals}f}亿"
    # 英文：亿 -> B / M（1亿 = 0.1B = 100M）
    if abs(f) >= 10:
        return f"{sign}{f / 10:.{decimals}f}B"
    return f"{sign}{f * 100:.0f}M"


# ============================================================
# 相对时间 / relative time
# ============================================================
def fmt_lang_seconds_ago(seconds) -> str:
    if seconds is None:
        return t("none_dash")
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return t("none_dash")
    if is_zh():
        if s < 60:
            return f"{int(s)}秒前"
        if s < 3600:
            return f"{int(s / 60)}分钟前"
        if s < 86400:
            return f"{int(s / 3600)}小时前"
        return f"{int(s / 86400)}天前"
    # English
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s / 60)}m ago"
    if s < 86400:
        return f"{int(s / 3600)}h ago"
    return f"{int(s / 86400)}d ago"


# ============================================================
# 月份 / months
# ============================================================
MONTHS_ZH = {i: f"{i}月" for i in range(1, 13)}
MONTHS_EN = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def month_map() -> dict:
    return MONTHS_ZH if is_zh() else MONTHS_EN


# ============================================================
# 策略模式 / strategy mode
# ============================================================
def strategy_mode_label(mode: str) -> str:
    if mode == "next_day_rotation":
        return t("mode_next_day")
    if mode == "continuous":
        return t("mode_continuous")
    return str(mode)


# ============================================================
# 交易方向 / trade side
# ============================================================
def side_label(side: str) -> str:
    if side == "buy":
        return t("side_buy")
    if side == "sell":
        return t("side_sell")
    return str(side)


# ============================================================
# 交易原因（数据层为中文，展示层按语言替换前缀）
# ============================================================
_REASON_RULES_ZH = [
    ("止损", "stop_loss"),
    ("止盈", "take_profit"),
    ("回测结束清仓", "end_liquidate"),
    ("次日14:30强制换仓-卖出", "rotation_sell"),
    ("14:30资金流信号-次日换仓买入", "rotation_buy"),
    ("下午2:30资金流信号", "signal230"),
]
_REASON_TPL_EN = {
    "stop_loss": "Stop loss ({rest})",
    "take_profit": "Take profit ({rest})",
    "end_liquidate": "Liquidation at backtest end",
    "rotation_sell": "14:30 forced rotation – sell",
    "rotation_buy": "14:30 fund-flow signal – rotation buy ({rest})",
    "signal230": "14:30 fund-flow signal – {rest}",
}


def reason_label(reason: str) -> str:
    if reason is None:
        return ""
    r = str(reason)
    if is_zh():
        return r
    for prefix, key in _REASON_RULES_ZH:
        if r.startswith(prefix):
            rest = r[len(prefix):].strip(" -–")
            tpl = _REASON_TPL_EN[key]
            if "{rest}" in tpl:
                rest_clean = rest.replace("score=", "score=")
                return tpl.format(rest=rest_clean) if rest_clean else tpl.replace(" ({rest})", "")
            return tpl
    return r


# ============================================================
# 回测器内部固定进度日志（backtester.py 的 progress_callback）
# ============================================================
_BT_LOG_ZH2KEY = {
    "初始化回测参数...": "log_bt_init",
    "获取ETF价格数据...": "log_bt_prices",
    "获取沪深300基准...": "log_bt_baseline",
    "获取资金流历史数据...": "log_bt_flow_hist",
    "处理收尾清仓...": "log_bt_final_close",
    "生成回测结果...": "log_bt_build_result",
    "运行次日14:30换仓策略...": "log_bt_rotation",
    "回测结束清仓...": "log_bt_end_close",
}

# 英文翻译（zh 模式下直接显示原文）
_BT_LOG_EN = {
    "log_bt_init": "Initializing backtest parameters...",
    "log_bt_prices": "Fetching ETF price data...",
    "log_bt_baseline": "Fetching CSI 300 benchmark...",
    "log_bt_flow_hist": "Fetching historical fund-flow data...",
    "log_bt_final_close": "Closing remaining positions...",
    "log_bt_build_result": "Building backtest result...",
    "log_bt_rotation": "Running next-day 14:30 rotation strategy...",
    "log_bt_end_close": "Closing positions at backtest end...",
}


def bt_log_msg(zh_msg: str) -> str:
    """翻译 backtester 进度回调产生的中文日志（英文模式）。
    动态部分（日期等）保留原文。"""
    if is_zh():
        return zh_msg
    key = _BT_LOG_ZH2KEY.get(zh_msg.strip())
    if key:
        return _BT_LOG_EN[key]
    m = re.match(r"处理日期: (.+)", zh_msg)
    if m:
        return f"Processing date: {m.group(1)}"
    m = re.match(r"换仓处理: (.+)", zh_msg)
    if m:
        return f"Rotation processing: {m.group(1)}"
    return zh_msg


def bt_status_msg(msg: str) -> str:
    """翻译调度器持久化的 last_backtest_msg（中文成功/失败消息）。"""
    if not msg:
        return msg
    m = re.match(
        r"自动回测成功: 总收益 ([+-]?[\d.]+)%，夏普 ([+-]?[\d.]+)，"
        r"最大回撤 ([+-]?[\d.]+)%，胜率 ([+-]?[\d.]+)%",
        msg
    )
    if m:
        return t("auto_bt_ok_msg", total=m.group(1), sharpe=m.group(2),
                 dd=m.group(3), win=m.group(4))
    m = re.match(r"自动回测失败: (.*)", msg)
    if m:
        inner = m.group(1)
        m2 = re.match(r"有效数据日期不足，仅找到 (\d+) 天", inner)
        if m2:
            inner = t("err_not_enough_days", n=m2.group(1))
        return t("auto_bt_failed", err=inner)
    return msg


def fetch_status_msg(msg: str) -> str:
    """翻译调度器持久化的 last_fetch_msg（中文采集状态消息）。"""
    if not msg:
        return msg
    if msg.strip() == "独立调度器在运行中（无需启动内嵌线程）":
        return t("fetch_standalone")
    m = re.match(r"调度器异常: (.*)", msg)
    if m:
        return t("sched_error_msg", err=m.group(1))
    m = re.match(r"采集成功( \[14:30快照\])?，共 (\d+) 条行业", msg)
    if m:
        shot = t("snapshot_tag") if m.group(1) else ""
        return t("fetch_ok_msg", shot=shot, n=m.group(2))
    m = re.match(r"采集失败: (.*)", msg)
    if m:
        return t("fetch_failed_msg", err=m.group(1))
    return msg


# ============================================================
# 行业名中英映射 / Industry name CN -> EN
# 数据层 JSON 保留中文，展示层通过 tr_industry() 翻译
# ============================================================
INDUSTRY_EN = {
    "IT服务": "IT Services",
    "专用设备": "Special Equipment",
    "中药": "Traditional Chinese Medicine",
    "互联网电商": "Internet E-commerce",
    "保险": "Insurance",
    "元件": "Electronic Components",
    "光伏设备": "Photovoltaic Equipment",
    "光学光电子": "Optics & Optoelectronics",
    "公路铁路运输": "Road & Rail Transport",
    "其他电子": "Other Electronics",
    "其他电源设备": "Other Power Equipment",
    "其他社会服务": "Other Social Services",
    "养殖业": "Animal Husbandry & Aquaculture",
    "军工电子": "Military Electronics",
    "军工装备": "Military Equipment",
    "农产品加工": "Agricultural Processing",
    "农化制品": "Agrochemicals",
    "包装印刷": "Packaging & Printing",
    "化学制品": "Chemical Products",
    "化学制药": "Chemical Pharmaceuticals",
    "化学原料": "Chemical Raw Materials",
    "化学纤维": "Chemical Fibers",
    "医疗器械": "Medical Devices",
    "医疗服务": "Medical Services",
    "医药商业": "Pharmaceutical Commerce",
    "半导体": "Semiconductors",
    "厨卫电器": "Kitchen & Bath Appliances",
    "塑料制品": "Plastic Products",
    "多元金融": "Diversified Financials",
    "家居用品": "Household Products",
    "小家电": "Small Home Appliances",
    "小金属": "Minor Metals",
    "工业金属": "Industrial Metals",
    "工程机械": "Construction Machinery",
    "建筑材料": "Building Materials",
    "建筑装饰": "Building Decoration",
    "影视院线": "Film & Cinema",
    "房地产": "Real Estate",
    "教育": "Education",
    "文化传媒": "Culture & Media",
    "旅游及酒店": "Tourism & Hotels",
    "服装家纺": "Apparel & Home Textiles",
    "机场航运": "Airports & Airlines",
    "橡胶制品": "Rubber Products",
    "汽车整车": "Automobile Manufacturing",
    "汽车服务及其他": "Auto Services & Others",
    "汽车零部件": "Auto Parts",
    "油气开采及服务": "Oil & Gas Exploration & Services",
    "消费电子": "Consumer Electronics",
    "港口航运": "Ports & Shipping",
    "游戏": "Gaming",
    "煤炭开采加工": "Coal Mining & Processing",
    "燃气": "Gas Utilities",
    "物流": "Logistics",
    "环保设备": "Environmental Equipment",
    "环境治理": "Environmental Remediation",
    "生物制品": "Biological Products",
    "电力": "Electric Power",
    "电子化学品": "Electronic Chemicals",
    "电机": "Electric Motors",
    "电池": "Batteries",
    "电网设备": "Grid Equipment",
    "白色家电": "White Goods",
    "白酒": "Baijiu (Chinese Liquor)",
    "石油加工贸易": "Oil Processing & Trading",
    "种植业与林业": "Planting & Forestry",
    "纺织制造": "Textile Manufacturing",
    "综合": "Conglomerates",
    "美容护理": "Beauty & Personal Care",
    "能源金属": "Energy Metals",
    "自动化设备": "Automation Equipment",
    "计算机设备": "Computer Hardware",
    "证券": "Securities & Brokerage",
    "贵金属": "Precious Metals",
    "贸易": "Trading",
    "轨交设备": "Rail Transit Equipment",
    "软件开发": "Software Development",
    "通信服务": "Telecom Services",
    "通信设备": "Telecom Equipment",
    "通用设备": "General Equipment",
    "造纸": "Paper Manufacturing",
    "金属新材料": "New Metal Materials",
    "钢铁": "Steel",
    "银行": "Banks",
    "零售": "Retail",
    "非金属材料": "Non-metallic Materials",
    "风电设备": "Wind Power Equipment",
    "食品加工制造": "Food Processing",
    "饮料制造": "Beverage Manufacturing",
    "黑色家电": "Home Electronics",
}


def tr_industry(name) -> str:
    """展示层行业名翻译：zh 返回原名，en 返回英文映射，未命中返回原名。"""
    if name is None:
        return ""
    s = str(name)
    if is_zh():
        return s
    return INDUSTRY_EN.get(s, s)
