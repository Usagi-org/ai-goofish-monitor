"""
通知服务
统一管理所有通知渠道
"""
import asyncio
from typing import Dict, List

from src.infrastructure.external.notification_clients.base import NotificationClient
from src.infrastructure.external.notification_clients.factory import (
    build_notification_clients,
    build_notification_clients_for_targets,
)
from src.services.notification_config_service import load_notification_settings
from src.infrastructure.config.settings import NotificationSettings


class NotificationService:
    """通知服务"""

    def __init__(
        self,
        clients: List[NotificationClient],
        settings: NotificationSettings | None = None,
    ):
        self.clients = [client for client in clients if client.is_enabled()]
        self.settings = settings

    async def send_notification(
        self,
        product_data: Dict,
        reason: str,
        targets: list[dict] | None = None,
    ) -> Dict[str, Dict[str, str | bool]]:
        """
        发送通知到所有启用的渠道

        Returns:
            各渠道发送结果，包含成功状态和消息
        """
        clients = self._resolve_clients(targets)
        if not clients:
            return {}

        tasks = [
            self._send_with_result(client, product_data, reason)
            for client in clients
        ]
        results = await asyncio.gather(*tasks)
        return self._index_results_by_channel(results)

    def _index_results_by_channel(
        self,
        results: List[Dict[str, str | bool]],
    ) -> Dict[str, Dict[str, str | bool]]:
        indexed: Dict[str, Dict[str, str | bool]] = {}
        counts: Dict[str, int] = {}
        for result in results:
            channel = str(result["channel"])
            counts[channel] = counts.get(channel, 0) + 1
            key = channel if counts[channel] == 1 else f"{channel}:{counts[channel]}"
            indexed[key] = result
        return indexed

    def _resolve_clients(
        self,
        targets: list[dict] | None,
    ) -> List[NotificationClient]:
        if not targets:
            return self.clients
        if self.settings is None:
            return []
        return [
            client
            for client in build_notification_clients_for_targets(self.settings, targets)
            if client.is_enabled()
        ]

    async def send_test_notification(self) -> Dict[str, Dict[str, str | bool]]:
        test_product = {
            "商品标题": "[测试通知] 闲鱼智能监控",
            "当前售价": "0",
            "商品链接": "https://www.goofish.com/",
        }
        return await self.send_notification(
            test_product,
            "这是一条测试通知，用于验证推送渠道是否可用。",
        )

    async def _send_with_result(
        self,
        client: NotificationClient,
        product_data: Dict,
        reason: str,
    ) -> Dict[str, str | bool]:
        try:
            await client.send(product_data, reason)
            return {
                "channel": client.channel_key,
                "label": client.display_name,
                "success": True,
                "message": "发送成功",
            }
        except Exception as exc:
            return {
                "channel": client.channel_key,
                "label": client.display_name,
                "success": False,
                "message": str(exc),
            }


def build_notification_service(
    settings: NotificationSettings | None = None,
) -> NotificationService:
    notification_settings = settings or load_notification_settings()
    return NotificationService(
        build_notification_clients(notification_settings),
        settings=notification_settings,
    )
