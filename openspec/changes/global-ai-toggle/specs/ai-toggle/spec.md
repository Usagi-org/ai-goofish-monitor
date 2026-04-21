## ADDED Requirements

### Requirement: 用户可以启用或禁用 AI 功能
系统应提供一个全局开关，允许用户启用或禁用所有 AI 相关功能。开关状态应持久化存储并在整个系统中生效。

#### Scenario: 用户在设置页面关闭 AI 功能
- **WHEN** 用户在设置页面将 AI 功能开关切换到"关闭"状态
- **THEN** 系统保存设置，所有 AI 相关 UI 和功能被禁用

#### Scenario: 用户在设置页面开启 AI 功能
- **WHEN** 用户在设置页面将 AI 功能开关切换到"开启"状态
- **THEN** 系统保存设置，所有 AI 相关 UI 和功能恢复正常

#### Scenario: 用户刷新页面后开关状态保持
- **WHEN** 用户关闭 AI 功能后刷新浏览器页面
- **THEN** AI 功能开关仍显示为"关闭"状态

### Requirement: 系统获取 AI 功能开关状态
系统应提供 API 接口供前端查询当前 AI 功能的启用状态。

#### Scenario: 前端应用启动时获取开关状态
- **WHEN** 前端应用加载完成
- **THEN** 前端调用 API 获取当前 AI 功能开关状态并更新 UI

#### Scenario: AI 开关状态变更后重新获取
- **WHEN** 用户切换 AI 功能开关
- **THEN** 前端调用 API 确认开关状态已更新

### Requirement: 任务创建时根据 AI 开关跳过 AI 逻辑
当 AI 功能被禁用时，创建任务应自动跳过 AI 相关的处理逻辑。

#### Scenario: AI 禁用状态下创建新任务
- **WHEN** AI 功能被禁用且用户创建新任务
- **THEN** 系统自动使用默认配置，不调用 AI 生成分析标准

#### Scenario: AI 禁用状态下任务表单隐藏 AI 选项
- **WHEN** AI 功能被禁用且用户打开任务创建表单
- **THEN** 表单不显示 AI 决策模式、图片分析等 AI 相关选项

### Requirement: 结果展示时根据 AI 开关隐藏 AI 分析
当 AI 功能被禁用时，结果页面不应显示 AI 分析相关字段和标识。

#### Scenario: AI 禁用状态下查看结果
- **WHEN** AI 功能被禁用且用户查看结果列表
- **THEN** 结果卡片不显示 AI Match 百分比、AI 推荐理由等信息

#### Scenario: AI 禁用状态下 Dashboard 不显示 AI 策略
- **WHEN** AI 功能被禁用且用户查看 Dashboard
- **THEN** Dashboard 不显示"AI 智能策略"卡片
