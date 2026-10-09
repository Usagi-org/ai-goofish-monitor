import asyncio
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.infrastructure.external.ai_client import AIClient, _sanitize_no_proxy_env
from src.services.ai_request_compat import build_responses_input


def _build_fake_client(responses_create_impl, chat_create_impl=None):
    responses = SimpleNamespace(create=responses_create_impl)
    chat = SimpleNamespace(
        completions=SimpleNamespace(create=chat_create_impl or responses_create_impl)
    )
    return SimpleNamespace(responses=responses, chat=chat)


def test_build_messages_without_images_uses_text_only_content():
    client = AIClient.__new__(AIClient)

    messages = client._build_messages(
        {"商品信息": {"商品标题": "MacBook Pro M2"}, "卖家信息": {"卖家信用等级": "优秀"}},
        [],
        "只分析文字描述和卖家资质。",
    )

    content = messages[0]["content"]
    assert isinstance(content, str)
    assert "MacBook Pro M2" in content
    assert "未提供商品图片" in content


def test_build_messages_with_images_uses_multimodal_content(monkeypatch):
    client = AIClient.__new__(AIClient)
    monkeypatch.setattr(AIClient, "encode_image", staticmethod(lambda _path: "ZmFrZQ=="))

    messages = client._build_messages(
        {"商品信息": {"商品标题": "MacBook Pro M2"}},
        ["fake-image.jpg"],
        "结合图片和文字综合判断。",
    )

    content = messages[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "image_url"
    assert content[-1]["type"] == "text"


def test_build_responses_input_converts_multimodal_messages():
    result = build_responses_input(
        [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ZmFrZQ=="}},
                    {"type": "text", "text": "hello"},
                ],
            }
        ]
    )

    assert result == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,ZmFrZQ==",
                    "detail": "auto",
                },
                {"type": "input_text", "text": "hello"},
            ],
        }
    ]


