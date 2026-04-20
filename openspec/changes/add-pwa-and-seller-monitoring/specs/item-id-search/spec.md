## ADDED Requirements

### Requirement: 用户可以通过商品 ID 精确搜索
系统 SHALL 支持通过闲鱼商品 ID 精确查找特定商品。

#### Scenario: 商品 ID 搜索
- **WHEN** 用户提供完整的商品 ID
- **THEN** 系统直接访问商品详情页，获取商品信息并返回

#### Scenario: 商品 ID 无效处理
- **WHEN** 商品 ID 不存在或商品已下架
- **THEN** 系统返回明确的错误提示「商品不存在或已下架」

#### Scenario: 商品 ID 搜索历史记录
- **WHEN** 用户执行商品 ID 搜索后
- **THEN** 系统记录搜索历史，支持用户快速查看最近搜索过的商品 ID

### Requirement: 商品 ID 与监控任务关联
系统 SHALL 支持将商品 ID 搜索结果与现有监控任务关联。

#### Scenario: 商品加入监控
- **WHEN** 用户通过 ID 搜索到商品后点击「加入监控」
- **THEN** 系统创建新的监控任务或添加到现有任务的商品追踪列表
