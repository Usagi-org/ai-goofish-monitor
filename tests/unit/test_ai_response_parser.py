from types import SimpleNamespace

import pytest

from src.services.ai_response_parser import (
    extract_ai_response_content,
    parse_ai_response_json,
    EmptyAIResponseError,
)


def test_parse_ai_response_json_uses_first_object_when_multiple_json_objects_are_concatenated():
    content = """```json
{"is_recommended": true, "reason": "first"}
{"is_recommended": false, "reason": "second"}
```"""

    result = parse_ai_response_json(content)

    assert result == {"is_recommended": True, "reason": "first"}


def test_parse_ai_response_json_extracts_json_from_wrapped_text():
    content = """分析结果如下：

```json
{"is_recommended": true, "reason": "wrapped"}
```

请按第一份结果处理。"""

    result = parse_ai_response_json(content)

    assert result == {"is_recommended": True, "reason": "wrapped"}


def test_parse_ai_response_json_raises_when_no_json_exists():
    with pytest.raises(ValueError):
        parse_ai_response_json("没有任何 JSON 内容")


def test_extract_ai_response_content_with_none_content_but_valid_reasoning_content():
    """当 content 为 None 但 reasoning_content 有值时，应该成功提取 reasoning_content 的内容"""
    # 创建 mock 对象模拟 OpenAI 风格的响应
    message = type('Message', (), {
        'content': None,
        'reasoning_content': '这是推理内容'
    })()
    choice = type('Choice', (), {'message': message})()
    response = type('Response', (), {'choices': [choice]})()

    result = extract_ai_response_content(response)

    assert result == '这是推理内容'


@pytest.mark.parametrize("finish_reason", ["stop", "length"])
def test_extract_ai_response_content_checks_completion_before_reasoning_fallback(finish_reason):
    response = SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=None, reasoning_content="gateway answer"),
    )])

    if finish_reason == "stop":
        assert extract_ai_response_content(response) == "gateway answer"
    else:
        with pytest.raises(ValueError, match="length"):
            extract_ai_response_content(response)


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls"])
def test_extract_ai_response_content_rejects_unfinished_chat_even_with_valid_json(
    finish_reason,
):
    response = SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content='{"ok": true}'),
    )])

    with pytest.raises(ValueError, match=finish_reason):
        extract_ai_response_content(response)


@pytest.mark.parametrize("status", ["incomplete", "failed", "in_progress", "queued", "cancelled"])
def test_extract_ai_response_content_rejects_unfinished_responses_with_text(status):
    response = SimpleNamespace(status=status, output_text='{"ok": true}')

    with pytest.raises(ValueError, match=status):
        extract_ai_response_content(response)


@pytest.mark.parametrize("finish_reason", ["stop", None])
def test_extract_ai_response_content_accepts_final_chat_with_optional_metadata(finish_reason):
    response = SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content='{"ok": true}', reasoning_content="推理过程"),
    )])

    assert extract_ai_response_content(response) == '{"ok": true}'


@pytest.mark.parametrize("status", ["completed", None])
def test_extract_ai_response_content_accepts_final_responses_with_optional_metadata(status):
    response = SimpleNamespace(status=status, output_text='{"ok": true}')

    assert extract_ai_response_content(response) == '{"ok": true}'


def test_extract_ai_response_content_raises_when_content_and_reasoning_content_are_empty():
    """当 content 和 reasoning_content 都为空时，应该抛出 EmptyAIResponseError"""
    # 创建 mock 对象
    message = type('Message', (), {
        'content': None,
        'reasoning_content': None
    })()
    choice = type('Choice', (), {'message': message})()
    response = type('Response', (), {'choices': [choice]})()

    with pytest.raises(EmptyAIResponseError):
        extract_ai_response_content(response)
