"""
通知客户端基类
定义通知客户端的统一接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from src.utils import convert_goofish_link


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
    async def send(self, product_data: Dict, reason: str) -> None:
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

        # 想要数
        want_count = product_data.get('想要人数', product_data.get('想要数'))
        # 价格变化
        price_change = product_data.get('price_change_display', '')
        # 想要数变化
        want_count_change = product_data.get('want_count_change_display', '')

        if self._pcurl_to_mobile and desktop_link and desktop_link != "#":
            mobile_link = convert_goofish_link(desktop_link)

        content_lines = [
            f"价格：{price}",
        ]
        # 卖家昵称
        seller_nickname = product_data.get('卖家昵称')
        if seller_nickname:
            content_lines.insert(0, f"卖家：{seller_nickname}")
        if want_count:
            content_lines.append(f"想要数：{want_count}")
        if price_change:
            content_lines.append(f"价格变化：{price_change}")
        if want_count_change:
            content_lines.append(f"想要数变化：{want_count_change}")
        # 添加当前时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content_lines.append(f"时间：{now}")

        short_title = title[:30]
        suffix = "..." if len(title) > 30 else ""
        notification_title = f"🚨 新推荐！{short_title}{suffix}"

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
