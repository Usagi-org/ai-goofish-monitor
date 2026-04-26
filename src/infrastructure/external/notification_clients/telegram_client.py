"""
Telegram 通知客户端
"""
import asyncio
from typing import Dict

import requests

from src.infrastructure.config.settings import DEFAULT_TELEGRAM_API_BASE_URL

from .base import (
    AlertNotificationData,
    NotificationClient,
)


class TelegramClient(NotificationClient):
    """Telegram 通知客户端"""

    channel_key = "telegram"
    display_name = "Telegram"

    def __init__(
        self,
        bot_token: str = None,
        chat_id: str = None,
        api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL,
        pcurl_to_mobile: bool = True,
    ):
        super().__init__(enabled=bool(bot_token and chat_id), pcurl_to_mobile=pcurl_to_mobile)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base_url = (
            (api_base_url or DEFAULT_TELEGRAM_API_BASE_URL).rstrip("/")
        )

    async def send(self, product_data: Dict, reason: str) -> None:
        """发送 Telegram 通知"""
        if not self.is_enabled():
            raise RuntimeError("Telegram 未启用")

        message = self._build_message(product_data, reason)
        telegram_message = [
            "🚨 <b>新推荐!</b>",
            "",
            f"<b>{message.title[:50]}{'...' if len(message.title) > 50 else ''}</b>",
            "",
            f"💰 价格: {message.price}",
            f"📝 原因: {message.reason}",
        ]
        if message.mobile_link:
            telegram_message.append(f"📱 <a href='{message.mobile_link}'>手机端链接</a>")
        telegram_message.append(f"💻 <a href='{message.desktop_link}'>电脑端链接</a>")

        telegram_api_url = f"{self.api_base_url}/bot{self.bot_token}/sendMessage"
        telegram_payload = {
            "chat_id": self.chat_id,
            "text": "\n".join(telegram_message),
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        headers = {"Content-Type": "application/json"}
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(
                telegram_api_url,
                json=telegram_payload,
                headers=headers,
                timeout=10
            )
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram 返回未知错误"))

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知到 Telegram
        
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

        telegram_message = [
            f"📉 <b>价格下跌预警</b>",
            "",
            f"<b>{level_emoji} 预警级别: {level_label}</b>",
            "",
            f"<b>📦 任务:</b> {alert_data.task_name}",
            f"<b>🔍 关键词:</b> {alert_data.keyword}",
            f"<b>📊 连续下跌:</b> {alert_data.consecutive_scans} 次扫描",
        ]

        if alert_data.previous_avg_price is not None:
            telegram_message.append(f"<b>📈 基准均价:</b> ¥{alert_data.previous_avg_price:.2f}")
        if alert_data.current_avg_price is not None:
            telegram_message.append(f"<b>📉 当前均价:</b> ¥{alert_data.current_avg_price:.2f}")
        if alert_data.drop_percentage is not None:
            telegram_message.append(f"<b>🔥 累计跌幅:</b> {alert_data.drop_percentage:.1f}%")

        if alert_data.message:
            telegram_message.extend([
                "",
                "<b>📝 详情:</b>",
                f"{alert_data.message}",
            ])

        telegram_api_url = f"{self.api_base_url}/bot{self.bot_token}/sendMessage"
        telegram_payload = {
            "chat_id": self.chat_id,
            "text": "\n".join(telegram_message),
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            headers = {"Content-Type": "application/json"}
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    telegram_api_url,
                    json=telegram_payload,
                    headers=headers,
                    timeout=10
                )
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "Telegram 返回未知错误"))
            return True
        except Exception:
            return False
