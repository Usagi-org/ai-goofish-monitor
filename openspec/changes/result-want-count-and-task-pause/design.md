## Context

本项目是基于 Playwright + AI 的闲鱼智能监控机器人，采用 FastAPI 后端 + Vue 3 前端的架构。当前已具备：
- 定时任务调度系统（APScheduler）
- WebSocket 实时通信基础设施
- 任务管理服务（创建、编辑、删除、启动、停止）
- 结果展示页面（包含商品卡片、筛选器）

现有的任务状态只有 `is_running` 字段，无法表达"已暂停"状态。WebSocket 主要用于任务状态广播，但未用于任务完成通知。

## Goals / Non-Goals

**Goals:**
- 在结果卡片上显示"想要数"字段（数据已存在于 ProductInfo 类型中）
- 为定时任务增加暂停/恢复功能，无需删除任务即可停止监控
- 定时任务完成后通过 WebSocket 推送通知，前端自动刷新并显示 Toast
- 保持前后端代码风格与现有架构一致

**Non-Goals:**
- 不修改现有的任务调度核心逻辑（APScheduler）
- 不修改爬虫抓取逻辑
- 不涉及数据库表结构大改（仅添加一个字段）
- 不修改用户认证/权限系统

## Decisions

### 1. 任务暂停状态存储方案
**决策**: 在 `tasks` 表中新增 `is_paused` 字段（BOOLEAN, 默认 false）

**原因**:
- 简单直接，与现有 `enabled`、`is_running` 字段风格一致
- 无需额外表或复杂状态机
- 查询性能好，判断逻辑简单

**替代方案**:
- 使用状态枚举（pending/running/paused/stopped）- 过于复杂，需要大规模重构
- 使用外部配置文件存储暂停状态 - 增加 I/O 开销，一致性难保证

### 2. 定时任务暂停实现方式
**决策**: 暂停时从调度器移除 Job，恢复时重新添加 Job

**原因**:
- APScheduler 原生支持 `remove_job` 和 `add_job`
- 暂停期间完全不消耗资源
- 恢复时使用原有 cron 表达式，行为可预测

**实现细节**:
- `pause_task(task_id)`: 调用 `scheduler.remove_job(f"task_{task_id}")`
- `resume_task(task_id)`: 从数据库读取 cron，重新 `scheduler.add_job(...)`

### 3. WebSocket 通知协议
**决策**: 新增消息类型 `task_completed`，携带任务 ID、任务名称、完成时间、商品数量

**消息格式**:
```json
{
  "type": "task_completed",
  "data": {
    "task_id": 123,
    "task_name": "MacBook",
    "completed_at": "2026-04-03T10:30:00Z",
    "items_count": 15
  }
}
```

**原因**: 与现有 `task_status_changed` 消息风格保持一致

### 4. 前端自动刷新策略
**决策**: 在 `ResultsView` 中监听 WebSocket，收到 `task_completed` 后调用 `refreshResults()`

**原因**:
- 简单直接，利用现有的 `useResults` composable
- 只在结果页面监听，不影响其他页面性能
- 用户可以看到最新数据，同时有明确的刷新按钮作为备选

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 数据库迁移可能失败 | 添加 IF NOT EXISTS 检查，启动时自动执行迁移 |
| 暂停任务后 cron 表达式丢失 | 从数据库读取完整任务信息后重建 Job |
| WebSocket 连接断开导致通知丢失 | 前端重连机制已存在，后端广播时清理断开连接 |
| 多用户同时操作状态冲突 | SQLite 事务保证一致性，前端乐观更新 + 失败回滚 |
| 想要数字段可能为空 | 前端做空值处理，显示"—"或隐藏该字段 |

## Migration Plan

### 数据库迁移
```python
# 在 sqlite_connection.py 的 bootstrap_sqlite_storage() 中
cursor.execute("ALTER TABLE tasks ADD COLUMN is_paused BOOLEAN DEFAULT 0")
```

### 部署步骤
1. 后端代码更新后重启服务
2. 数据库迁移自动执行
3. 前端重新构建或开发模式自动热更新

### 回滚策略
1. 回滚代码到上一版本
2. `is_paused` 字段保留但不影响运行（旧代码忽略该字段）
3. 如需删除字段：`ALTER TABLE tasks DROP COLUMN is_paused`

## Open Questions

无
