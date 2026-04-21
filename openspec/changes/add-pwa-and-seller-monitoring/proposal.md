## Why

当前监控器以商品关键词为核心，缺少商家维度监控、精确 ID 搜索、PWA 桌面化体验以及动态指标（价格/想要数）变化通知。用户需要更精细的监控能力和更及时的通知机制。

## What Changes

- **新增商家维度监控** - 通过卖家 ID 监控其店铺下所有商品，支持按商家维度设置监控规则
- **新增商品 ID 精确搜索** - 支持通过闲鱼商品 ID 直接定位特定商品
- **PWA 桌面化体验** - 配置 PWA manifest 和 Service Worker，支持安装为桌面应用、独立窗口运行
- **新增动态指标监控** - 追踪商品价格变化和想要数变化，触发阈值时推送通知
- **新增飞书/钉钉通知渠道** - 扩展 NotificationService 支持企业协作工具推送

## Capabilities

### New Capabilities
- `seller-monitoring`: 商家维度监控，包括卖家 ID 解析、店铺商品列表抓取、商家维度的过滤规则
- `item-id-search`: 通过闲鱼商品 ID 精确搜索和定位特定商品
- `pwa-desktop`: PWA 配置（manifest.json、Service Worker），支持桌面安装和独立窗口运行
- `metrics-tracking`: 价格和想要数历史追踪、变化检测、阈值告警规则
- `feishu-dingtalk-notification`: 飞书和钉钉 Webhook 通知渠道集成

### Modified Capabilities
- `notification-system`: 扩展现有通知系统以支持新的通知渠道和触发条件

## Impact

- **前端**: `web-ui/` 需要添加 PWA manifest、Service Worker 注册、安装提示 UI
- **后端**: `src/services/` 新增 SellerMonitoringService，扩展 AIAnalysisService 支持指标追踪
- **爬虫**: `src/scraper.py` 需要支持卖家 ID 搜索和商品 ID 精确查询
- **数据库**: 新增卖家信息表、商品指标历史记录表
- **通知**: `NotificationService` 新增飞书/钉钉发送方法，支持基于指标变化的触发逻辑
