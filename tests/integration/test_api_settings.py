import requests
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
    "PUSHPLUS_TOKEN",
    "PUSHPLUS_TOPIC",
    "GOTIFY_URL",
    "GOTIFY_TOKEN",
    "BARK_URL",
    "WX_BOT_URL",
    "DINGTALK_WEBHOOK",
    "DINGTALK_SECRET",
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
    assert payload["NTFY_TOPIC_URL"] == "https://ntfy.sh/demo-topic"
    assert payload["GOTIFY_URL"] == "https://gotify.example.com"
    assert payload["TELEGRAM_CHAT_ID"] == "123456"
    assert payload["TELEGRAM_API_BASE_URL"] == "https://tg.example.com/proxy"
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
    _clear_settings_env(monkeypatch)
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


def test_notification_test_endpoint_ignores_other_channel_dirty_fields(tmp_path, monkeypatch):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NTFY_TOPIC_URL=https://ntfy.sh/demo-topic\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    captured = []

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def _fake_post(url, data=None, headers=None, timeout=None, **kwargs):
        captured.append({
            "url": url,
            "data": data,
            "headers": headers,
        })
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)

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

    assert response.status_code == 200
    payload = response.json()
    assert list(payload["results"]) == ["ntfy"]
    assert payload["results"]["ntfy"]["success"] is True
    assert len(captured) == 1
    assert captured[0]["url"] == "https://ntfy.sh/demo-topic"


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
    client = _build_settings_client()

    response = client.get("/api/settings/notifications")

    assert response.status_code == 200
    payload = response.json()
    assert payload["NTFY_TOPIC_URL"] == "https://ntfy.sh/runtime-topic"
    assert payload["TELEGRAM_CHAT_ID"] == "20001"
    assert payload["TELEGRAM_API_BASE_URL"] == "https://runtime-tg-proxy.example.com"
    assert payload["BARK_URL"] == ""
    assert payload["BARK_URL_SET"] is True
    assert payload["TELEGRAM_BOT_TOKEN_SET"] is True
    assert sorted(payload["CONFIGURED_CHANNELS"]) == ["bark", "ntfy", "telegram"]


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