def test_call_ai_retries_without_structured_output_when_model_rejects_it():
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        model_name="fake-model",
        enable_response_format=True,
        enable_thinking=False,
    )
    request_history = []

    async def fake_create(**kwargs):
        request_history.append(kwargs)
        if len(request_history) == 1:
            raise Exception(
                "Error code: 400 - {'error': {'code': 'InvalidParameter', "
                "'message': 'The parameter `response_format.type` specified in "
                "the request are not valid: `json_object` is not supported by "
                "this model.', 'param': 'response_format.type'}}"
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok":true}')
                )
            ]
        )

    client.client = _build_fake_client(fake_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert request_history[0]["messages"][0]["content"] == "hi"
    assert request_history[0]["response_format"]["type"] == "json_object"
    assert "response_format" not in request_history[1]


def test_call_ai_falls_back_to_responses_when_chat_completions_api_is_missing():
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        model_name="fake-model",
        enable_response_format=True,
        enable_thinking=False,
    )
    request_history = []

    async def fake_chat_create(**kwargs):
        request_history.append(("chat", kwargs))
        raise Exception("Error code: 404 - page not found")

    async def fake_responses_create(**kwargs):
        request_history.append(("responses", kwargs))
        if len([item for item in request_history if item[0] == "responses"]) == 1:
            raise Exception(
                "Error code: 400 - {'error': {'code': 'InvalidParameter', "
                "'message': 'The parameter `text.format.type` specified in "
                "the request are not valid: `json_object` is not supported by "
                "this model.', 'param': 'text.format.type'}}"
            )
        return SimpleNamespace(output_text='{"ok":true}')

    client.client = _build_fake_client(fake_responses_create, fake_chat_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert request_history[0][0] == "chat"
    assert request_history[1][0] == "responses"
    assert request_history[1][1]["text"]["format"]["type"] == "json_object"
    assert request_history[2][0] == "responses"
    assert "text" not in request_history[2][1]


def test_call_ai_retries_without_temperature_when_gateway_rejects_it():
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        model_name="fake-model",
        enable_response_format=False,
        enable_thinking=False,
    )
    request_history = []

    async def fake_create(**kwargs):
        request_history.append(kwargs)
        if len(request_history) == 1:
            raise Exception("temperature is not supported by this gateway")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok":true}')
                )
            ]
        )

    client.client = _build_fake_client(fake_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert request_history[0]["temperature"] == 0.1
    assert "temperature" not in request_history[1]


def test_call_ai_retries_when_response_content_is_empty():
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        model_name="fake-model",
        enable_response_format=False,
        enable_thinking=False,
    )
    request_history = []

    async def fake_create(**kwargs):
        request_history.append(kwargs)
        if len(request_history) < 4:
            return SimpleNamespace(output_text="")
        return SimpleNamespace(output_text='{"ok":true}')

    client.client = _build_fake_client(fake_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert len(request_history) == 4


def test_call_ai_raises_after_all_empty_response_retries_are_exhausted():
    client = AIClient.__new__(AIClient)
    client.settings = SimpleNamespace(
        model_name="fake-model",
        enable_response_format=False,
        enable_thinking=False,
    )
    request_history = []

    async def fake_create(**kwargs):
        request_history.append(kwargs)
        return SimpleNamespace(output_text="")

    client.client = _build_fake_client(fake_create)

    with pytest.raises(ValueError, match="AI响应内容为空"):
        asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert len(request_history) == 4


def test_close_closes_underlying_async_client_and_clears_reference():
    client = AIClient.__new__(AIClient)
    close_state = {"closed": False}

    async def fake_close():
        close_state["closed"] = True

    client.client = SimpleNamespace(close=fake_close)

    asyncio.run(client.close())

    assert close_state["closed"] is True
    assert client.client is None


def test_parse_response_uses_first_json_object_when_response_contains_multiple_objects():
    client = AIClient.__new__(AIClient)

    result = client._parse_response("""```json
{"ok": true, "reason": "first"}
{"ok": false, "reason": "second"}
```""")

    assert result == {"ok": True, "reason": "first"}


# -- _sanitize_no_proxy_env tests --


def test_sanitize_no_proxy_strips_ipv6_cidr(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.0/8,::1/128")
    _sanitize_no_proxy_env()
    assert os.environ["NO_PROXY"] == "localhost,127.0.0.0/8,::1"


def test_sanitize_no_proxy_strips_lowercase_variant(monkeypatch):
    monkeypatch.setenv("no_proxy", "localhost,::1/128,fe80::1/64")
    _sanitize_no_proxy_env()
    assert os.environ["no_proxy"] == "localhost,::1,fe80::1"


def test_sanitize_no_proxy_preserves_ipv4_cidr(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "10.0.0.0/8,192.168.0.0/16")
    _sanitize_no_proxy_env()
    assert os.environ["NO_PROXY"] == "10.0.0.0/8,192.168.0.0/16"


def test_sanitize_no_proxy_noop_without_env(monkeypatch):
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    _sanitize_no_proxy_env()


def test_sanitize_no_proxy_handles_both_keys(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "::1/128")
    monkeypatch.setenv("no_proxy", "fe80::1/10")
    _sanitize_no_proxy_env()
    assert os.environ["NO_PROXY"] == "::1"
    assert os.environ["no_proxy"] == "fe80::1"


def test_sanitize_no_proxy_unwraps_bracketed_ipv6(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,::1,[::1]")
    monkeypatch.setenv("no_proxy", "[::1/128],10.0.0.0/8,[not-ipv6]")
    _sanitize_no_proxy_env()
    assert os.environ["NO_PROXY"] == "localhost,127.0.0.1,::1,::1"
    assert os.environ["no_proxy"] == "::1,10.0.0.0/8,[not-ipv6]"


def test_bracketed_ipv6_no_proxy_does_not_break_openai_client(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,[::1]")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,[::1]")
    _sanitize_no_proxy_env()

    from openai import AsyncOpenAI

    AsyncOpenAI(api_key="sk-test", base_url="https://example.com/v1")


def test_legacy_config_client_initializes_with_bracketed_no_proxy(tmp_path):
    env = os.environ.copy()
    env.update(
        {
            "NO_PROXY": "localhost,127.0.0.1,[::1]",
            "no_proxy": "localhost,127.0.0.1,[::1]",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://example.com/v1",
            "OPENAI_MODEL_NAME": "fake-model",
            "PROXY_URL": "",
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os\n"
                "from openai import AsyncOpenAI\n"
                "from src.config import client\n"
                "assert isinstance(client, AsyncOpenAI)\n"
                "assert '[::1]' not in os.environ.get('NO_PROXY', '')\n"
                "assert '[::1]' not in os.environ.get('no_proxy', '')\n"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
