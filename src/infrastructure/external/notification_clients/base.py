"""
通知客户端基类
定义通知客户端的统一接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from src.utils import convert_goofish_link


class NotificationType(Enum):
    """通知类型"""
    RECOMMENDATION = "recommendation"
    PRICE_ALERT = "price_alert"


@dataclass(frozen=True)
class AlertNotificationData:
    """预警通知数据"""
    task_name: str
    keyword: str
    alert_level: str
    previous_avg_price: Optional[float]
    current_avg_price: Optional[float]
    drop_percentage: Optional[float]
    consecutive_scans: int
    message: str


@dataclass(frozen=True)
class NotificationMessage:
    title: str
    price: str
    reason: str
    desktop_link: str
    mobile_link: str | None
    notification_title: str
    content: str
    image_url: str | None
    notification_type: NotificationType = NotificationType.RECOMMENDATION


class NotificationClient(ABC):
    """通知客户端抽象基类"""

    channel_key = "unknown"
    display_name = "未知渠道"

    def __init__(self, enabled: bool = False, pcurl_to_mobile: bool = True):
        self._enabled = enabled
        self._pcurl_to_mobile = pcurl_to_mobile

    def is_enabled(self) -> bool:
        """检查客户端是否启用"""
        return self._enabled

    @abstractmethod
    async def send(self, product_data: Dict, reason: str) -> bool:
        """
        发送通知

        Args:
            product_data: 商品数据
            reason: 推荐原因

        Returns:
            是否发送成功
        """
        raise NotImplementedError

    def _build_message(self, product_data: Dict, reason: str) -> NotificationMessage:
        """格式化消息内容"""
        title = product_data.get('商品标题', 'N/A')
        price = product_data.get('当前售价', 'N/A')
        desktop_link = product_data.get('商品链接', '#')
        mobile_link = None

        if self._pcurl_to_mobile and desktop_link and desktop_link != "#":
            mobile_link = convert_goofish_link(desktop_link)

        content_lines = [
            f"价格: {price}",
            f"原因: {reason}",
        ]
        if mobile_link:
            content_lines.append(f"手机端链接: {mobile_link}")
            content_lines.append(f"电脑端链接: {desktop_link}")
        else:
            content_lines.append(f"链接: {desktop_link}")

        short_title = title[:30]
        suffix = "..." if len(title) > 30 else ""
        notification_title = f"🚨 新推荐! {short_title}{suffix}"

        main_image = product_data.get('商品主图链接')
        if not main_image:
            image_list = product_data.get('商品图片列表', [])
            if image_list:
                main_image = image_list[0]

        return NotificationMessage(
            title=title,
            price=price,
            reason=reason,
            desktop_link=desktop_link,
            mobile_link=mobile_link,
            notification_title=notification_title,
            content="\n".join(content_lines),
            image_url=main_image,
        )

    def _build_alert_message(self, alert_data: AlertNotificationData) -> NotificationMessage:
        """
        格式化价格预警通知内容
        
        Args:
            alert_data: 预警通知数据
            
        Returns:
            格式化后的通知消息
        """
        task_name = alert_data.task_name
        keyword = alert_data.keyword
        alert_level = alert_data.alert_level
        consecutive_scans = alert_data.consecutive_scans
        drop_percentage = alert_data.drop_percentage
        prev_price = alert_data.previous_avg_price
        curr_price = alert_data.current_avg_price

        level_emoji = {
            "critical": "🔴",
            "warning": "🟠",
        }.get(alert_level.lower(), "🟠")

        level_label = {
            "critical": "严重",
            "warning": "警告",
        }.get(alert_level.lower(), "警告")

        notification_title = f"📉 价格下跌预警 - {level_emoji} {level_label}"

        content_lines = [
            f"【任务】{task_name}",
            f"【关键词】{keyword}",
            f"【预警级别】{level_emoji} {level_label}",
            f"【连续下跌次数】{consecutive_scans} 次扫描",
        ]

        if prev_price is not None and curr_price is not None:
            content_lines.append(f"【基准均价】¥{prev_price:.2f}")
            content_lines.append(f"【当前均价】¥{curr_price:.2f}")

        if drop_percentage is not None:
            content_lines.append(f"【累计跌幅】{drop_percentage:.1f}%")

        if alert_data.message:
            content_lines.append("")
            content_lines.append(f"【详情】{alert_data.message}")

        return NotificationMessage(
            title=f"价格预警: {task_name}",
            price=f"跌幅 {drop_percentage:.1f}%" if drop_percentage is not None else "N/A",
            reason=alert_data.message or "价格持续下跌",
            desktop_link="#",
            mobile_link=None,
            notification_title=notification_title,
            content="\n".join(content_lines),
            image_url=None,
            notification_type=NotificationType.PRICE_ALERT,
        )

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知（默认实现，子类可重写）
        
        Args:
            alert_data: 预警通知数据
            
        Returns:
            是否发送成功
        """
        if not self.is_enabled():
            return False
        
        message = self._build_alert_message(alert_data)
        
        fake_product_data = {
            "商品标题": message.title,
            "当前售价": message.price,
            "商品链接": "#",
        }
        
        return await self.send(fake_product_data, message.reason)