def test_dingtalk_notification_settings_lifecycle_validation_and_single_channel_test(
    tmp_path, monkeypatch
):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    # 1. 单独填写 DINGTALK_SECRET 未填 DINGTALK_WEBHOOK 时报错 422
    secret_only_resp = client.put(
        "/api/settings/notifications",
        json={"DINGTALK_SECRET": "SECtestsecret"},
    )
    assert secret_only_resp.status_code == 422
    assert "配置 DINGTALK_SECRET 前必须先填写 DINGTALK_WEBHOOK" in secret_only_resp.text

    # 2. 保存 DINGTALK_WEBHOOK 与 DINGTALK_SECRET，校验脱敏回显与状态位
    save_resp = client.put(
        "/api/settings/notifications",
        json={
            "DINGTALK_WEBHOOK": "https://oapi.dingtalk.com/robot/send?access_token=dt-token",
            "DINGTALK_SECRET": "SECtestsecret",
        },
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["configured_channels"] == ["dingtalk"]

    get_resp = client.get("/api/settings/notifications")
    assert get_resp.status_code == 200
    notif_payload = get_resp.json()
    assert notif_payload["DINGTALK_WEBHOOK"] == ""
    assert notif_payload["DINGTALK_SECRET"] == ""
    assert notif_payload["DINGTALK_WEBHOOK_SET"] is True
    assert notif_payload["DINGTALK_SECRET_SET"] is True
    assert notif_payload["CONFIGURED_CHANNELS"] == ["dingtalk"]

    status_resp = client.get("/api/settings/status")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["notification_configured"] is True
    assert status_payload["configured_notification_channels"] == ["dingtalk"]
    assert status_payload["env_file"]["dingtalk_webhook_set"] is True
    assert status_payload["env_file"]["dingtalk_secret_set"] is True

    # 3. 单渠道测试（合并已存储的密文配置并加签请求）
    captured = {}

    class _FakeDingTalkResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"errcode": 0, "errmsg": "ok"}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeDingTalkResponse()

    monkeypatch.setattr("requests.post", _fake_post)

    test_resp = client.post(
        "/api/settings/notifications/test",
        json={"channel": "dingtalk", "settings": {}},
    )
    assert test_resp.status_code == 200
    test_payload = test_resp.json()
    assert list(test_payload["results"]) == ["dingtalk"]
    assert test_payload["results"]["dingtalk"]["success"] is True
    assert test_payload["results"]["dingtalk"]["label"] == "钉钉"
    assert "access_token=dt-token" in captured["url"]
    assert "timestamp=" in captured["url"]
    assert "sign=" in captured["url"]
    assert captured["json"]["msgtype"] == "markdown"

    # 4. 清空钉钉渠道配置
    clear_resp = client.put(
        "/api/settings/notifications",
        json={"DINGTALK_WEBHOOK": None, "DINGTALK_SECRET": None},
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["configured_channels"] == []

    after_clear = client.get("/api/settings/notifications").json()
    assert after_clear["DINGTALK_WEBHOOK_SET"] is False
    assert after_clear["DINGTALK_SECRET_SET"] is False
    assert after_clear["CONFIGURED_CHANNELS"] == []
    env_text = env_file.read_text(encoding="utf-8")
    assert "DINGTALK_WEBHOOK" not in env_text
    assert "DINGTALK_SECRET" not in env_text


def test_dingtalk_test_endpoint_redacts_credentials_and_rejects_malformed_200_payloads(
    tmp_path, monkeypatch
):
    _clear_settings_env(monkeypatch)
    env_file = tmp_path / ".env"
    token_value = "dt-super-secret-token-777"
    secret_value = "SECtopsecretkey999"
    env_file.write_text(
        "\n".join(
            [
                f"DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token={token_value}",
                f"DINGTALK_SECRET={secret_value}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_manager, "env_file", env_file)
    client = _build_settings_client()

    def _assert_no_leaked_secrets(raw_text: str) -> None:
        for sensitive in ("access_token", token_value, secret_value, "sign="):
            assert sensitive not in raw_text

    # 1. HTTP 403 失败响应不泄露完整 URL、token、secret、sign=
    class _ForbiddenResponse:
        ok = False
        status_code = 403

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _ForbiddenResponse())
    http_403_resp = client.post(
        "/api/settings/notifications/test",
        json={"channel": "dingtalk", "settings": {}},
    )
    assert http_403_resp.status_code == 200
    http_403_result = http_403_resp.json()["results"]["dingtalk"]
    assert http_403_result["success"] is False
    assert "HTTP 403" in http_403_result["message"]
    _assert_no_leaked_secrets(http_403_resp.text)

    # 2. 网络异常（底层异常消息故意携带完整签名 URL）绝不泄露敏感参数
    def _raise_connection_error(url, **kwargs):
        raise requests.ConnectionError(
            f"HTTPSConnectionPool(host='oapi.dingtalk.com', port=443): Max retries exceeded with url: {url}"
        )

    monkeypatch.setattr("requests.post", _raise_connection_error)
    net_err_resp = client.post(
        "/api/settings/notifications/test",
        json={"channel": "dingtalk", "settings": {}},
    )
    assert net_err_resp.status_code == 200
    net_err_result = net_err_resp.json()["results"]["dingtalk"]
    assert net_err_result["success"] is False
    assert "网络连接失败" in net_err_result["message"]
    _assert_no_leaked_secrets(net_err_resp.text)

    # 3. HTTP 200 但网关返回 {"error": "upstream unavailable"} 或 {"errcode": False} 均判定失败
    for malformed_body, expected_snippet in (
        ({"error": "upstream unavailable"}, "upstream unavailable"),
        ({"errcode": False}, "缺少有效 errcode"),
    ):
        class _Malformed200Response:
            ok = True
            status_code = 200

            def json(self, body=malformed_body):
                return body

        monkeypatch.setattr(
            "requests.post",
            lambda *args, **kwargs: _Malformed200Response(),
        )
        malformed_resp = client.post(
            "/api/settings/notifications/test",
            json={"channel": "dingtalk", "settings": {}},
        )
        assert malformed_resp.status_code == 200
        malformed_result = malformed_resp.json()["results"]["dingtalk"]
        assert malformed_result["success"] is False
        assert expected_snippet in malformed_result["message"]
        _assert_no_leaked_secrets(malformed_resp.text)
