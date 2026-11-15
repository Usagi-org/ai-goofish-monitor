import asyncio
import base64
import hashlib
import hmac
from urllib.parse import parse_qs, quote_plus, urlparse

import pytest
import requests

from src.infrastructure.external.notification_clients.base import NotificationClient
from src.infrastructure.external.notification_clients.dingtalk_client import DingTalkClient
from src.infrastructure.external.notification_clients.pushplus_client import PushPlusClient
from src.infrastructure.external.notification_clients.webhook_client import WebhookClient
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


def _product():
    return {
        "商品标题": "Sony A7M4",
        "当前售价": "9999",
        "商品链接": "https://www.goofish.com/item/123",
    }


def test_pushplus_client_sends_text_template_and_requires_business_code(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 200, "msg": "请求成功"}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)
    client = PushPlusClient("test-token", "group-code", pcurl_to_mobile=False)

    asyncio.run(client.send(_product(), "价格合适"))

    assert captured["url"] == "https://www.pushplus.plus/send"
    assert captured["json"]["token"] == "test-token"
    assert captured["json"]["topic"] == "group-code"
    assert captured["json"]["template"] == "txt"
    assert captured["json"]["content"].startswith("价格: 9999\n原因: 价格合适")


def test_pushplus_client_rejects_business_error_with_http_200(monkeypatch):
    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 903, "msg": "无效的用户token"}

    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse(),
    )
    client = PushPlusClient("bad-token", pcurl_to_mobile=False)

    with pytest.raises(RuntimeError, match="无效的用户token"):
        asyncio.run(client.send(_product(), "价格合适"))


def test_dingtalk_client_sends_markdown_with_image_without_secret(monkeypatch):
    captured = {}

    class _FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"errcode": 0, "errmsg": "ok"}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)
    webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=token123"
    client = DingTalkClient(webhook_url=webhook_url, pcurl_to_mobile=True)

    product = {
        "商品标题": "Sony A7M4",
        "当前售价": "9999",
        "商品链接": "https://www.goofish.com/item?id=123",
        "商品主图链接": "https://img.alicdn.com/test.jpg",
    }
    asyncio.run(client.send(product, "价格合适"))

    assert captured["url"] == webhook_url
    assert captured["timeout"] == 10
    assert captured["json"]["msgtype"] == "markdown"
    assert captured["json"]["markdown"]["title"] == "🚨 新推荐! Sony A7M4"
    text = captured["json"]["markdown"]["text"]
    assert "## 🚨 新推荐! Sony A7M4" in text
    assert "![商品图片](https://img.alicdn.com/test.jpg)" in text
    assert "- 价格: 9999" in text
    assert "- 原因: 价格合适" in text
    assert "手机端链接:" in text
    assert "- 电脑端链接: [https://www.goofish.com/item?id=123](https://www.goofish.com/item?id=123)" in text


def test_dingtalk_client_signs_webhook_url_with_hmac_sha256(monkeypatch):
    captured = {}

    class _FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"errcode": 0, "errmsg": "ok"}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)
    monkeypatch.setattr(
        "src.infrastructure.external.notification_clients.dingtalk_client.time.time",
        lambda: 1700000000.123,
    )

    secret = "SECtestsecret123"
    webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=token123"
    client = DingTalkClient(webhook_url=webhook_url, secret=secret, pcurl_to_mobile=False)

    asyncio.run(client.send(_product(), "价格合适"))

    expected_ts = "1700000000123"
    expected_raw_b64 = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            f"{expected_ts}\n{secret}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    expected_quoted_sign = quote_plus(expected_raw_b64)

    assert (
        captured["url"]
        == f"{webhook_url}&timestamp={expected_ts}&sign={expected_quoted_sign}"
    )
    parsed_query = parse_qs(urlparse(captured["url"]).query)
    assert parsed_query["access_token"] == ["token123"]
    assert parsed_query["timestamp"] == [expected_ts]
    assert parsed_query["sign"] == [expected_raw_b64]


def test_dingtalk_client_raises_on_nonzero_errcode(monkeypatch):
    class _FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"errcode": 310000, "errmsg": "sign not match"}

    monkeypatch.setattr(
        "requests.post",
        lambda *args, **kwargs: _FakeResponse(),
    )
    client = DingTalkClient(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=token123",
        pcurl_to_mobile=False,
    )

    with pytest.raises(RuntimeError, match="sign not match"):
        asyncio.run(client.send(_product(), "价格合适"))


def test_dingtalk_client_does_not_leak_credentials_on_http_or_network_errors(monkeypatch):
    webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=secret-bot-token-999"
    secret = "SECsupersecret888"
    client = DingTalkClient(webhook_url=webhook_url, secret=secret, pcurl_to_mobile=False)

    class _ForbiddenResponse:
        ok = False
        status_code = 403

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _ForbiddenResponse())
    with pytest.raises(RuntimeError) as http_exc:
        asyncio.run(client.send(_product(), "价格合适"))
    http_msg = str(http_exc.value)
    assert "HTTP 403" in http_msg
    for forbidden in ("access_token", "secret-bot-token-999", secret, "sign="):
        assert forbidden not in http_msg

    def _raise_timeout(url, **kwargs):
        raise requests.Timeout(f"Read timed out for url: {url}")

    monkeypatch.setattr("requests.post", _raise_timeout)
    with pytest.raises(RuntimeError) as timeout_exc:
        asyncio.run(client.send(_product(), "价格合适"))
    timeout_msg = str(timeout_exc.value)
    assert timeout_msg == "钉钉请求超时"
    for forbidden in ("access_token", "secret-bot-token-999", secret, "sign="):
        assert forbidden not in timeout_msg

    def _raise_conn_error(url, **kwargs):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr("requests.post", _raise_conn_error)
    with pytest.raises(RuntimeError) as conn_exc:
        asyncio.run(client.send(_product(), "价格合适"))
    conn_msg = str(conn_exc.value)
    assert conn_msg == "钉钉请求异常：网络连接失败"
    for forbidden in ("access_token", "secret-bot-token-999", secret, "sign="):
        assert forbidden not in conn_msg


@pytest.mark.parametrize(
    ("payload", "expected_match"),
    [
        ({"error": "upstream unavailable"}, "upstream unavailable"),
        ({"errcode": False}, "缺少有效 errcode"),
    ],
)
def test_dingtalk_client_rejects_missing_or_boolean_errcode_on_http_200(
    monkeypatch, payload, expected_match
):
    class _FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return payload

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _FakeResponse())
    client = DingTalkClient(
        webhook_url="https://oapi.dingtalk.com/robot/send?access_token=token123",
        pcurl_to_mobile=False,
    )

    with pytest.raises(RuntimeError, match=expected_match):
        asyncio.run(client.send(_product(), "价格合适"))
