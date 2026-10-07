"""
A股资金流动态检测与ETF交易系统主界面
基于Streamlit构建的交互式仪表盘
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import base64
import threading
import time
import pickle
import logging

logger = logging.getLogger(__name__)
import io
import warnings
warnings.filterwarnings('ignore')

from config import ROOT_DIR, BACKTEST_CFG, INDUSTRY_ETF_MAPPING, DATA_DIR, SYS_CFG
from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import ETFFetcher, IndustryETFMapper
from flow_analyzer import SignalGenerator, FlowAnalyzer
from backtester import ETFBacktester, BacktestResult
from video_generator import FundFlowVideoGenerator
import i18n

# 界面语言：默认英文，切换后保存在 session_state
if "lang" not in st.session_state:
    st.session_state.lang = "en"
i18n.set_lang(st.session_state.lang)

st.set_page_config(
    page_title=i18n.t("app_title"),
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto"  # 桌面展开；移动端自动收起为抽屉，避免遮挡内容
)


def inject_custom_css():
    """注入全局自定义 CSS - 美化界面 + 暗黑模式 + Tooltip"""
    # 暗黑模式检测：从 session_state 读取
    dark_mode = st.session_state.get("dark_mode", False)
    if dark_mode:
        _inject_dark_mode_css()
        return

    st.markdown("""
    <style>
    /* ===== 全局字体与背景 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    }

    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    /* ===== 顶部 Hero 区域 ===== */
    .hero-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #0f9b8e 100%);
        border-radius: 18px;
        padding: 28px 36px;
        margin-bottom: 24px;
        color: white;
        position: relative;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(30, 60, 114, 0.25);
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 6px;
        letter-spacing: 0.5px;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        opacity: 0.85;
        font-weight: 400;
    }
    .hero-badges {
        margin-top: 14px;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    .hero-badge {
        background: rgba(255, 255, 255, 0.18);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.25);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 500;
    }

    /* ===== Metric 卡片美化 ===== */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e5e7eb;
        padding: 14px 18px;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.08);
        border-color: #2a5298;
    }
    div[data-testid="stMetric"] label {
        font-size: 0.78rem !important;
        color: #6b7280 !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.4px;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
        font-weight: 700 !important;
        color: #1f2937 !important;
    }

    /* ===== Tab 美化 ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f3f4f6;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 22px;
        font-weight: 600;
        font-size: 0.92rem;
        color: #6b7280;
        background: transparent;
        border: none;
        transition: all 0.25s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(42, 82, 152, 0.08);
        color: #2a5298;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(30, 60, 114, 0.3);
    }
    .stTabs [data-baseweb="tab-highlight"] { background-color: transparent !important; }
    .stTabs [data-baseweb="tab-border-bottom"] { display: none !important; }

    /* ===== 按钮颜色语义修正 =====
       - primary (蓝色渐变)：积极操作如运行回测、采集
       - secondary (白底蓝边)：辅助操作
       - danger (红色)：仅用于删除/停止
       - success (绿色)：成功确认类
    */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.55rem 1.2rem !important;
        transition: all 0.2s ease !important;
        border: 1px solid transparent !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.12) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        border: none !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #2a5298 0%, #0f9b8e 100%) !important;
    }
    .stButton > button[kind="secondary"] {
        background: white !important;
        border: 1px solid #d1d5db !important;
        color: #374151 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #2a5298 !important;
        color: #2a5298 !important;
    }
    /* 红色按钮（仅删除/停止）*/
    .danger-btn > button, button[data-testid*="delete"] {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%) !important;
        color: white !important;
    }
    /* 绿色按钮（成功类）*/
    .success-btn > button {
        background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important;
        color: white !important;
    }

    /* ===== Expander ===== */
    .stExpander {
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
        overflow: hidden;
        background: white !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
        margin-bottom: 14px !important;  /* 折叠面板间垂直间距 */
    }
    .stExpander > details > summary {
        font-weight: 600 !important;
        padding: 14px 20px !important;
        background: #f9fafb !important;
        border-bottom: 1px solid #e5e7eb;
    }

    /* ===== Dataframe ===== */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%) !important;
        border-right: 1px solid #e5e7eb;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #1e3c72 !important;
        font-weight: 700 !important;
        padding-bottom: 8px;
        border-bottom: 2px solid #2a5298;
        margin-bottom: 14px;
    }

    /* ===== 页面内 H2/H3 标题 ===== */
    .stMarkdown h2 {
        position: relative;
        padding-left: 16px !important;
        color: #1e3c72 !important;
        font-weight: 700 !important;
        margin-top: 8px !important;
        margin-bottom: 16px !important;
    }
    .stMarkdown h2::before {
        content: '';
        position: absolute;
        left: 0; top: 0.24em;
        width: 5px; height: 0.72em;
        background: linear-gradient(180deg, #1e3c72 0%, #2a5298 100%);
        border-radius: 3px;
    }
    .stMarkdown h3 {
        color: #374151 !important;
        font-weight: 600 !important;
        margin-top: 18px !important;
        margin-bottom: 10px !important;
    }

    /* ===== Caption / Info / Warn ===== */
    .stCaption {
        font-size: 0.78rem !important;
        color: #6b7280 !important;
    }
    .stAlert {
        border-radius: 10px !important;
        border: 1px solid transparent !important;
    }

    /* ===== Plotly 图表 ===== */
    .stPlotlyChart, iframe {
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    }

    /* ===== 涨跌色（A股红涨绿跌）===== */
    .pos { color: #dc2626 !important; font-weight: 600; }
    .neg { color: #16a34a !important; font-weight: 600; }

    /* ===== 状态徽章 ===== */
    .status-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 14px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 8px;
    }
    .status-pill.online {
        background: #dcfce7; color: #166534; border: 1px solid #86efac;
    }
    .status-pill.offline {
        background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;
    }
    .status-pill.pending {
        background: #fef3c7; color: #92400e; border: 1px solid #fcd34d;
    }

    /* ===== 数据新鲜度倒计时 ===== */
    .freshness-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(90deg, #dbeafe 0%, #ede9fe 100%);
        color: #1e40af;
        padding: 5px 14px;
        border-radius: 14px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #bfdbfe;
    }
    .freshness-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #16a34a;
        animation: pulse-dot 1.5s infinite;
    }
    .freshness-dot.stale {
        background: #dc2626;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.2); }
    }

    /* ===== 低分行高亮 ===== */
    .low-score-row {
        background-color: #fef3c7 !important;
    }
    .low-score-row td {
        color: #92400e !important;
    }

    /* ===== 加载骨架屏 ===== */
    .skeleton-loading {
        background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s infinite;
        border-radius: 8px;
        height: 60px;
        margin: 10px 0;
    }
    @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* ===== 分割线 ===== */
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, #d1d5db, transparent) !important;
        margin: 24px 0 !important;
    }

    /* ===== 滚动条 ===== */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #f1f5f9; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

    /* ===== 键盘快捷键提示 ===== */
    kbd {
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-bottom-width: 2px;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.75rem;
        font-family: monospace;
        color: #374151;
    }
    .shortcut-hint {
        color: #9ca3af;
        font-size: 0.75rem;
        margin-left: 6px;
    }

    /* ===== 对比表格 ===== */
    .comparison-table th {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: white !important;
        text-align: center !important;
    }
    .comparison-table .current-cell {
        background: #dbeafe !important;
        font-weight: 600;
    }
    .comparison-table .better {
        color: #dc2626;  /* 红色=更好（A股红涨） */
        font-weight: 600;
    }
    .comparison-table .worse {
        color: #16a34a;  /* 绿色=更差（A股绿跌） */
        font-weight: 600;
    }

    /* ============================================================
       交互与动效增强（补丁式，不覆盖 Streamlit 核心布局）
       ============================================================ */

    /* 图表卡片：白底圆角细边阴影 */
    .stPlotlyChart, .stVegaLiteChart {
        background: #ffffff;
        border: 1px solid #edf1f6;
        border-radius: 14px;
        padding: 10px 10px 4px 10px;
        margin: 6px 0 14px 0;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04),
                    0 8px 24px -18px rgba(15, 23, 42, 0.18);
        transition: box-shadow 0.25s ease, transform 0.25s ease;
    }
    .stPlotlyChart:hover {
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06),
                    0 16px 36px -20px rgba(30, 60, 114, 0.28);
    }

    /* Tab 面板淡入上移 */
    .stTabs [data-baseweb="tab-panel"] {
        animation: tab-fade-in 0.32s cubic-bezier(0.22, 1, 0.36, 1);
    }
    @keyframes tab-fade-in {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* 按钮按压反馈 + 触摸高度 */
    .stButton > button, .stDownloadButton > button {
        transition: transform 0.12s ease, box-shadow 0.2s ease,
                    background-color 0.2s ease, border-color 0.2s ease;
        min-height: 42px;
    }
    .stButton > button:active, .stDownloadButton > button:active {
        transform: scale(0.97);
    }
    .stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.22);
        outline: none;
    }

    /* 输入控件圆角与聚焦反馈 */
    .stSelectbox > div > div,
    .stTextInput > div > div,
    .stDateInput > div > div {
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .stSelectbox > div > div:focus-within,
    .stTextInput > div > div:focus-within,
    .stDateInput > div > div:focus-within {
        border-color: #93c5fd !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
    }

    /* 表格/宽图表容器横向滚动，避免移动端挤压 */
    .stDataFrame, .stTable { overflow-x: auto; -webkit-overflow-scrolling: touch; }

    /* Expander 触摸区域 */
    .streamlit-expanderHeader,
    [data-testid="stExpander"] summary {
        min-height: 44px;
        font-weight: 600;
    }

    /* ===== 移动端 / 平板响应式 ===== */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 14px !important;
            padding-right: 14px !important;
            padding-top: 1.5rem !important;
        }
        .hero-header {
            padding: 20px 18px !important;
            border-radius: 16px !important;
        }
        .hero-title { font-size: 1.35rem !important; line-height: 1.3 !important; }
        .hero-subtitle { font-size: 0.82rem !important; margin-top: 6px !important; }
        .hero-badges { gap: 6px !important; margin-top: 10px !important; }
        .hero-badge { font-size: 0.72rem !important; padding: 3px 10px !important; }
        /* 列堆叠时收紧纵向间距 */
        [data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
        /* 图表内边距收紧 */
        .stPlotlyChart { padding: 6px 4px 2px 4px; border-radius: 12px; }
        /* Tab 标签可横向滚动，不挤压文字 */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto;
            scrollbar-width: none;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
        .stTabs [data-baseweb="tab"] {
            white-space: nowrap;
            min-width: max-content;
            padding: 8px 14px !important;
        }
        /* 侧边栏内边距 */
        [data-testid="stSidebar"] .block-container {
            padding-top: 1rem !important;
        }
        /* metric 卡片字号略缩 */
        [data-testid="stMetricValue"] { font-size: 1.25rem !important; }
        /* 页面标题随窄屏收缩（Streamlit 默认 H2=36px 过大） */
        .stMarkdown h2 { font-size: 1.55rem !important; line-height: 1.3 !important; }
        .stMarkdown h3 { font-size: 1.2rem !important; line-height: 1.35 !important; }
        /* 滑块增大触摸区 */
        .stSlider { min-height: 34px; }
        /* 表格/图表横向滚动 */
        .stPlotlyChart, .stDataFrame { max-width: 100%; }
    }

    @media (max-width: 420px) {
        .hero-title { font-size: 1.15rem !important; }
        .stMarkdown h2 { font-size: 1.32rem !important; }
        .stMarkdown h3 { font-size: 1.08rem !important; }
        .stButton > button, .stDownloadButton > button {
            min-height: 46px;   /* 小屏手机更大的触摸目标 */
        }
    }

    /* 尊重系统"减少动态效果"偏好 */
    @media (prefers-reduced-motion: reduce) {
        .stTabs [data-baseweb="tab-panel"],
        .stPlotlyChart, .stButton > button,
        .stDownloadButton > button {
            animation: none !important;
            transition: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def _inject_dark_mode_css():
    """暗黑模式 CSS"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    }

    /* 暗黑模式主色：深蓝黑背景 */
    .stApp, .block-container, section[data-testid="stSidebar"] {
        background: #0f172a !important;
        color: #e2e8f0 !important;
    }
    .block-container {
        padding-top: 1.5rem !important;
        max-width: 1400px !important;
    }

    /* Hero 区域 - 暗黑更炫 */
    .hero-header {
        background: linear-gradient(135deg, #1e293b 0%, #312e81 50%, #0f9b8e 100%) !important;
        box-shadow: 0 10px 30px rgba(49, 46, 129, 0.4) !important;
    }

    /* Metric 卡片 */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #3b82f6 !important;
        box-shadow: 0 6px 14px rgba(59, 130, 246, 0.2) !important;
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
    }

    /* Tab */
    .stTabs [data-baseweb="tab-list"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(59, 130, 246, 0.15) !important;
        color: #60a5fa !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
        color: white !important;
    }

    /* 按钮 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
    }
    .stButton > button[kind="secondary"] {
        background: #1e293b !important;
        border: 1px solid #475569 !important;
        color: #e2e8f0 !important;
    }

    /* Expander */
    .stExpander {
        background: #1e293b !important;
        border-color: #334155 !important;
    }
    .stExpander > details > summary {
        background: #0f172a !important;
        color: #e2e8f0 !important;
        border-bottom-color: #334155 !important;
    }

    /* H2/H3 */
    .stMarkdown h2 {
        color: #60a5fa !important;
    }
    .stMarkdown h2::before {
        background: linear-gradient(180deg, #3b82f6 0%, #6366f1 100%) !important;
    }
    .stMarkdown h3 {
        color: #cbd5e1 !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
        border-right: 1px solid #334155 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #60a5fa !important;
        border-bottom-color: #3b82f6 !important;
    }

    /* Dataframe / Plotly 容器：图表保持白底"卡片"观感，暗底下对比清晰 */
    .stDataFrame {
        background: #1e293b !important;
    }
    .stPlotlyChart {
        background: #ffffff !important;
        border: 1px solid #334155 !important;
        border-radius: 14px !important;
        box-shadow: 0 10px 30px -18px rgba(0, 0, 0, 0.7) !important;
    }

    /* 状态徽章在暗黑模式下保持高对比度 */
    .status-pill.online {
        background: rgba(22, 163, 74, 0.25) !important;
        color: #4ade80 !important;
        border-color: rgba(22, 163, 74, 0.5) !important;
    }
    .status-pill.offline {
        background: rgba(220, 38, 38, 0.25) !important;
        color: #f87171 !important;
        border-color: rgba(220, 38, 38, 0.5) !important;
    }
    .status-pill.pending {
        background: rgba(245, 158, 11, 0.25) !important;
        color: #fbbf24 !important;
        border-color: rgba(245, 158, 11, 0.5) !important;
    }

    /* 滚动条暗黑 */
    ::-webkit-scrollbar-track { background: #1e293b !important; }
    ::-webkit-scrollbar-thumb { background: #475569 !important; }
    ::-webkit-scrollbar-thumb:hover { background: #64748b !important; }

    /* Alert */
    .stAlert {
        background: #1e293b !important;
    }

    /* 涨跌色保持 */
    .pos { color: #f87171 !important; }
    .neg { color: #4ade80 !important; }
    </style>
    """, unsafe_allow_html=True)


def render_header(sched_status: dict = None, standalone_running: bool = None):
    """渲染顶部 Hero 区域"""
    now = datetime.now()
    # 判断交易状态
    wd = now.weekday()
    t = now.time()
    from datetime import datetime as _dt
    is_trading = wd < 5 and (
        _dt.strptime("09:30", "%H:%M").time() <= t <= _dt.strptime("11:30", "%H:%M").time() or
        _dt.strptime("13:00", "%H:%M").time() <= t <= _dt.strptime("15:00", "%H:%M").time()
    )
    if is_trading:
        market_status = f'<span class="status-pill online">🟢 {i18n.t("status_trading")}</span>'
    elif wd < 5 and t < _dt.strptime("09:30", "%H:%M").time():
        market_status = f'<span class="status-pill pending">⏳ {i18n.t("status_premarket")}</span>'
    elif wd < 5 and t > _dt.strptime("15:00", "%H:%M").time():
        market_status = f'<span class="status-pill offline">⚫ {i18n.t("status_closed")}</span>'
    else:
        market_status = f'<span class="status-pill offline">⚫ {i18n.t("status_weekend")}</span>'

    # 调度器状态徽章
    if standalone_running is True:
        sched_badge = f'<span class="status-pill online">🟢 {i18n.t("sched_standalone_badge")}</span>'
    elif standalone_running is False:
        sched_badge = f'<span class="status-pill pending">🟡 {i18n.t("sched_embedded_badge")}</span>'
    else:
        sched_badge = ''

    # 最新更新时间 + 数据新鲜度
    last_update = ""
    freshness_html = ""
    if sched_status and sched_status.get("last_update_time"):
        try:
            from formatters import fmt_time_ago
            ago = fmt_time_ago(sched_status["last_update_time"])
            # 60 秒内为新鲜，否则失效
            last_dt = datetime.fromisoformat(sched_status["last_update_time"])
            seconds_ago = (now - last_dt).total_seconds()
            is_stale = seconds_ago > 600  # 10 分钟视为失活
            dot_class = "stale" if is_stale else ""
            freshness_html = (
                f'<span class="freshness-badge">'
                f'<span class="freshness-dot {dot_class}"></span>'
                f'{i18n.t("data_updated", ago=ago)}'
                f'</span>'
            )
            last_update = f'<span class="hero-badge">{i18n.t("last_update", time=sched_status["last_update_time"][:19])}</span>'
        except Exception:
            last_update = f'<span class="hero-badge">{i18n.t("last_update", time=sched_status["last_update_time"][:19])}</span>'

    st.markdown(f"""
    <div class="hero-header">
        <div class="hero-title">{i18n.t("app_title")}</div>
        <div class="hero-subtitle">{i18n.t("app_subtitle")}</div>
        <div class="hero-badges">
            <span class="hero-badge">{now.strftime('%Y-%m-%d %H:%M:%S')}</span>
            <span class="hero-badge">{market_status}</span>
            <span class="hero-badge">{sched_badge}</span>
            {last_update}
            {freshness_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def inject_keyboard_shortcuts():
    """注入键盘快捷键监听脚本 - 通过 query 参数触发 Streamlit 重运行"""
    shortcuts = """
    <script>
    // 顶层窗口监听（处理 iframe 沙盒）
    try {
        const targetWindow = window.parent || window;
        document.addEventListener('keydown', function(e) {
            // 仅响应 Ctrl+Shift 组合
            if (!(e.ctrlKey && e.shiftKey)) return;

            let shortcut = null;
            const k = e.key.toLowerCase();
            if (k === 'f') shortcut = 'fetch';
            else if (k === 'b') shortcut = 'backtest';
            else if (k === 'd') shortcut = 'dark';

            if (shortcut) {
                e.preventDefault();
                // 通过修改 URL query 参数触发 Streamlit 重运行
                try {
                    const url = new URL(targetWindow.location.href);
                    url.searchParams.set('shortcut', shortcut);
                    targetWindow.history.replaceState({}, '', url);
                    targetWindow.location.reload();
                } catch (err) {
                    console.log('Shortcut trigger failed:', err);
                }
            }
        });
    } catch (err) {
        console.log('Shortcut script init failed:', err);
    }
    </script>
    """
    st.components.v1.html(shortcuts, height=0)


if 'last_tab' not in st.session_state:
    st.session_state.last_tab = "实时资金流"

if 'backtest_result' not in st.session_state:
    st.session_state.backtest_result = None

if 'batch_results' not in st.session_state:
    st.session_state.batch_results = {}

if 'backtest_logs' not in st.session_state:
    st.session_state.backtest_logs = []

if 'backtest_progress' not in st.session_state:
    st.session_state.backtest_progress = 0

if 'backtest_running' not in st.session_state:
    st.session_state.backtest_running = False

if 'backtest_error' not in st.session_state:
    st.session_state.backtest_error = None

if 'video_progress' not in st.session_state:
    st.session_state.video_progress = 0

if 'video_logs' not in st.session_state:
    st.session_state.video_logs = []

if 'selected_video' not in st.session_state:
    st.session_state.selected_video = None

if 'filter_date' not in st.session_state:
    st.session_state.filter_date = datetime.now().strftime("%Y-%m-%d")


def get_session_storage():
    """获取会话存储（模拟持久化）"""
    session_path = DATA_DIR / "session_state.pkl"
    if session_path.exists():
        try:
            with open(session_path, 'rb') as f:
                return pickle.load(f)
        except:
            return {}
    return {}


def save_session_storage(data):
    """保存会话存储"""
    session_path = DATA_DIR / "session_state.pkl"
    try:
        with open(session_path, 'wb') as f:
            pickle.dump(data, f)
    except:
        pass


def load_session_state():
    """加载会话状态"""
    storage = get_session_storage()
    if 'last_tab' in storage:
        st.session_state.last_tab = storage['last_tab']


def save_session_state():
    """保存会话状态"""
    storage = {'last_tab': st.session_state.last_tab}
    save_session_storage(storage)


def get_download_link(df: pd.DataFrame, filename: str, title: str = "Download CSV"):
    """生成下载链接"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{title}</a>'
    return href


def render_sidebar():
    """渲染侧边栏控制面板"""
    with st.sidebar:
        # 语言切换（默认英文）
        lang_opts = {"EN": "en", "中文": "zh"}
        lang_idx = 0 if st.session_state.get("lang", "en") == "en" else 1
        sel_lang_label = st.selectbox(
            i18n.t("lang_label"),
            options=list(lang_opts.keys()),
            index=lang_idx,
            key="lang_select"
        )
        if lang_opts[sel_lang_label] != st.session_state.get("lang", "en"):
            st.session_state.lang = lang_opts[sel_lang_label]
            i18n.set_lang(st.session_state.lang)
            st.rerun()

        # 顶部品牌区
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                    color: white; padding: 16px 20px; border-radius: 12px; margin-bottom: 18px;">
            <div style="font-size: 1.1rem; font-weight: 700; margin-bottom: 4px;">{i18n.t("sidebar_title")}</div>
            <div style="font-size: 0.8rem; opacity: 0.85;">{i18n.t("sidebar_subtitle")}</div>
        </div>
        """, unsafe_allow_html=True)

        # 暗黑模式开关（月/日图标表达开关含义，保留）
        dark_mode = st.session_state.get("dark_mode", False)
        dm_cols = st.columns([3, 1])
        with dm_cols[1]:
            if st.button("🌙" if dark_mode else "☀️", help="Dark / Light"):
                st.session_state.dark_mode = not dark_mode
                st.rerun()
        with dm_cols[0]:
            st.caption(i18n.t("theme_caption_dark" if dark_mode else "theme_caption_light"))

        st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True)

        with st.expander(i18n.t("grp_cost"), expanded=True):
            BACKTEST_CFG.commission_rate = st.number_input(
                i18n.t("commission"), min_value=0.0, max_value=0.5, value=0.03, step=0.01
            ) / 100
            BACKTEST_CFG.slippage_rate = st.number_input(
                i18n.t("slippage"), min_value=0.0, max_value=0.5, value=0.05, step=0.01
            ) / 100
            BACKTEST_CFG.stamp_tax_rate = st.number_input(
                i18n.t("stamp_tax"), min_value=0.0, max_value=0.5, value=0.0, step=0.01
            ) / 100

        with st.expander(i18n.t("grp_risk"), expanded=True):
            BACKTEST_CFG.stop_loss = st.number_input(
                i18n.t("stop_loss"), min_value=-20.0, max_value=0.0, value=-5.0, step=0.5
            ) / 100
            BACKTEST_CFG.take_profit = st.number_input(
                i18n.t("take_profit"), min_value=0.0, max_value=50.0, value=15.0, step=0.5
            ) / 100

        with st.expander(i18n.t("grp_strategy"), expanded=True):
            BACKTEST_CFG.max_positions = st.number_input(
                i18n.t("max_positions"), min_value=1, max_value=20, value=5, step=1
            )
            BACKTEST_CFG.position_size = st.number_input(
                i18n.t("position_size"), min_value=0.01, max_value=1.0, value=0.2, step=0.05
            )
            BACKTEST_CFG.buy_threshold = st.slider(
                i18n.t("buy_threshold"), min_value=0, max_value=100, value=70, step=1
            )
            rebalance_time = st.text_input(
                i18n.t("rebalance_time"), value=BACKTEST_CFG.rebalance_time, key='rebalance_time'
            )
            BACKTEST_CFG.rebalance_time = rebalance_time

            BACKTEST_CFG.strategy_mode = st.selectbox(
                i18n.t("strategy_mode"),
                options=["next_day_rotation", "continuous"],
                index=0,
                format_func=lambda x: i18n.t("mode_next_day" if x == "next_day_rotation" else "mode_continuous"),
            )
            BACKTEST_CFG.execution_price = st.selectbox(
                i18n.t("execution_price"),
                options=["close", "open"],
                index=0,
                format_func=lambda x: i18n.t("exec_close" if x == "close" else "exec_open"),
            )

        with st.expander(i18n.t("grp_fetch"), expanded=True):
            SYS_CFG.auto_refresh_interval = st.number_input(
                i18n.t("refresh_interval"), min_value=60, max_value=3600, value=300, step=60
            )

        # 恢复默认参数按钮
        st.markdown('<div style="height: 14px;"></div>', unsafe_allow_html=True)
        if st.button(i18n.t("reset_defaults"), use_container_width=True):
            BACKTEST_CFG.commission_rate = 0.0003
            BACKTEST_CFG.slippage_rate = 0.0005
            BACKTEST_CFG.stamp_tax_rate = 0.0
            BACKTEST_CFG.stop_loss = -0.05
            BACKTEST_CFG.take_profit = 0.15
            BACKTEST_CFG.max_positions = 5
            BACKTEST_CFG.position_size = 0.2
            BACKTEST_CFG.buy_threshold = 70
            BACKTEST_CFG.rebalance_time = "14:30"
            BACKTEST_CFG.strategy_mode = "next_day_rotation"
            BACKTEST_CFG.execution_price = "close"
            SYS_CFG.auto_refresh_interval = 300
            st.toast(i18n.t("toast_reset"))
            st.rerun()

        st.markdown("---")

        # 快捷键提示
        with st.expander(i18n.t("grp_shortcuts")):
            st.markdown(f"""
            - <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd> {i18n.t("shortcut_fetch")}
            - <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>B</kbd> {i18n.t("shortcut_backtest")}
            - <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd> {i18n.t("shortcut_dark")}
            - <kbd>F5</kbd> {i18n.t("shortcut_f5")}
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"### {i18n.t('data_dirs')}")
        st.markdown(f"{i18n.t('root_dir')}: `{ROOT_DIR}`")
        st.markdown(f"{i18n.t('data_dir')}: `{DATA_DIR}`")


def render_real_time_dashboard():
    """渲染实时资金监控页面"""
    st.markdown(f"## {i18n.t('rt_title')}")

    fetcher = FundFlowFetcher()
    mapper = IndustryETFMapper()
    signal_gen = SignalGenerator(mapper)

    # ===== 调度器状态卡片（自动采集由后台调度器负责）=====
    try:
        from streamlit_scheduler import get_scheduler
        sched = get_scheduler()
        # 检测独立调度器是否在运行
        standalone_running = sched.is_standalone_running()

        # 仅当独立调度器没运行时才启动内嵌线程
        if not standalone_running and not sched.status["running"]:
            sched.start(standalone=False)

        sched_status = sched.get_status()
        st.markdown(f"### {i18n.t('rt_scheduler')}")

        # 调度模式提示
        if standalone_running:
            st.success(i18n.t("rt_standalone_on"), icon="✅")
        else:
            st.warning(i18n.t("rt_standalone_off"), icon="⚠️")

        # ====== 健康度：心跳/线程存活/崩溃次数 判定 ======
        last_hb = sched_status.get("last_heartbeat")
        thread_alive = sched_status.get("thread_alive", False)
        crash_count = sched_status.get("loop_crash_count", 0)
        last_crash_msg = sched_status.get("last_crash_msg", "")
        # 心跳新鲜度：120 秒内算新鲜
        hb_fresh = False
        hb_seconds = None
        if last_hb:
            try:
                hb_dt = datetime.fromisoformat(last_hb)
                hb_seconds = (datetime.now() - hb_dt).total_seconds()
                hb_fresh = hb_seconds < 120
            except Exception:
                pass
        # 综合健康状态（彩色圆点承载状态语义，保留）
        if standalone_running:
            if hb_fresh and thread_alive:
                health_badge = f'<span class="status-pill online">🟢 {i18n.t("health_healthy")}</span>'
            elif hb_fresh and not thread_alive:
                health_badge = f'<span class="status-pill warn">🟡 {i18n.t("health_hb_stale_main")}</span>'
            else:
                health_badge = f'<span class="status-pill offline">🔴 {i18n.t("health_hb_timeout")}</span>'
        else:
            if sched_status.get("running") and thread_alive:
                health_badge = f'<span class="status-pill online">🟢 {i18n.t("health_normal")}</span>'
            elif sched_status.get("running"):
                health_badge = f'<span class="status-pill warn">🟡 {i18n.t("health_running_no_main")}</span>'
            else:
                health_badge = f'<span class="status-pill offline">⚪ {i18n.t("health_not_started")}</span>'

        s_cols = st.columns(6)
        s_cols[0].metric(
            i18n.t("m_sched_mode"),
            f"🟢 {i18n.t('m_mode_standalone')}" if standalone_running else f"🟡 {i18n.t('m_mode_embedded')}",
            help=i18n.t("m_mode_help")
        )
        s_cols[1].metric(
            i18n.t("m_health"),
            "",
            help=i18n.t("m_health_help")
        )
        s_cols[1].markdown(health_badge, unsafe_allow_html=True)
        s_cols[2].metric(i18n.t("m_today_fetches"), sched_status["today_fetch_count"])
        s_cols[3].metric(
            i18n.t("m_signal_1430"),
            i18n.t("m_signal_yes") if sched_status["today_signal_recorded"] else i18n.t("m_signal_no"),
            help=i18n.t("m_signal_help")
        )
        s_cols[4].metric(
            i18n.t("m_last_fetch"),
            sched_status["last_fetch_time"][:19] if sched_status["last_fetch_time"] else "—"
        )
        s_cols[5].metric(i18n.t("m_last_fetch_n"), sched_status["last_fetch_count"])

        # 诊断子面板
        with st.expander(i18n.t("diag_title"), expanded=False):
            dcol1, dcol2, dcol3, dcol4 = st.columns(4)
            hb_delta = i18n.t("diag_fresh") if hb_fresh else (i18n.t("diag_timeout") if hb_seconds else i18n.t("diag_no_hb"))
            dcol1.metric(
                i18n.t("diag_last_hb"),
                f"{int(hb_seconds)}s" if hb_seconds is not None else "—",
                delta=hb_delta,
            )
            dcol2.metric(
                i18n.t("diag_thread"),
                f"✅ {i18n.t('diag_alive')}" if thread_alive else f"❌ {i18n.t('diag_dead')}",
            )
            dcol3.metric(
                i18n.t("diag_watchdog"),
                crash_count,
                help=i18n.t("diag_watchdog_help")
            )
            dcol4.metric(
                i18n.t("diag_hb_total"),
                sched_status.get("heartbeat_count", 0),
            )
            if last_crash_msg:
                st.warning(
                    i18n.t("diag_last_crash",
                           time=sched_status.get('last_crash_time', '—')[:19],
                           msg=last_crash_msg)
                )
            # 最近历史记录
            history = sched_status.get("history", [])
            if history:
                st.markdown(f"**{i18n.t('diag_history_title')}**")
                recent = history[-10:][::-1]
                h_rows = []
                for h in recent:
                    h_rows.append({
                        i18n.t("col_time"): h.get("time", ""),
                        i18n.t("col_action"): h.get("action", ""),
                        i18n.t("col_detail"): ", ".join(
                            f"{k}={v}" for k, v in h.items()
                            if k not in ("time", "action")
                        )
                    })
                st.dataframe(pd.DataFrame(h_rows), hide_index=True, use_container_width=True, height=280)
            else:
                st.caption(i18n.t("no_history"))

        if sched_status["last_fetch_msg"]:
            st.info(i18n.fetch_status_msg(sched_status['last_fetch_msg']))

        # 显示 14:30 信号 TOP5（如已记录）
        if sched_status["today_signal_recorded"] and sched_status.get("last_signal_top5"):
            with st.expander(i18n.t("signal_today_title", time=sched_status.get('last_signal_time', '—')[:19]), expanded=False):
                top5_list = sched_status["last_signal_top5"]
                t5_cols = st.columns(len(top5_list))
                for i, name in enumerate(top5_list):
                    t5_cols[i].metric(f"#{i+1}", name)

        # 最新自动操作更新时间（所有自动操作的统一时间戳）
        if sched_status.get("last_update_time"):
            st.caption(i18n.t("last_auto_update", time=sched_status['last_update_time'][:19]))

        # 调度控制按钮
        ctrl_cols = st.columns(3)
        with ctrl_cols[0]:
            if st.button(i18n.t("btn_pause_fetch") if sched_status["running"] else i18n.t("btn_start_fetch"),
                         use_container_width=True, key="realtime_sched_toggle",
                         disabled=standalone_running,
                         help=i18n.t("btn_pause_fetch_help")):
                if sched_status["running"]:
                    sched.stop()
                    st.toast(i18n.t("toast_fetch_paused"))
                else:
                    sched.start(standalone=False)
                    st.toast(i18n.t("toast_fetch_started"))
                st.rerun()
        # 保留手动采集窗口
        with ctrl_cols[1]:
            if st.button(i18n.t("btn_manual_fetch"), use_container_width=True, key="realtime_manual_fetch"):
                with st.spinner(i18n.t("spinner_fetching")):
                    try:
                        from datetime import datetime as _dt
                        sched._do_fetch(_dt.now())
                        st.toast(i18n.t("toast_fetch_ok"))
                        st.rerun()
                    except Exception as e:
                        st.error(i18n.t("manual_fetch_failed", err=e))
        with ctrl_cols[2]:
            if st.button(i18n.t("btn_refresh_page"), use_container_width=True, key="realtime_refresh"):
                st.session_state.refresh_key = time.time()
                st.rerun()

        st.markdown("---")
    except Exception as e:
        st.warning(i18n.t("sched_failed_warn", err=e))

    # ===== 自动刷新页面（让用户能看到最新数据） =====
    auto_refresh = st.checkbox(i18n.t("auto_refresh"), value=False,
                                help=i18n.t("auto_refresh_help", n=SYS_CFG.auto_refresh_interval))
    if auto_refresh:
        st.components.v1.html(
            f'<script>setTimeout(() => window.location.reload(), {SYS_CFG.auto_refresh_interval * 1000});</script>',
            height=0
        )

    with st.spinner(i18n.t("spinner_loading_flow")):
        try:
            df = fetcher.fetch_cached()

            if df.empty:
                st.warning(i18n.t("rt_no_data"))
                return

            analyzer = FlowAnalyzer()
            df = analyzer.rank_industries(df)
            df = analyzer.calc_inflow_ratio(df)

            # 导入格式化工具
            from formatters import fmt_signed_money, fmt_money, fmt_signed_pct, fmt_pct, fmt_score

            col_net = '净额' if '净额' in df.columns else 'net_flow'
            col_inflow = '流入资金' if '流入资金' in df.columns else 'inflow'
            col_outflow = '流出资金' if '流出资金' in df.columns else 'outflow'
            col_change = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'

            total_net = df[col_net].sum()
            total_inflow = df[col_inflow].sum()
            total_outflow = df[col_outflow].sum()

            positive_count = len(df[df[col_net] > 0])
            negative_count = len(df[df[col_net] < 0])

            metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)

            with metrics_col1:
                net_color = "#16a34a" if total_net >= 0 else "#dc2626"  # A股红涨绿跌，正绿负红
                net_value = fmt_signed_money(total_net)
                st.markdown(f"""
                <div style="text-align: center; background-color: {net_color}15; padding: 15px; border-radius: 10px; border: 1px solid {net_color}40;">
                    <div style="font-size: 24px; font-weight: bold; color: {net_color};">
                        {net_value}
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">{i18n.t("kpi_net")}</div>
                </div>
                """, unsafe_allow_html=True)

            with metrics_col2:
                st.markdown(f"""
                <div style="text-align: center; background-color: #16a34a15; padding: 15px; border-radius: 10px; border: 1px solid #16a34a40;">
                    <div style="font-size: 24px; font-weight: bold; color: #16a34a;">
                        {fmt_money(total_inflow)}
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">{i18n.t("kpi_inflow")}</div>
                </div>
                """, unsafe_allow_html=True)

            with metrics_col3:
                st.markdown(f"""
                <div style="text-align: center; background-color: #dc262615; padding: 15px; border-radius: 10px; border: 1px solid #dc262640;">
                    <div style="font-size: 24px; font-weight: bold; color: #dc2626;">
                        {fmt_money(total_outflow)}
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">{i18n.t("kpi_outflow")}</div>
                </div>
                """, unsafe_allow_html=True)

            with metrics_col4:
                ratio = positive_count / (positive_count + negative_count) * 100 if (positive_count + negative_count) > 0 else 0
                st.markdown(f"""
                <div style="text-align: center; background-color: #0ea5e915; padding: 15px; border-radius: 10px; border: 1px solid #0ea5e940;">
                    <div style="font-size: 24px; font-weight: bold; color: #0ea5e9;">
                        {ratio:.1f}%
                    </div>
                    <div style="font-size: 12px; color: #6b7280;">{i18n.t("kpi_inflow_ratio")}</div>
                </div>
                """, unsafe_allow_html=True)

            # ===== 图表：默认 TOP10，支持展开 TOP20 =====
            chart_top_n = st.session_state.get("realtime_chart_top_n", 10)
            chart_cols = st.columns([3, 1, 1])
            with chart_cols[1]:
                if st.button(i18n.t("btn_show_top20") if chart_top_n == 10 else i18n.t("btn_collapse_top10"),
                             use_container_width=True, key="realtime_chart_toggle"):
                    st.session_state["realtime_chart_top_n"] = 20 if chart_top_n == 10 else 10
                    st.rerun()
            with chart_cols[2]:
                st.caption(i18n.t("showing_top", n=chart_top_n, total=len(df)))

            st.markdown(f"### {i18n.t('industry_top_title', n=chart_top_n)}")

            top_df = df.head(chart_top_n).copy()
            top_df['行业'] = top_df['行业'].apply(i18n.tr_industry)
            top_df['颜色'] = top_df[col_net].apply(lambda x: '#16a34a' if x >= 0 else '#dc2626')

            fig = px.bar(
                top_df,
                x=col_net,
                y='行业',
                orientation='h',
                color='颜色',
                text=top_df[col_net].apply(lambda x: fmt_signed_money(x)),
                labels={col_net: i18n.t('chart_net_flow', unit=i18n.unit_100m()),
                        '行业': i18n.t('chart_industry')},
                title=i18n.t('chart_rank_title', n=chart_top_n)
            )
            fig.update_layout(
                height=max(400, chart_top_n * 28),
                showlegend=False,
                yaxis={'categoryorder': 'total ascending'}
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"### {i18n.t('etf_alert_title')}")

            try:
                etf_df = mapper.map_industry_flow_to_etf(df)

                if etf_df.empty:
                    st.info(i18n.t("no_etf_mapping"))
                else:
                    etf_df['score'] = signal_gen.score_etf(etf_df)

                    warning_count = len(etf_df[etf_df['score'] >= BACKTEST_CFG.buy_threshold])
                    near_warning_count = len(etf_df[(etf_df['score'] >= 60) & (etf_df['score'] < BACKTEST_CFG.buy_threshold)])
                    below_threshold_count = len(etf_df[etf_df['score'] < 60])

                    if warning_count > 0:
                        st.success(i18n.t("found_buy", n=warning_count, threshold=BACKTEST_CFG.buy_threshold))
                    if near_warning_count > 0:
                        st.info(i18n.t("found_near", n=near_warning_count, threshold=BACKTEST_CFG.buy_threshold))
                    if below_threshold_count > 0:
                        st.warning(i18n.t("found_below", n=below_threshold_count))

                    # 基于原始评分构建高亮颜色映射
                    score_to_color = {}
                    for idx, s in zip(etf_df.index, etf_df['score']):
                        if s >= BACKTEST_CFG.buy_threshold:
                            score_to_color[idx] = '#d1fae5'  # 浅绿：达标
                        elif s >= 60:
                            score_to_color[idx] = '#fef3c7'  # 浅黄：未达阈值
                        else:
                            score_to_color[idx] = '#fee2e2'  # 浅红：未达标

                    def highlight_score_col(val, idx):
                        """根据行索引返回背景色"""
                        return f'background-color: {score_to_color.get(idx, "")}'

                    # 应用数值格式化（仅展示层）
                    display_df = etf_df[['etf_code', 'etf_name', 'net_flow', 'change_pct', 'score']].copy()
                    display_df.columns = [
                        i18n.t("col_code"), i18n.t("col_name"),
                        i18n.t("col_netflow", unit=i18n.unit_100m()),
                        i18n.t("col_change"), i18n.t("col_score")
                    ]
                    # 格式化为字符串
                    display_df[i18n.t("col_netflow", unit=i18n.unit_100m())] = display_df[i18n.t("col_netflow", unit=i18n.unit_100m())].apply(
                        lambda x: i18n.fmt_flow_money(x, signed=False)
                    )
                    display_df[i18n.t("col_change")] = display_df[i18n.t("col_change")].apply(lambda x: f"{x:+.2f}%")
                    display_df[i18n.t("col_score")] = display_df[i18n.t("col_score")].apply(lambda x: f"{x:.1f}")
                    # 增加状态文字标注列
                    def status_label(s):
                        if s >= BACKTEST_CFG.buy_threshold:
                            return f"✅ {i18n.t('st_buy')}"
                        elif s >= 60:
                            return f"⚠️ {i18n.t('st_near')}"
                        return f"❌ {i18n.t('st_low')}"
                    display_df[i18n.t("col_status")] = etf_df['score'].apply(status_label)

                    # 应用高亮到评分列（基于行索引）
                    score_col_name = i18n.t("col_score")
                    def style_score_column(col):
                        colors = [score_to_color.get(idx, '') for idx in col.index]
                        return [f'background-color: {c}' if c else '' for c in colors]

                    st.dataframe(
                        display_df.style.apply(style_score_column, subset=[score_col_name]),
                        use_container_width=True,
                        hide_index=True,
                        height=min(600, 40 * len(display_df) + 50)
                    )

                    col_download, col_filter = st.columns(2)
                    with col_download:
                        st.markdown(get_download_link(display_df, 'etf_scores.csv', i18n.t("export_etf_scores")), unsafe_allow_html=True)

                    if fetcher.is_1430_window():
                        if st.button(i18n.t("btn_record_signal"), use_container_width=True):
                            try:
                                top5 = etf_df.sort_values('score', ascending=False).head(5)

                                signal_record = {
                                    'date': datetime.now().strftime("%Y-%m-%d"),
                                    'time': datetime.now().strftime("%H:%M:%S"),
                                    'top5_etfs': top5[['etf_code', 'etf_name', 'score', 'net_flow', 'change_pct']].to_dict('records'),
                                    'total_industry_count': len(df),
                                    'total_etf_count': len(etf_df),
                                }

                                signal_dir = ROOT_DIR / "signals"
                                signal_dir.mkdir(parents=True, exist_ok=True)
                                signal_file = signal_dir / f"{datetime.now().strftime('%Y%m%d')}_signal.json"

                                with open(signal_file, 'w', encoding='utf-8') as f:
                                    json.dump(signal_record, f, ensure_ascii=False, indent=2)

                                st.success(i18n.t("signal_saved", path=signal_file))
                                st.write(i18n.t("signal_picked", names=[e['etf_name'] for e in signal_record['top5_etfs']]))
                            except Exception as e:
                                st.error(i18n.t("signal_save_failed", err=e))
            except Exception as e:
                st.error(i18n.t("etf_score_failed", err=e))
                import traceback
                st.exception(traceback.format_exc())

            st.markdown(f"### {i18n.t('hist_signals_title')}")

            signal_dir = ROOT_DIR / "signals"
            if signal_dir.exists():
                signal_files = sorted(list(signal_dir.glob("*_signal.json")), reverse=True)

                if signal_files:
                    selected_file = st.selectbox(i18n.t("select_date"), [f.name[:8] for f in signal_files])
                    selected_path = signal_dir / f"{selected_file}_signal.json"

                    if selected_path.exists():
                        with open(selected_path, 'r', encoding='utf-8') as f:
                            signal_data = json.load(f)

                        st.markdown(f"**{i18n.t('record_time')}:** {signal_data['date']} {signal_data['time']}")
                        st.markdown(f"**{i18n.t('total_industries')}:** {signal_data['total_industry_count']} | **{i18n.t('total_etfs')}:** {signal_data['total_etf_count']}")

                        if signal_data['top5_etfs']:
                            signal_df = pd.DataFrame(signal_data['top5_etfs'])
                            signal_df.columns = [
                                i18n.t("col_code"), i18n.t("col_name"), i18n.t("col_score"),
                                i18n.t("col_netflow", unit=i18n.unit_100m()), i18n.t("col_change")
                            ]
                            st.dataframe(signal_df.style.background_gradient(subset=[i18n.t("col_score")], cmap='RdYlGn'), use_container_width=True)
                else:
                    st.info(i18n.t("no_signals"))
            else:
                st.info(i18n.t("no_signal_dir"))

            st.markdown(f"### {i18n.t('flow_detail_title')}")

            display_cols = ['行业', col_inflow, col_outflow, col_net, col_change]
            display_names = [
                i18n.t("chart_industry"),
                i18n.t("col_inflow_amt", unit=i18n.unit_100m()),
                i18n.t("col_outflow_amt", unit=i18n.unit_100m()),
                i18n.t("col_net_amt", unit=i18n.unit_100m()),
                i18n.t("col_change_pct"),
            ]

            col_map = {'净额': col_net, '流入资金': col_inflow, '流出资金': col_outflow}
            sort_options = ['净额', '流入资金', '流出资金']
            sort_labels = {
                '净额': i18n.t("sort_net"),
                '流入资金': i18n.t("sort_inflow"),
                '流出资金': i18n.t("sort_out"),
            }
            valid_sort_options = [opt for opt in sort_options if col_map[opt] in df.columns]

            sort_by_display = st.selectbox(
                i18n.t("sort_by"), valid_sort_options, index=0,
                format_func=lambda x: sort_labels[x]
            )
            sort_by_actual = col_map[sort_by_display]
            ascending = st.checkbox(i18n.t("ascending"), value=False)

            sorted_df = df.sort_values(sort_by_actual, ascending=ascending)[display_cols].copy()
            sorted_df['行业'] = sorted_df['行业'].apply(i18n.tr_industry)
            sorted_df.columns = display_names

            net_col_name = i18n.t("col_net_amt", unit=i18n.unit_100m())
            change_col_name = i18n.t("col_change_pct")
            st.dataframe(
                sorted_df.style.background_gradient(subset=[net_col_name, change_col_name], cmap='RdYlGn'),
                use_container_width=True,
                hide_index=True
            )

            st.markdown(get_download_link(sorted_df, 'industry_flow.csv', i18n.t("export_detail")), unsafe_allow_html=True)

            st.markdown(f"### {i18n.t('trend_title')}")

            history_df = fetcher.fetch_history_summary()
            if not history_df.empty:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=history_df['time'],
                    y=history_df['total_net'],
                    mode='lines+markers',
                    name=i18n.t("trace_net_inflow"),
                    line=dict(color='#28a745', width=2),
                    marker=dict(size=6)
                ))
                fig_trend.update_layout(
                    title=i18n.t("chart_trend_title"),
                    xaxis_title=i18n.t("axis_time"),
                    yaxis_title=i18n.t("axis_netflow_yi"),
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig_trend, use_container_width=True)

        except Exception as e:
            st.error(i18n.t("data_fetch_failed", err=e))


