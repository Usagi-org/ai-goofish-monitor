## Why

当前系统中 AI 功能分散在多处（AI 分析、AI 推荐、AI 智能策略等），用户无法一键禁用所有 AI 相关功能。虽然已有 `SKIP_AI_ANALYSIS` 环境变量，但：
1. 前端仍显示 AI 相关 UI（AI Match、AI 推荐标识、AI 智能策略卡片）
2. 创建任务时仍有 AI 判断逻辑
3. 需要修改配置文件或环境变量，不够便捷

需要一个统一的开关，让用户可以在设置页面一键禁用/启用所有 AI 功能，避免对不需要 AI 的用户产生干扰。

## What Changes

- **新增**：设置页面"AI 功能"总开关（启用/禁用）
- **新增**：数据库持久化存储 AI 开关状态
- **新增**：后端 API 获取/更新 AI 功能开关状态
- **修改**：前端 AI 相关 UI 根据开关动态显示/隐藏
- **修改**：任务创建时跳过 AI 相关逻辑（AI 生成标准、图片分析等）
- **修改**：结果展示时不显示 AI 分析相关字段

## Capabilities

### New Capabilities

- `ai-toggle`: AI 功能全局开关能力，包括设置存储、API 接口、前端开关组件

### Modified Capabilities

- `task-management`: 任务创建/更新时根据 AI 开关跳过 AI 相关逻辑
- `result-display`: 结果展示时根据 AI 开关隐藏 AI 分析字段

## Impact

- **前端**: `SettingsView.vue`, `TaskForm.vue`, `ResultCard.vue`, Dashboard AI 策略卡片
- **后端**: `SettingsView.vue` 对应的 API, `task_generation_runner.py`, `item_analysis_dispatcher.py`
- **数据库**: 新增 `app_settings` 表或扩展现有配置表存储 AI 开关状态
- **API**: 新增 `/api/settings/ai-enabled` GET/PUT 接口
