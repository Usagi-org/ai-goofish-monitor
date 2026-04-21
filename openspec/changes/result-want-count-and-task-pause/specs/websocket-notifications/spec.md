## ADDED Requirements

### Requirement: 定时任务完成后通过 WebSocket 推送通知
系统必须在定时任务执行完成后，通过 WebSocket 向所有连接的客户端推送完成通知。

#### Scenario: 任务完成推送
- **WHEN** 定时任务执行完成（爬虫进程结束）
- **THEN** 系统通过 WebSocket 广播 task_completed 消息，包含 task_id、task_name、completed_at、items_count

#### Scenario: 推送失败处理
- **WHEN** WebSocket 连接已断开
- **THEN** 系统将断开的连接从 active_connections 中移除，不影响其他连接的推送

### Requirement: 前端实时显示任务完成通知
前端必须在收到 task_completed 消息后，向用户显示 Toast 通知。

#### Scenario: 显示任务完成 Toast
- **WHEN** 前端收到 task_completed WebSocket 消息
- **THEN** 显示 Toast 通知"任务 {task_name} 已完成，发现 {items_count} 个商品"

#### Scenario: WebSocket 断线重连
- **WHEN** WebSocket 连接断开
- **THEN** 前端自动重连，确保后续通知能正常接收
