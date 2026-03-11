"""
Bark 通知客户端
"""
import asyncio
import requests
from typing import Dict
from .base import NotificationClient


class BarkClient(NotificationClient):
    """Bark 通知客户端"""

    channel_key = "bark"
    display_name = "Bark"

    def __init__(self, bark_url: str = None, pcurl_to_mobile: bool = True):
        super().__init__(enabled=bool(bark_url), pcurl_to_mobile=pcurl_to_mobile)
        self.bark_url = bark_url

    async def send(self, product_data: Dict, reason: str) -> None:
        """发送 Bark 通知"""
        if not self.is_enabled():
            raise RuntimeError("Bark 未启用")

        message = self._build_message(product_data, reason)
        bark_payload = {
            "title": message.notification_title,
            "body": message.content,
            "url": message.mobile_link or message.desktop_link,
            "level": "timeSensitive",
            "group": "闲鱼监控"
        }

        if message.image_url:
            bark_payload["icon"] = message.image_url

        headers = {"Content-Type": "application/json; charset=utf-8"}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                self.bark_url,
                json=bark_payload,
                headers=headers,
                timeout=10
            )
        )
        response.raise_for_status()
