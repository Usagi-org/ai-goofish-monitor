"""
Ntfy 通知客户端
"""
import asyncio
import requests
from typing import Dict
from .base import (
    AlertNotificationData,
    NotificationClient,
)


class NtfyClient(NotificationClient):
    """Ntfy 通知客户端"""

    channel_key = "ntfy"
    display_name = "Ntfy"

    def __init__(self, topic_url: str = None, pcurl_to_mobile: bool = True):
        super().__init__(enabled=bool(topic_url), pcurl_to_mobile=pcurl_to_mobile)
        self.topic_url = topic_url

    async def send(self, product_data: Dict, reason: str) -> None:
        """发送 Ntfy 通知"""
        if not self.is_enabled():
            raise RuntimeError("Ntfy 未启用")

        message = self._build_message(product_data, reason)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                self.topic_url,
                data=message.content.encode('utf-8'),
                headers={
                    "Title": message.notification_title.encode('utf-8'),
                    "Priority": "urgent",
                    "Tags": "bell,vibration"
                },
                timeout=10
            )
        )
        response.raise_for_status()

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知到 Ntfy
        
        Args:
            alert_data: 预警通知数据
            
        Returns:
            是否发送成功
        """
        if not self.is_enabled():
            return False

        level_label = {
            "critical": "严重",
            "warning": "警告",
        }.get(alert_data.alert_level.lower(), "警告")

        level_emoji = {
            "critical": "🔴",
            "warning": "🟠",
        }.get(alert_data.alert_level.lower(), "🟠")

        title = f"📉 价格下跌预警 - {level_emoji} {level_label}"

        content_lines = [
            f"任务: {alert_data.task_name}",
            f"关键词: {alert_data.keyword}",
            f"连续下跌: {alert_data.consecutive_scans} 次",
        ]

        if alert_data.current_avg_price is not None:
            content_lines.append(f"当前均价: ¥{alert_data.current_avg_price:.2f}")
        if alert_data.drop_percentage is not None:
            content_lines.append(f"累计跌幅: {alert_data.drop_percentage:.1f}%")

        content = "\n".join(content_lines)

        priority = "5" if alert_data.alert_level.lower() == "critical" else "3"
        tags = "warning,chart_with_downwards_trend"

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    self.topic_url,
                    data=content.encode('utf-8'),
                    headers={
                        "Title": title.encode('utf-8'),
                        "Priority": priority,
                        "Tags": tags
                    },
                    timeout=10
                )
            )
            response.raise_for_status()
            return True
        except Exception:
            return False
