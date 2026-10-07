"""
资金流动态视频生成模块
基于每5分钟刷新的资金流数据，生成动态视频
功能：收盘自动合成、帧缓存清理、视频管理、帧画面升级
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
# 跨平台中文字体：Windows 用 SimHei/YaHei，Linux 云端用 Noto CJK
matplotlib.rcParams['font.sans-serif'] = [
    'SimHei', 'Microsoft YaHei',          # Windows
    'Noto Sans CJK SC', 'WenQuanYi Micro Hei',  # Linux
    'PingFang SC', 'Heiti SC',            # macOS
    'DejaVu Sans',                         # 通用回退
]
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from datetime import datetime, timedelta
from pathlib import Path
import io
import base64
import os
import time
import logging
from typing import List, Dict, Optional

from config import VIDEOS_DIR, ROOT_DIR, SYS_CFG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FundFlowVideoGenerator:
    """资金流动态视频生成器"""

    def __init__(self):
        self.video_dir = self._ensure_writable_dir(VIDEOS_DIR)
        self.frames: List[Dict] = []
        self._video_generated_today = False

    def _ensure_writable_dir(self, primary_dir: Path) -> Path:
        """确保目录可写，不可写时返回备用目录"""
        import os
        try:
            if not primary_dir.exists():
                primary_dir.mkdir(parents=True, exist_ok=True)
            
            test_file = primary_dir / ".test_write"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return primary_dir
        except PermissionError:
            alt_dir = Path(os.path.expanduser("~")) / ".fundflow" / "videos"
            alt_dir.mkdir(parents=True, exist_ok=True)
            return alt_dir

    def add_frame(self, data: Dict):
        """添加一帧数据"""
        self.frames.append({
            'timestamp': datetime.now(),
            'data': data
        })
        if len(self.frames) > 500:
            self.frames = self.frames[-500:]

    def clear_frames(self):
        """清空帧缓存"""
        self.frames.clear()

    def auto_clean_old_frames(self):
        """自动清理超过指定天数的缓存帧"""
        cutoff_date = datetime.now() - timedelta(days=SYS_CFG.frame_cache_days)
        old_count = len(self.frames)
        self.frames = [f for f in self.frames if f['timestamp'] >= cutoff_date]
        removed_count = old_count - len(self.frames)
        if removed_count > 0:
            logger.info(f"自动清理了 {removed_count} 条过期帧数据")
        return removed_count

    def is_time_to_generate(self) -> bool:
        """判断是否到达自动生成视频的时间"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        
        today_str = now.strftime("%Y%m%d")
        if self._video_generated_today == today_str:
            return False
        
        target_time = datetime.strptime(SYS_CFG.video_auto_generate_time, "%H:%M").time()
        current_time = now.time()
        
        return current_time >= target_time and current_time < datetime.strptime("15:30", "%H:%M").time()

    def clear_frames_with_confirmation(self) -> bool:
        """带二次确认的清空帧缓存（用于页面交互）"""
        today_frames = [f for f in self.frames if f['timestamp'].date() == datetime.now().date()]
        if today_frames:
            logger.warning(f"清空帧缓存将删除今日 {len(today_frames)} 条数据")
            return False
        self.frames.clear()
        logger.info("帧缓存已清空")
        return True

    def generate_video(self, output_path: Optional[str] = None, fps: int = 1, progress_callback=None) -> str:
        """
        生成资金流动态视频
        Args:
            output_path: 输出路径，默认为自动生成
            fps: 帧率，默认1帧/秒
            progress_callback: 进度回调函数
        Returns:
            视频文件路径
        """
        if len(self.frames) < 2:
            raise ValueError("至少需要2帧数据才能生成视频")

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.video_dir / f"fund_flow_{timestamp}.mp4")

        times = [f['timestamp'].strftime('%H:%M:%S') for f in self.frames]
        dates = [f['timestamp'].strftime('%Y-%m-%d') for f in self.frames]
        total_nets = [f['data'].get('total_net', 0) for f in self.frames]
        positive_counts = [f['data'].get('positive_count', 0) for f in self.frames]
        negative_counts = [f['data'].get('negative_count', 0) for f in self.frames]
        total_inflows = [f['data'].get('total_inflow', 0) for f in self.frames]
        total_outflows = [f['data'].get('total_outflow', 0) for f in self.frames]

        x = np.arange(len(times))
        max_net = max(abs(min(total_nets)), abs(max(total_nets))) * 1.1 if total_nets else 100
        max_count = max(positive_counts + negative_counts) * 1.2 if positive_counts else 50

        fig = plt.figure(figsize=(16, 14))
        gs = fig.add_gridspec(4, 2, height_ratios=[2, 1.5, 1.5, 0.3])
        
        ax1 = fig.add_subplot(gs[0, :])
        ax2 = fig.add_subplot(gs[1, 0])
        ax3 = fig.add_subplot(gs[1, 1])
        ax4 = fig.add_subplot(gs[2, 0])
        ax5 = fig.add_subplot(gs[2, 1])
        ax_info = fig.add_subplot(gs[3, :])
        ax_info.axis('off')

        line1, = ax1.plot([], [], color='#28a745', linewidth=2, marker='o', markersize=6)
        ax1.set_ylabel('净流入 (亿元)', fontsize=12)
        ax1.set_title('A股资金流动态监控', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(-max_net, max_net)
        ax1.set_xlim(0, len(times) - 1)
        ax1.set_xticks([])

        fill_collections = []

        def update(frame_idx):
            frame_idx = min(frame_idx, len(times) - 1)

            if progress_callback:
                progress_callback(int((frame_idx + 1) / len(times) * 100))

            line1.set_data(x[:frame_idx + 1], total_nets[:frame_idx + 1])

            for fc in fill_collections:
                fc.remove()
            fill_collections.clear()
            fc = ax1.fill_between(x[:frame_idx + 1], total_nets[:frame_idx + 1],
                                  alpha=0.3, color='#28a745' if total_nets[frame_idx] >= 0 else '#dc3545')
            fill_collections.append(fc)

            for txt in ax1.texts:
                txt.remove()
            ax1.text(0.02, 0.95, f"时间: {times[frame_idx]}", transform=ax1.transAxes,
                    fontsize=10, bbox=dict(facecolor='white', alpha=0.8))
            net_color = '#28a745' if total_nets[frame_idx] >= 0 else '#dc3545'
            ax1.text(0.98, 0.95, f"净流入: {total_nets[frame_idx]:+.1f}亿", transform=ax1.transAxes,
                    fontsize=10, bbox=dict(facecolor='white', alpha=0.8),
                    horizontalalignment='right', color=net_color)

            ax2.clear()
            ax2.set_title('行业资金排名 TOP15', fontsize=12)
            ax2.grid(True, alpha=0.3)
            
            current_data = self.frames[frame_idx]['data']
            if 'top_industries' in current_data:
                top_inds = current_data['top_industries'][:15]
                names = [ind['name'] for ind in top_inds]
                values = [ind['net'] for ind in top_inds]
                colors = ['#28a745' if v >= 0 else '#dc3545' for v in values]
                y_pos = np.arange(len(names))
                ax2.barh(y_pos, values, color=colors)
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(names, fontsize=8)
                ax2.set_xlabel('净流入(亿)')
            else:
                ax2.text(0.5, 0.5, '数据加载中...', transform=ax2.transAxes, ha='center')

            ax3.clear()
            ax3.set_title('ETF评分排名 TOP10', fontsize=12)
            ax3.grid(True, alpha=0.3)
            
            if 'top_etfs' in current_data:
                top_etfs = current_data['top_etfs'][:10]
                names = [etf['name'] for etf in top_etfs]
                scores = [etf['score'] for etf in top_etfs]
                colors = ['#28a745' if s >= 70 else '#ffc107' if s >= 60 else '#dc3545' for s in scores]
                y_pos = np.arange(len(names))
                ax3.barh(y_pos, scores, color=colors)
                ax3.set_yticks(y_pos)
                ax3.set_yticklabels(names, fontsize=8)
                ax3.set_xlabel('评分')
                ax3.set_xlim(0, 100)
            else:
                ax3.text(0.5, 0.5, '数据加载中...', transform=ax3.transAxes, ha='center')

            ax4.clear()
            ax4.set_title('资金流入/流出对比', fontsize=12)
            ax4.grid(True, alpha=0.3)
            bar_width = 0.35
            idx = np.arange(5)
            recent_inflows = total_inflows[-5:] if len(total_inflows) >= 5 else total_inflows
            recent_outflows = total_outflows[-5:] if len(total_outflows) >= 5 else total_outflows
            recent_times = times[-5:] if len(times) >= 5 else times
            
            ax4.bar(idx - bar_width/2, recent_inflows, bar_width, label='流入', color='#28a745')
            ax4.bar(idx + bar_width/2, recent_outflows, bar_width, label='流出', color='#dc3545')
            ax4.set_xticks(idx)
            ax4.set_xticklabels(recent_times, rotation=45, fontsize=8)
            ax4.set_ylabel('金额(亿)')
            ax4.legend(fontsize=10)

            ax5.clear()
            ax5.set_title('涨跌家数对比', fontsize=12)
            ax5.grid(True, alpha=0.3)
            recent_positive = positive_counts[-5:] if len(positive_counts) >= 5 else positive_counts
            recent_negative = negative_counts[-5:] if len(negative_counts) >= 5 else negative_counts
            
            ax5.bar(idx - bar_width/2, recent_positive, bar_width, label='上涨', color='#28a745')
            ax5.bar(idx + bar_width/2, recent_negative, bar_width, label='下跌', color='#dc3545')
            ax5.set_xticks(idx)
            ax5.set_xticklabels(recent_times, rotation=45, fontsize=8)
            ax5.set_ylabel('家数')
            ax5.legend(fontsize=10)

            ax_info.clear()
            ax_info.axis('off')
            info_text = f"📅 {dates[frame_idx]} | ⏱️ {times[frame_idx]} | 📊 净流入: {total_nets[frame_idx]:+.1f}亿 | " \
                       f"📈 流入: {total_inflows[frame_idx]:.1f}亿 | 📉 流出: {total_outflows[frame_idx]:.1f}亿 | " \
                       f"🔥 {positive_counts[frame_idx]}家上涨 | 💧 {negative_counts[frame_idx]}家下跌"
            ax_info.text(0.5, 0.5, info_text, transform=ax_info.transAxes,
                        fontsize=10, ha='center', va='center', wrap=True)

            return [line1] + fill_collections

        anim = FuncAnimation(fig, update, frames=len(times), interval=1000 / fps, repeat=False)

        try:
            writer = FFMpegWriter(fps=fps, bitrate=2000)
            anim.save(output_path, writer=writer)
        except Exception as e:
            logger.warning(f"FFMpeg写入失败，降级为GIF: {e}")
            output_path = output_path.replace('.mp4', '.gif')
            writer = PillowWriter(fps=fps)
            anim.save(output_path, writer=writer)
        plt.close(fig)

        self._video_generated_today = datetime.now().strftime("%Y%m%d")
        logger.info(f"视频生成完成: {output_path}")
        return output_path

    def generate_video_from_history(self, history_data: List[Dict], output_path: Optional[str] = None,
                                   fps: int = 1) -> str:
        """
        从历史数据生成视频
        """
        self.frames = []
        for item in history_data:
            self.add_frame(item['data'])
        return self.generate_video(output_path, fps)

    def generate_video_from_snapshots(self, snapshots_df, output_path: Optional[str] = None,
                                       fps: int = 2, top_n: int = 15) -> str:
        """
        基于5分钟快照 DataFrame 生成 Bar Chart Race 风格动态视频
        snapshots_df: 由 DynamicVisualizer.load_snapshots() 返回的 DataFrame
        """
        if snapshots_df.empty:
            raise ValueError("快照数据为空")

        import pandas as pd
        from fundflow_fetcher import FundFlowFetcher
        from etf_fetcher import IndustryETFMapper
        from flow_analyzer import FlowAnalyzer, SignalGenerator

        fetcher = FundFlowFetcher()
        mapper = IndustryETFMapper()
        analyzer = FlowAnalyzer()
        signal_gen = SignalGenerator(mapper)

        # 按时间聚合每帧
        timestamps = sorted(snapshots_df['timestamp'].unique())
        self.frames = []

        for ts in timestamps:
            group = snapshots_df[snapshots_df['timestamp'] == ts]
            if group.empty:
                continue

            total_net = float(group['net_flow'].sum())
            total_inflow = float(group['inflow'].sum())
            total_outflow = float(group['outflow'].sum())
            positive_count = int((group['net_flow'] > 0).sum())
            negative_count = int((group['net_flow'] < 0).sum())

            top_inds = group.nlargest(top_n, 'net_flow')
            top_industries = [
                {'name': str(r['industry']), 'net': float(r['net_flow'])}
                for _, r in top_inds.iterrows()
            ]

            # ETF 评分
            top_etfs = []
            try:
                # 重构一个完整 DataFrame 供评分使用
                flow_df = group.rename(columns={
                    'industry': '行业', 'net_flow': '净额',
                    'inflow': '流入资金', 'outflow': '流出资金',
                    'change_pct': '行业-涨跌幅'
                })
                ranked = analyzer.rank_industries(flow_df)
                ranked = analyzer.calc_inflow_ratio(ranked)
                etf_df = mapper.map_industry_flow_to_etf(ranked)
                if not etf_df.empty:
                    etf_df['score'] = signal_gen.score_etf(etf_df)
                    etf_top = etf_df.nlargest(10, 'score')
                    for _, r in etf_top.iterrows():
                        top_etfs.append({
                            'name': str(r['etf_name']),
                            'score': float(r['score']) if pd.notna(r['score']) else 0,
                        })
            except Exception as e:
                logger.warning(f"ETF评分失败: {e}")

            self.frames.append({
                'timestamp': ts if isinstance(ts, datetime) else datetime.now(),
                'data': {
                    'total_net': total_net,
                    'positive_count': positive_count,
                    'negative_count': negative_count,
                    'total_inflow': total_inflow,
                    'total_outflow': total_outflow,
                    'top_industries': top_industries,
                    'top_etfs': top_etfs,
                }
            })

        if len(self.frames) < 2:
            raise ValueError("帧数不足2帧，无法生成视频")

        return self.generate_video(output_path, fps)

    def get_video_html(self, video_path: str) -> str:
        """获取视频HTML嵌入代码"""
        video_path = Path(video_path)
        if not video_path.exists():
            return ""

        with open(video_path, 'rb') as f:
            video_bytes = f.read()

        video_base64 = base64.b64encode(video_bytes).decode('utf-8')

        if video_path.suffix == '.mp4':
            video_src = f"data:video/mp4;base64,{video_base64}"
            html = f"""
            <video width="100%" controls autoplay loop muted>
                <source src="{video_src}" type="video/mp4">
                您的浏览器不支持视频播放
            </video>
            """
        else:
            video_src = f"data:image/gif;base64,{video_base64}"
            html = f"""
            <img src="{video_src}" width="100%" alt="资金流动态图" />
            """
        return html

    def generate_summary_image(self) -> str:
        """生成资金流汇总图片"""
        if len(self.frames) < 1:
            return ""

        last_data = self.frames[-1]['data']

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))

        times = [f['timestamp'].strftime('%H:%M') for f in self.frames]
        total_nets = [f['data'].get('total_net', 0) for f in self.frames]
        total_inflows = [f['data'].get('total_inflow', 0) for f in self.frames]
        total_outflows = [f['data'].get('total_outflow', 0) for f in self.frames]
        positive_counts = [f['data'].get('positive_count', 0) for f in self.frames]
        negative_counts = [f['data'].get('negative_count', 0) for f in self.frames]

        axes[0, 0].plot(times, total_nets, color='#28a745', linewidth=2, marker='o')
        axes[0, 0].set_title('资金流趋势', fontsize=12)
        axes[0, 0].set_xlabel('时间')
        axes[0, 0].set_ylabel('净流入(亿)')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].tick_params(axis='x', rotation=45)

        bar_colors = ['#28a745' if n >= 0 else '#dc3545' for n in total_nets]
        axes[0, 1].bar(times, total_nets, color=bar_colors)
        axes[0, 1].set_title('资金流柱状图', fontsize=12)
        axes[0, 1].set_xlabel('时间')
        axes[0, 1].set_ylabel('净流入(亿)')
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].tick_params(axis='x', rotation=45)

        idx = np.arange(len(times))
        width = 0.35
        axes[1, 0].bar(idx - width/2, positive_counts, width, label='上涨', color='#28a745')
        axes[1, 0].bar(idx + width/2, negative_counts, width, label='下跌', color='#dc3545')
        axes[1, 0].set_title('涨跌家数', fontsize=12)
        axes[1, 0].set_xlabel('时间')
        axes[1, 0].set_ylabel('家数')
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].tick_params(axis='x', rotation=45)
        axes[1, 0].legend()

        axes[1, 1].bar(idx - width/2, total_inflows, width, label='流入', color='#28a745')
        axes[1, 1].bar(idx + width/2, total_outflows, width, label='流出', color='#dc3545')
        axes[1, 1].set_title('资金流入流出', fontsize=12)
        axes[1, 1].set_xlabel('时间')
        axes[1, 1].set_ylabel('金额(亿)')
        axes[1, 1].grid(True, alpha=0.3)
        axes[1, 1].tick_params(axis='x', rotation=45)
        axes[1, 1].legend()

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        return f"data:image/png;base64,{img_base64}"

    def get_video_files(self) -> List[Dict]:
        """获取视频文件列表"""
        import os
        files = []
        if self.video_dir.exists():
            for f in sorted(self.video_dir.glob('*.mp4')) + sorted(self.video_dir.glob('*.gif')):
                files.append({
                    'name': f.name,
                    'path': str(f),
                    'size': self._format_size(f.stat().st_size),
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'mp4' if f.suffix == '.mp4' else 'gif',
                })
        return sorted(files, key=lambda x: x['modified'], reverse=True)

    def delete_video(self, filename: str) -> bool:
        """删除指定视频文件"""
        import os
        filepath = self.video_dir / filename
        if filepath.exists():
            try:
                os.remove(filepath)
                return True
            except Exception:
                return False
        return False

    def clear_all_videos(self) -> int:
        """清理所有视频文件"""
        import os
        count = 0
        for f in self.video_dir.glob('*.mp4'):
            try:
                os.remove(f)
                count += 1
            except Exception:
                pass
        for f in self.video_dir.glob('*.gif'):
            try:
                os.remove(f)
                count += 1
            except Exception:
                pass
        return count

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


if __name__ == "__main__":
    generator = FundFlowVideoGenerator()

    test_data = []
    base_time = datetime.now()
    for i in range(20):
        test_data.append({
            'timestamp': base_time + timedelta(minutes=5 * i),
            'data': {
                'total_net': np.random.uniform(-50, 100),
                'positive_count': np.random.randint(20, 40),
                'negative_count': np.random.randint(20, 40),
                'total_inflow': np.random.uniform(50, 200),
                'total_outflow': np.random.uniform(50, 200),
                'top_industries': [{'name': f'行业{i}', 'net': np.random.uniform(-20, 50)} for i in range(15)],
                'top_etfs': [{'name': f'ETF{i}', 'score': np.random.uniform(40, 95)} for i in range(10)],
            }
        })

    video_path = generator.generate_video_from_history(test_data, fps=2)
    print(f"视频已生成: {video_path}")