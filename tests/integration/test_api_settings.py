from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import settings
from src.infrastructure.config.env_manager import env_manager


_SETTINGS_ENV_KEYS = [
    "ACCOUNT_ROTATION_ENABLED",
    "ACCOUNT_ROTATION_MODE",
    "ACCOUNT_ROTATION_RETRY_LIMIT",
    "ACCOUNT_BLACKLIST_TTL",
    "ACCOUNT_STATE_DIR",
    "PROXY_ROTATION_ENABLED",
    "PROXY_ROTATION_MODE",
    "PROXY_POOL",
    "PROXY_ROTATION_RETRY_LIMIT",
    "PROXY_BLACKLIST_TTL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL_NAME",
    "SKIP_AI_ANALYSIS",
    "PROXY_URL",
    "NTFY_TOPIC_URL",
    "GOTIFY_URL",
    "GOTIFY_TOKEN",
    "BARK_URL",
    "WX_BOT_URL",
    "WECOM_APP_CORPID",
    "WECOM_APP_SECRET",
    "WECOM_APP_AGENTID",
    "WECOM_APP_TOUSER",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_API_BASE_URL",
    "WEBHOOK_URL",
    "WEBHOOK_METHOD",
    "WEBHOOK_HEADERS",
    "WEBHOOK_CONTENT_TYPE",
    "WEBHOOK_QUERY_PARAMETERS",
    "WEBHOOK_BODY",
    "PCURL_TO_MOBILE",
]


class _IdleProcessService:
    def __init__(self) -> None:
        self.processes = {}


def _build_settings_client() -> TestClient:
    app = FastAPI()
    app.include_router(settings.router)
    app.dependency_overrides[deps.get_process_service] = _IdleProcessService
    return TestClient(app)


