"""
通知配置工厂
"""
from src.infrastructure.config.settings import NotificationSettings

from .feishu_client import FeishuClient


def build_notification_clients(settings: NotificationSettings):
    pcurl_to_mobile = settings.pcurl_to_mobile
    return [
        FeishuClient(settings.feishu_webhook_url, pcurl_to_mobile=pcurl_to_mobile),
    ]
