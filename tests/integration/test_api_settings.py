from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import settings
from src.infrastructure.config.env_manager import env_manager


class _IdleProcessService:
    def __init__(self) -> None:
        self.processes = {}


def _build_settings_client() -> TestClient:
    app = FastAPI()
    app.include_router(settings.router)
    app.dependency_overrides[deps.get_process_service] = _IdleProcessService
    return TestClient(app)


def test_rotation_settings_include_account_rotation_fields(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ACCOUNT_ROTATION_ENABLED=false",
                "ACCOUNT_ROTATION_MODE=per_task",
                "ACCOUNT_ROTATION_RETRY_LIMIT=2",
                "ACCOUNT_BLACKLIST_TTL=300",
                "ACCOUNT_STATE_DIR=state",
                "PROXY_ROTATION_ENABLED=false",
                "PROXY_ROTATION_MODE=per_task",
                "PROXY_ROTATION_RETRY_LIMIT=2",
                "PROXY_BLACKLIST_TTL=300",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)

    client = _build_settings_client()

    response = client.get("/api/settings/rotation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ACCOUNT_ROTATION_ENABLED"] is False
    assert payload["ACCOUNT_ROTATION_MODE"] == "per_task"
    assert payload["ACCOUNT_STATE_DIR"] == "state"

    update_response = client.put(
        "/api/settings/rotation",
        json={
            "ACCOUNT_ROTATION_ENABLED": True,
            "ACCOUNT_ROTATION_MODE": "on_failure",
            "ACCOUNT_ROTATION_RETRY_LIMIT": 4,
            "ACCOUNT_BLACKLIST_TTL": 900,
            "ACCOUNT_STATE_DIR": "accounts",
        },
    )
    assert update_response.status_code == 200

    latest = env_file.read_text(encoding="utf-8")
    assert "ACCOUNT_ROTATION_ENABLED=true" in latest
    assert "ACCOUNT_ROTATION_MODE=on_failure" in latest
    assert "ACCOUNT_ROTATION_RETRY_LIMIT=4" in latest
    assert "ACCOUNT_BLACKLIST_TTL=900" in latest
    assert "ACCOUNT_STATE_DIR=accounts" in latest


def test_notification_settings_redact_sensitive_values_and_expose_flags(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic",
                "GOTIFY_URL=https://gotify.example.com",
                "GOTIFY_TOKEN=secret-token",
                "BARK_URL=https://api.day.app/private-key/",
                "WX_BOT_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret",
                "TELEGRAM_BOT_TOKEN=telegram-secret",
                "TELEGRAM_CHAT_ID=123456",
                "WEBHOOK_URL=https://hooks.example.com/notify?token=secret",
                'WEBHOOK_HEADERS={"Authorization":"Bearer secret"}',
                'WEBHOOK_BODY={"message":"{{content}}"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    response = client.get("/api/settings/notifications")

    assert response.status_code == 200
    payload = response.json()
    assert payload["NTFY_TOPIC_URL"] == "https://ntfy.sh/demo-topic"
    assert payload["GOTIFY_URL"] == "https://gotify.example.com"
    assert payload["TELEGRAM_CHAT_ID"] == "123456"
    assert payload["BARK_URL"] == ""
    assert payload["WX_BOT_URL"] == ""
    assert payload["GOTIFY_TOKEN"] == ""
    assert payload["TELEGRAM_BOT_TOKEN"] == ""
    assert payload["WEBHOOK_URL"] == ""
    assert payload["WEBHOOK_HEADERS"] == ""
    assert payload["BARK_URL_SET"] is True
    assert payload["WX_BOT_URL_SET"] is True
    assert payload["GOTIFY_TOKEN_SET"] is True
    assert payload["TELEGRAM_BOT_TOKEN_SET"] is True
    assert payload["WEBHOOK_URL_SET"] is True
    assert payload["WEBHOOK_HEADERS_SET"] is True
    assert payload["WEBHOOK_BODY"] == '{"message":"{{content}}"}'


def test_update_notification_settings_rejects_invalid_channel_config(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    gotify_response = client.put(
        "/api/settings/notifications",
        json={"GOTIFY_URL": "https://gotify.example.com"},
    )
    assert gotify_response.status_code == 422
    assert "GOTIFY_TOKEN" in gotify_response.text

    webhook_response = client.put(
        "/api/settings/notifications",
        json={
            "WEBHOOK_URL": "https://hooks.example.com/notify",
            "WEBHOOK_METHOD": "POST",
            "WEBHOOK_CONTENT_TYPE": "JSON",
            "WEBHOOK_HEADERS": '{"Authorization": "Bearer secret"',
        },
    )
    assert webhook_response.status_code == 422
    assert "WEBHOOK_HEADERS" in webhook_response.text


def test_system_status_includes_notification_channel_flags(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic",
                "GOTIFY_URL=https://gotify.example.com",
                "GOTIFY_TOKEN=secret-token",
                "BARK_URL=https://api.day.app/private-key/",
                "WX_BOT_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret",
                "TELEGRAM_BOT_TOKEN=telegram-secret",
                "TELEGRAM_CHAT_ID=123456",
                "WEBHOOK_URL=https://hooks.example.com/notify",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    response = client.get("/api/settings/status")

    assert response.status_code == 200
    env_payload = response.json()["env_file"]
    assert env_payload["ntfy_topic_url_set"] is True
    assert env_payload["gotify_url_set"] is True
    assert env_payload["gotify_token_set"] is True
    assert env_payload["bark_url_set"] is True
    assert env_payload["wx_bot_url_set"] is True
    assert env_payload["telegram_bot_token_set"] is True
    assert env_payload["telegram_chat_id_set"] is True
    assert env_payload["webhook_url_set"] is True


def test_notification_test_endpoint_merges_stored_secret_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "TELEGRAM_BOT_TOKEN=stored-token",
                "TELEGRAM_CHAT_ID=10001",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    captured = {}

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)

    response = client.post(
        "/api/settings/notifications/test",
        json={
            "channel": "telegram",
            "settings": {
                "TELEGRAM_CHAT_ID": "20002",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]["telegram"]["success"] is True
    assert captured["url"].endswith("/botstored-token/sendMessage")
    assert captured["json"]["chat_id"] == "20002"
