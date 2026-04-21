"""
飞书机器人通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import NotificationClient


class FeishuClient(NotificationClient):
    """飞书机器人通知客户端"""

    channel_key = "feishu"
    display_name = "飞书"

    def __init__(self, webhook_url: str | None = None, pcurl_to_mobile: bool = True):
        super().__init__(enabled=bool(webhook_url), pcurl_to_mobile=pcurl_to_mobile)
        self.webhook_url = webhook_url

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("飞书 未启用")

        message = self._build_message(product_data, reason)

        # 飞书富文本消息格式
        content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": "blue",
                "title": {
                    "content": "🔔 闲鱼监控通知",
                    "tag": "plain_text"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**商品标题**: {message.title}\n{message.content}",
                        "tag": "lark_md"
                    }
                }
            ]
        }

        payload = {
            "msg_type": "interactive",
            "card": content
        }

        headers = {"Content-Type": "application/json"}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=10,
            ),
        )
        response.raise_for_status()
        result = response.json()
        if result.get("code", 0) != 0:
            raise RuntimeError(f"飞书返回错误：{result.get('msg', '未知错误')}")
