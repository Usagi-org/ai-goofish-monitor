## Context

当前系统已有 `SKIP_AI_ANALYSIS` 环境变量用于跳过 AI 分析，但：
1. 仅在后端生效，前端仍显示 AI 相关 UI
2. 需要修改 `.env` 文件或重启服务才能切换
3. 任务创建流程中的 AI 生成标准逻辑不受影响
4. Dashboard 的"AI 智能策略"卡片仍会显示

系统架构：
```
前端 (Vue 3)                后端 (FastAPI)              数据库 (SQLite)
├─ SettingsView            ├─ /api/settings/ai         ├─ app_settings (新增)
├─ TaskForm                ├─ /api/settings/ai-enabled ├─ tasks
├─ ResultCard              ├─ /api/tasks/generate      ├─ result_items
└─ Dashboard               └─ ItemAnalysisDispatcher   └─ result_items.raw_json
```

## Goals / Non-Goals

**Goals:**
- 在设置页面添加 AI 功能总开关，用户可一键禁用/启用
- 开关状态持久化存储到数据库
- 前端所有 AI 相关 UI 根据开关动态显示/隐藏
- 后端跳过 AI 分析、AI 生成标准等逻辑
- 任务创建表单在 AI 禁用时隐藏 AI 相关选项

**Non-Goals:**
- 不删除现有 AI 代码，仅添加条件判断
- 不影响已存储的 AI 分析结果展示（历史数据仍可显示）
- 不修改 AI 分析核心逻辑（`ai_handler.py`, `ai_client.py` 等）

## Decisions

### 1. 存储方案：数据库 + 内存缓存

**决策**: 使用数据库表 `app_settings` 存储 AI 开关状态，服务启动时加载到内存。

**理由**:
- 支持多用户/多会话共享同一配置
- 避免每次请求都查数据库
- 支持运行时动态切换，无需重启

**替代方案**:
- 仅用环境变量：需要重启服务，用户体验差
- 仅用前端 localStorage：多设备不同步，后端无法感知

### 2. API 设计：独立端点

**决策**: 新增 `/api/settings/ai-enabled` GET/PUT 端点

**理由**:
- 与现有 `/api/settings/ai` 分离，职责清晰
- 避免污染现有 AI 配置响应结构
- 前端可独立订阅开关状态

### 3. 前端状态管理：复用 useSettings

**决策**: 在 `useSettings.ts` 中添加 `isAiEnabled` 状态

**理由**:
- 现有 `useSettings` 已管理设置相关状态
- 组件可统一通过 composable 获取状态
- 保持代码结构一致性

### 4. UI 隐藏策略：条件渲染

**决策**: 使用 `v-if="isAiEnabled"` 包裹 AI 相关 UI

**理由**:
- 彻底移除 DOM，避免用户通过开发者工具看到
- 性能优于 `v-show`（CSS 隐藏）
- 代码意图清晰

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| 开关切换后，正在运行的任务可能仍会产生 AI 结果 | 下次爬取时生效，当前运行任务不受影响 |
| 历史 AI 分析结果仍存储在数据库中 | 保留历史数据，仅隐藏不删除 |
| 前端组件多处需要添加条件判断 | 抽取公共逻辑到 composable |
| 开关状态与后端不同步 | 关键操作前校验后端状态 |

## Migration Plan

1. 创建数据库表 `app_settings`
2. 添加后端 API `/api/settings/ai-enabled`
3. 更新前端 `useSettings.ts` 和 `SettingsView.vue`
4. 更新 AI 相关 UI 组件添加条件渲染
5. 更新任务创建逻辑跳过 AI 生成

## Open Questions

- 是否需要为 AI 开关添加权限控制（如仅管理员可修改）？
- 是否需要在开关关闭时清除待处理的 AI 分析任务队列？
