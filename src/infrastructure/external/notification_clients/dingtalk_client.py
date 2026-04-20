"""
钉钉机器人通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import NotificationClient


class DingtalkClient(NotificationClient):
    """钉钉机器人通知客户端"""

    channel_key = "dingtalk"
    display_name = "钉钉"

    def __init__(self, webhook_url: str | None = None, pcurl_to_mobile: bool = True):
        super().__init__(enabled=bool(webhook_url), pcurl_to_mobile=pcurl_to_mobile)
        self.webhook_url = webhook_url

    async def send(self, product_data: Dict, reason: str) -> None:
        if not self.is_enabled():
            raise RuntimeError("钉钉 未启用")

        message = self._build_message(product_data, reason)

        # 钉钉 markdown 消息格式
        markdown_content = (
            f"## {message.notification_title}\n\n"
            f"- **商品标题**: {message.title}\n"
            f"- **价格**: {message.price}\n"
            f"- **推荐原因**: {message.reason}\n"
        )

        if message.mobile_link:
            markdown_content += f"- **手机端链接**: [{message.mobile_link}]({message.mobile_link})\n"
            markdown_content += f"- **电脑端链接**: [{message.desktop_link}]({message.desktop_link})\n"
        else:
            markdown_content += f"- **商品链接**: [{message.desktop_link}]({message.desktop_link})\n"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "闲鱼监控通知",
                "text": markdown_content
            }
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
        if result.get("errcode", 0) != 0:
            raise RuntimeError(f"钉钉返回错误：{result.get('errmsg', '未知错误')}")
