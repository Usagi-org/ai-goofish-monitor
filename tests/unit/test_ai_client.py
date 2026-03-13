import asyncio
from types import SimpleNamespace

from src.infrastructure.external.ai_client import AIClient
from src.services.ai_request_compat import build_responses_input


def _build_fake_client(create_impl):
    responses = SimpleNamespace(create=create_impl)
    return SimpleNamespace(responses=responses)


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
                "'message': 'The parameter `text.format.type` specified in "
                "the request are not valid: `json_object` is not supported by "
                "this model.', 'param': 'text.format.type'}}"
            )
        return SimpleNamespace(output_text='{"ok":true}')

    client.client = _build_fake_client(fake_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert request_history[0]["input"][0]["content"][0]["type"] == "input_text"
    assert request_history[0]["text"]["format"]["type"] == "json_object"
    assert "text" not in request_history[1]


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
        return SimpleNamespace(output_text='{"ok":true}')

    client.client = _build_fake_client(fake_create)

    response = asyncio.run(client._call_ai([{"role": "user", "content": "hi"}]))

    assert response == '{"ok":true}'
    assert request_history[0]["temperature"] == 0.1
    assert "temperature" not in request_history[1]
