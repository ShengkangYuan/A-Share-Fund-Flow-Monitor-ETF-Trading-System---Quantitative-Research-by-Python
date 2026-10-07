"""
动态可视化模块 - Bar Chart Race 风格
功能：
1. 从 fundflow_cache 读取5分钟间隔的快照
2. 生成 Bar Chart Race 风格的动态条形图（plotly animation_frame）
3. 多面板：行业资金排名 + ETF评分 + 净流入趋势 + 涨跌家数
4. 用于 Streamlit 内嵌展示
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

from config import DATA_DIR
from fundflow_fetcher import FundFlowFetcher
from etf_fetcher import IndustryETFMapper
from flow_analyzer import FlowAnalyzer, SignalGenerator
import i18n

logger = logging.getLogger(__name__)

# ============================================================
# 统一图表主题（与 dashboard CSS 色系一致）
# ============================================================
CHART_FONT = dict(family="Inter, 'Microsoft YaHei', 'PingFang SC', sans-serif",
                  size=12, color="#374151")
CHART_GRID = "#eef2f7"
CHART_ZEROLINE = "#cbd5e1"
# 多行业线条的区分色板（10 色，色相差异大，深浅兼顾）
LINE_PALETTE = [
    "#2563eb", "#0d9488", "#7c3aed", "#ea580c", "#db2777",
    "#0891b2", "#65a30d", "#ca8a04", "#dc2626", "#4f46e5",
    "#059669", "#9333ea", "#c2410c", "#0284c7", "#be185d",
]


def _apply_theme(fig: go.Figure, height: int = 450, top: int = 70,
                 bottom: int = 60, left: int = 70, right: int = 24) -> go.Figure:
    """给图表统一应用字体/背景/网格/悬浮提示/外边距主题。"""
    fig.update_layout(
        font=CHART_FONT,
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(t=top, b=bottom, l=left, r=right),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#d1d5db",
            font=dict(family=CHART_FONT["family"], size=12, color="#1f2937"),
        ),
    )
    axis_common = dict(
        gridcolor=CHART_GRID,
        zerolinecolor=CHART_ZEROLINE,
        linecolor="#d1d5db",
        tickfont=dict(size=11, color="#6b7280"),
        title_font=dict(size=12, color="#374151"),
    )
    fig.update_xaxes(**axis_common)
    fig.update_yaxes(**axis_common)
    return fig


def _sample_time_points(points, max_frames: int = 64):
    """时间点过多时等距抽样（始终保留首末帧），保证动画流畅。"""
    pts = list(points)
    n = len(pts)
    if n <= max_frames:
        return pts
    step = (n - 1) / (max_frames - 1)
    idx = sorted({int(round(i * step)) for i in range(max_frames)})
    if n - 1 not in idx:
        idx[-1] = n - 1
    return [pts[i] for i in idx]


def _style_play_buttons(extra_pad_top: int = 55) -> list:
    """统一样式的 Plotly 动画 播放/暂停 按钮。"""
    return [{
        "type": "buttons",
        "buttons": [
            {
                "label": "▶  " + i18n.t("btn_play"),
                "method": "animate",
                "args": [None, {"frame": {"duration": 600, "redraw": False},
                                "fromcurrent": True,
                                "transition": {"duration": 300}}],
            },
            {
                "label": "⏸  " + i18n.t("btn_pause_anim"),
                "method": "animate",
                "args": [[None], {"frame": {"duration": 0, "redraw": False},
                                  "mode": "immediate"}],
            },
        ],
        "direction": "right",
        "showactive": False,
        "x": 0.0, "xanchor": "left",
        "y": 0.0, "yanchor": "bottom",
        "pad": {"t": extra_pad_top, "b": 6, "l": 4},
        "font": {"size": 12, "color": "#1f2937"},
        "bgcolor": "#f3f4f6",
        "bordercolor": "#d1d5db",
        "borderwidth": 1,
    }]



class DynamicVisualizer:
    """Bar Chart Race 风格动态可视化生成器"""

    def __init__(self):
        self.fetcher = FundFlowFetcher()
        self.mapper = IndustryETFMapper()
        self.analyzer = FlowAnalyzer()
        self.signal_gen = SignalGenerator(self.mapper)
        self.cache_dir = DATA_DIR / "fundflow_cache"

    # ===== 数据加载 =====
    def load_snapshots(self, date_str: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """
        加载快照数据，返回 long-format DataFrame
        每行: timestamp, industry, net_flow, inflow, outflow, change_pct
        """
        if date_str:
            files = sorted(self.cache_dir.glob(f"{date_str}_*.json"))
        else:
            files = sorted(self.cache_dir.glob("*.json"), key=lambda x: x.stat().st_mtime)

        if limit and len(files) > limit:
            files = files[-limit:]

        records = []
        for f in files:
            try:
                df = pd.read_json(f)
                if df.empty:
                    continue
                ts_str = f.name[:15]  # YYYYMMDD_HHMMSS
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")

                col_industry = '行业' if '行业' in df.columns else 'industry'
                col_net = '净额' if '净额' in df.columns else 'net_flow'
                col_in = '流入资金' if '流入资金' in df.columns else 'inflow'
                col_out = '流出资金' if '流出资金' in df.columns else 'outflow'
                col_change = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'

                for _, row in df.iterrows():
                    records.append({
                        'timestamp': ts,
                        'time_str': ts.strftime('%H:%M:%S'),
                        'date_str': ts.strftime('%Y-%m-%d'),
                        'snapshot': '_snapshot' in f.name,
                        'industry': str(row[col_industry]),
                        'net_flow': float(row[col_net]) if pd.notna(row[col_net]) else 0,
                        'inflow': float(row[col_in]) if pd.notna(row[col_in]) else 0,
                        'outflow': float(row[col_out]) if pd.notna(row[col_out]) else 0,
                        'change_pct': float(row[col_change]) if pd.notna(row[col_change]) else 0,
                    })
            except Exception as e:
                logger.warning(f"读取快照 {f.name} 失败: {e}")
                continue

        if not records:
            return pd.DataFrame()
        out = pd.DataFrame(records)
        # 展示层行业名翻译（zh 模式 tr_industry 原样返回）
        out['industry'] = out['industry'].map(i18n.tr_industry)
        return out

    def load_summary_series(self, date_str: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """加载每个快照的汇总指标时序"""
        df = self.load_snapshots(date_str, limit)
        if df.empty:
            return df
        agg = df.groupby(['timestamp', 'time_str', 'date_str', 'snapshot']).agg(
            total_net=('net_flow', 'sum'),
            total_inflow=('inflow', 'sum'),
            total_outflow=('outflow', 'sum'),
            positive_count=('net_flow', lambda x: (x > 0).sum()),
            negative_count=('net_flow', lambda x: (x < 0).sum()),
        ).reset_index()
        return agg

    def load_etf_scores(self, date_str: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """加载每个快照对应的 ETF 评分时序"""
        if date_str:
            files = sorted(self.cache_dir.glob(f"{date_str}_*.json"))
        else:
            files = sorted(self.cache_dir.glob("*.json"), key=lambda x: x.stat().st_mtime)

        if limit and len(files) > limit:
            files = files[-limit:]

        records = []
        for f in files:
            try:
                df = pd.read_json(f)
                if df.empty:
                    continue
                ts_str = f.name[:15]
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")

                ranked = self.analyzer.rank_industries(df)
                ranked = self.analyzer.calc_inflow_ratio(ranked)
                etf_df = self.mapper.map_industry_flow_to_etf(ranked)
                if etf_df.empty:
                    continue
                etf_df['score'] = self.signal_gen.score_etf(etf_df)

                for _, row in etf_df.iterrows():
                    records.append({
                        'timestamp': ts,
                        'time_str': ts.strftime('%H:%M:%S'),
                        'date_str': ts.strftime('%Y-%m-%d'),
                        'etf_code': row['etf_code'],
                        'etf_name': row['etf_name'],
                        'score': float(row['score']) if pd.notna(row['score']) else 0,
                        'net_flow': float(row['net_flow']) if pd.notna(row['net_flow']) else 0,
                    })
            except Exception as e:
                logger.warning(f"ETF评分计算失败 {f.name}: {e}")
                continue

        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    # ===== Bar Chart Race - 行业资金排名 =====
    def render_industry_race(self, snapshots_df: pd.DataFrame, top_n: int = 15) -> go.Figure:
        """
        行业资金排名 Bar Chart Race
        每帧展示 top_n 行业的净流入排名，按时间自动播放
        """
        if snapshots_df.empty:
            return go.Figure()

        # 仅保留连续竞价时段快照，剔除盘前/盘后调度器采到的重复帧
        _hm = snapshots_df['timestamp'].dt.hour * 100 \
            + snapshots_df['timestamp'].dt.minute
        snapshots_df = snapshots_df[
            ((_hm >= 925) & (_hm <= 1135)) | ((_hm >= 1255) & (_hm <= 1505))
        ]
        if snapshots_df.empty:
            return _apply_theme(go.Figure(), height=420)

        # 帧过多时等距抽样，保证动画流畅
        keep_ts = set(_sample_time_points(sorted(snapshots_df['timestamp'].unique()), 64))
        snapshots_df = snapshots_df[snapshots_df['timestamp'].isin(keep_ts)]

        # 每个时间点取 top_n
        frames_data = []
        for ts, group in snapshots_df.groupby('timestamp'):
            top = group.nlargest(top_n, 'net_flow')
            top = top.sort_values('net_flow', ascending=True)  # 横向条形图升序
            for _, row in top.iterrows():
                frames_data.append({
                    'timestamp': ts,
                    'time_str': row['time_str'],
                    'industry': row['industry'],
                    'net_flow': row['net_flow'],
                    'change_pct': row['change_pct'],
                })

        race_df = pd.DataFrame(frames_data)
        if race_df.empty:
            return go.Figure()

        # 用 plotly express animation_frame
        fig = px.bar(
            race_df,
            y='industry', x='net_flow',
            color='net_flow',
            animation_frame='time_str',
            orientation='h',
            range_x=[race_df['net_flow'].min() * 1.1 if race_df['net_flow'].min() < 0 else 0,
                     race_df['net_flow'].max() * 1.1],
            color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
            labels={'net_flow': i18n.t('chg_netflow_yi'), 'industry': i18n.t('chart_industry'), 'time_str': i18n.t('chg_time')},
            title=i18n.t('race_industry_title', n=top_n),
        )
        _apply_theme(fig, height=620, top=86, bottom=108, left=130, right=80)
        fig.update_layout(
            xaxis_title=i18n.t('chg_netflow_yi'),
            yaxis_title='',
            yaxis=dict(autorange=False),
            title=dict(x=0.01, y=0.98, xanchor='left', yanchor='top',
                       font=dict(size=15, color="#111827")),
            transition={'duration': 500, 'easing': 'cubic-in-out'},
            coloraxis_colorbar=dict(
                title=i18n.t('colorbar_net'), thickness=12, len=0.85,
                tickfont=dict(size=10, color="#6b7280"),
                title_font=dict(size=11, color="#374151"),
            ),
        )
        fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 800
        fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 400
        fig.layout.updatemenus[0].bgcolor = "#f3f4f6"
        fig.layout.updatemenus[0].bordercolor = "#d1d5db"
        return fig

    # ===== Bar Chart Race - ETF 评分 =====
    def render_etf_score_race(self, etf_df: pd.DataFrame, top_n: int = 12) -> go.Figure:
        """ETF 评分 Bar Chart Race"""
        if etf_df.empty:
            return go.Figure()

        # 仅保留连续竞价时段快照，剔除盘前/盘后重复帧
        _hm = etf_df['timestamp'].dt.hour * 100 + etf_df['timestamp'].dt.minute
        etf_df = etf_df[
            ((_hm >= 925) & (_hm <= 1135)) | ((_hm >= 1255) & (_hm <= 1505))
        ]
        if etf_df.empty:
            return _apply_theme(go.Figure(), height=420)

        # 帧过多时等距抽样，保证动画流畅
        keep_ts = set(_sample_time_points(sorted(etf_df['timestamp'].unique()), 64))
        etf_df = etf_df[etf_df['timestamp'].isin(keep_ts)]

        frames_data = []
        for ts, group in etf_df.groupby('timestamp'):
            top = group.nlargest(top_n, 'score').sort_values('score', ascending=True)
            for _, row in top.iterrows():
                frames_data.append({
                    'time_str': row['time_str'],
                    'etf_name': row['etf_name'],
                    'score': row['score'],
                    'net_flow': row['net_flow'],
                })

        race_df = pd.DataFrame(frames_data)
        if race_df.empty:
            return go.Figure()

        fig = px.bar(
            race_df,
            y='etf_name', x='score',
            color='score',
            animation_frame='time_str',
            orientation='h',
            range_x=[0, 100],
            color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
            labels={'score': i18n.t('chg_score'), 'etf_name': i18n.t('chg_etf'), 'time_str': i18n.t('chg_time')},
            title=i18n.t('race_etf_title', n=top_n),
        )
        _apply_theme(fig, height=620, top=86, bottom=108, left=150, right=80)
        fig.update_layout(
            xaxis_title=i18n.t('chg_score'),
            yaxis_title='',
            yaxis=dict(autorange=False),
            title=dict(x=0.01, y=0.98, xanchor='left', yanchor='top',
                       font=dict(size=15, color="#111827")),
            transition={'duration': 500, 'easing': 'cubic-in-out'},
            coloraxis_colorbar=dict(
                title=i18n.t('colorbar_score'), thickness=12, len=0.85,
                tickfont=dict(size=10, color="#6b7280"),
                title_font=dict(size=11, color="#374151"),
            ),
        )
        fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 800
        fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 400
        fig.layout.updatemenus[0].bgcolor = "#f3f4f6"
        fig.layout.updatemenus[0].bordercolor = "#d1d5db"
        return fig

    # ===== 净流入趋势线 =====
    def render_net_flow_trend(self, summary_df: pd.DataFrame) -> go.Figure:
        """全市场净流入趋势线"""
        if summary_df.empty:
            return _apply_theme(go.Figure(), height=360)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=summary_df['time_str'], y=summary_df['total_net'],
            mode='lines+markers', name=i18n.t('netflow_trace'),
            line=dict(color='#2563eb', width=2.4),
            marker=dict(size=6, color='#2563eb',
                        line=dict(width=1, color="white")),
            fill='tozeroy',
            fillcolor='rgba(37, 99, 235, 0.12)',
        ))
        _apply_theme(fig, height=400, top=56, bottom=56)
        fig.update_layout(
            title=dict(text=i18n.t('trend_live_title'), x=0.015, y=0.96,
                       xanchor='left', yanchor='top',
                       font=dict(size=15, color="#111827")),
            xaxis_title=i18n.t('chg_time'), yaxis_title=i18n.t('chg_netflow_yi'),
            hovermode='x unified',
            xaxis=dict(tickangle=-30, nticks=14),
            showlegend=False,
        )
        return fig

    # ===== 涨跌家数对比 =====
    def render_up_down_bars(self, summary_df: pd.DataFrame) -> go.Figure:
        """涨跌行业家数对比"""
        if summary_df.empty:
            return _apply_theme(go.Figure(), height=340)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=summary_df['time_str'], y=summary_df['positive_count'],
            name=i18n.t('up'), marker_color='#16a34a',
            marker_line_width=0, opacity=0.92,
        ))
        fig.add_trace(go.Bar(
            x=summary_df['time_str'], y=-summary_df['negative_count'],
            name=i18n.t('down'), marker_color='#dc2626',
            marker_line_width=0, opacity=0.92,
        ))
        _apply_theme(fig, height=380, top=84, bottom=56)
        fig.update_layout(
            title=dict(text=i18n.t('chart_updown_title'), x=0.015, y=0.97,
                       xanchor='left', yanchor='top',
                       font=dict(size=14, color="#111827")),
            xaxis_title=i18n.t('chg_time'), yaxis_title=i18n.t('axis_count'),
            barmode='relative',
            hovermode='x unified',
            xaxis=dict(tickangle=-30, nticks=12),
            legend=dict(orientation='h', x=0.01, xanchor='left',
                        y=0.97, yanchor='top', bgcolor='rgba(0,0,0,0)'),
            bargap=0.25,
        )
        return fig

    # ===== 流入流出对比 =====
    def render_inflow_outflow(self, summary_df: pd.DataFrame) -> go.Figure:
        """流入流出资金对比"""
        if summary_df.empty:
            return _apply_theme(go.Figure(), height=340)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=summary_df['time_str'], y=summary_df['total_inflow'],
            name=i18n.t('inflow_word'), marker_color='#16a34a',
            marker_line_width=0, opacity=0.92,
        ))
        fig.add_trace(go.Bar(
            x=summary_df['time_str'], y=summary_df['total_outflow'],
            name=i18n.t('outflow_word'), marker_color='#dc2626',
            marker_line_width=0, opacity=0.92,
        ))
        _apply_theme(fig, height=380, top=84, bottom=56)
        fig.update_layout(
            title=dict(text=i18n.t('chart_inout_title'), x=0.015, y=0.97,
                       xanchor='left', yanchor='top',
                       font=dict(size=14, color="#111827")),
            xaxis_title=i18n.t('chg_time'), yaxis_title=i18n.t('axis_amount_yi'),
            barmode='group',
            hovermode='x unified',
            xaxis=dict(tickangle=-30, nticks=12),
            legend=dict(orientation='h', x=0.01, xanchor='left',
                        y=0.97, yanchor='top', bgcolor='rgba(0,0,0,0)'),
            bargap=0.25, bargroupgap=0.08,
        )
        return fig

    # ===== 单日收盘资金流向动态线图 =====
    def render_intraday_close_line(self, snapshots_df: pd.DataFrame, top_n: int = 10,
                                   session: str = "all") -> go.Figure:
        """
        单日收盘资金流向动态线图
        - X 轴：采集时间点（按时间推进）
        - Y 轴：累计净流入金额
        - 多条线代表 TOP N 行业，行业配色固定
        - 每帧添加一个新时间点，线条随之延伸（类似实时心电图）
        - session: morning 9:30-11:30 / afternoon 13:00-15:00 / all 全部快照
        """
        if snapshots_df.empty:
            return _apply_theme(go.Figure(), height=420)

        # 确保时间排序
        df = snapshots_df.copy().sort_values('timestamp')

        # 交易时段过滤：all=上午+下午两个连续竞价时段（剔除盘前/盘后调度快照）
        hm = df['timestamp'].dt.hour * 100 + df['timestamp'].dt.minute
        if session == "morning":
            df = df[(hm >= 925) & (hm <= 1135)]
        elif session == "afternoon":
            df = df[(hm >= 1255) & (hm <= 1505)]
        else:
            df = df[((hm >= 925) & (hm <= 1135)) | ((hm >= 1255) & (hm <= 1505))]

        if df.empty:
            fig = go.Figure()
            _apply_theme(fig, height=420)
            fig.update_layout(
                title=i18n.t("mainflow_empty_title",
                             sess=i18n.t({"morning": "sess_morning",
                                          "afternoon": "sess_afternoon",
                                          "all": "sess_all"}[session])),
                annotations=[{"text": i18n.t("no_snap_in_session"),
                              "showarrow": False, "font": {"size": 15, "color": "#9ca3af"}}],
            )
            return fig

        # 选出当日累计净流入排名 TOP N 的行业（按当日最终值）
        final = df.groupby('industry')['net_flow'].last().sort_values(ascending=False)
        top_industries = final.head(top_n).index.tolist()
        color_map = {ind: LINE_PALETTE[i % len(LINE_PALETTE)]
                     for i, ind in enumerate(top_industries)}

        # 构造透视表：行=时间点，列=行业，值=累计净流入
        pivot = df[df['industry'].isin(top_industries)].pivot_table(
            index=['timestamp', 'time_str'],
            columns='industry',
            values='net_flow',
            aggfunc='sum'
        ).fillna(0)

        # 累计求和（资金流向累计）
        cum = pivot.cumsum()
        # 帧过多时等距抽样，保证播放流畅（帧内仍展示截至该时点的完整延伸）
        frame_ts = _sample_time_points(cum.index.tolist(), 64)

        def _trace(ind, x, y):
            c = color_map[ind]
            return go.Scatter(
                x=x, y=y,
                mode='lines+markers',
                name=ind,
                line=dict(width=2.4, color=c),
                marker=dict(size=5, color=c,
                            line=dict(width=1, color="white")),
                hovertemplate=(f'<b>{ind}</b><br>'
                               + i18n.t('hover_cum_net') + '<extra></extra>'),
            )

        # 动画帧：每帧新增一个时间点
        frames = []
        pos = {ts: i for i, ts in enumerate(cum.index)}
        for ts in frame_ts:
            sub = cum.iloc[:pos[ts] + 1]
            x_vals = sub.index.get_level_values('time_str')
            frames.append(go.Frame(
                data=[_trace(ind, x_vals, sub[ind])
                      for ind in top_industries if ind in sub.columns],
                name=ts[1],
            ))

        # 初始帧
        first_row = cum.iloc[:1]
        initial_data = [
            _trace(ind, first_row.index.get_level_values('time_str'), first_row[ind])
            for ind in top_industries if ind in first_row.columns
        ]

        fig = go.Figure(data=initial_data, frames=frames)
        _apply_theme(fig, height=580, top=108, bottom=118, left=72, right=20)
        fig.update_layout(
            title=dict(
                text=i18n.t('close_line_title', n=top_n),
                x=0.015, y=0.985, xanchor='left', yanchor='top',
                font=dict(size=15, color="#111827"),
            ),
            xaxis_title=i18n.t('axis_fetch_time'),
            yaxis_title=i18n.t('axis_cum_net'),
            hovermode='x unified',
            # 图例：顶部横向、固定 entry 宽度自动换行，与标题分层不重叠
            legend=dict(
                orientation='h',
                x=0.01, xanchor='left',
                y=0.945, yanchor='top',
                entrywidth=155, entrywidthmode='pixels',
                itemwidth=30, itemsizing='constant',
                bgcolor='rgba(0,0,0,0)',
                font=dict(size=11.5, color="#374151"),
            ),
            xaxis=dict(tickangle=-32, nticks=12, showspikes=True,
                       spikemode='across', spikecolor="#cbd5e1",
                       spikethickness=1, spikedash='dot'),
            yaxis=dict(showspikes=False),
            updatemenus=_style_play_buttons(extra_pad_top=52),
            sliders=[{
                "active": 0,
                "steps": [
                    {"label": ts[1], "method": "animate",
                     "args": [[ts[1]], {"frame": {"duration": 300, "redraw": False},
                                         "mode": "immediate"}]}
                    for ts in frame_ts
                ],
                "currentvalue": {
                    "visible": True,
                    "prefix": i18n.t("slider_time_prefix") + " ",
                    "xanchor": "right",
                    "font": {"size": 12, "color": "#1f2937"},
                },
                "pad": {"b": 6, "t": 34},
                "bgcolor": "#f8fafc",
                "bordercolor": "#e5e7eb",
                "borderwidth": 1,
                "tickcolor": "#9ca3af",
                "font": {"size": 10, "color": "#6b7280"},
                "minorticklen": 2,
            }],
        )
        return fig

    # ===== 单日午盘主力资金流向动态柱状图 =====
    def render_intraday_mainflow_bar(self, snapshots_df: pd.DataFrame, top_n: int = 15,
                                      session: str = "afternoon") -> go.Figure:
        """
        单日午盘主力资金流向动态柱状图
        - X 轴：行业（TOP N）
        - Y 轴：当前净流入金额
        - 每帧更新柱状图，按时间推进
        - session: "morning" 上午盘 9:30-11:30 / "afternoon" 下午盘 13:00-15:00 / "all" 全天
        """
        if snapshots_df.empty:
            return _apply_theme(go.Figure(), height=420)

        df = snapshots_df.copy()

        # 提取时间用于过滤
        df['hour'] = df['timestamp'].dt.hour
        df['minute'] = df['timestamp'].dt.minute
        df['hm'] = df['hour'] * 100 + df['minute']

        if session == "morning":
            df = df[(df['hm'] >= 925) & (df['hm'] <= 1135)]
            session_label = i18n.t("sess_morning")
        elif session == "afternoon":
            df = df[(df['hm'] >= 1255) & (df['hm'] <= 1505)]
            session_label = i18n.t("sess_afternoon")
        else:
            # all=上午+下午两个连续竞价时段（剔除盘前/盘后调度快照）
            df = df[((df['hm'] >= 925) & (df['hm'] <= 1135))
                    | ((df['hm'] >= 1255) & (df['hm'] <= 1505))]
            session_label = i18n.t("sess_all")

        if df.empty:
            fig = go.Figure()
            _apply_theme(fig, height=420)
            fig.update_layout(
                title=dict(text=i18n.t('mainflow_empty_title', sess=session_label),
                           x=0.015, y=0.97, xanchor='left', yanchor='top',
                           font=dict(size=15, color="#111827")),
                annotations=[{"text": i18n.t("no_snap_in_session"),
                              "showarrow": False,
                              "font": {"size": 15, "color": "#9ca3af"}}]
            )
            return fig

        # 每个时间点取 TOP N（按净流入绝对值排序），帧过多时抽样
        time_points = _sample_time_points(sorted(df['timestamp'].unique()), 64)
        frames_data = []
        for ts in time_points:
            group = df[df['timestamp'] == ts]
            # 主力：按净流入排序
            top = group.nlargest(top_n, 'net_flow').sort_values('net_flow', ascending=True)
            time_str = top['time_str'].iloc[0] if not top.empty else ""
            for _, row in top.iterrows():
                frames_data.append({
                    'time_str': time_str,
                    'industry': row['industry'],
                    'net_flow': row['net_flow'],
                    'change_pct': row['change_pct'],
                })

        race_df = pd.DataFrame(frames_data)
        if race_df.empty:
            return _apply_theme(go.Figure(), height=420)

        # 计算固定的 Y 轴范围（避免动画过程中跳动）
        y_min = race_df['net_flow'].min() * 1.1 if race_df['net_flow'].min() < 0 else 0
        y_max = race_df['net_flow'].max() * 1.1

        # 使用 plotly express animation_frame
        fig = px.bar(
            race_df,
            y='industry', x='net_flow',
            color='net_flow',
            animation_frame='time_str',
            orientation='h',
            range_x=[y_min, y_max],
            color_continuous_scale=['#dc2626', '#f59e0b', '#16a34a'],
            labels={'net_flow': i18n.t('chg_netflow_yi'), 'industry': i18n.t('chart_industry'), 'time_str': i18n.t('chg_time')},
            title=i18n.t('mainflow_title', sess=session_label, n=top_n),
            hover_data={'change_pct': ':.2f'}
        )
        _apply_theme(fig, height=620, top=86, bottom=108, left=130, right=80)
        fig.update_layout(
            xaxis_title=i18n.t('chg_netflow_yi'),
            yaxis_title='',
            yaxis=dict(autorange=False),
            title=dict(x=0.01, y=0.98, xanchor='left', yanchor='top',
                       font=dict(size=15, color="#111827")),
            transition={'duration': 400, 'easing': 'cubic-in-out'},
            coloraxis_colorbar=dict(
                title=i18n.t('colorbar_net'), thickness=12, len=0.85,
                tickfont=dict(size=10, color="#6b7280"),
                title_font=dict(size=11, color="#374151"),
            ),
        )
        fig.layout.sliders[0].bgcolor = "#f8fafc"
        fig.layout.sliders[0].bordercolor = "#e5e7eb"
        fig.layout.sliders[0].tickcolor = "#9ca3af"
        fig.layout.sliders[0].font = {"size": 10, "color": "#6b7280"}
        fig.layout.sliders[0].currentvalue = {
            "visible": True,
            "prefix": i18n.t("slider_time_prefix") + " ",
            "xanchor": "right",
            "font": {"size": 12, "color": "#1f2937"},
        }
        fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 700
        fig.layout.updatemenus[0].buttons[0].args[1]['frame']['redraw'] = False
        fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 300
        fig.layout.updatemenus[0].bgcolor = "#f3f4f6"
        fig.layout.updatemenus[0].bordercolor = "#d1d5db"
        fig.layout.updatemenus[0].direction = "right"
        fig.layout.updatemenus[0].x = 0.01
        fig.layout.updatemenus[0].xanchor = "left"
        fig.layout.updatemenus[0].pad = {"t": 38, "b": 6}
        return fig

    # ===== 综合仪表盘 =====
    def render_full_dashboard(self, date_str: Optional[str] = None, limit: int = 60) -> Dict[str, go.Figure]:
        """生成全套动态图表"""
        snapshots = self.load_snapshots(date_str, limit)
        summary = self.load_summary_series(date_str, limit)
        etf_scores = self.load_etf_scores(date_str, limit)

        return {
            'industry_race': self.render_industry_race(snapshots),
            'etf_score_race': self.render_etf_score_race(etf_scores),
            'net_flow_trend': self.render_net_flow_trend(summary),
            'up_down_bars': self.render_up_down_bars(summary),
            'inflow_outflow': self.render_inflow_outflow(summary),
            'snapshots_count': len(snapshots),
            'time_range': (
                snapshots['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S'),
                snapshots['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S'),
            ) if not snapshots.empty else None,
        }


if __name__ == "__main__":
    viz = DynamicVisualizer()
    print("Loading snapshots...")
    snap = viz.load_snapshots(limit=20)
    print(f"Snapshots: {len(snap)}, span: {snap['timestamp'].min() if not snap.empty else 'N/A'} ~ {snap['timestamp'].max() if not snap.empty else 'N/A'}")

    if not snap.empty:
        print("\nGenerating Bar Chart Race...")
        fig = viz.render_industry_race(snap)
        print(f"Chart frames: {len(fig.frames)}")

    print("\nGenerating ETF score Race...")
    etf_df = viz.load_etf_scores(limit=20)
    if not etf_df.empty:
        fig2 = viz.render_etf_score_race(etf_df)
        print(f"ETF score chart frames: {len(fig2.frames)}")
