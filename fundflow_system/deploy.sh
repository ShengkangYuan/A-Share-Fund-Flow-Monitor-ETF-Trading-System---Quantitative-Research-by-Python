#!/bin/bash
# ================================================
# A股资金流系统 - 云端部署一键脚本
# 使用方式：在云服务器上 git clone 项目后运行 bash deploy.sh
# ================================================

set -e

echo "================================================"
echo "  A股资金流系统 - 云端部署"
echo "================================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，正在安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
    echo "✅ Docker 安装完成"
fi

# 检查 docker-compose
if ! docker compose version &> /dev/null; then
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ docker-compose 未安装，正在安装..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        echo "✅ docker-compose 安装完成"
    fi
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# 创建数据和信号目录
mkdir -p data/fundflow_cache data/videos data/daily data/backtest data/signals data/reports signals

# 构建并启动
echo ""
echo "🔨 正在构建 Docker 镜像（首次可能需要几分钟）..."
$COMPOSE_CMD build

echo ""
echo "🚀 启动容器..."
$COMPOSE_CMD up -d

echo ""
echo "================================================"
echo "  ✅ 部署完成！"
echo ""
echo "  📊 看板地址: http://$(hostname -I | awk '{print $1}'):8501"
echo "  🛰️ 独立调度器: 已在后台运行（24/7 自动采集）"
echo ""
echo "  常用命令:"
echo "    查看状态: $COMPOSE_CMD ps"
echo "    查看日志: $COMPOSE_CMD logs -f"
echo "    停止:     $COMPOSE_CMD down"
echo "    重启:     $COMPOSE_CMD restart"
echo "================================================"
