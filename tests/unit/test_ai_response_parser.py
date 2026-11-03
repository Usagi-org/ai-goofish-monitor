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


@pytest.mark.parametrize(
    "content",
    [
        '根据规则[1]，结论如下：{"is_recommended": true, "reason": "x"}',
        '第[2]条不满足。\n```json\n{"is_recommended": true, "reason": "x"}\n```',
    ],
)
def test_parse_ai_response_json_skips_bracketed_reference_before_object(content):
    result = parse_ai_response_json(content)

    assert result == {"is_recommended": True, "reason": "x"}


def test_parse_ai_response_json_still_returns_array_when_no_object_exists():
    result = parse_ai_response_json('结果如下：[1, 2] 以上。')

    assert result == [1, 2]


def test_parse_ai_response_json_keeps_whole_array_of_objects_in_wrapped_text():
    result = parse_ai_response_json('结果如下：[ {"id": 1}, {"id": 2} ] 以上。')

    assert result == [{"id": 1}, {"id": 2}]
