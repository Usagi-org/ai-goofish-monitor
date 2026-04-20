## 1. 数据库迁移

- [x] 1.1 创建 `app_settings` 表（key, value, updated_at）
- [x] 1.2 添加初始化默认值（ai_enabled = true）
- [x] 1.3 编写数据库迁移脚本并测试

## 2. 后端 - AI 开关 API

- [x] 2.1 创建 `AiToggleService` 服务类
- [x] 2.2 添加 `GET /api/settings/ai-enabled` 接口获取开关状态
- [x] 2.3 添加 `PUT /api/settings/ai-enabled` 接口更新开关状态
- [x] 2.4 在 `src/config.py` 中添加全局变量同步开关状态

## 3. 后端 - AI 逻辑条件判断

- [x] 3.1 在 `task_generation_runner.py` 中添加 AI 开关检查
- [x] 3.2 在 `item_analysis_dispatcher.py` 中添加 AI 开关检查
- [x] 3.3 在 `scraper.py` 中传递 AI 开关状态

## 4. 前端 - 设置状态管理

- [x] 4.1 在 `useSettings.ts` 中添加 `isAiEnabled` 状态
- [x] 4.2 添加 `getAiEnabled()` 和 `setAiEnabled()` API 函数
- [x] 4.3 添加 TypeScript 类型定义

## 5. 前端 - 设置页面 UI

- [x] 5.1 在 `SettingsView.vue` 中添加 AI 开关切换组件
- [x] 5.2 添加开关状态同步逻辑
- [x] 5.3 添加切换成功/失败提示

## 6. 前端 - AI 相关 UI 条件渲染

- [x] 6.1 `TaskForm.vue` 隐藏 AI 决策模式、图片分析选项
- [x] 6.2 `ResultCard.vue` 隐藏 AI Match、AI 推荐理由
- [x] 6.3 `DashboardView.vue` 隐藏"AI 智能策略"卡片
- [x] 6.4 其他组件检查并添加条件渲染

## 7. 测试与验证

- [x] 7.1 测试 AI 开关切换后端 API
- [x] 7.2 测试前端 UI 根据开关正确显示/隐藏
- [x] 7.3 测试任务创建时跳过 AI 逻辑
- [x] 7.4 验证开关状态刷新后保持
