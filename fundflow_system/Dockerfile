FROM python:3.11-slim

# 时区设为上海（A股交易时间）
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 切换 apt 为阿里云镜像源（国内构建加速）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统依赖（字体 + ffmpeg）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# 先装依赖（利用阿里云 PyPI 镜像加速 + Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/fundflow_cache /app/data/videos /app/data/daily \
    /app/data/backtest /app/data/signals /app/data/reports /app/signals

# 暴露 Streamlit 端口
EXPOSE 8501

# 默认启动看板（docker-compose 会覆盖此命令）
CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
