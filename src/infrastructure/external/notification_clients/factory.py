"""
通知客户端工厂
"""
from src.infrastructure.config.settings import NotificationSettings

from .telegram_client import TelegramClient
from .wecom_app_client import WeComAppClient
from .webhook_client import WebhookClient


def build_notification_clients(settings: NotificationSettings):
    pcurl_to_mobile = settings.pcurl_to_mobile
    return [
        WeComAppClient(
            corpid=settings.wecom_app_corpid,
            corpsecret=settings.wecom_app_secret,
            agentid=settings.wecom_app_agentid,
            touser=settings.wecom_app_touser,
            pcurl_to_mobile=pcurl_to_mobile,
        ),
        TelegramClient(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            settings.telegram_api_base_url,
            pcurl_to_mobile=pcurl_to_mobile,
        ),
        WebhookClient(
            settings.webhook_url,
            webhook_method=settings.webhook_method,
            webhook_headers=settings.webhook_headers,
            webhook_content_type=settings.webhook_content_type,
            webhook_query_parameters=settings.webhook_query_parameters,
            webhook_body=settings.webhook_body,
            pcurl_to_mobile=pcurl_to_mobile,
        ),
    ]


def build_notification_clients_for_targets(settings: NotificationSettings, targets):
    if not targets:
        return build_notification_clients(settings)

    pcurl_to_mobile = settings.pcurl_to_mobile
    clients = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        channel = str(target.get("channel") or "").strip()
        recipient = str(target.get("recipient") or "").strip()
        if channel == "default":
            clients.extend(build_notification_clients(settings))
        elif channel == "telegram" and recipient:
            clients.append(
                TelegramClient(
                    settings.telegram_bot_token,
                    recipient,
                    settings.telegram_api_base_url,
                    pcurl_to_mobile=pcurl_to_mobile,
                )
            )
        elif channel == "wecom_app" and recipient:
            clients.append(
                WeComAppClient(
                    corpid=settings.wecom_app_corpid,
                    corpsecret=settings.wecom_app_secret,
                    agentid=settings.wecom_app_agentid,
                    touser=recipient,
                    pcurl_to_mobile=pcurl_to_mobile,
                )
            )
    return clients
