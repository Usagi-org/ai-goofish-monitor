"""
Gotify 通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import (
    AlertNotificationData,
    NotificationClient,
)


class GotifyClient(NotificationClient):
    """Gotify 通知客户端"""

    channel_key = "gotify"
    display_name = "Gotify"

    def __init__(
        self,
        gotify_url: str | None = None,
        gotify_token: str | None = None,
        pcurl_to_mobile: bool = True,
    ):
        super().__init__(
            enabled=bool(gotify_url and gotify_token),
            pcurl_to_mobile=pcurl_to_mobile,
        )
        self.gotify_url = (gotify_url or "").rstrip("/")
        self.gotify_token = gotify_token

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("Gotify 未启用")

        message = self._build_message(product_data, reason)
        payload = {
            "title": (None, message.notification_title),
            "message": (None, message.content),
            "priority": (None, "5"),
        }
        final_url = f"{self.gotify_url}/message?token={self.gotify_token}"
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(final_url, files=payload, timeout=10),
        )
        response.raise_for_status()

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知到 Gotify
        
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
            f"**任务**: {alert_data.task_name}",
            f"**关键词**: {alert_data.keyword}",
            f"**连续下跌**: {alert_data.consecutive_scans} 次扫描",
        ]

        if alert_data.previous_avg_price is not None:
            content_lines.append(f"**基准均价**: ¥{alert_data.previous_avg_price:.2f}")
        if alert_data.current_avg_price is not None:
            content_lines.append(f"**当前均价**: ¥{alert_data.current_avg_price:.2f}")
        if alert_data.drop_percentage is not None:
            content_lines.append(f"**累计跌幅**: {alert_data.drop_percentage:.1f}%")

        content = "\n".join(content_lines)

        priority = "8" if alert_data.alert_level.lower() == "critical" else "5"

        try:
            payload = {
                "title": (None, title),
                "message": (None, content),
                "priority": (None, priority),
            }
            final_url = f"{self.gotify_url}/message?token={self.gotify_token}"
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(final_url, files=payload, timeout=10),
            )
            response.raise_for_status()
            return True
        except Exception:
            return False
