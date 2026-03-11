"""
Gotify 通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import NotificationClient


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
