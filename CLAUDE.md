# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 Playwright + AI 的闲鱼智能监控机器人。FastAPI 后端 + Vue 3 前端，支持多任务并发监控、多模态 AI 商品分析、多渠道通知推送。

## 核心架构

```
API 层 (src/api/routes/)         — FastAPI 路由，通过依赖注入获取服务
    ↓
服务层 (src/services/)            — 业务逻辑，核心服务见下表
    ↓
领域层 (src/domain/)              — Task 模型、Repository 抽象接口
    ↓
基础设施层 (src/infrastructure/)   — SQLite 持久化、AI/通知客户端、配置管理
```

### 关键入口

| 文件 | 用途 |
|------|------|
| `src/app.py` | FastAPI 主入口，lifespan 管理、路由注册、静态文件挂载、SPA catch-all |
| `spider_v2.py` | 爬虫 CLI 入口，被 ProcessService 以子进程方式调用 |
| `src/scraper.py` | Playwright 爬虫核心逻辑 |

### 服务层一览

| 服务 | 职责 |
|------|------|
| `TaskService` | 任务 CRUD |
| `ProcessService` | 爬虫子进程管理（start/stop/lifecycle hooks） |
| `SchedulerService` | APScheduler 定时调度 |
| `TaskGenerationService` | AI 驱动的任务创建（后台 job 模式） |
| `AIAnalysisService` / `ai_handler.py` | 多模态 AI 商品分析 |
| `NotificationService` | 多渠道通知（ntfy/Bark/企业微信/Telegram/Gotify/Webhook） |
| `AccountStrategyService` | 多账号轮换策略 |
| `DashboardService` | 前端仪表盘数据聚合 |

### 依赖注入

服务实例在 `src/app.py` 创建，通过 `src/api/dependencies.py` 的 setter/setter 注入到路由层。测试时通过 `app.dependency_overrides` 替换为 Fake 实现（见 `tests/conftest.py`）。

### 数据持久化

- **SQLite**（主存储）：默认路径 `data/app.sqlite3`，可通过 `APP_DATABASE_FILE` 自定义
- `sqlite_bootstrap.py`：首次启动自动建库建表，并尝试从旧 `config.json`/`jsonl/`/`price_history/` 导入历史数据
- **文件系统**：`state/`（登录态）、`prompts/`（提示词）、`logs/`（运行日志）、`images/`（商品图片）
- Repository 模式：`src/domain/repositories/task_repository.py` 定义抽象接口，`SqliteTaskRepository` 实现

### 数据流

1. Web UI / API 创建任务 → SQLite
2. SchedulerService 按 cron 触发 / 手动启动
3. ProcessService 启动 `spider_v2.py` 子进程
4. scraper.py 使用 Playwright 抓取商品
5. AIAnalysisService 调用多模态模型分析（必须支持图片输入）
6. NotificationService 推送符合条件的商品
7. WebSocket 广播 `task_status_changed` 事件到前端

## 前端架构 (`web-ui/`)

Vue 3 + Vite + TypeScript + shadcn-vue + Tailwind CSS + vue-i18n（中英双语）

**路由结构**（`web-ui/src/router/index.ts`）：
```
/login          — 登录页
/               — MainLayout（侧边栏导航），含：
  /dashboard    — 监控概览
  /tasks        — 任务管理（AI 创建 + 关键词规则创建）
  /accounts     — 闲鱼账号管理
  /results      — 结果浏览
  /logs         — 运行日志
  /settings     — 系统设置
```

前端 composable 按视图拆分：`useTasks`、`useDashboard`、`useLogs`、`useResults`、`useSettings`、`useWebSocket`、`useTaskGenerationJob`。

Vite 开发服务器代理 `/api`、`/auth`、`/ws` 到 `http://127.0.0.1:8000`。`npm run build` 生成 `web-ui/dist/`，由 `start.sh` 复制到仓库根 `dist/` 供 FastAPI 静态挂载。

## 开发命令

