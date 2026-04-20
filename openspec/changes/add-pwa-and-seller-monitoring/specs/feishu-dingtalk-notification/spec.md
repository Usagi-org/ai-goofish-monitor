## ADDED Requirements

### Requirement: 系统 SHALL 支持飞书 Webhook 通知
系统 SHALL 支持通过飞书群机器人 Webhook 推送通知消息。

#### Scenario: 飞书 Webhook 配置
- **WHEN** 用户在 .env 中配置 FEISHU_WEBHOOK_URL
- **THEN** 系统初始化飞书通知渠道

#### Scenario: 发送飞书通知
- **WHEN** 触发通知条件（价格变化、想要数激增等）
- **THEN** 系统向飞书 Webhook 发送 POST 请求，包含商品标题、图片、价格、链接

#### Scenario: 飞书消息格式
- **WHEN** 发送飞书消息时
- **THEN** 使用飞书要求的 JSON 格式（text 或 post 类型），包含富文本和商品图片

### Requirement: 系统 SHALL 支持钉钉 Webhook 通知
系统 SHALL 支持通过钉钉群机器人 Webhook 推送通知消息。

#### Scenario: 钉钉 Webhook 配置
- **WHEN** 用户在 .env 中配置 DINGTALK_WEBHOOK_URL
- **THEN** 系统初始化钉钉通知渠道

#### Scenario: 发送钉钉通知
- **WHEN** 触发通知条件时
- **THEN** 系统向钉钉 Webhook 发送 POST 请求，包含商品信息

#### Scenario: 钉钉消息格式
- **WHEN** 发送钉钉消息时
- **THEN** 使用钉钉要求的 markdown 或 link 消息格式

### Requirement: 通知渠道优先级
系统 SHALL 支持同时配置多个通知渠道，按优先级依次发送。

#### Scenario: 多渠道同时推送
- **WHEN** 用户配置了多个通知渠道（ntfy/Bark/飞书/钉钉等）
- **THEN** 系统同时向所有启用的渠道发送通知

#### Scenario: 发送失败重试
- **WHEN** 某个通知渠道发送失败时
- **THEN** 系统重试 3 次，仍失败则记录错误日志但不影响其他渠道
