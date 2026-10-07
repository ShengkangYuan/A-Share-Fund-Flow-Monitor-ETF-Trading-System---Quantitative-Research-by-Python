#!/bin/bash
# ================================================================
# A股资金流系统 - 阿里云服务器初始化 + 部署（新手友好版）
# 在阿里云 Workbench 终端里逐段复制粘贴执行即可
# ================================================================

set -e

echo "================================================"
echo "  ① 检测系统版本"
echo "================================================"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "系统: $PRETTY_NAME"
    OS_TYPE=$ID
else
    OS_TYPE="unknown"
    echo "无法检测系统版本"
fi

echo ""
echo "================================================"
echo "  ② 安装 Docker"
echo "================================================"
if command -v docker &> /dev/null; then
    echo "✅ Docker 已安装，跳过"
else
    echo "正在安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
    echo "✅ Docker 安装完成"
fi

docker --version

echo ""
echo "================================================"
echo "  ③ 安装 Docker Compose"
echo "================================================"
if docker compose version &> /dev/null 2>&1; then
    echo "✅ Docker Compose (plugin) 已可用"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    echo "✅ docker-compose 已安装"
    COMPOSE_CMD="docker-compose"
else
    echo "正在安装 docker-compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    COMPOSE_CMD="docker-compose"
    echo "✅ docker-compose 安装完成"
fi

echo ""
echo "================================================"
echo "  ④ 创建项目目录"
echo "================================================"
mkdir -p /opt/fundflow_system
cd /opt/fundflow_system
echo "工作目录: $(pwd)"

echo ""
echo "================================================"
echo "  ✅ 环境准备完成！"
echo ""
echo "  下一步："
echo "  请将本地 fundflow_system 项目的代码上传到"
echo "  /opt/fundflow_system/ 目录"
echo ""
echo "  上传方法（在本地 Windows 电脑执行）："
echo "  scp -r C:\\Users\\eason\\Desktop\\python\\test\\fundflow_system\\* root@你的服务器IP:/opt/fundflow_system/"
echo ""
echo "  上传完成后，在服务器上运行："
echo "  cd /opt/fundflow_system && bash deploy.sh"
echo "================================================"
