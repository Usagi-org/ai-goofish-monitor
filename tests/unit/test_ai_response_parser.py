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


def test_extract_ai_response_content_rejects_reasoning_only_reply():
    """推理过程不能代替空的正式回答。"""
    # 创建 mock 对象模拟 OpenAI 风格的响应
    message = type('Message', (), {
        'content': None,
        'reasoning_content': '这是推理内容'
    })()
    choice = type('Choice', (), {'message': message})()
    response = type('Response', (), {'choices': [choice]})()

    with pytest.raises(EmptyAIResponseError):
        extract_ai_response_content(response)


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


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls"])
def test_rejects_unfinished_chat_even_if_text_is_valid_json(reason):
    from types import SimpleNamespace as NS
    response = NS(choices=[NS(finish_reason=reason, message=NS(content='{"ok":true}'))])
    with pytest.raises(ValueError, match="未完成|拒绝"):
        extract_ai_response_content(response)


def test_rejects_incomplete_responses_before_reading_output_text():
    from types import SimpleNamespace as NS
    with pytest.raises(ValueError, match="未完成"):
        extract_ai_response_content(NS(status="incomplete", output_text='{"ok":true}'))


def test_json_parser_ignores_numbered_reference_before_object():
    assert parse_ai_response_json('参考[1]，结果：{"ok":true}') == {"ok": True}


@pytest.mark.parametrize("content", ['[1,2]', 'null', 'true', '{"outer": {"ok": true}'])
def test_json_parser_rejects_nonobject_or_truncated_outer_object(content):
    with pytest.raises(ValueError):
        parse_ai_response_json(content)
