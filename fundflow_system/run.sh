#!/bin/bash
# ================================================================
# A股资金流系统 - 纯 Docker 部署脚本（无需 docker-compose）
# 使用方式：cd fundflow_system && bash run.sh
# ================================================================

set -e

APP_NAME="fundflow_system"
IMAGE_TAG="fundflow-system:latest"
DATA_DIR="$(pwd)/data"
SIGNALS_DIR="$(pwd)/signals"
TZ_SET="Asia/Shanghai"

echo "================================================"
echo "  A股资金流系统 - Docker 部署"
echo "================================================"

# 创建数据目录
mkdir -p "$DATA_DIR"/{fundflow_cache,videos,daily,backtest,signals,reports} "$SIGNALS_DIR"

# 清理旧容器
echo ""
echo "🧹 清理旧容器..."
docker rm -f fundflow-web 2>/dev/null || true
docker rm -f fundflow-scheduler 2>/dev/null || true

# 构建镜像
echo ""
echo "🔨 构建镜像（首次 3-5 分钟）..."
docker build -t "$IMAGE_TAG" .

# 启动看板容器
echo ""
echo "🚀 启动看板容器..."
docker run -d \
    --name fundflow-web \
    --restart unless-stopped \
    -p 8501:8501 \
    -v "$DATA_DIR:/app/data" \
    -v "$SIGNALS_DIR:/app/signals" \
    -e TZ="$TZ_SET" \
    -e SCHEDULER_MODE=embedded \
    "$IMAGE_TAG" \
    streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false

# 启动调度器容器
echo ""
echo "🚀 启动调度器容器（24/7 自动采集）..."
docker run -d \
    --name fundflow-scheduler \
    --restart unless-stopped \
    -v "$DATA_DIR:/app/data" \
    -v "$SIGNALS_DIR:/app/signals" \
    -e TZ="$TZ_SET" \
    -e SCHEDULER_MODE=standalone \
    "$IMAGE_TAG" \
    python scheduler_runner.py

# 显示状态
sleep 3
echo ""
echo "================================================"
echo "  ✅ 部署完成！"
echo ""
echo "  容器状态:"
docker ps --filter "name=fundflow" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "  📊 看板地址: http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo "  常用命令:"
echo "    查看日志: docker logs -f fundflow-web"
echo "             docker logs -f fundflow-scheduler"
echo "    停止:    docker rm -f fundflow-web fundflow-scheduler"
echo "    重启:    bash run.sh"
echo "================================================"
