## 1. 数据库迁移

- [ ] 1.1 在 `sqlite_connection.py` 中为 `tasks` 表添加 `is_paused` 字段（BOOLEAN DEFAULT 0）
- [ ] 1.2 确保迁移逻辑支持 IF NOT EXISTS，避免重复执行报错

## 2. 后端模型更新

- [ ] 2.1 在 `src/domain/models/task.py` 的 Task 和 TaskUpdate 中添加 `is_paused: bool = False` 字段
- [ ] 2.2 更新 `web-ui/src/types/task.d.ts` 前端类型定义，添加 `is_paused: boolean`

## 3. 后端暂停/恢复 API 实现

- [ ] 3.1 在 `src/services/scheduler_service.py` 中添加 `pause_task(task_id)` 方法
- [ ] 3.2 在 `src/services/scheduler_service.py` 中添加 `resume_task(task_id)` 方法
- [ ] 3.3 在 `src/api/routes/tasks.py` 中添加 `POST /api/tasks/{task_id}/pause` 端点
- [ ] 3.4 在 `src/api/routes/tasks.py` 中添加 `POST /api/tasks/{task_id}/resume` 端点

## 4. 后端 WebSocket 通知实现

- [ ] 4.1 在 `src/services/process_service.py` 中，任务完成时调用 `websocket.broadcast_message("task_completed", {...})`
- [ ] 4.2 确保广播消息包含 task_id、task_name、completed_at、items_count 字段

## 5. 前端任务列表 UI 更新

- [ ] 5.1 在 `web-ui/src/components/tasks/TasksTable.vue` 中为暂停/恢复按钮添加列
- [ ] 5.2 根据任务 is_paused 状态显示不同按钮（暂停中显示"恢复"，否则显示"暂停"）
- [ ] 5.3 在 `web-ui/src/composables/useTasks.ts` 中添加 `pauseTask` 和 `resumeTask` 函数

## 6. 前端结果卡片想要数显示

- [ ] 6.1 在 `web-ui/src/components/results/ResultCard.vue` 中添加想要数字段展示
- [ ] 6.2 处理想要数为空时的显示逻辑（显示"—"）
- [ ] 6.3 处理大数字格式化（超过 1000 显示为 1k+）

## 7. 前端 WebSocket 监听和自动刷新

- [ ] 7.1 在 `web-ui/src/composables/useResults.ts` 中添加 WebSocket 监听
- [ ] 7.2 收到 `task_completed` 消息后自动调用 `refreshResults()`
- [ ] 7.3 收到消息后显示 Toast 通知

## 8. 测试验证

- [ ] 8.1 验证暂停功能：暂停任务后 cron 不再触发
- [ ] 8.2 验证恢复功能：恢复任务后 cron 正常执行
- [ ] 8.3 验证 WebSocket 通知：任务完成后前端收到消息
- [ ] 8.4 验证想要数显示：结果卡片正确展示想要数