def render_backtest_dashboard():
    """渲染ETF回测页面"""
    st.markdown(f"## {i18n.t('bt_title')}")

    # ===== 自动回测状态卡片 =====
    try:
        from streamlit_scheduler import get_scheduler
        sched = get_scheduler()
        sched_status = sched.get_status()

        st.markdown(f"### {i18n.t('bt_daily_title')}")
        b_cols = st.columns(5)
        b_cols[0].metric(
            i18n.t("bt_today"),
            ("✅ " if sched_status.get('today_backtest_done', False) else "") +
            (i18n.t("bt_done") if sched_status.get('today_backtest_done', False) else i18n.t("bt_pending")),
            help=i18n.t("bt_today_help")
        )
        b_cols[1].metric(
            i18n.t("bt_last_time"),
            sched_status.get("last_backtest_time", "—")[:19] if sched_status.get("last_backtest_time") else "—"
        )
        b_cols[2].metric(
            i18n.t("bt_last_update"),
            sched_status.get("last_update_time", "—")[:19] if sched_status.get("last_update_time") else "—",
            help=i18n.t("bt_last_update_help")
        )
        # 摘要指标
        summary = sched_status.get("last_backtest_summary", {})
        b_cols[3].metric(i18n.t("bt_total_return"), f"{summary.get('total_return', 0):+.2f}%" if summary else "—")
        b_cols[4].metric(i18n.t("bt_sharpe"), f"{summary.get('sharpe_ratio', 0):.2f}" if summary else "—")

        # 详细信息
        if sched_status.get("last_backtest_msg"):
            st.info(i18n.bt_status_msg(sched_status['last_backtest_msg']))

        if summary:
            with st.expander(i18n.t("bt_full_metrics"), expanded=False):
                sm_cols = st.columns(4)
                sm_cols[0].metric(i18n.t("bt_strategy_mode"), i18n.strategy_mode_label(summary.get("strategy_mode", "—")))
                sm_cols[1].metric(i18n.t("bt_period"), f"{summary.get('start_date','—')} ~ {summary.get('end_date','—')}")
                sm_cols[2].metric(i18n.t("bt_annualized"), f"{summary.get('annualized_return', 0):+.2f}%")
                sm_cols[3].metric(i18n.t("bt_max_dd"), f"{summary.get('max_drawdown', 0):.2f}%")

                sm2 = st.columns(4)
                sm2[0].metric("Sortino", f"{summary.get('sortino_ratio', 0):.2f}")
                sm2[1].metric("Calmar", f"{summary.get('calmar_ratio', 0):.2f}")
                sm2[2].metric(i18n.t("bt_win_rate"), f"{summary.get('win_rate', 0):.1f}%")
                sm2[3].metric(i18n.t("bt_profit_factor"), f"{summary.get('profit_factor', 0):.2f}")

                sm3 = st.columns(4)
                sm3[0].metric("Alpha", f"{summary.get('alpha', 0):+.2f}%")
                sm3[1].metric("Beta", f"{summary.get('beta', 0):.2f}")
                sm3[2].metric(i18n.t("bt_baseline"), f"{summary.get('baseline_return', 0):+.2f}%")
                sm3[3].metric(i18n.t("bt_excess"), f"{summary.get('excess_return', 0):+.2f}%")

                if summary.get("report_file"):
                    st.code(i18n.t("bt_report_path", path=summary['report_file']))

        # 手动触发自动回测
        bt_ctrl = st.columns(2)
        with bt_ctrl[0]:
            if st.button(i18n.t("btn_run_auto_bt"), use_container_width=True, type="primary",
                         help=i18n.t("btn_run_auto_bt_help")):
                with st.spinner(i18n.t("spinner_auto_bt")):
                    try:
                        sched.run_backtest_manually()
                        st.toast(i18n.t("toast_auto_bt_done"))
                        st.rerun()
                    except Exception as e:
                        st.error(i18n.t("auto_bt_failed", err=e))
        with bt_ctrl[1]:
            if st.button(i18n.t("btn_reset_bt_flag"), use_container_width=True,
                         help=i18n.t("btn_reset_bt_help")):
                with sched.status_lock:
                    sched.status["today_backtest_done"] = False
                sched._persist_status()
                st.toast(i18n.t("toast_reset_bt"))
                st.rerun()

        st.markdown("---")
    except Exception as e:
        st.warning(i18n.t("bt_sched_failed", err=e))

    # ===== 手动回测配置 =====
    st.markdown(f"### {i18n.t('bt_manual_title')}")

    col_start, col_end = st.columns(2)

    with col_start:
        start_date = st.date_input(
            i18n.t("bt_start_date"),
            value=datetime.now() - timedelta(days=365),
            help=i18n.t("bt_start_help")
        )

    with col_end:
        end_date = st.date_input(
            i18n.t("bt_end_date"),
            value=datetime.now(),
            help=i18n.t("bt_end_help")
        )

    # 一键从历史接口补齐数据（解决"有效数据日期不足"）
    with st.expander(i18n.t("bt_backfill_title"), expanded=False):
        st.caption(i18n.t("bt_backfill_desc"))
        backfill_days = st.slider(
            i18n.t("bt_backfill_days"), min_value=10, max_value=90, value=30, step=5
        )
        if st.button(i18n.t("btn_backfill"), use_container_width=True):
            pb = st.progress(0)
            status_txt = st.empty()
            try:
                from fundflow_fetcher import FundFlowFetcher
                ff = FundFlowFetcher()
                def _cb(cur, total, msg):
                    pb.progress(cur / max(total, 1))
                    status_txt.text(f"[{cur}/{total}] {msg}")
                result = ff.backfill_history_from_eastmoney(days=backfill_days, progress_callback=_cb)
                st.success(i18n.t("bt_backfill_ok", n=len(result)))
            except Exception as e:
                st.error(i18n.t("bt_backfill_failed", err=e))

    results_container = st.container()
    progress_status = st.status(i18n.t("bt_status_preparing"), expanded=False)
    progress_bar = st.progress(0)
    log_area = st.empty()

    metrics_container = st.empty()
    equity_chart_container = st.empty()
    heatmap_container = st.empty()
    trades_container = st.empty()

    if st.button(i18n.t("btn_start_bt"), use_container_width=True, type="primary"):
        st.session_state.backtest_running = True
        st.session_state.backtest_progress = 0
        st.session_state.backtest_logs = []
        st.session_state.backtest_result = None
        st.session_state.backtest_error = None

        def run_backtest():
            import time as time_module
            start_time = time_module.time()
            timeout = 120

            try:
                def log(msg, progress=None):
                    if progress is not None:
                        st.session_state.backtest_progress = progress
                    st.session_state.backtest_logs.append(msg)
                    logger.info(msg)

                log(i18n.t("log_read_signals"), 5)

                fundflow_fetcher = FundFlowFetcher()
                fundflow_history = fundflow_fetcher.fetch_history_for_backtest(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                if not fundflow_history:
                    raise RuntimeError(i18n.t("log_no_history"))

                valid_dates = list(fundflow_history.keys())
                if len(valid_dates) < 5:
                    raise RuntimeError(i18n.t("log_not_enough_dates", n=len(valid_dates)))

                log(i18n.t("log_got_days", n=len(valid_dates)), 15)

                log(i18n.t("log_download_etf"), 20)

                from etf_fetcher import IndustryETFMapper
                mapper = IndustryETFMapper()
                all_etf_codes = list(set(code for _, (code, _) in INDUSTRY_ETF_MAPPING.items()))

                prices = {}
                etf_fetcher = ETFFetcher()
                for i, code in enumerate(all_etf_codes):
                    if time_module.time() - start_time > timeout:
                        raise RuntimeError(i18n.t("log_bt_timeout"))

                    df = etf_fetcher.fetch_etf_hist(code, days=730)
                    if not df.empty:
                        prices[code] = df

                    if (i + 1) % 5 == 0:
                        log(i18n.t("log_downloaded_n", i=i+1, n=len(all_etf_codes)), 20 + int((i+1)/len(all_etf_codes)*20))

                if not prices:
                    raise RuntimeError(i18n.t("log_no_prices"))

                log(i18n.t("log_got_prices", n=len(prices)), 35)

                log(i18n.t("log_running"), 40)

                backtester = ETFBacktester(BACKTEST_CFG)
                result = backtester.run(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    lambda pct, msg: log(i18n.bt_log_msg(msg), 40 + int(pct * 0.5))
                )

                log(i18n.t("log_strategy_done"), 90)

                log(i18n.t("log_metrics"), 95)

                st.session_state.backtest_result = result
                log(i18n.t("log_done"), 100)

            except Exception as e:
                st.session_state.backtest_error = str(e)
                log(i18n.t("log_failed", err=e), 0)
                logger.error(f"回测失败: {e}", exc_info=True)
            finally:
                st.session_state.backtest_running = False

        thread = threading.Thread(target=run_backtest)
        thread.start()

    if st.session_state.backtest_running:
        progress_status.update(label=i18n.t("bt_status_running"), state="running", expanded=True)

        with progress_status:
            while st.session_state.backtest_running:
                progress_bar.progress(st.session_state.backtest_progress)

                logs_display = "\n".join(st.session_state.backtest_logs[-20:])
                log_area.markdown(f"```\n{logs_display}\n```")

                time.sleep(0.5)

        progress_bar.progress(100)

    if st.session_state.backtest_error:
        progress_status.update(label=i18n.t("bt_status_failed"), state="error", expanded=True)
        with progress_status:
            st.error(st.session_state.backtest_error)
            logs_display = "\n".join(st.session_state.backtest_logs)
            st.markdown(f"```\n{logs_display}\n```")
        return

    if st.session_state.backtest_result:
        result = st.session_state.backtest_result
        progress_status.update(label=i18n.t("bt_status_done"), state="complete", expanded=False)

        with metrics_container.container():
            st.markdown(f"### {i18n.t('perf_title')}")

            # 顶部核心指标卡片
            cols = st.columns(7)
            metrics = [
                (i18n.t("pm_final_capital"), f"{result.final_capital:,.2f}", '#17a2b8'),
                (i18n.t("pm_total_return"), f"{result.total_return:+.2f}%", '#28a745' if result.total_return >= 0 else '#dc3545'),
                (i18n.t("pm_annualized"), f"{result.annualized_return:+.2f}%", '#17a2b8'),
                (i18n.t("pm_sharpe"), f"{result.sharpe_ratio:.2f}", '#ffc107'),
                (i18n.t("pm_max_dd"), f"{result.max_drawdown:.2f}%", '#dc3545'),
                (i18n.t("pm_win_rate"), f"{result.win_rate:.2f}%", '#28a745'),
                (i18n.t("pm_total_trades"), f"{result.total_trades}", '#17a2b8'),
            ]

            for col, (label, value, color) in zip(cols, metrics):
                with col:
                    st.markdown(f"""
                    <div style="text-align: center; background-color: {color}20; padding: 12px; border-radius: 8px;">
                        <div style="font-size: 18px; font-weight: bold; color: {color};">{value}</div>
                        <div style="font-size: 11px; color: #666;">{label}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # 详细指标分组展示
            def _metric_card(label, value, color='#495057'):
                return f"""
                <div style="background-color: {color}15; border-left: 3px solid {color}; padding: 8px 10px; border-radius: 4px; margin-bottom: 6px;">
                    <div style="font-size: 13px; font-weight: bold; color: {color};">{value}</div>
                    <div style="font-size: 10px; color: #888;">{label}</div>
                </div>"""

            def _fmt(v, suffix='', prec=2):
                if isinstance(v, (int,)):
                    return f"{v}{suffix}"
                try:
                    return f"{float(v):.{prec}f}{suffix}"
                except Exception:
                    return str(v)

            col_a, col_b, col_c, col_d = st.columns(4)

            with col_a:
                st.markdown(f"**{i18n.t('grp_return')}**")
                st.markdown(_metric_card(i18n.t("pm_excess_csi300"), _fmt(result.excess_return, '%'), '#28a745' if result.excess_return >= 0 else '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_csi300"), _fmt(result.baseline_return, '%'), '#17a2b8'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_final_funds"), f"{result.final_capital:,.0f}", '#495057'), unsafe_allow_html=True)

            with col_b:
                st.markdown(f"**{i18n.t('grp_risk')}**")
                st.markdown(_metric_card(i18n.t("pm_sortino"), _fmt(result.sortino_ratio), '#ffc107'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_calmar"), _fmt(result.calmar_ratio), '#ffc107'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_vol"), _fmt(result.volatility, '%'), '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_down_vol"), _fmt(result.downside_volatility, '%'), '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card("VaR(95%)", _fmt(result.var_95, '%'), '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card("CVaR(95%)", _fmt(result.cvar_95, '%'), '#dc3545'), unsafe_allow_html=True)

            with col_c:
                st.markdown(f"**{i18n.t('grp_trade_stats')}**")
                st.markdown(_metric_card(i18n.t("bt_profit_factor"), _fmt(result.profit_factor, prec=2), '#28a745'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_avg_win"), f"+{result.avg_win_pnl:,.0f}", '#28a745'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_avg_loss"), f"{result.avg_lose_pnl:,.0f}", '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_max_win"), f"+{result.max_win_pnl:,.0f}", '#28a745'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_max_loss"), f"{result.max_lose_pnl:,.0f}", '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_streaks"), f"{result.max_consecutive_wins} / {result.max_consecutive_losses}", '#495057'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_avg_holding"), _fmt(result.avg_holding_days, i18n.t("days_word"), prec=1), '#495057'), unsafe_allow_html=True)

            with col_d:
                st.markdown(f"**{i18n.t('grp_benchmark')}**")
                st.markdown(_metric_card(i18n.t("pm_alpha"), _fmt(result.alpha, '%'), '#28a745' if result.alpha >= 0 else '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_beta"), _fmt(result.beta, prec=2), '#17a2b8'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_info_ratio"), _fmt(result.information_ratio), '#ffc107'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_tracking_error"), _fmt(result.tracking_error, '%'), '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_upside_capture"), _fmt(result.upside_capture, '%'), '#28a745'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_downside_capture"), _fmt(result.downside_capture, '%'), '#dc3545'), unsafe_allow_html=True)
                st.markdown(_metric_card(i18n.t("pm_capital_util"), _fmt(result.capital_utilization, '%'), '#495057'), unsafe_allow_html=True)

            # 回撤详情
            if result.max_drawdown_start:
                st.markdown("---")
                dd_cols = st.columns(5)
                recovery_str = f"{result.max_drawdown_recovery}{i18n.t('days_word')}" if result.max_drawdown_recovery >= 0 else i18n.t("dd_not_recovered")
                dd_metrics = [
                    (i18n.t("dd_start"), result.max_drawdown_start, '#dc3545'),
                    (i18n.t("dd_trough"), result.max_drawdown_end, '#dc3545'),
                    (i18n.t("dd_duration"), f"{result.max_drawdown_duration}{i18n.t('days_word')}", '#ffc107'),
                    (i18n.t("dd_recovery"), recovery_str, '#17a2b8'),
                    (i18n.t("dd_longest_hold"), f"{result.max_holding_days}{i18n.t('days_word')}", '#495057'),
                ]
                for col, (label, value, color) in zip(dd_cols, dd_metrics):
                    with col:
                        st.markdown(f"""
                        <div style="text-align: center; background-color: {color}15; padding: 10px; border-radius: 6px; border: 1px solid {color}40;">
                            <div style="font-size: 14px; font-weight: bold; color: {color};">{value}</div>
                            <div style="font-size: 10px; color: #888;">{label}</div>
                        </div>""", unsafe_allow_html=True)

            # 导出完整报告
            st.markdown("---")
            export_cols = st.columns(3)
            with export_cols[0]:
                if st.button(i18n.t("btn_save_report"), use_container_width=True):
                    try:
                        from backtester import ETFBacktester as _BT
                        path = _BT().save_result(result)
                        st.success(i18n.t("report_saved", path=path))
                    except Exception as e:
                        st.error(i18n.t("save_failed", err=e))
            with export_cols[1]:
                st.markdown(get_download_link(result.equity_curve.reset_index(), 'equity_curve.csv', i18n.t("export_equity")), unsafe_allow_html=True)
            with export_cols[2]:
                if not result.daily_stats.empty:
                    st.markdown(get_download_link(result.daily_stats.reset_index(), 'daily_stats.csv', i18n.t("export_daily_stats")), unsafe_allow_html=True)

            # ===== 与历史回测对比 =====
            st.markdown(f"### {i18n.t('compare_title')}")
            try:
                from pathlib import Path as _P
                bt_dir = _P("data/backtest")
                history_records = []
                if bt_dir.exists():
                    # 遍历所有 summary.json 文件
                    for sf in sorted(bt_dir.glob("*_summary.json"), reverse=True):
                        try:
                            import json as _json
                            with open(sf, 'r', encoding='utf-8') as f:
                                d = _json.load(f)
                            history_records.append({
                                i18n.t("cmp_file"): sf.stem.replace('_summary', ''),
                                i18n.t("cmp_time"): d.get("backtest_at", sf.name.split('_')[0]),
                                i18n.t("cmp_period"): f"{d.get('start_date','—')}~{d.get('end_date','—')}",
                                i18n.t("cmp_strategy"): i18n.strategy_mode_label(d.get('strategy_mode', '—')),
                                i18n.t("cmp_total"): float(d.get('total_return', 0)),
                                i18n.t("cmp_annual"): float(d.get('annualized_return', 0)),
                                i18n.t("cmp_sharpe"): float(d.get('sharpe_ratio', 0)),
                                i18n.t("cmp_dd"): float(d.get('max_drawdown', 0)),
                                i18n.t("cmp_win"): float(d.get('win_rate', 0)),
                            })
                        except Exception:
                            continue

                # 当前回测指标加入对比
                current_label = f"**{i18n.t('cmp_current')}**"
                current_record = {
                    i18n.t("cmp_file"): current_label,
                    i18n.t("cmp_time"): datetime.now().strftime("%Y-%m-%d %H:%M"),
                    i18n.t("cmp_period"): f"{result.start_date}~{result.end_date}",
                    i18n.t("cmp_strategy"): i18n.strategy_mode_label(getattr(BACKTEST_CFG, 'strategy_mode', '—')),
                    i18n.t("cmp_total"): result.total_return,
                    i18n.t("cmp_annual"): result.annualized_return,
                    i18n.t("cmp_sharpe"): result.sharpe_ratio,
                    i18n.t("cmp_dd"): result.max_drawdown,
                    i18n.t("cmp_win"): result.win_rate,
                }
                history_records.insert(0, current_record)

                if len(history_records) >= 2:
                    # 对比表
                    hist_df = pd.DataFrame(history_records).head(10)
                    cmp_file_col = i18n.t("cmp_file")
                    # 应用高亮：本次行用蓝色高亮，最佳指标用红色加粗
                    def highlight_current(s):
                        return ['background-color: #dbeafe; font-weight: bold' if v == current_label else '' for v in s]

                    # 对总收益、夏普、胜率列标红最佳值
                    def highlight_best(col, lower_better=False):
                        vals = pd.to_numeric(col, errors='coerce')
                        if lower_better:
                            best = vals.min()
                        else:
                            best = vals.max()
                        return ['color: #dc2626; font-weight: bold' if v == best else '' for v in vals]

                    styled = hist_df.style.apply(highlight_current, subset=[cmp_file_col])
                    for col in [i18n.t("cmp_total"), i18n.t("cmp_annual"), i18n.t("cmp_sharpe"), i18n.t("cmp_win")]:
                        if col in hist_df.columns:
                            styled = styled.apply(highlight_best, subset=[col])
                    if i18n.t("cmp_dd") in hist_df.columns:
                        styled = styled.apply(lambda c: highlight_best(c, lower_better=True), subset=[i18n.t("cmp_dd")])

                    # 数值格式化
                    fmt_map = {
                        i18n.t("cmp_total"): '{:+.2f}',
                        i18n.t("cmp_annual"): '{:+.2f}',
                        i18n.t("cmp_sharpe"): '{:.2f}',
                        i18n.t("cmp_dd"): '{:.2f}',
                        i18n.t("cmp_win"): '{:.2f}',
                    }
                    styled = styled.format(fmt_map)

                    st.dataframe(styled, use_container_width=True, hide_index=True, height=min(400, 40*len(hist_df)+50))

                    st.caption(i18n.t("cmp_caption"))

                    # 对比柱状图：总收益 vs 夏普（最近10次）
                    try:
                        chart_df = hist_df.iloc[1:11].copy() if len(hist_df) > 1 else hist_df.copy()
                        if not chart_df.empty:
                            fig_cmp = go.Figure()
                            total_col = i18n.t("cmp_total")
                            fig_cmp.add_trace(go.Bar(
                                x=chart_df[i18n.t("cmp_time")],
                                y=chart_df[total_col],
                                name=total_col,
                                marker_color=['#dc2626' if v >= 0 else '#16a34a' for v in chart_df[total_col]]
                            ))
                            fig_cmp.update_layout(
                                title=i18n.t("cmp_chart_title"),
                                xaxis_title=i18n.t("axis_bt_time"),
                                yaxis_title=i18n.t("axis_total_return"),
                                height=350,
                                margin=dict(l=20, r=20, t=50, b=20)
                            )
                            st.plotly_chart(fig_cmp, use_container_width=True)
                    except Exception as e:
                        st.caption(i18n.t("cmp_render_failed", err=e))
                else:
                    st.info(i18n.t("cmp_not_enough"))
            except Exception as e:
                st.warning(i18n.t("cmp_load_failed", err=e))

        with equity_chart_container.container():
            st.markdown(f"### {i18n.t('equity_title')}")

            equity_df = result.equity_curve.copy()

            # 计算回撤序列（供后续多处使用）
            running_max = equity_df['total_value'].cummax()
            equity_df['drawdown'] = (equity_df['total_value'] - running_max) / running_max * 100

            # 抽样降采样，避免绘图过密
            if len(equity_df) > 500:
                step = max(1, int(len(equity_df) / 500))
                plot_df = equity_df.iloc[::step].copy()
            else:
                plot_df = equity_df.copy()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=plot_df.index, y=plot_df['total_value'],
                mode='lines', name=i18n.t("trace_equity"),
                line=dict(color='#28a745', width=2),
                hovertemplate=f'{i18n.t("hover_date")}: %{{x}}<br>%{{y:,.0f}}<extra></extra>'
            ))

            if 'baseline_pct' in plot_df.columns and plot_df['baseline_pct'].notna().any():
                baseline_value = result.initial_capital * (1 + plot_df['baseline_pct'] / 100)
                fig.add_trace(go.Scatter(
                    x=plot_df.index, y=baseline_value,
                    mode='lines', name=i18n.t("trace_baseline"),
                    line=dict(color='#17a2b8', width=2, dash='dash'),
                    hovertemplate=f'{i18n.t("hover_date")}: %{{x}}<br>%{{y:,.0f}}<extra></extra>'
                ))

            # 高亮最大回撤区间
            try:
                if result.max_drawdown_start and result.max_drawdown_end:
                    dd_start = pd.to_datetime(result.max_drawdown_start)
                    dd_end = pd.to_datetime(result.max_drawdown_end)
                    peak_val = equity_df.loc[:dd_start, 'total_value'].max()
                    fig.add_vrect(
                        x0=dd_start, x1=dd_end,
                        fillcolor="rgba(220,53,69,0.12)", layer="below",
                        line=dict(color="#dc3545", width=1, dash="dot"),
                        annotation_text=i18n.t("anno_dd_zone", pct=f"{result.max_drawdown:.1f}"),
                        annotation_position="top left",
                        annotation=dict(font_size=11, font_color="#dc3545")
                    )
                    fig.add_trace(go.Scatter(
                        x=[dd_start], y=[peak_val],
                        mode='markers+text', name=i18n.t("trace_dd_start"),
                        marker=dict(color='#dc3545', size=10, symbol='triangle-down'),
                        text=[i18n.t("trace_peak")], textposition='top center',
                        hovertemplate='%{y:,.0f}<extra></extra>'
                    ))
                    trough_val = equity_df.loc[dd_end, 'total_value']
                    fig.add_trace(go.Scatter(
                        x=[dd_end], y=[trough_val],
                        mode='markers+text', name=i18n.t("trace_dd_trough"),
                        marker=dict(color='#dc3545', size=10, symbol='triangle-up'),
                        text=[i18n.t("trace_low")], textposition='bottom center',
                        hovertemplate='%{y:,.0f}<extra></extra>'
                    ))
            except Exception:
                pass

            fig.update_layout(
                title=i18n.t("chart_equity_title"),
                xaxis_title=i18n.t("axis_date"), yaxis_title=i18n.t("axis_total_assets"),
                height=500, hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"### {i18n.t('dd_analysis_title')}")

            dd_plot = plot_df.copy()
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=dd_plot.index, y=dd_plot['drawdown'],
                fill='tozeroy', mode='lines', name=i18n.t("trace_drawdown"),
                line=dict(color='#dc3545', width=2),
                fillcolor='rgba(220, 53, 69, 0.25)',
                hovertemplate=f'{i18n.t("hover_date")}: %{{x}}<br>%{{y:.2f}}%<extra></extra>'
            ))
            # 标注最大回撤点
            try:
                if result.max_drawdown_end:
                    trough_date = pd.to_datetime(result.max_drawdown_end)
                    if trough_date in dd_plot.index:
                        fig_dd.add_trace(go.Scatter(
                            x=[trough_date], y=[dd_plot.loc[trough_date, 'drawdown']],
                            mode='markers+text', name=i18n.t("trace_dd_trough"),
                            marker=dict(color='#dc3545', size=12, symbol='x'),
                            text=[f'{result.max_drawdown:.2f}%'],
                            textposition='bottom center',
                            hovertemplate='%{y:.2f}%<extra></extra>'
                        ))
            except Exception:
                pass
            fig_dd.update_layout(
                title=i18n.t("chart_dd_title"),
                xaxis_title=i18n.t("axis_date"), yaxis_title=i18n.t("axis_dd_pct"),
                height=350, hovermode='x unified',
                yaxis=dict(zeroline=True, zerolinecolor='#888', zerolinewidth=1)
            )
            st.plotly_chart(fig_dd, use_container_width=True)

            # 滚动收益与滚动波动率
            st.markdown(f"### {i18n.t('rolling_title')}")
            try:
                daily_ret = equity_df['total_value'].pct_change()
                rolling_ret = (1 + daily_ret).rolling(20).apply(np.prod, raw=True) - 1
                rolling_vol = daily_ret.rolling(20).std() * np.sqrt(252)
                fig_roll = go.Figure()
                fig_roll.add_trace(go.Scatter(
                    x=rolling_ret.index, y=rolling_ret * 100,
                    mode='lines', name=i18n.t("trace_rolling_ret"),
                    line=dict(color='#28a745', width=1.5),
                    hovertemplate=f'{i18n.t("hover_date")}: %{{x}}<br>%{{y:.2f}}%<extra></extra>'
                ))
                fig_roll.add_trace(go.Scatter(
                    x=rolling_vol.index, y=rolling_vol * 100,
                    mode='lines', name=i18n.t("trace_rolling_vol"),
                    line=dict(color='#ffc107', width=1.5),
                    yaxis='y2',
                    hovertemplate=f'{i18n.t("hover_date")}: %{{x}}<br>%{{y:.2f}}%<extra></extra>'
                ))
                fig_roll.update_layout(
                    title=i18n.t("chart_rolling_title"),
                    xaxis_title=i18n.t("axis_date"),
                    yaxis=dict(title=i18n.t("axis_rolling_ret")),
                    yaxis2=dict(title=i18n.t("axis_rolling_vol"), overlaying='y', side='right'),
                    height=350, hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig_roll, use_container_width=True)
            except Exception:
                pass

            # 年度收益柱状图
            st.markdown(f"### {i18n.t('yearly_title')}")
            try:
                yearly_ret = equity_df['total_value'].resample('Y').last().pct_change().dropna() * 100
                if len(yearly_ret) > 0:
                    fig_year = go.Figure()
                    fig_year.add_trace(go.Bar(
                        x=[d.year for d in yearly_ret.index],
                        y=yearly_ret.values,
                        name=i18n.t("trace_yearly"),
                        marker_color=['#28a745' if v >= 0 else '#dc3545' for v in yearly_ret.values],
                        text=[f'{v:.2f}%' for v in yearly_ret.values],
                        textposition='outside'
                    ))
                    fig_year.update_layout(
                        title=i18n.t("chart_yearly_title"),
                        xaxis_title=i18n.t("axis_year"), yaxis_title=i18n.t("axis_return_pct"),
                        height=300, showlegend=False
                    )
                    fig_year.add_hline(y=0, line_color='#888', line_width=1)
                    st.plotly_chart(fig_year, use_container_width=True)
            except Exception:
                pass

        with heatmap_container.container():
            st.markdown(f"### {i18n.t('heatmap_title')}")

            if not equity_df.empty:
                # 优先使用 daily_stats 中预计算的 daily_return；否则现场计算
                if 'daily_return' not in equity_df.columns:
                    equity_df['daily_return'] = equity_df['total_value'].pct_change() * 100
                    equity_df['daily_return'] = equity_df['daily_return'].fillna(0)

                monthly_df = equity_df['daily_return'].resample('M').sum().reset_index()
                monthly_df['year'] = monthly_df['date'].dt.year
                monthly_df['month'] = monthly_df['date'].dt.month
                month_names = i18n.month_map()
                monthly_df['month_name'] = monthly_df['month'].map(month_names)
                monthly_df['month_name'] = pd.Categorical(monthly_df['month_name'], categories=list(month_names.values()), ordered=True)

                pivot_df = monthly_df.pivot(index='year', columns='month_name', values='daily_return')

                fig_heat = px.imshow(
                    pivot_df,
                    labels=dict(x=i18n.t("axis_month"), y=i18n.t("axis_year_only"), color=i18n.t("color_monthly_ret")),
                    color_continuous_scale='RdYlGn',
                    text_auto='.1f'
                )
                fig_heat.update_layout(height=350, xaxis_title=i18n.t("axis_month"), yaxis_title=i18n.t("axis_year_only"))
                st.plotly_chart(fig_heat, use_container_width=True)

                # 月度胜率统计
                st.markdown(f"#### {i18n.t('monthly_win_title')}")
                monthly_win = (monthly_df['daily_return'] > 0).sum()
                monthly_total = len(monthly_df)
                monthly_loss = (monthly_df['daily_return'] < 0).sum()
                best_month = monthly_df.loc[monthly_df['daily_return'].idxmax()]
                worst_month = monthly_df.loc[monthly_df['daily_return'].idxmin()]
                m_cols = st.columns(4)
                m_cols[0].metric(i18n.t("m_profit_months"), f"{monthly_win}", f"{monthly_win/monthly_total*100:.0f}%" if monthly_total > 0 else "0%")
                m_cols[1].metric(i18n.t("m_loss_months"), f"{monthly_loss}", f"{monthly_loss/monthly_total*100:.0f}%" if monthly_total > 0 else "0%")
                m_cols[2].metric(i18n.t("m_best_month"), f"{best_month['daily_return']:+.2f}%", f"{int(best_month['year'])}-{int(best_month['month'])}")
                m_cols[3].metric(i18n.t("m_worst_month"), f"{worst_month['daily_return']:+.2f}%", f"{int(worst_month['year'])}-{int(worst_month['month'])}")

        with trades_container.container():
            st.markdown(f"### {i18n.t('trades_title')}")

            if result.trades:
                trades_df = pd.DataFrame([{
                    i18n.t("tr_col_date"): t.date,
                    i18n.t("tr_col_dir"): i18n.side_label(t.direction),
                    i18n.t("tr_col_code"): t.etf_code,
                    i18n.t("tr_col_name"): t.etf_name,
                    i18n.t("tr_col_price"): t.price,
                    i18n.t("tr_col_shares"): t.shares,
                    i18n.t("tr_col_amount"): round(t.amount, 2),
                    i18n.t("tr_col_pnl"): round(t.pnl, 2),
                    i18n.t("tr_col_pnl_pct"): round(t.pnl / t.amount * 100, 2) if t.amount > 0 else 0,
                    i18n.t("tr_col_reason"): i18n.reason_label(t.reason),
                    i18n.t("tr_col_hold_days"): t.holding_days,
                } for t in result.trades])

                sell_label = i18n.t("side_sell")
                def highlight_pnl(row):
                    if row[i18n.t("tr_col_dir")] == sell_label:
                        if row[i18n.t("tr_col_pnl")] >= 0:
                            return [''] * 4 + ['background-color: #d4edda'] + [''] * 6
                        else:
                            return [''] * 4 + ['background-color: #f8d7da'] + [''] * 6
                    return [''] * len(row)

                st.dataframe(
                    trades_df.style.apply(highlight_pnl, axis=1),
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown(get_download_link(trades_df, 'trades.csv', i18n.t("export_trades")), unsafe_allow_html=True)

        st.markdown(f"### {i18n.t('batch_title')}")

        if st.button(i18n.t("btn_run_batch"), use_container_width=True):
            st.session_state.batch_results = {}

            max_positions_list = [3, 5, 8]
            thresholds = [65, 70, 75]

            total_runs = len(max_positions_list) * len(thresholds)
            current_run = 0

            batch_progress_bar = st.progress(0)
            batch_log_area = st.empty()

            start_time = time.time()
            timeout = 300

            for max_pos in max_positions_list:
                for threshold in thresholds:
                    if time.time() - start_time > timeout:
                        st.error(i18n.t("batch_timeout"))
                        break

                    current_run += 1
                    batch_progress_bar.progress(current_run / total_runs)
                    batch_log_area.text(i18n.t("batch_running", pos=max_pos, score=threshold, i=current_run, n=total_runs))

                    temp_cfg = BACKTEST_CFG.__class__(**BACKTEST_CFG.__dict__)
                    temp_cfg.max_positions = max_pos
                    temp_cfg.buy_threshold = threshold

                    backtester = ETFBacktester(temp_cfg)
                    combo_name = i18n.t("batch_combo_name", pos=max_pos, score=threshold)
                    try:
                        batch_result = backtester.run(
                            start_date.strftime("%Y-%m-%d"),
                            end_date.strftime("%Y-%m-%d")
                        )
                        st.session_state.batch_results[combo_name] = batch_result
                    except Exception as e:
                        st.warning(i18n.t("batch_combo_failed", pos=max_pos, score=threshold, err=e))

            batch_progress_bar.progress(100)
            batch_log_area.text(i18n.t("batch_done"))

        if st.session_state.batch_results:
            fig_batch = go.Figure()

            batch_summary = []

            for name, batch_result in st.session_state.batch_results.items():
                equity_df = batch_result.equity_curve
                normalized = equity_df['total_value'] / batch_result.initial_capital * 100

                if len(equity_df) > 500:
                    equity_df = equity_df.iloc[::int(len(equity_df)/500)]
                    normalized = normalized.iloc[::int(len(normalized)/500)]

                fig_batch.add_trace(go.Scatter(
                    x=equity_df.index,
                    y=normalized,
                    mode='lines',
                    name=name,
                    line=dict(width=1.5)
                ))

                batch_summary.append({
                    i18n.t("batch_col_combo"): name,
                    i18n.t("batch_col_total"): batch_result.total_return,
                    i18n.t("batch_col_annual"): batch_result.annualized_return,
                    i18n.t("batch_col_dd"): batch_result.max_drawdown,
                    i18n.t("batch_col_sharpe"): batch_result.sharpe_ratio,
                    i18n.t("batch_col_win"): batch_result.win_rate,
                    i18n.t("batch_col_trades"): batch_result.total_trades,
                })

            fig_batch.update_layout(
                title=i18n.t("batch_chart_title"),
                xaxis_title=i18n.t("axis_date"),
                yaxis_title=i18n.t("axis_return_pct"),
                height=400,
                hovermode='x unified'
            )
            st.plotly_chart(fig_batch, use_container_width=True)

            st.markdown(f"### {i18n.t('batch_table_title')}")

            summary_df = pd.DataFrame(batch_summary)
            st.dataframe(summary_df.style.highlight_max(subset=[i18n.t("batch_col_total"), i18n.t("batch_col_sharpe")]), use_container_width=True)

            st.markdown(get_download_link(summary_df, 'batch_results.csv', i18n.t("export_batch")), unsafe_allow_html=True)


def render_video_dashboard():
    """渲染视频管理页面"""
    st.markdown(f"## {i18n.t('vid_title')}")

    video_gen = FundFlowVideoGenerator()

    col1, col2 = st.columns(2)

    with col1:
        if st.button(i18n.t("btn_make_video"), use_container_width=True, type="primary"):
            st.session_state.video_progress = 0
            st.session_state.video_logs = []
            st.session_state.video_running = True

            def generate():
                try:
                    def progress_callback(percent):
                        st.session_state.video_progress = percent

                    if len(video_gen.frames) < 2:
                        st.session_state.video_logs.append(i18n.t("vid_few_frames"))
                        return

                    video_path = video_gen.generate_video(progress_callback=progress_callback)
                    st.session_state.video_progress = 100
                    st.session_state.video_logs.append(i18n.t("vid_done", path=video_path))
                except Exception as e:
                    st.session_state.video_logs.append(i18n.t("vid_failed", err=e))
                finally:
                    st.session_state.video_running = False

            thread = threading.Thread(target=generate)
            thread.start()

    with col2:
        if st.button(i18n.t("btn_clear_frames"), use_container_width=True):
            today_count = len([f for f in video_gen.frames if f['timestamp'].date() == datetime.now().date()])
            if today_count > 0:
                st.warning(i18n.t("vid_clear_warn", n=today_count))
                if st.button(i18n.t("btn_confirm_clear"), key="confirm_clear"):
                    video_gen.clear_frames()
                    st.success(i18n.t("vid_frames_cleared"))
            else:
                video_gen.clear_frames()
                st.success(i18n.t("vid_frames_cleared"))

    # 非阻塞进度面板：每秒轮询线程写入的 session_state，
    # 完成后自动整体 rerun 刷新视频列表（不再用 while+sleep 卡死主线程）
    @st.fragment(run_every=timedelta(seconds=1))
    def _video_progress_panel():
        pct = int(st.session_state.get("video_progress", 0) or 0)
        running = st.session_state.get("video_running", False)
        logs = st.session_state.get("video_logs", [])
        if running or (pct > 0 and pct < 100):
            st.progress(min(pct, 99) / 100.0,
                        text=i18n.t("vid_generating", pct=min(pct, 99)))
        elif pct >= 100:
            st.progress(1.0)
            if logs:
                st.success(logs[-1])
        elif logs:
            # 帧数不足等未启动生成的提示
            st.info(logs[-1])
        else:
            return
        # 生成刚结束：触发一次整体刷新以更新视频列表
        if not running and st.session_state.get("_video_need_full_refresh"):
            st.session_state["_video_need_full_refresh"] = False
            st.rerun()

    st.session_state["_video_need_full_refresh"] = \
        st.session_state.get("video_running", False) or \
        st.session_state.get("_video_need_full_refresh", False)
    _video_progress_panel()

    st.markdown(f"### {i18n.t('vid_list_title')}")

    filter_date = st.date_input(i18n.t("vid_filter_date"), value=None, key="video_filter_date")

    video_files = video_gen.get_video_files()

    if filter_date:
        filter_str = filter_date.strftime("%Y%m%d")
        video_files = [f for f in video_files if filter_str in f['name']]

    if video_files:
        # ===== 批量操作工具栏 =====
        st.markdown(f"#### {i18n.t('batch_ops')}")

        # 初始化选择集
        if "video_selected" not in st.session_state:
            st.session_state["video_selected"] = set()

        # 全选/取消全选
        batch_cols = st.columns([1, 1, 1, 1])
        with batch_cols[0]:
            if st.button(i18n.t("btn_select_all"), use_container_width=True):
                st.session_state["video_selected"] = set(f['name'] for f in video_files)
                st.rerun()
        with batch_cols[1]:
            if st.button(i18n.t("btn_deselect_all"), use_container_width=True):
                st.session_state["video_selected"] = set()
                st.rerun()
        with batch_cols[2]:
            selected_count = len(st.session_state["video_selected"])
            if st.button(i18n.t("btn_batch_delete", n=selected_count), use_container_width=True,
                         disabled=selected_count == 0):
                deleted = 0
                for name in list(st.session_state["video_selected"]):
                    if video_gen.delete_video(name):
                        deleted += 1
                st.session_state["video_selected"] = set()
                st.success(i18n.t("vid_deleted_n", n=deleted))
                st.rerun()
        with batch_cols[3]:
            if selected_count > 0:
                st.caption(i18n.t("vid_selected_n", n=selected_count))
            else:
                st.caption(i18n.t("vid_none_selected"))

        st.markdown("---")

        # 视频列表（带复选框）
        st.markdown(f"#### {i18n.t('vid_table_title')}")

        # 用 dataframe + 多选交互
        video_table_data = []
        for f in video_files:
            video_table_data.append({
                i18n.t("col_select"): f['name'] in st.session_state["video_selected"],
                i18n.t("col_filename"): f['name'],
                i18n.t("col_size"): f['size'],
                i18n.t("col_type"): f['type'].upper(),
                i18n.t("col_modified"): f['modified'],
                "路径": str(f['path'])
            })
        video_table_df = pd.DataFrame(video_table_data)

        select_col = i18n.t("col_select")
        filename_col = i18n.t("col_filename")
        size_col = i18n.t("col_size")
        type_col = i18n.t("col_type")
        modified_col = i18n.t("col_modified")

        # 显示表格
        edited = st.data_editor(
            video_table_df[[select_col, filename_col, size_col, type_col, modified_col]],
            use_container_width=True,
            hide_index=True,
            key="video_table_editor",
            column_config={
                select_col: st.column_config.CheckboxColumn(select_col, default=False)
            },
            height=min(400, 40 * len(video_table_df) + 50)
        )

        # 同步选择状态
        if edited is not None:
            new_selected = set()
            for _, row in edited.iterrows():
                if row[select_col]:
                    new_selected.add(row[filename_col])
            if new_selected != st.session_state["video_selected"]:
                st.session_state["video_selected"] = new_selected

        # 单个视频预览（下拉选择）
        st.markdown("---")
        st.markdown(f"#### {i18n.t('single_preview')}")
        selected_name = st.selectbox(
            i18n.t("select_video_preview"),
            [f['name'] for f in video_files],
            index=0,
            key="video_preview_select"
        )

        selected_video = next(f for f in video_files if f['name'] == selected_name)

        col_view, col_info = st.columns([3, 1])

        with col_view:
            st.markdown(f"### {i18n.t('vid_preview_title')}")
            html = video_gen.get_video_html(selected_video['path'])
            if html:
                st.markdown(html, unsafe_allow_html=True)
            else:
                st.warning(i18n.t("vid_cannot_load"))

        with col_info:
            st.markdown(f"### {i18n.t('vid_info_title')}")
            st.write(f"**{i18n.t('vid_file_name')}:** {selected_video['name']}")
            st.write(f"**{i18n.t('vid_size')}:** {selected_video['size']}")
            st.write(f"**{i18n.t('vid_type')}:** {selected_video['type'].upper()}")
            st.write(f"**{i18n.t('vid_modified')}:** {selected_video['modified']}")

            # 下载单文件
            try:
                with open(selected_video['path'], 'rb') as f:
                    video_bytes = f.read()
                st.download_button(
                    i18n.t("btn_download_video"),
                    data=video_bytes,
                    file_name=selected_video['name'],
                    mime=f"video/{selected_video['type']}",
                    use_container_width=True
                )
            except Exception as e:
                st.error(i18n.t("vid_read_failed", err=e))

            if st.button(i18n.t("btn_delete_file"), use_container_width=True):
                if video_gen.delete_video(selected_name):
                    st.success(i18n.t("vid_file_deleted"))
                    st.rerun()
                else:
                    st.error(i18n.t("vid_delete_failed"))

        # 批量下载（zip）
        st.markdown("---")
        st.markdown(f"#### {i18n.t('batch_download_title')}")
        if selected_count > 0:
            if st.button(i18n.t("btn_zip_download", n=selected_count), use_container_width=True):
                import io, zipfile
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for name in st.session_state["video_selected"]:
                        v_match = next((f for f in video_files if f['name'] == name), None)
                        if v_match and v_match['path'].exists():
                            zf.write(v_match['path'], arcname=name)
                zip_buffer.seek(0)
                st.download_button(
                    i18n.t("btn_download_zip"),
                    data=zip_buffer.getvalue(),
                    file_name=f"videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        else:
            st.caption(i18n.t("vid_zip_hint"))

        st.markdown("---")

        if st.button(i18n.t("btn_clear_all_videos"), use_container_width=True):
            if st.button(i18n.t("btn_confirm_clear_all"), key="confirm_batch_delete"):
                count = video_gen.clear_all_videos()
                st.session_state["video_selected"] = set()
                st.success(i18n.t("vid_deleted_n", n=count))
                st.rerun()

    else:
        st.info(i18n.t("vid_no_files"))

    st.markdown(f"### {i18n.t('vid_frame_status')}")

    frame_count = len(video_gen.frames)
    today_frames = len([f for f in video_gen.frames if f['timestamp'].date() == datetime.now().date()])

    col_stats1, col_stats2 = st.columns(2)
    with col_stats1:
        st.markdown(f"""
        <div style="text-align: center; background-color: #17a2b820; padding: 15px; border-radius: 10px;">
            <div style="font-size: 24px; font-weight: bold; color: #17a2b8;">{frame_count}</div>
            <div style="font-size: 12px; color: #666;">{i18n.t("vid_total_frames")}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_stats2:
        st.markdown(f"""
        <div style="text-align: center; background-color: #28a74520; padding: 15px; border-radius: 10px;">
            <div style="font-size: 24px; font-weight: bold; color: #28a745;">{today_frames}</div>
            <div style="font-size: 12px; color: #666;">{i18n.t("vid_today_frames")}</div>
        </div>
        """, unsafe_allow_html=True)


def render_dynamic_visualization_dashboard():
    """动态可视化页面：Bar Chart Race + 多面板实时分析 + 调度器状态"""
    st.markdown(f"## {i18n.t('dv_title')}")
    st.caption(i18n.t("dv_caption"))

    # ===== 调度器状态卡片 =====
    try:
        from streamlit_scheduler import get_scheduler
        sched = get_scheduler()
        status = sched.get_status()
        standalone_running = sched.is_standalone_running()

        # 心跳新鲜度
        last_hb = status.get("last_heartbeat")
        hb_seconds = None
        hb_fresh = False
        if last_hb:
            try:
                hb_seconds = (datetime.now() - datetime.fromisoformat(last_hb)).total_seconds()
                hb_fresh = hb_seconds < 120
            except Exception:
                pass
        thread_alive = status.get("thread_alive", False)
        crash_count = status.get("loop_crash_count", 0)

        st.markdown(f"### {i18n.t('dv_bg_scheduler')}")
        if standalone_running:
            st.success(i18n.t("dv_standalone_on"), icon="✅")
        s_cols = st.columns(6)
        s_cols[0].metric(
            i18n.t("m_run_status"),
            f"🟢 {i18n.t('st_running')}" if status["running"] else f"🔴 {i18n.t('st_stopped')}"
        )
        # 健康状态
        if status["running"]:
            if hb_fresh and thread_alive:
                _hb = f"🟢 {i18n.t('health_healthy')}"
            elif hb_fresh:
                _hb = f"🟡 {i18n.t('health_hb_stale_main')}"
            else:
                _hb = f"🔴 {i18n.t('health_hb_timeout')}"
        else:
            _hb = f"⚪ {i18n.t('health_not_started')}"
        s_cols[1].metric(
            i18n.t("m_health2"), _hb,
            i18n.t("hb_ago", n=int(hb_seconds)) if hb_seconds else i18n.t("hb_none")
        )
        s_cols[2].metric(i18n.t("m_today_fetches"), status["today_fetch_count"])
        s_cols[3].metric(
            i18n.t("m_signal_1430"),
            i18n.t("m_signal_yes") if status["today_signal_recorded"] else i18n.t("m_signal_no")
        )
        s_cols[4].metric(
            i18n.t("m_last_fetch"),
            status["last_fetch_time"][:19] if status["last_fetch_time"] else "—"
        )
        s_cols[5].metric(i18n.t("m_watchdog"), crash_count)

        if status["last_fetch_msg"]:
            st.info(i18n.fetch_status_msg(status["last_fetch_msg"]))
        if status.get("last_crash_msg"):
            st.warning(i18n.t("dv_last_crash",
                              time=status.get('last_crash_time', '')[:19],
                              msg=status['last_crash_msg']))

        # 控制按钮
        ctrl_cols = st.columns(3)
        with ctrl_cols[0]:
            if st.button(i18n.t("btn_pause_collect") if status["running"] else i18n.t("btn_start_collect"),
                         use_container_width=True,
                         disabled=standalone_running,
                         help=i18n.t("btn_collect_help")):
                if status["running"]:
                    sched.stop()
                else:
                    sched.start()
                st.rerun()
        with ctrl_cols[1]:
            if st.button(i18n.t("btn_fetch_once"), use_container_width=True):
                from datetime import datetime
                sched._do_fetch(datetime.now())
                st.rerun()
        with ctrl_cols[2]:
            if st.button(i18n.t("btn_clear_preview"), use_container_width=True):
                st.session_state.pop('dynamic_viz_cache', None)
                st.rerun()

        # 采集历史
        if status["history"]:
            with st.expander(i18n.t("fetch_history_title", n=min(15, len(status['history']))), expanded=False):
                hist_df = pd.DataFrame(status["history"][-15:][::-1])
                st.dataframe(hist_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(i18n.t("dv_sched_failed", err=e))

    st.markdown("---")

    # ===== 动态可视化主体 =====
    try:
        from dynamic_visualizer import DynamicVisualizer
        viz = DynamicVisualizer()
    except Exception as e:
        st.error(i18n.t("dv_viz_load_failed", err=e))
        return

    # 日期选择
    cache_dir = DATA_DIR / "fundflow_cache"
    cache_files = sorted(cache_dir.glob("*.json"), key=lambda x: x.name)
    if not cache_files:
        st.warning(i18n.t("dv_no_cache"))
        return

    available_dates = sorted({f.name[:8] for f in cache_files}, reverse=True)

    sel_cols = st.columns([2, 2, 2])
    with sel_cols[0]:
        sel_date = st.selectbox(i18n.t("dv_select_date"), options=available_dates, index=0)
    with sel_cols[1]:
        snap_limit = st.slider(i18n.t("dv_snap_limit"), min_value=10, max_value=200, value=50, step=10)
    with sel_cols[2]:
        top_n = st.slider(i18n.t("dv_top_n"), min_value=5, max_value=30, value=15, step=1)

    # 加载按钮（缓存以避免每次rerun都重新加载）
    cache_key = f"dynamic_viz_{sel_date}_{snap_limit}_{top_n}"
    if st.button(i18n.t("btn_generate"), use_container_width=True, type="primary"):
        st.session_state['dynamic_viz_cache'] = None  # 强制刷新
        st.session_state['dynamic_viz_cache_key'] = cache_key
        with st.spinner(i18n.t("dv_loading_snaps")):
            snapshots = viz.load_snapshots(date_str=sel_date, limit=snap_limit)
            summary = viz.load_summary_series(date_str=sel_date, limit=snap_limit)
            etf_scores = viz.load_etf_scores(date_str=sel_date, limit=snap_limit)
            st.session_state['dynamic_viz_cache'] = {
                'snapshots': snapshots, 'summary': summary, 'etf_scores': etf_scores,
                'date_str': sel_date,
            }
        st.success(i18n.t("dv_loaded",
                          rows=len(snapshots), points=len(summary), scores=len(etf_scores)))
        st.rerun()

    # 从缓存读取
    cache = st.session_state.get('dynamic_viz_cache')
    if cache is None or cache.get('date_str') != sel_date:
        st.info(i18n.t("dv_click_hint"))
        return

    snapshots = cache['snapshots']
    summary = cache['summary']
    etf_scores = cache['etf_scores']

    if snapshots.empty:
        st.warning(i18n.t("dv_no_snaps_date"))
        return

    # 顶部统计
    time_range = f"{snapshots['timestamp'].min():%H:%M:%S} → {snapshots['timestamp'].max():%H:%M:%S}"
    t_cols = st.columns(4)
    t_cols[0].metric(i18n.t("m_snapshots"), len(snapshots['timestamp'].unique()))
    t_cols[1].metric(i18n.t("m_time_span"), time_range.split(' → ')[0] + " ~ " + time_range.split(' → ')[-1])
    t_cols[2].metric(i18n.t("m_industries"), snapshots['industry'].nunique())
    t_cols[3].metric(
        i18n.t("m_latest_net"),
        f"{summary['total_net'].iloc[-1]:+.1f}{i18n.unit_100m()}" if not summary.empty else "—"
    )

    st.markdown("---")
    st.markdown(f"### {i18n.t('dv_industry_race')}")
    fig1 = viz.render_industry_race(snapshots, top_n=top_n)
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown(f"### {i18n.t('dv_etf_race')}")
    fig2 = viz.render_etf_score_race(etf_scores, top_n=min(top_n, 12))
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown(f"### {i18n.t('dv_close_line_title')}")
    st.caption(i18n.t("dv_close_line_caption"))
    line_cols = st.columns([2, 2, 1])
    with line_cols[0]:
        close_session = st.selectbox(
            i18n.t("dv_session"),
            options=["all", "morning", "afternoon"],
            index=0,
            format_func=lambda x: {
                "afternoon": i18n.t("sess_afternoon"),
                "morning": i18n.t("sess_morning"),
                "all": i18n.t("sess_all"),
            }.get(x, x),
            key="close_line_session"
        )
    with line_cols[2]:
        line_top_n = st.slider(i18n.t("dv_line_n"), min_value=3, max_value=20, value=10, step=1, key="line_top_n")
    fig_close_line = viz.render_intraday_close_line(snapshots, top_n=line_top_n,
                                                     session=close_session)
    st.plotly_chart(fig_close_line, use_container_width=True)

    st.markdown("---")
    st.markdown(f"### {i18n.t('dv_mainflow_title')}")
    st.caption(i18n.t("dv_mainflow_caption"))
    bar_cols = st.columns([2, 2, 1])
    with bar_cols[0]:
        session_sel = st.selectbox(
            i18n.t("dv_session"),
            options=["afternoon", "morning", "all"],
            index=0,
            format_func=lambda x: {
                "afternoon": i18n.t("sess_afternoon"),
                "morning": i18n.t("sess_morning"),
                "all": i18n.t("sess_all"),
            }.get(x, x),
            key="mainflow_session"
        )
    with bar_cols[1]:
        mainflow_top_n = st.slider(i18n.t("dv_bar_n"), min_value=5, max_value=30, value=15, step=1, key="mainflow_top_n")
    fig_mainflow = viz.render_intraday_mainflow_bar(snapshots, top_n=mainflow_top_n, session=session_sel)
    st.plotly_chart(fig_mainflow, use_container_width=True)

    st.markdown("---")
    st.markdown(f"### {i18n.t('dv_net_trend')}")
    fig3 = viz.render_net_flow_trend(summary)
    st.plotly_chart(fig3, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"### {i18n.t('dv_up_down')}")
        fig4 = viz.render_up_down_bars(summary)
        st.plotly_chart(fig4, use_container_width=True)
    with c2:
        st.markdown(f"### {i18n.t('dv_in_out')}")
        fig5 = viz.render_inflow_outflow(summary)
        st.plotly_chart(fig5, use_container_width=True)

    st.markdown("---")
    st.markdown(f"### {i18n.t('dv_make_video_title')}")
    g_cols = st.columns([3, 1])
    with g_cols[1]:
        gen_fps = st.select_slider(i18n.t("dv_fps"), options=[1, 2, 4, 8], value=2)
        if st.button(i18n.t("btn_gen_race_video"), use_container_width=True, type="primary"):
            from video_generator import FundFlowVideoGenerator
            with st.spinner(i18n.t("spinner_gen_video")):
                try:
                    gen = FundFlowVideoGenerator()
                    path = gen.generate_video_from_snapshots(snapshots, fps=gen_fps, top_n=top_n)
                    st.success(i18n.t("vid_generated"))
                    st.video(str(path))
                    with open(path, "rb") as f:
                        st.download_button(
                            i18n.t("btn_download_video2"), f, file_name=Path(path).name,
                            mime="video/mp4" if str(path).endswith(".mp4") else "image/gif"
                        )
                except Exception as e:
                    st.error(i18n.t("vid_gen_failed", err=e))


def main():
    """主函数"""
    load_session_state()

    # ===== 键盘快捷键处理（通过 query 参数触发）=====
    qp = st.query_params
    shortcut = qp.get("shortcut", "")
    if shortcut == "fetch":
        # 手动采集一次
        try:
            from streamlit_scheduler import get_scheduler
            from datetime import datetime as _dt
            sched = get_scheduler()
            with st.spinner(i18n.t("spinner_shortcut_fetch")):
                sched._do_fetch(_dt.now())
                st.toast(i18n.t("toast_sc_fetch_ok"))
        except Exception as e:
            st.error(i18n.t("sc_fetch_failed", err=e))
        # 清除参数避免重复触发
        del qp["shortcut"]
    elif shortcut == "dark":
        st.session_state.dark_mode = not st.session_state.get("dark_mode", False)
        st.toast(i18n.t("toast_sc_theme",
                        mode=i18n.t("theme_dark" if st.session_state.dark_mode else "theme_light")))
        del qp["shortcut"]
    elif shortcut == "backtest":
        # 立即运行自动回测（独立调度器入口）
        try:
            from streamlit_scheduler import get_scheduler
            sched = get_scheduler()
            with st.spinner(i18n.t("spinner_sc_bt")):
                sched.run_backtest_manually()
                st.toast(i18n.t("toast_sc_bt_ok"))
        except Exception as e:
            st.error(i18n.t("sc_bt_failed", err=e))
        del qp["shortcut"]

    # 注入全局美化 CSS
    inject_custom_css()

    # 注入键盘快捷键监听（通过修改 URL 触发 query 参数）
    inject_keyboard_shortcuts()

    render_sidebar()

    # 确保后台调度器在运行（自动采集 5 分钟 + 14:30 信号记录）
    sched_status = None
    standalone_running = None
    try:
        from streamlit_scheduler import get_scheduler
        sched = get_scheduler()
        standalone_running = sched.is_standalone_running()
        if not standalone_running and not sched.status["running"]:
            sched.start(standalone=False)
        sched_status = sched.get_status()
    except Exception as e:
        st.warning(i18n.t("sched_start_failed", err=e))

    # 渲染顶部 Hero 区域
    render_header(sched_status=sched_status, standalone_running=standalone_running)

    tab1, tab2, tab3, tab4 = st.tabs([
        i18n.t("tab_realtime"), i18n.t("tab_visual"),
        i18n.t("tab_video"), i18n.t("tab_backtest")
    ])

    with tab1:
        st.session_state.last_tab = "实时资金流"
        render_real_time_dashboard()

    with tab2:
        st.session_state.last_tab = "动态可视化"
        render_dynamic_visualization_dashboard()

    with tab3:
        st.session_state.last_tab = "视频管理"
        render_video_dashboard()

    with tab4:
        st.session_state.last_tab = "ETF回测"
        render_backtest_dashboard()

    # 页脚
    st.markdown(f"""
    <div style="text-align: center; padding: 20px 0; color: #9ca3af; font-size: 0.78rem; border-top: 1px solid #e5e7eb; margin-top: 40px;">
        {i18n.t("footer")}
    </div>
    """, unsafe_allow_html=True)

    save_session_state()


if __name__ == "__main__":
    main()