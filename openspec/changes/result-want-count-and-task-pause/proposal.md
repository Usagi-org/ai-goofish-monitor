## Why

用户在使用监控机器人时发现三个关键问题：
1. 结果页面缺少"想要数"字段，无法快速判断商品热度
2. 定时任务无法暂停/恢复，用户需要手动删除任务来停止监控
3. 定时任务执行后页面不会自动更新，用户需要手动刷新才能看到新数据

## What Changes

- **结果页面显示想要数** - 在 ResultCard 组件中添加"想要数"字段展示
- **定时任务暂停/恢复功能** - 新增任务 `is_paused` 状态字段，支持暂停和恢复操作
- **定时任务完成后的实时通知** - WebSocket 推送 + 前端 Toast 提示
- **页面数据自动刷新** - 前端监听 WebSocket 消息后自动重新获取结果数据

## Capabilities

### New Capabilities

- `task-pause-resume`: 任务的暂停/恢复状态管理，包括数据库字段、API 端点、前端 UI
- `websocket-notifications`: 定时任务完成后的 WebSocket 实时推送机制
- `result-want-count-display`: 结果卡片展示想要数的 UI 功能

### Modified Capabilities

- `task-management`: 任务状态从简单的 is_running 扩展到包含 is_paused 状态

## Impact

- **后端**:
  - `src/domain/models/task.py` - 添加 `is_paused` 字段
  - `src/services/scheduler_service.py` - 暂停逻辑判断
  - `src/api/routes/tasks.py` - 新增暂停/恢复 API
  - `src/api/routes/websocket.py` - 新增任务完成通知推送
  - 数据库迁移 - 添加 `is_paused` 字段
- **前端**:
  - `web-ui/src/components/results/ResultCard.vue` - 显示想要数
  - `web-ui/src/components/tasks/TasksTable.vue` - 暂停/恢复按钮
  - `web-ui/src/composables/useTasks.ts` - 新增 API 调用
  - `web-ui/src/composables/useResults.ts` - WebSocket 监听自动刷新
  - `web-ui/src/types/task.d.ts` - 类型定义更新
