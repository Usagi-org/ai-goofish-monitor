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
                        "content": f"**商品标题**: {message.title}\n**价格**: {message.price}\n**推荐原因**: {message.reason}",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "content": f"[点击查看商品详情]({message.desktop_link})",
                        "tag": "lark_md"
                    }
                }
            ]
        }

        # 如果有图片，添加到消息中
        if message.image_url:
            content["elements"].insert(1, {
                "tag": "img",
                "img_key": "",
                "alt": {
                    "content": "商品图片",
                    "tag": "plain_text"
                }
            })
            # 飞书图片需要特殊处理，这里简化处理，直接显示文本链接
            content["elements"][1] = {
                "tag": "div",
                "text": {
                    "content": f"![商品图片]({message.image_url})",
                    "tag": "lark_md"
                }
            }

        if message.mobile_link:
            content["elements"].append({
                "tag": "div",
                "text": {
                    "content": f"**手机端链接**: [{message.mobile_link}]({message.mobile_link})",
                    "tag": "lark_md"
                }
            })

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
