# Stage 1: Build the Vue application
FROM node:22-alpine AS frontend-builder
WORKDIR /web-ui
COPY web-ui/package*.json ./
RUN npm install
COPY web-ui/ .
RUN npm run build

# Stage 2: Build the python environment with dependencies
FROM python:3.11-slim-bookworm AS builder

# 设置环境变量以防止交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 创建虚拟环境
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 安装 Python 依赖到虚拟环境中 (使用国内镜像源加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 只下载 Playwright 的 Chromium 浏览器，系统依赖在下一阶段安装
RUN playwright install chromium

# Stage 3: Create the final, lean image
FROM python:3.11-slim-bookworm

# 设置工作目录和环境变量
WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
# 新增环境变量，用于区分Docker环境和本地环境
ENV RUNNING_IN_DOCKER=true
# 告知 Playwright 在哪里找到浏览器
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
# 设置时区为中国时区
ENV TZ=Asia/Shanghai

# 从 builder 阶段复制虚拟环境，这样我们就可以使用 playwright 命令
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# 安装所有运行浏览器所需的系统级依赖（包括libzbar0）和网络诊断工具
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        tini \
        libzbar0 \
        curl \
        wget \
        iputils-ping \
        dnsutils \
        iproute2 \
        netcat-openbsd \
        telnet \
    && playwright install-deps chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制预先下载好的浏览器
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# 复制前端构建产物到 /app/dist
COPY --from=frontend-builder /web-ui/dist /app/dist

# 复制应用代码
# .dockerignore 文件会处理排除项-m
COPY . .

# 声明服务运行的端口
EXPOSE 8000

# 使用 tini 作为 init，负责回收孤儿子进程
ENTRYPOINT ["tini", "--"]

# 容器启动时执行的命令
# 使用新架构的启动方式
CMD ["python", "-m", "src.app"]