def _clear_settings_env(monkeypatch) -> None:
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_rotation_settings_include_account_rotation_fields(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
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
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic",
                "GOTIFY_URL=https://gotify.example.com",
                "GOTIFY_TOKEN=secret-token",
                "BARK_URL=https://api.day.app/private-key/",
                "WX_BOT_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret",
                "WECOM_APP_CORPID=corp-id",
                "WECOM_APP_SECRET=app-secret",
                "WECOM_APP_AGENTID=1000001",
                "WECOM_APP_TOUSER=user1|user2",
                "TELEGRAM_BOT_TOKEN=telegram-secret",
                "TELEGRAM_CHAT_ID=123456",
                "TELEGRAM_API_BASE_URL=https://tg.example.com/proxy",
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
    assert "NTFY_TOPIC_URL" not in payload
    assert "GOTIFY_URL" not in payload
    assert "BARK_URL" not in payload
    assert "WX_BOT_URL" not in payload
    assert payload["TELEGRAM_CHAT_ID"] == "123456"
    assert payload["TELEGRAM_API_BASE_URL"] == "https://tg.example.com/proxy"
    assert payload["WECOM_APP_CORPID"] == "corp-id"
    assert payload["WECOM_APP_AGENTID"] == "1000001"
    assert payload["WECOM_APP_TOUSER"] == "user1|user2"
    assert payload["WECOM_APP_SECRET"] == ""
    assert payload["TELEGRAM_BOT_TOKEN"] == ""
    assert payload["WEBHOOK_URL"] == ""
    assert payload["WEBHOOK_HEADERS"] == ""
    assert payload["WECOM_APP_SECRET_SET"] is True
    assert payload["TELEGRAM_BOT_TOKEN_SET"] is True
    assert payload["WEBHOOK_URL_SET"] is True
    assert payload["WEBHOOK_HEADERS_SET"] is True
    assert payload["WEBHOOK_BODY"] == '{"message":"{{content}}"}'


def test_update_notification_settings_rejects_invalid_channel_config(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    telegram_proxy_response = client.put(
        "/api/settings/notifications",
        json={"TELEGRAM_API_BASE_URL": "not-a-url"},
    )
    assert telegram_proxy_response.status_code == 422
    assert "TELEGRAM_API_BASE_URL" in telegram_proxy_response.text

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

    wecom_app_response = client.put(
        "/api/settings/notifications",
        json={
            "WECOM_APP_CORPID": "corp-id",
            "WECOM_APP_AGENTID": "1000001",
        },
    )
    assert wecom_app_response.status_code == 422
    assert "WECOM_APP_SECRET" in wecom_app_response.text


def test_update_notification_settings_persists_wecom_app_config(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    response = client.put(
        "/api/settings/notifications",
        json={
            "WECOM_APP_CORPID": "corp-id",
            "WECOM_APP_SECRET": "app-secret",
            "WECOM_APP_AGENTID": "1000001",
            "WECOM_APP_TOUSER": "user1|user2",
        },
    )

    assert response.status_code == 200
    assert "wecom_app" in response.json()["configured_channels"]
    latest = env_file.read_text(encoding="utf-8")
    assert "WECOM_APP_CORPID=corp-id" in latest
    assert "WECOM_APP_SECRET=app-secret" in latest
    assert "WECOM_APP_AGENTID=1000001" in latest
    assert 'WECOM_APP_TOUSER=user1|user2' in latest or 'WECOM_APP_TOUSER="user1|user2"' in latest


def test_wecom_app_departments_and_users_use_configured_app_credentials(
    tmp_path, monkeypatch
):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "WECOM_APP_CORPID=corp-id",
                "WECOM_APP_SECRET=app-secret",
                "WECOM_APP_AGENTID=1000001",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    requests_seen = []

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def _fake_get(url, params=None, timeout=None):
        requests_seen.append((url, params, timeout))
        if url.endswith("/gettoken"):
            return _FakeResponse({"errcode": 0, "access_token": "token-1"})
        if url.endswith("/department/list"):
            return _FakeResponse(
                {
                    "errcode": 0,
                    "department": [
                        {"id": 1, "name": "总部", "parentid": 0, "order": 10},
                    ],
                }
            )
        if url.endswith("/user/simplelist"):
            return _FakeResponse(
                {
                    "errcode": 0,
                    "userlist": [
                        {"userid": "zhangsan", "name": "张三", "department": [1]},
                    ],
                }
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("requests.get", _fake_get)
    client = _build_settings_client()

    departments_response = client.get("/api/settings/notifications/wecom-app/departments")
    users_response = client.get(
        "/api/settings/notifications/wecom-app/users",
        params={"department_id": 1, "fetch_child": 1},
    )

    assert departments_response.status_code == 200
    assert departments_response.json() == {
        "departments": [{"id": 1, "name": "总部", "parentid": 0, "order": 10}]
    }
    assert users_response.status_code == 200
    assert users_response.json() == {
        "users": [{"userid": "zhangsan", "name": "张三", "department": [1]}]
    }
    assert requests_seen[0][1] == {"corpid": "corp-id", "corpsecret": "app-secret"}
    assert requests_seen[1][1] == {"access_token": "token-1"}
    assert requests_seen[2][1] == {"corpid": "corp-id", "corpsecret": "app-secret"}
    assert requests_seen[3][1] == {
        "access_token": "token-1",
        "department_id": 1,
        "fetch_child": 1,
    }
    assert all(item[2] == settings.WECOM_API_TIMEOUT_SECONDS for item in requests_seen)


def test_wecom_app_contacts_require_app_credentials(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    response = client.get("/api/settings/notifications/wecom-app/departments")

    assert response.status_code == 422
    assert response.json()["detail"] == "企业微信应用未完整配置"


def test_system_status_includes_notification_channel_flags(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic",
                "GOTIFY_URL=https://gotify.example.com",
                "GOTIFY_TOKEN=secret-token",
                "BARK_URL=https://api.day.app/private-key/",
                "WX_BOT_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=secret",
                "WECOM_APP_CORPID=corp-id",
                "WECOM_APP_SECRET=app-secret",
                "WECOM_APP_AGENTID=1000001",
                "WECOM_APP_TOUSER=user1",
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
    assert "ntfy_topic_url_set" not in env_payload
    assert "gotify_url_set" not in env_payload
    assert "gotify_token_set" not in env_payload
    assert "bark_url_set" not in env_payload
    assert "wx_bot_url_set" not in env_payload
    assert env_payload["wecom_app_corpid_set"] is True
    assert env_payload["wecom_app_secret_set"] is True
    assert env_payload["wecom_app_agentid_set"] is True
    assert env_payload["wecom_app_touser_set"] is True
    assert env_payload["telegram_bot_token_set"] is True
    assert env_payload["telegram_chat_id_set"] is True
    assert env_payload["webhook_url_set"] is True


def test_notification_test_endpoint_merges_stored_secret_values(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "TELEGRAM_BOT_TOKEN=stored-token",
                "TELEGRAM_CHAT_ID=10001",
                "TELEGRAM_API_BASE_URL=https://tg-proxy.example.com/base",
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
    assert captured["url"] == "https://tg-proxy.example.com/base/botstored-token/sendMessage"
    assert captured["json"]["chat_id"] == "20002"


def test_notification_test_endpoint_rejects_retired_channels(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    response = client.post(
        "/api/settings/notifications/test",
        json={
            "channel": "ntfy",
            "settings": {
                "GOTIFY_URL": "not-a-url",
                "WEBHOOK_BODY": '{"message":"{{content}}"}',
            },
        },
    )

    assert response.status_code == 422
    assert "不支持的通知渠道: ntfy" in response.text


def test_ai_settings_fall_back_to_runtime_environment_when_env_file_missing(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    monkeypatch.setattr(env_manager, "env_file", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://runtime.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "runtime-model")
    monkeypatch.setenv("PROXY_URL", "http://127.0.0.1:7890")
    client = _build_settings_client()

    ai_response = client.get("/api/settings/ai")
    assert ai_response.status_code == 200
    assert ai_response.json() == {
        "OPENAI_BASE_URL": "https://runtime.example.com/v1",
        "OPENAI_MODEL_NAME": "runtime-model",
        "SKIP_AI_ANALYSIS": False,
        "PROXY_URL": "http://127.0.0.1:7890",
    }

    status_response = client.get("/api/settings/status")
    assert status_response.status_code == 200
    env_payload = status_response.json()["env_file"]
    assert env_payload["exists"] is False
    assert env_payload["openai_api_key_set"] is True
    assert env_payload["openai_base_url_set"] is True
    assert env_payload["openai_model_name_set"] is True


def test_notification_settings_fall_back_to_runtime_environment_when_env_file_missing(
    tmp_path, monkeypatch
):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    monkeypatch.setattr(env_manager, "env_file", env_file)
    monkeypatch.setenv("NTFY_TOPIC_URL", "https://ntfy.sh/runtime-topic")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "runtime-telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "20001")
    monkeypatch.setenv("TELEGRAM_API_BASE_URL", "https://runtime-tg-proxy.example.com")
    monkeypatch.setenv("BARK_URL", "https://api.day.app/runtime-secret/")
    monkeypatch.setenv("WECOM_APP_CORPID", "runtime-corp")
    monkeypatch.setenv("WECOM_APP_SECRET", "runtime-secret")
    monkeypatch.setenv("WECOM_APP_AGENTID", "1000002")
    client = _build_settings_client()

    response = client.get("/api/settings/notifications")

    assert response.status_code == 200
    payload = response.json()
    assert "NTFY_TOPIC_URL" not in payload
    assert payload["TELEGRAM_CHAT_ID"] == "20001"
    assert payload["TELEGRAM_API_BASE_URL"] == "https://runtime-tg-proxy.example.com"
    assert "BARK_URL" not in payload
    assert "BARK_URL_SET" not in payload
    assert payload["WECOM_APP_CORPID"] == "runtime-corp"
    assert payload["WECOM_APP_AGENTID"] == "1000002"
    assert payload["WECOM_APP_SECRET"] == ""
    assert payload["WECOM_APP_SECRET_SET"] is True
    assert payload["TELEGRAM_BOT_TOKEN_SET"] is True
    assert sorted(payload["CONFIGURED_CHANNELS"]) == ["telegram", "wecom_app"]


def test_ai_test_endpoint_falls_back_to_responses_when_chat_completions_api_404(
    tmp_path, monkeypatch
):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()
    request_history = []

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = type(
                "_Responses",
                (),
                {"create": self._responses_create},
            )()
            self.chat = type(
                "_Chat",
                (),
                {
                    "completions": type(
                        "_Completions",
                        (),
                        {"create": self._chat_create},
                    )()
                },
            )()

        def _responses_create(self, **kwargs):
            request_history.append(("responses", kwargs))
            return type(
                "_Response",
                (),
                {"output_text": "OK"},
            )()

        def _chat_create(self, **kwargs):
            request_history.append(("chat", kwargs))
            raise Exception("Error code: 404 - page not found")

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    response = client.post(
        "/api/settings/ai/test",
        json={
            "OPENAI_API_KEY": "demo",
            "OPENAI_BASE_URL": "https://example.com/v1/",
            "OPENAI_MODEL_NAME": "demo-model",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["response"] == "OK"
    assert request_history[0][0] == "chat"
    assert request_history[0][1]["messages"][0]["content"] == settings.AI_TEST_PROMPT
    assert request_history[1][0] == "responses"
    assert request_history[1][1]["input"][0]["content"][0]["text"] == settings.AI_TEST_PROMPT
