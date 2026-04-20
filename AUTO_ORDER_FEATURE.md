# 自动下单功能

## 功能概述

当搜索到符合指定价格的商品后，系统可以自动生成下单链接并推送通知，实现半自动化的商品监控和购买流程。

## 主要特性

1. **价格匹配检测**
   - 支持设置目标价格（当商品价格 ≤ 目标价时触发）
   - 支持设置价格区间（当商品价格在最低价和最高价之间时触发）
   - 目标价格优先级高于价格区间

2. **下单链接生成**
   - 自动生成 PC 端下单链接
   - 自动生成移动端下单链接
   - 链接直接跳转到闲鱼订单确认页面

3. **通知推送**
   - 发现商品时通知（价格匹配才发送）
   - 下单链接自动附加到通知中
   - 支持所有已配置的通知渠道（Ntfy、Bark、Telegram、企业微信等）

## 配置方式

### 1. 创建任务时配置

在 Web UI 创建或编辑任务时，展开"自动下单"部分：

- **启用自动下单**: 开启后会根据价格匹配自动生成下单链接
- **目标价格**: 设置期望的购买价格（可选）
  - 如果设置了目标价格，当商品价格 ≤ 目标价时触发
  - 如果未设置，则使用价格范围判断
- **下单操作**:
  - `仅通知`: 只发送通知，不生成链接
  - `生成下单链接`: 价格匹配时生成下单链接并通知
  - `自动购买`: 实验性功能，暂未完全实现

### 2. API 配置

通过 API 创建任务时，添加以下字段：

```json
{
  "task_name": "测试任务",
  "keyword": "iPhone 15",
  "min_price": "4000",
  "max_price": "5000",
  "auto_order_enabled": true,
  "auto_order_target_price": "4500",
  "auto_order_action": "generate_link"
}
```

## 工作流程

1. **商品搜索**: 爬虫监控搜索结果
2. **价格检测**: 对每个商品检查价格是否匹配设定条件
3. **链接生成**: 如果价格匹配，生成下单链接
4. **通知推送**: 发送通知，包含商品信息和下单链接
5. **用户操作**: 用户点击通知中的链接，跳转到闲鱼订单确认页手动完成支付

## 通知示例

当发现符合价格条件的商品时，通知内容会包含：

```
商品标题：iPhone 15 Pro Max 256G 蓝色钛金属
当前售价：8999
下单链接 (PC): https://www.goofish.com/order/confirm?itemId=xxx&price=8999
下单链接 (手机): https://m.goofish.com/order/confirm?itemId=xxx&price=8999

[自动下单] 价格匹配，已生成下单链接，请点击链接购买。
```

## 技术实现

### 后端服务

- `src/services/auto_order_service.py`: 自动下单核心逻辑
- `src/services/order_link_service.py`: 订单链接生成
- `src/services/item_analysis_dispatcher.py`: 集成到商品分析流程

### 前端组件

- `web-ui/src/components/tasks/TaskForm.vue`: 添加自动下单配置 UI
- `web-ui/src/i18n/messages/zh-CN-extra.ts`: 添加翻译

### 数据模型

任务模型新增字段：

```python
class Task(BaseModel):
    auto_order_enabled: bool = False
    auto_order_target_price: Optional[str] = None
    auto_order_action: Literal["notify_only", "generate_link", "auto_buy"] = "notify_only"
```

## 注意事项

1. **半自动模式**: 当前实现为半自动，生成链接后需要用户手动点击并确认支付
2. **价格格式**: 价格支持多种格式（如 `5000`、`¥5,000`、`5000.00`）
3. **链接有效期**: 生成的下单链接直接跳转到闲鱼，链接本身长期有效，但商品可能下架
4. **安全提示**: 请确保在官方闲鱼网站打开链接，避免钓鱼风险

## 未来计划

- [ ] 自动填写收货地址
- [ ] 自动提交订单（需要闲鱼 API 支持）
- [ ] 多商品比价功能
- [ ] 历史价格趋势分析
- [ ] 自动议价功能

## 测试

运行测试脚本：

```bash
python3 << 'PYEOF'
from src.services.auto_order_service import AutoOrderService

service = AutoOrderService()
is_match, reason = service.check_price_match(
    item_price="4500",
    target_price="5000",
    min_price=None,
    max_price=None
)
print(f"价格匹配：{is_match}, 原因：{reason}")
PYEOF
```

## 相关文档

- [任务管理](./README.md#任务管理)
- [通知推送配置](./README.md#通知推送)
- [价格筛选](./README.md#价格筛选)
