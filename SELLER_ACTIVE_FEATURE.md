# 卖家活跃时间检测功能

## 功能概述

在搜索商品时自动检测卖家的上线时间（最后活跃时间），并在前台提供筛选选项，帮助用户快速定位活跃卖家，提高沟通效率和购买成功率。

## 主要特性

1. **卖家活跃时间检测**
   - 从闲鱼用户个人主页 API 采集最后活跃时间
   - 从商品详情页 API 获取卖家在线状态
   - 智能解析和格式化活跃时间
   - 计算活跃度等级（非常活跃/活跃/一般/不活跃）

2. **前台筛选功能**
   - 任务创建时可选择卖家活跃时间范围
   - 结果查看时可筛选特定活跃时间段的商品
   - 支持 5 个时间段选项：
     - 不限（默认）
     - 1 小时内活跃
     - 24 小时内活跃
     - 3 天内活跃
     - 7 天内活跃

3. **智能格式化显示**
   - 刚刚在线（<1 分钟）
   - X 分钟前（1-60 分钟）
   - X 小时前（1-24 小时）
   - X 天前（1-7 天）
   - X 周前（7-30 天）
   - 具体日期（超过 30 天）

## 技术实现

### 后端服务

#### 1. `src/services/seller_active_service.py`
```python
# 核心服务函数
- format_active_time(last_active_time)       # 格式化活跃时间
- is_seller_recently_active(time, hours)     # 判断是否活跃
- get_active_level(last_active_time)         # 获取活跃等级
```

#### 2. `src/parsers.py`
扩展 `parse_user_head_data` 函数，添加：
- 提取 `lastActiveTime` 字段
- 提取 `onlineStatus` 字段

#### 3. `src/scraper.py`
在详情页采集中添加：
- 从 `sellerDO` 对象提取活跃时间
- 传递给 `ItemAnalysisJob`

#### 4. `src/services/item_analysis_dispatcher.py`
- 扩展 `ItemAnalysisJob` 新增字段
- 在加载卖家信息时集成活跃时间处理
- 添加格式化后的活跃时间字段

### 前端组件

#### 1. 任务表单 `TaskForm.vue`
添加"卖家活跃时间"筛选区域：
```vue
<Select v-model="form.seller_active_option">
  <SelectItem value="__none__">不筛选</SelectItem>
  <SelectItem value="1 小时内">1 小时内活跃</SelectItem>
  <SelectItem value="24 小时内">24 小时内活跃</SelectItem>
  <SelectItem value="3 天内">3 天内活跃</SelectItem>
  <SelectItem value="7 天内">7 天内活跃</SelectItem>
</Select>
```

#### 2. 类型定义 `result.d.ts`
扩展 `SellerInfo` 接口：
```typescript
interface SellerInfo {
  "卖家最后活跃时间"?: string;
  "卖家活跃时间格式化"?: string;
  "卖家活跃等级"?: string;
  "卖家在线状态"?: string;
  // ... 其他字段
}
```

#### 3. 翻译文件 `zh-CN-extra.ts`
添加中英文翻译支持。

## 数据流程

```
1. 爬虫访问用户个人主页
   ↓
2. 调用 mtop.idle.web.user.page.head API
   ↓
3. 提取 lastActiveTime 和 onlineStatus
   ↓
4. 访问商品详情页
   ↓
5. 从 sellerDO 对象提取活跃信息
   ↓
6. 传递给 ItemAnalysisDispatcher
   ↓
7. 格式化活跃时间（format_active_time）
   ↓
8. 计算活跃等级（get_active_level）
   ↓
9. 合并到卖家信息并存储
   ↓
10. 前端根据筛选条件过滤
```

## 使用方式

### 创建任务时筛选

1. 创建新任务
2. 展开"卖家活跃时间"部分
3. 选择活跃时间范围（如"24 小时内活跃"）
4. 系统会自动筛选符合条件的商品

### 结果查看时筛选

1. 在结果页面
2. 使用筛选栏中的"卖家活跃时间"选项
3. 动态过滤已采集的商品

## 活跃等级说明

| 等级 | 条件 | 说明 |
|------|------|------|
| 非常活跃 | 1 小时内 | 卖家正在线或刚刚离开 |
| 活跃 | 24 小时内 | 卖家今天活跃过 |
| 一般 | 72 小时内 | 卖家最近 3 天活跃 |
| 不活跃 | 超过 72 小时 | 卖家较长时间未活跃 |
| 未知 | 无法获取 | API 未返回活跃时间 |

## API 字段说明

### 用户个人主页 API
```json
{
  "data": {
    "module": {
      "base": {
        "userInfo": {
          "lastActiveTime": "2024-01-15T10:30:00Z",
          "onlineStatus": "online"
        }
      }
    }
  }
}
```

### 商品详情页 API
```json
{
  "data": {
    "sellerDO": {
      "lastActiveTime": "2024-01-15T10:30:00Z",
      "onlineStatus": "online",
      "activeType": "recent"
    }
  }
}
```

## 示例输出

### 格式化活跃时间
```
输入："2024-01-15T10:30:00+08:00"
输出："2 小时前"

输入："2024-01-14T10:30:00+08:00"
输出："1 天前"

输入：null
输出："未知"
```

### 活跃等级
```
输入："2024-01-15T10:30:00+08:00" (当前时间 11:30)
输出："非常活跃"

输入："2024-01-15T08:30:00+08:00" (当前时间 20:30)
输出："活跃"

输入："2024-01-12T10:30:00+08:00"
输出："一般"

输入："2024-01-01T10:30:00+08:00"
输出："不活跃"
```

## 注意事项

1. **数据可用性**: 不是所有卖家都有活跃时间数据，取决于闲鱼 API 返回
2. **隐私保护**: 部分卖家可能隐藏了活跃状态
3. **实时性**: 活跃时间不是实时更新的，有一定延迟
4. **缓存**: 卖家信息会被缓存，避免重复请求

## 未来优化

- [ ] 支持按卖家活跃等级排序
- [ ] 在商品卡片中直观展示活跃等级徽章
- [ ] 支持"只看不活跃卖家"的排除选项
- [ ] 统计卖家平均响应时间
- [ ] 结合评价时间计算活跃度

## 相关文件

### 后端
- `src/services/seller_active_service.py` - 活跃时间服务
- `src/parsers.py` - 用户数据解析
- `src/scraper.py` - 数据采集
- `src/services/item_analysis_dispatcher.py` - 信息集成

### 前端
- `web-ui/src/components/tasks/TaskForm.vue` - 任务表单
- `web-ui/src/types/result.d.ts` - 类型定义
- `web-ui/src/i18n/messages/zh-CN-extra.ts` - 翻译

## 测试验证

运行 Python 测试：
```python
from src.services.seller_active_service import (
    format_active_time,
    get_active_level,
)

# 测试格式化
print(format_active_time("2024-01-15T10:30:00+08:00"))
# 输出："2 小时前"

# 测试活跃等级
print(get_active_level("2024-01-15T10:30:00+08:00"))
# 输出："非常活跃"
```

## 更新日志

- 2024-01-20: 初始版本发布
  - 添加卖家活跃时间检测
  - 支持 5 个时间段筛选
  - 智能格式化显示
  - 活跃等级评估
