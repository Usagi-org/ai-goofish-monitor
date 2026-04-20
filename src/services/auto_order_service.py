"""
自动下单服务
处理价格匹配检测和下单逻辑
"""
import asyncio
from typing import Dict, Optional, Tuple

from src.services.order_link_service import OrderLinkService


class AutoOrderService:
    """自动下单服务"""
    
    def __init__(self):
        self.order_link_service = OrderLinkService()
    
    def check_price_match(
        self,
        item_price: str,
        target_price: Optional[str],
        min_price: Optional[str],
        max_price: Optional[str]
    ) -> Tuple[bool, str]:
        """
        检查商品价格是否匹配设定条件
        
        Args:
            item_price: 商品当前价格
            target_price: 目标价格（如果设置了，则优先使用）
            min_price: 最低价格
            max_price: 最高价格
            
        Returns:
            (是否匹配，匹配原因)
        """
        try:
            price_value = float(str(item_price).replace("¥", "").replace(",", "").strip())
        except (ValueError, TypeError, AttributeError):
            return False, "价格格式异常"
        
        # 如果设置了目标价格，检查是否等于或低于目标价
        if target_price:
            try:
                target_value = float(str(target_price).replace("¥", "").replace(",", "").strip())
                if price_value <= target_value:
                    return True, f"价格 {price_value:.2f} 已达到目标价 {target_value:.2f}"
                return False, f"价格 {price_value:.2f} 高于目标价 {target_value:.2f}"
            except (ValueError, TypeError):
                return False, "目标价格格式异常"
        
        # 如果设置了价格区间，检查是否在区间内
        if min_price or max_price:
            min_value = None
            max_value = None
            
            try:
                if min_price:
                    min_value = float(str(min_price).replace("¥", "").replace(",", "").strip())
            except (ValueError, TypeError):
                pass
            
            try:
                if max_price:
                    max_value = float(str(max_price).replace("¥", "").replace(",", "").strip())
            except (ValueError, TypeError):
                pass
            
            # 检查价格区间
            if min_value is not None and price_value < min_value:
                return False, f"价格 {price_value:.2f} 低于最低价 {min_value:.2f}"
            if max_value is not None and price_value > max_value:
                return False, f"价格 {price_value:.2f} 高于最高价 {max_value:.2f}"
            
            if min_value is not None or max_value is not None:
                return True, f"价格 {price_value:.2f} 在设定区间内"
        
        # 没有设置任何价格条件，默认匹配
        return True, "未设置价格条件"
    
    async def process_auto_order(
        self,
        item_data: Dict,
        task_config: Dict,
    ) -> Dict:
        """
        处理自动下单逻辑
        
        Args:
            item_data: 商品数据
            task_config: 任务配置
            
        Returns:
            处理结果
        """
        auto_order_enabled = task_config.get("auto_order_enabled", False)
        auto_order_action = task_config.get("auto_order_action", "notify_only")
        auto_order_target_price = task_config.get("auto_order_target_price")
        min_price = task_config.get("min_price")
        max_price = task_config.get("max_price")
        
        result = {
            "should_notify": True,
            "order_link": None,
            "mobile_order_link": None,
            "action_taken": "none",
            "reason": "",
        }
        
        # 检查价格是否匹配
        item_price = str(item_data.get("当前售价", ""))
        is_match, reason = self.check_price_match(
            item_price=item_price,
            target_price=auto_order_target_price,
            min_price=min_price,
            max_price=max_price,
        )
        
        result["reason"] = reason
        
        if not is_match:
            result["should_notify"] = False
            return result
        
        # 如果不启用自动下单，只通知
        if not auto_order_enabled:
            result["reason"] = f"{reason}（未启用自动下单）"
            return result
        
        # 根据操作类型处理
        if auto_order_action == "notify_only":
            result["action_taken"] = "notify_only"
            
        elif auto_order_action == "generate_link":
            # 生成订单链接
            item_id = str(item_data.get("商品 ID", ""))
            seller_id = str(item_data.get("卖家 ID", "")) if item_data.get("卖家 ID") else None
            
            result["order_link"] = self.order_link_service.generate_order_link(
                item_id=item_id,
                price=item_price,
                seller_id=seller_id,
            )
            
            result["mobile_order_link"] = self.order_link_service.generate_mobile_order_link(
                item_id=item_id,
                price=item_price,
                seller_id=seller_id,
            )
            
            result["action_taken"] = "link_generated"
            result["reason"] = f"{reason} - 已生成下单链接"
            
        elif auto_order_action == "auto_buy":
            # TODO: 实现自动购买逻辑（需要闲鱼 API 支持）
            # 目前生成链接并提示用户手动购买
            item_id = str(item_data.get("商品 ID", ""))
            seller_id = str(item_data.get("卖家 ID", "")) if item_data.get("卖家 ID") else None
            
            result["order_link"] = self.order_link_service.generate_order_link(
                item_id=item_id,
                price=item_price,
                seller_id=seller_id,
            )
            
            result["mobile_order_link"] = self.order_link_service.generate_mobile_order_link(
                item_id=item_id,
                price=item_price,
                seller_id=seller_id,
            )
            
            result["action_taken"] = "auto_buy_pending"
            result["reason"] = f"{reason} - 自动购买暂未完全实现，请手动点击链接购买"
        
        return result
    
    async def send_order_success_notification(
        self,
        item_data: Dict,
        task_name: str,
        price: str,
        notification_service=None
    ):
        """
        发送下单成功通知
        
        Args:
            item_data: 商品数据
            task_name: 任务名称
            price: 成交价格
            notification_service: 通知服务实例
        """
        if not notification_service:
            return
        
        notification_data = {
            "商品标题": f"[下单成功] {item_data.get('商品标题', '未知商品')}",
            "当前售价": price,
            "商品链接": item_data.get("商品链接", "#"),
            "任务名称": task_name,
            "下单时间": item_data.get("snapshot_time", ""),
        }
        
        reason = f"任务 '{task_name}' 监控到商品价格为 {price}，已自动/手动下单。"
        
        try:
            await notification_service.send_notification(notification_data, reason)
        except Exception as e:
            # 记录错误但不抛出异常
            print(f"发送下单成功通知失败：{e}")
    
    async def send_order_failure_notification(
        self,
        item_data: Dict,
        task_name: str,
        failure_reason: str,
        notification_service=None
    ):
        """
        发送下单失败通知
        
        Args:
            item_data: 商品数据
            task_name: 任务名称
            failure_reason: 失败原因
            notification_service: 通知服务实例
        """
        if not notification_service:
            return
        
        notification_data = {
            "商品标题": f"[下单失败] {item_data.get('商品标题', '未知商品')}",
            "当前售价": str(item_data.get("当前售价", "")),
            "商品链接": item_data.get("商品链接", "#"),
            "任务名称": task_name,
            "失败原因": failure_reason,
        }
        
        reason = f"任务 '{task_name}' 监控到商品，但下单失败：{failure_reason}。"
        
        try:
            await notification_service.send_notification(notification_data, reason)
        except Exception as e:
            # 记录错误但不抛出异常
            print(f"发送下单失败通知失败：{e}")
