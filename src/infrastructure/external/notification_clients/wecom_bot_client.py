"""
企业微信机器人通知客户端
"""
import asyncio
from typing import Dict

import requests

from .base import (
    AlertNotificationData,
    NotificationClient,
    NotificationType,
)


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

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知到企业微信
        
        Args:
            alert_data: 预警通知数据
            
        Returns:
            是否发送成功
        """
        if not self.is_enabled():
            return False

        level_color = {
            "critical": "red",
            "warning": "orange",
            "info": "info",
        }.get(alert_data.alert_level.lower(), "warning")

        level_label = {
            "critical": "严重",
            "warning": "警告",
            "info": "一般",
        }.get(alert_data.alert_level.lower(), "预警")

        level_emoji = {
            "critical": "🔴",
            "warning": "🟠",
            "info": "🔵",
        }.get(alert_data.alert_level.lower(), "⚠️")

        markdown_lines = [
            f"## 📉 价格下跌预警",
            "",
        ]

        if level_color == "red":
            markdown_lines.append(f"> <font color=\"red\">**{level_emoji} 预警级别: {level_label}**</font>")
        elif level_color == "orange":
            markdown_lines.append(f"> <font color=\"orange\">**{level_emoji} 预警级别: {level_label}**</font>")
        else:
            markdown_lines.append(f"> {level_emoji} **预警级别: {level_label}**")

        markdown_lines.extend([
            "",
            "---",
            "",
            f"- **任务名称**: {alert_data.task_name}",
            f"- **搜索关键词**: {alert_data.keyword}",
            f"- **连续下跌次数**: {alert_data.consecutive_scans} 次扫描",
        ])

        if alert_data.previous_avg_price is not None:
            markdown_lines.append(f"- **基准均价**: ¥{alert_data.previous_avg_price:.2f}")
        if alert_data.current_avg_price is not None:
            markdown_lines.append(f"- **当前均价**: ¥{alert_data.current_avg_price:.2f}")
        if alert_data.drop_percentage is not None:
            markdown_lines.append(f"- **累计跌幅**: <font color=\"red\">**{alert_data.drop_percentage:.1f}%**</font>")

        if alert_data.message:
            markdown_lines.extend([
                "",
                "---",
                "",
                f"**详情说明**:",
                "",
                f"{alert_data.message}",
            ])

        markdown_lines.extend([
            "",
            "---",
            "",
            "> 💡 请及时关注价格波动，评估是否需要调整监控策略。",
        ])

        payload = {
            "msgtype": "markdown",
            "markdown": {"content": "\n".join(markdown_lines)},
        }
        headers = {"Content-Type": "application/json"}

        try:
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
            return True
        except Exception:
            return False
