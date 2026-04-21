# Stage 1: Build the Vue application
FROM node:22-alpine AS frontend-builder
WORKDIR /web-ui
COPY web-ui/package*.json ./
RUN npm ci
COPY web-ui/ .
RUN npm run build

# Stage 2: Build the python environment with dependencies
FROM python:3.11-slim-bookworm AS builder

# 设置环境变量以防止交互式提示
ENV DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# 创建虚拟环境并安装 Python 运行时依赖
RUN python3 -m venv $VIRTUAL_ENV
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-runtime.txt

# Stage 3: Create the final, lean image
FROM python:3.11-slim-bookworm

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    RUNNING_IN_DOCKER=true \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Shanghai

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# 使用阿里云镜像源加速 apt 更新（Debian Bookworm）
RUN rm -f /etc/apt/sources.list.d/*.list \
    && echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    tzdata \
    tini \
    libzbar0 \
    && playwright install --with-deps --no-shell chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=frontend-builder /dist /app/dist

COPY src /app/src
COPY spider_v2.py /app/spider_v2.py
COPY prompts /app/prompts
COPY static /app/static
COPY config.json.example /app/config.json.example

RUN mkdir -p /app/data /app/state /app/logs /app/images /app/jsonl /app/price_history

EXPOSE 8000

USER root

ENTRYPOINT ["tini", "--"]

CMD ["python", "-m", "src.app"]
