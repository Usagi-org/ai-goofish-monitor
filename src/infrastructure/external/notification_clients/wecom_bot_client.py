"""
企业微信机器人通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import NotificationClient


class WeComBotClient(NotificationClient):
    """企业微信机器人通知客户端"""

    channel_key = "wecom"
    display_name = "企业微信"

    def __init__(self, bot_url: str | None = None, pcurl_to_mobile: bool = True):
        super().__init__(enabled=bool(bot_url), pcurl_to_mobile=pcurl_to_mobile)
        self.bot_url = bot_url

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("企业微信 未启用")

        message = self._build_message(product_data, reason)
        markdown_lines = [f"## {message.notification_title}", ""]
        markdown_lines.append(f"- 价格: {message.price}")
        markdown_lines.append(f"- 原因: {message.reason}")
        if message.mobile_link:
            markdown_lines.append(f"- 手机端链接: [{message.mobile_link}]({message.mobile_link})")
        markdown_lines.append(f"- 电脑端链接: [{message.desktop_link}]({message.desktop_link})")
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": "\n".join(markdown_lines)},
        }
        headers = {"Content-Type": "application/json"}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                self.bot_url,
                json=payload,
                headers=headers,
                timeout=10,
            ),
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errcode", 0) != 0:
            raise RuntimeError(result.get("errmsg", "企业微信返回未知错误"))