```bash
# 后端开发
python -m src.app
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

# 爬虫（独立运行）
python spider_v2.py                          # 所有启用任务
python spider_v2.py --task-name "MacBook"    # 指定任务
python spider_v2.py --debug-limit 3          # 调试模式，限制商品数
python spider_v2.py --config custom.json     # 自定义配置（兼容旧模式）

# 前端
cd web-ui && npm install && npm run dev      # 开发
cd web-ui && npm run build                   # 构建

# 一键本地启动（检查依赖 + 前端构建 + 启动后端）
bash start.sh

# Docker
docker compose up --build -d
docker compose logs -f app
docker compose down
```

## 测试

```bash
pytest                                          # 运行所有测试
pytest tests/unit/test_utils.py                 # 单个文件
pytest tests/unit/test_utils.py::test_safe_get  # 单个函数
pytest --cov=src                                # 覆盖率
pytest -m live                                  # 真实流量冒烟测试（需凭据）
```

- 框架：pytest（同步，不依赖 pytest-asyncio）
- 测试目录：`tests/unit/`、`tests/integration/`、`tests/live/`
- 标记：`live`（需真实凭据）、`live_slow`（慢速可选测试）
- 测试 fixtures：`tests/conftest.py` 提供 `api_client`（FastAPI TestClient + Fake 服务注入）

## 配置

环境变量 (`.env`)：
- AI 模型：`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_NAME`
- 通知：`NTFY_TOPIC_URL`, `BARK_URL`, `WX_BOT_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `FEISHU_WEBHOOK_URL`, `DINGTALK_WEBHOOK_URL`
- 爬虫：`RUN_HEADLESS`, `LOGIN_IS_EDGE`
- Web 认证：`WEB_USERNAME`, `WEB_PASSWORD`
- 端口：`SERVER_PORT`
必填：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL_NAME`（模型须支持 Vision）

其他重要配置见 `.env.example`：通知渠道、代理轮换、任务失败保护、Web 认证（默认 `admin/admin123`）等。

## 提交规范

Conventional Commits：`feat(...)`、`fix(...)`、`refactor(...)`、`chore(...)`、`docs(...)`。

## 新增功能（v2.1+）

### 商家维度监控
- 服务：`SellerMonitoringService` (`src/services/seller_monitoring_service.py`)
- API：`/api/sellers/*`
- 功能：卖家黑名单/白名单、卖家信息采集、店铺商品监控

### 商品 ID 精确搜索
- 方法：`scrape_item_by_id()` in `src/scraper.py`
- API：`POST /api/sellers/search/item-id`
- 历史记录存储在 `search_history` 表

### 指标追踪（价格/想要数）
- 服务：`MetricsTrackingService` (`src/services/metrics_tracking_service.py`)
- API：`/api/metrics/item/{item_id}/*`
- 自动记录每次爬取的价格和想要数，支持变化检测

### 通知渠道扩展
- 飞书：`FeishuClient` (`src/infrastructure/external/notification_clients/feishu_client.py`)
- 钉钉：`DingtalkClient` (`src/infrastructure/external/notification_clients/dingtalk_client.py`)
- 内置重试机制（3 次，指数退避）

### PWA 支持
- 前端：`web-ui/vite.config.ts` 配置 `vite-plugin-pwa`
- 安装提示组件：`web-ui/src/components/PWAInstallPrompt.vue`
- 构建后生成 `dist/manifest.webmanifest` 和 Service Worker

## 数据库表

新增表（`src/infrastructure/persistence/sqlite_connection.py`）：
- `seller_info` - 卖家信息（ID、昵称、芝麻信用等）
- `item_metrics_history` - 商品指标历史（价格、想要数、浏览量）
- `seller_list` - 卖家黑名单/白名单
- `search_history` - 商品 ID 搜索历史

## 注意事项

- AI 模型必须支持图片上传（多模态）
- Docker 部署需通过 Web UI 手动更新登录状态（`state/` 目录）
- 遇到滑动验证码时设置 `RUN_HEADLESS=false` 手动处理
- 生产环境务必修改默认 Web 认证密码
- PWA 功能需要 HTTPS 环境（本地开发除外）
- 不要提交真实凭据或 cookies（如 `state.json`）
