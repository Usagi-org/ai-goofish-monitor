import asyncio

from src.infrastructure.external.notification_clients.base import NotificationClient
from src.infrastructure.config.settings import NotificationSettings
from src.infrastructure.external.notification_clients.factory import (
    build_notification_clients_for_targets,
)
from src.infrastructure.external.notification_clients.webhook_client import WebhookClient
from src.services.notification_config_service import (
    build_configured_channels,
    build_notification_settings_response,
)
from src.services.notification_service import NotificationService


class _OkClient(NotificationClient):
    channel_key = "ok"
    display_name = "OK"

    async def send(self, product_data, reason):
        return None


class _FailClient(NotificationClient):
    channel_key = "fail"
    display_name = "FAIL"

    async def send(self, product_data, reason):
        raise RuntimeError("boom")


def test_notification_service_collects_success_and_failure_results():
    service = NotificationService([_OkClient(enabled=True), _FailClient(enabled=True)])

    results = asyncio.run(
        service.send_notification({"商品标题": "Sony A7M4"}, "价格合适")
    )

    assert results["ok"]["success"] is True
    assert results["ok"]["message"] == "发送成功"
    assert results["fail"]["success"] is False
    assert results["fail"]["message"] == "boom"


def test_webhook_client_renders_json_templates(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

    def _fake_post(url, headers=None, json=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["data"] = data
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)

    client = WebhookClient(
        webhook_url="https://hooks.example.com/notify",
        webhook_method="POST",
        webhook_headers='{"Authorization":"Bearer token"}',
        webhook_content_type="JSON",
        webhook_query_parameters='{"task":"{{title}}"}',
        webhook_body='{"message":"{{content}}","link":"{{desktop_link}}"}',
        pcurl_to_mobile=False,
    )

    asyncio.run(
        client.send(
            {
                "商品标题": "Sony A7M4",
                "当前售价": "9999",
                "商品链接": "https://www.goofish.com/item/123",
            },
            "价格合适",
        )
    )

    assert "task=%F0%9F%9A%A8+%E6%96%B0%E6%8E%A8%E8%8D%90%21+Sony+A7M4" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["json"]["message"].startswith("价格: 9999")
    assert captured["json"]["link"] == "https://www.goofish.com/item/123"
    assert captured["data"] is None


def test_target_factory_overrides_telegram_chat_id():
    settings = NotificationSettings(
        telegram_bot_token="token",
        telegram_chat_id="global-chat",
    )

    clients = build_notification_clients_for_targets(
        settings,
        [{"channel": "telegram", "recipient": "task-chat"}],
    )

    telegram = [client for client in clients if client.channel_key == "telegram"][0]
    assert telegram.chat_id == "task-chat"
    assert telegram.bot_token == "token"


def test_target_factory_overrides_wecom_app_touser():
    settings = NotificationSettings(
        wecom_app_corpid="corp",
        wecom_app_secret="secret",
        wecom_app_agentid="1000001",
        wecom_app_touser="@all",
    )

    clients = build_notification_clients_for_targets(
        settings,
        [{"channel": "wecom_app", "recipient": "user1|user2"}],
    )

    wecom_app = [client for client in clients if client.channel_key == "wecom_app"][0]
    assert wecom_app.touser == "user1|user2"
    assert wecom_app.corpid == "corp"


def test_target_factory_empty_targets_uses_global_default():
    settings = NotificationSettings(
        telegram_bot_token="token",
        telegram_chat_id="global-chat",
    )

    clients = build_notification_clients_for_targets(settings, [])

    telegram = [client for client in clients if client.channel_key == "telegram"][0]
    assert telegram.chat_id == "global-chat"


def test_retired_channels_are_not_reported_as_configured_channels():
    settings = NotificationSettings(
        wecom_app_corpid="corp",
        wecom_app_secret="secret",
        wecom_app_agentid="1000001",
        telegram_bot_token="tg-token",
        telegram_chat_id="tg-chat",
        webhook_url="https://hooks.example.com/notify",
    )

    assert build_configured_channels(settings) == [
        "wecom_app",
        "telegram",
        "webhook",
    ]


def test_notification_settings_response_surfaces_channel_metadata():
    settings = NotificationSettings(
        wecom_app_corpid="corp",
        wecom_app_secret="secret",
        wecom_app_agentid="1000001",
        telegram_bot_token="tg-token",
        telegram_chat_id="tg-chat",
    )

    response = build_notification_settings_response(settings)

    assert response["CONFIGURED_CHANNELS"] == ["wecom_app", "telegram"]
    assert response["PREFERRED_CHANNELS"] == ["wecom_app"]
    assert "DEPRECATED_CHANNELS" not in response
    assert response["ADVANCED_COMPAT_CHANNELS"] == ["webhook"]
