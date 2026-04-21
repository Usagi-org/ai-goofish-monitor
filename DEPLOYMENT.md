# 部署指南

## 跨平台 Docker 构建与部署

### 背景

本项目在 ARM 架构（Mac M 系列芯片）上开发，但线上服务器为 x86_64 架构。默认构建的 Docker 镜像是 ARM 架构，无法在 x86 服务器上运行。

### 核心问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 服务器上拉取的镜像无法运行 | 在 ARM 架构的 Mac 上构建的 Docker 镜像默认是 `arm64` 架构，而线上服务器是 `x86_64/amd64` 架构 | 使用 `docker buildx --platform linux/amd64` 进行跨平台构建 |
| `Failed to connect to 127.0.0.1 port 7890` | Git 配置了代理但代理服务器未运行 | `git config --global --unset http.proxy` |
| `archive/tar: invalid tar header` | 上传到服务器的是源代码压缩包，不是 Docker 镜像 | 使用 Docker Hub 推送和拉取镜像 |
| `tag does not exist` | 本地镜像 tag 与推送时使用的 tag 不匹配 | 先打 tag 再推送 |
| `spawnSync ETXTBSY` | npm ci 时文件被占用 | 使用 `docker buildx prune -f` 清理缓存，添加 `--no-cache` 参数 |

### 跨平台构建流程（ARM → x86）

```bash
# 1. 创建并激活 buildx builder（首次执行）
docker buildx create --name mybuilder --use
docker buildx inspect --bootstrap

# 2. 清理缓存（避免 ETXTBSY 错误）
docker buildx prune -f

# 3. 构建 x86_64 镜像并推送到 Docker Hub
docker buildx build \
  --platform linux/amd64 \
  -t joshuayang2001/ai-goofish-monitor:latest \
  --push \
  --no-cache \
  .
```

### 服务器部署步骤

```bash
# 1. 拉取镜像
docker pull joshuayang2001/ai-goofish-monitor:latest

# 2. 停止并删除旧容器
docker stop ai-goofish-monitor-app 2>/dev/null || true
docker rm ai-goofish-monitor-app 2>/dev/null || true

# 3. 启动新容器
docker run -d \
  --name ai-goofish-monitor-app \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /opt/1panel/apps/ai-goofish/data:/app/data \
  -v /opt/1panel/apps/ai-goofish/state:/app/state \
  -v /opt/1panel/apps/ai-goofish/config.json:/app/config.json \
  -v /opt/1panel/apps/ai-goofish/.env:/app/.env \
  -e APP_DATABASE_FILE=/app/data/app.sqlite3 \
  joshuayang2001/ai-goofish-monitor:latest

# 4. 数据库迁移（添加 is_paused 字段）
docker exec ai-goofish-monitor-app python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/app.sqlite3')
try:
    conn.execute('ALTER TABLE tasks ADD COLUMN is_paused INTEGER NOT NULL DEFAULT 0')
    conn.commit()
    print('数据库迁移成功')
except Exception as e:
    print(f'迁移完成或跳过：{e}')
"
```

### 推荐的 CI/CD 流程

1. **本地开发**：在 ARM 机器上开发测试
2. **构建镜像**：使用 `docker buildx --platform linux/amd64` 构建 x86 镜像
3. **推送镜像**：推送到 Docker Hub（或其他镜像仓库）
4. **服务器部署**：从 Docker Hub 拉取 x86 镜像并运行
5. **数据库迁移**：执行必要的数据库迁移脚本

### Dockerfile 优化

Dockerfile 中已配置阿里云镜像源，加速 apt 包安装：

```dockerfile
RUN rm -f /etc/apt/sources.list.d/*.list \
    && echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata tini libzbar0 \
    && playwright install --with-deps --no-shell chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

### 验证部署

```bash
# 检查容器状态
docker ps | grep ai-goofish-monitor-app

# 查看容器日志
docker logs -f ai-goofish-monitor-app

# 测试 API
curl http://localhost:8000/api/health

# 验证镜像架构
docker inspect joshuayang2001/ai-goofish-monitor:latest | grep Architecture
# 应输出："Architecture": "amd64"
```

### 环境要求

- Docker 20.10+（支持 buildx）
- 服务器：Linux x86_64
- 内存：建议 2GB+
- 磁盘：建议 10GB+ 可用空间
