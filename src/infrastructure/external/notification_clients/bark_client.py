"""
Bark 通知客户端
"""
import asyncio
import requests
from typing import Dict
from .base import (
    AlertNotificationData,
    NotificationClient,
)


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

    async def send_alert(self, alert_data: AlertNotificationData) -> bool:
        """
        发送价格预警通知到 Bark
        
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

        body_lines = [
            f"任务: {alert_data.task_name}",
            f"关键词: {alert_data.keyword}",
            f"连续下跌: {alert_data.consecutive_scans} 次",
        ]

        if alert_data.current_avg_price is not None:
            body_lines.append(f"当前均价: ¥{alert_data.current_avg_price:.2f}")
        if alert_data.drop_percentage is not None:
            body_lines.append(f"累计跌幅: {alert_data.drop_percentage:.1f}%")

        body = "\n".join(body_lines)

        bark_payload = {
            "title": title,
            "body": body,
            "level": "timeSensitive",
            "group": "闲鱼预警",
            "sound": "alarm.caf" if alert_data.alert_level.lower() == "critical" else "glitch.caf",
        }

        try:
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
            return True
        except Exception:
            return False
