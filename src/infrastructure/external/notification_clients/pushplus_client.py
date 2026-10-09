"""
PushPlus 通知客户端
https://www.pushplus.plus
"""
import asyncio
import requests
from typing import Dict
from .base import NotificationClient


class PushPlusClient(NotificationClient):
    """PushPlus 通知客户端"""

    channel_key = "pushplus"
    display_name = "PushPlus"

    def __init__(
        self,
        token: str = None,
        topic: str = None,
        pcurl_to_mobile: bool = True,
    ):
        super().__init__(enabled=bool(token), pcurl_to_mobile=pcurl_to_mobile)
        self.token = token
        self.topic = topic
        self.api_url = "https://www.pushplus.plus/send"

    async def send(self, product_data: Dict, reason: str) -> None:
        """发送 PushPlus 通知"""
        if not self.is_enabled():
            raise RuntimeError("PushPlus 未启用或未配置 token")

        message = self._build_message(product_data, reason)

        payload = {
            "token": self.token,
            "title": message.notification_title,
            "content": message.content,
            "template": "html",
        }

        if self.topic:
            payload["topic"] = self.topic

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                self.api_url,
                json=payload,
                timeout=10,
            ),
        )
        response.raise_for_status()
