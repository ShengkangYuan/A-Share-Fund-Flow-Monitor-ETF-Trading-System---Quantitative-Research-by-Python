"""
可视化模块 - 独立的可视化图表生成
支持：资金流向图、ETF信号图、热力图、导出为HTML/PNG
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from typing import Optional, List, Tuple

from config import REPORTS_DIR
from flow_analyzer import TradeSignal


class Visualizer:
    """可视化工具"""

    @staticmethod
    def plot_industry_flow(df: pd.DataFrame, top_n: int = 15,
                           save_path: Optional[str] = None) -> go.Figure:
        """
        行业资金流向条形图（流入/流出分开显示）
        Args:
            df: 行业资金流数据
            top_n: 显示前N个
            save_path: 保存HTML路径，不填则返回figure
        """
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_ind = '行业' if '行业' in df.columns else 'industry'
        col_chg = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'

        top_in = df.nlargest(top_n, col_net)
        top_out = df.nsmallest(top_n, col_net)
        plot_df = pd.concat([top_in, top_out])

        colors = ['#e74c3c' if v < 0 else '#2ecc71' for v in plot_df[col_net]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=plot_df[col_net],
            y=plot_df[col_ind],
            orientation='h',
            marker_color=colors,
            text=[f"{v:+.1f}亿" for v in plot_df[col_net]],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>净流入: %{x:.2f}亿<br>涨跌幅: %{customdata:.2f}%<extra></extra>',
            customdata=plot_df[col_chg],
        ))

        fig.update_layout(
            title=dict(
                text=f"行业资金净流入/流出 TOP {top_n}",
                font=dict(size=16),
            ),
            xaxis=dict(title="净流入 (亿元)", gridcolor='#f0f0f0'),
            yaxis=dict(title="", autorange="reversed"),
            height=500,
            template="plotly_white",
            margin=dict(l=10, r=60, t=50, b=10),
            hoverlabel=dict(bgcolor="white", font_size=12),
        )

        if save_path:
            fig.write_html(save_path)
        return fig

    @staticmethod
    def plot_flow_vs_change(df: pd.DataFrame, save_path: Optional[str] = None) -> go.Figure:
        """资金流 vs 涨跌幅散点图（四象限分析）"""
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_chg = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'
        col_ind = '行业' if '行业' in df.columns else 'industry'

        # 四象限分类
        df = df.copy()
        df['象限'] = '其他'
        df.loc[(df[col_net] > 0) & (df[col_chg] > 0), '象限'] = '量价齐升 🟢'
        df.loc[(df[col_net] > 0) & (df[col_chg] < 0), '象限'] = '资金抄底 🔵'
        df.loc[(df[col_net] < 0) & (df[col_chg] > 0), '象限'] = '资金流出 📉'
        df.loc[(df[col_net] < 0) & (df[col_chg] < 0), '象限'] = '量价齐跌 🔴'

        colors = {'量价齐升 🟢': '#2ecc71', '资金抄底 🔵': '#3498db',
                  '资金流出 📉': '#f39c12', '量价齐跌 🔴': '#e74c3c', '其他': '#95a5a6'}

        fig = px.scatter(
            df, x=col_chg, y=col_net,
            text=col_ind, color='象限',
            color_discrete_map=colors,
            size=col_net, size_max=80,
            title="行业资金流四象限分析",
            labels={col_chg: '涨跌幅 (%)', col_net: '资金净流入 (亿)'},
            height=500,
        )

        # 象限分割线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_traces(
            textposition='top center',
            textfont=dict(size=9),
            marker=dict(line=dict(width=1, color='white')),
        )
        fig.update_layout(
            template="plotly_white",
            hoverlabel=dict(bgcolor="white", font_size=12),
        )

        if save_path:
            fig.write_html(save_path)
        return fig

    @staticmethod
    def plot_etf_radar(signals: List[TradeSignal], top_n: int = 8,
                       save_path: Optional[str] = None) -> go.Figure:
        """ETF雷达图 - 多维度评分对比"""
        if not signals:
            return go.Figure()

        top = signals[:top_n]
        categories = ['净流入评分', '涨跌幅评分', '流入流出比', '综合评分']

        fig = go.Figure()
        for sig in top:
            fig.add_trace(go.Scatterpolar(
                r=[sig.score, sig.score, sig.inflow_outflow_ratio * 10, sig.score],
                theta=categories,
                fill='toself',
                name=f"{sig.etf_name}({sig.score:.0f}分)",
                opacity=0.7,
            ))

        fig.update_layout(
            title=dict(text="ETF综合评分雷达图", font=dict(size=16)),
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=500,
            template="plotly_white",
        )

        if save_path:
            fig.write_html(save_path)
        return fig

    @staticmethod
    def plot_etf_signal_gauge(signal: TradeSignal,
                              save_path: Optional[str] = None) -> go.Figure:
        """单个ETF信号仪表盘"""
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=signal.score,
            domain=dict(x=[0, 1], y=[0, 1]),
            title=dict(text=f"{signal.etf_name}<br>{signal.etf_code}"),
            delta=dict(
                reference=50,
                valueformat=".0f",
                increasing=dict(color="#2ecc71"),
                decreasing=dict(color="#e74c3c"),
            ),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1),
                bar=dict(color="#2ecc81" if signal.signal == "buy"
                         else ("#e74c3c" if signal.signal == "sell" else "#f39c12")),
                steps=[
                    dict(range=[0, 30], color="#f8d7da"),
                    dict(range=[30, 70], color="#fff3cd"),
                    dict(range=[70, 100], color="#d4edda"),
                ],
                threshold=dict(
                    line=dict(color="red", width=4),
                    thickness=0.75,
                    value=70,
                ),
            ),
        ))

        fig.update_layout(height=400, template="plotly_white")
        if save_path:
            fig.write_html(save_path)
        return fig

    @staticmethod
    def plot_top_industries(df: pd.DataFrame, n_cols: int = 5,
                            save_path: Optional[str] = None) -> go.Figure:
        """仪表板风格：显示TOP N行业指标卡"""
        col_net = '净额' if '净额' in df.columns else 'net_flow'
        col_chg = '行业-涨跌幅' if '行业-涨跌幅' in df.columns else 'change_pct'
        col_ind = '行业' if '行业' in df.columns else 'industry'

        top_in = df.nlargest(10, col_net)
        top_out = df.nsmallest(10, col_net)

        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("净流入TOP 10", "净流出TOP 10"),
            vertical_spacing=0.15,
        )

        for i, (data, row) in enumerate([(top_in, 1), (top_out, 2)], 1):
            colors = ['#2ecc71'] * len(data) if i == 1 else ['#e74c3c'] * len(data)
            fig.add_trace(go.Bar(
                x=data[col_net], y=data[col_ind],
                orientation='h', marker_color=colors,
                text=[f"{v:+.1f}亿" for v in data[col_net]],
                textposition='outside',
                hovertemplate='%{y}<br>净额: %{x:.2f}亿<br>涨跌幅: %{customdata:.2f}%<extra></extra>',
                customdata=data[col_chg],
                showlegend=False,
            ), row=row, col=1)

        fig.update_layout(
            height=600,
            template="plotly_white",
            margin=dict(l=10, r=60, t=40, b=10),
            yaxis1=dict(autorange="reversed"),
            yaxis2=dict(autorange="reversed"),
        )

        if save_path:
            fig.write_html(save_path)
        return fig

    @staticmethod
    def create_full_report(flow_df: pd.DataFrame, signals: List[TradeSignal],
                           save_html: bool = True) -> str:
        """生成完整的HTML分析报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        col_net = '净额' if '净额' in flow_df.columns else 'net_flow'
        col_chg = '行业-涨跌幅' if '行业-涨跌幅' in flow_df.columns else 'change_pct'
        col_ind = '行业' if '行业' in flow_df.columns else 'industry'

        buys = [s for s in signals if s.signal == "buy"]
        sells = [s for s in signals if s.signal == "sell"]

        # 生成各个图表
        fig1 = Visualizer.plot_industry_flow(flow_df)
        fig2 = Visualizer.plot_flow_vs_change(flow_df)
        fig3 = Visualizer.plot_etf_signal_chart(signals)

        from plotly.io import to_html
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8">
        <title>A股资金流检测报告 {now}</title>
        <style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 20px; background: #f8f9fa; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea, #764ba2);
                       color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 5px 0 0; opacity: 0.9; }}
            .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }}
            .card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .card h3 {{ margin: 0 0 5px; font-size: 14px; color: #666; }}
            .card .value {{ font-size: 28px; font-weight: bold; }}
            .card .value.green {{ color: #2ecc71; }}
            .card .value.red {{ color: #e74c3c; }}
            .section {{ background: white; padding: 20px; border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
            .chart {{ width: 100%; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; }}
            .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
                      font-size: 12px; font-weight: bold; }}
            .badge.buy {{ background: #d4edda; color: #28a745; }}
            .badge.sell {{ background: #f8d7da; color: #dc3545; }}
            .badge.hold {{ background: #fff3cd; color: #ffc107; }}
        </style>
        </head>
        <body>
        <div class="container">
            <div class="header">
                <h1>📊 A股资金流动态检测日报</h1>
                <p>生成时间: {now} | 数据来源: 东方财富</p>
            </div>

            <div class="summary">
                <div class="card">
                    <h3>全市场净流入</h3>
                    <div class="value {'green' if flow_df[col_net].sum() > 0 else 'red'}">
                        {flow_df[col_net].sum():+.1f}亿
                    </div>
                </div>
                <div class="card">
                    <h3>行业涨跌比</h3>
                    <div class="value">
                        {len(flow_df[flow_df[col_chg] > 0])} / {len(flow_df)}
                    </div>
                </div>
                <div class="card">
                    <h3>买入信号</h3>
                    <div class="value green">{len(buys)}</div>
                </div>
                <div class="card">
                    <h3>卖出信号</h3>
                    <div class="value red">{len(sells)}</div>
                </div>
            </div>

            <div class="section">
                <h2>📈 TOP 5 买入信号</h2>
                <table>
                    <tr><th>ETF</th><th>评分</th><th>净流入</th><th>信号</th><th>理由</th></tr>
        """
        for s in buys[:5]:
            html_content += f"""
                    <tr>
                        <td>{s.etf_name}({s.etf_code})</td>
                        <td>{s.score:.0f}</td>
                        <td>{s.net_flow:+.1f}亿</td>
                        <td><span class="badge buy">买入</span></td>
                        <td>{s.reason}</td>
                    </tr>
            """
        html_content += """
                </table>
            </div>

            <div class="section">
                <h2>📉 TOP 5 卖出信号</h2>
                <table>
                    <tr><th>ETF</th><th>评分</th><th>净流入</th><th>信号</th><th>理由</th></tr>
        """
        for s in sells[:5]:
            html_content += f"""
                    <tr>
                        <td>{s.etf_name}({s.etf_code})</td>
                        <td>{s.score:.0f}</td>
                        <td>{s.net_flow:+.1f}亿</td>
                        <td><span class="badge sell">卖出</span></td>
                        <td>{s.reason}</td>
                    </tr>
            """

        html_content += f"""
                </table>
            </div>

            <div class="section">
                <h2>🏆 TOP 10 净流入行业</h2>
                <table>
                    <tr><th>排名</th><th>行业</th><th>净流入(亿)</th><th>涨跌幅</th><th>领涨股</th></tr>
        """
        col_leader = '领涨股' if '领涨股' in flow_df.columns else 'leader_stock'
        col_leader_chg = '领涨股-涨跌幅' if '领涨股-涨跌幅' in flow_df.columns else 'leader_change_pct'
        for i, (_, row) in enumerate(flow_df.nlargest(10, col_net).iterrows(), 1):
            html_content += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{row[col_ind]}</td>
                        <td style="color:{'#2ecc71' if row[col_net] > 0 else '#e74c3c'}">{row[col_net]:+.2f}</td>
                        <td style="color:{'#2ecc71' if row[col_chg] > 0 else '#e74c3c'}">{row[col_chg]:+.2f}%</td>
                        <td>{row.get(col_leader, '-')}</td>
                    </tr>
            """

        html_content += """
                </table>
            </div>

            <div class="section">
                <h2>📊 图表分析</h2>
        """
        html_content += f'<div class="chart">{to_html(fig1, include_plotlyjs="cdn", full_html=False)}</div>'
        html_content += f'<div class="chart">{to_html(fig2, include_plotlyjs="cdn", full_html=False)}</div>'
        if fig3:
            html_content += f'<div class="chart">{to_html(fig3, include_plotlyjs="cdn", full_html=False)}</div>'

        html_content += """
            </div>

            <div style="text-align: center; color: #999; margin: 20px 0; font-size: 12px;">
                <p>A股资金流动态检测与ETF交易系统 | 数据来源: 东方财富</p>
            </div>
        </body>
        </html>
        """

        if save_html:
            fpath = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            fpath.write_text(html_content, encoding='utf-8')
            print(f"✓ HTML报告已保存: {fpath}")

        return html_content

    # 复用dashboard中的ETF信号图
    @staticmethod
    def plot_etf_signal_chart(signals: List[TradeSignal], top_n: int = 20) -> Optional[go.Figure]:
        """ETF信号评分图"""
        if not signals:
            return None
        df = pd.DataFrame([{
            'name': f"{s.etf_name}({s.etf_code})",
            'score': s.score,
            'signal': s.signal,
            'net_flow': s.net_flow,
        } for s in signals[:top_n]])

        if df.empty:
            return None

        colors = {'buy': '#2ecc71', 'sell': '#e74c3c', 'hold': '#f39c12'}
        bar_colors = [colors[s] for s in df['signal']]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['score'], y=df['name'],
            orientation='h', marker_color=bar_colors,
            text=[f"{s:.0f}分" for s in df['score']],
            textposition='outside',
        ))

        fig.add_vline(x=70, line_dash="dash", line_color="#2ecc71",
                       annotation_text="买入线", annotation_position="top right")
        fig.add_vline(x=30, line_dash="dash", line_color="#e74c3c",
                       annotation_text="卖出线", annotation_position="top right")

        fig.update_layout(
            title="ETF综合评分排名",
            xaxis=dict(title="评分", range=[0, 105]),
            yaxis=dict(autorange="reversed"),
            height=500, template="plotly_white",
            margin=dict(l=10, r=60, t=40, b=10),
        )
        return fig


if __name__ == "__main__":
    # 测试可视化
    from fundflow_fetcher import FundFlowFetcher
    from etf_fetcher import IndustryETFMapper
    from flow_analyzer import SignalGenerator

    fetcher = FundFlowFetcher()
    df = fetcher.fetch_industry_flow()

    mapper = IndustryETFMapper()
    signal_gen = SignalGenerator(mapper)
    signals = signal_gen.generate_etf_signals(df)

    # 生成报告
    Visualizer.create_full_report(df, signals, save_html=True)
    print("✓ 可视化报告生成完成")
