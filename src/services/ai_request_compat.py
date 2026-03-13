"""AI 请求兼容性辅助逻辑。"""

from typing import Any, Dict, Iterable, List


INPUT_TEXT_TYPE = "input_text"
INPUT_IMAGE_TYPE = "input_image"
IMAGE_DETAIL_AUTO = "auto"
JSON_OUTPUT_TYPE = "json_object"
UNSUPPORTED_JSON_OUTPUT_MARKERS = (
    "not supported by this model",
    "json_object",
    "json_schema",
    "text.format",
    "response_format.type",
)
UNSUPPORTED_TEMPERATURE_MARKERS = (
    "temperature",
    "sampling temperature",
)


def build_responses_input(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 Chat Completions 风格的消息转换为 Responses API 输入。"""
    input_items: List[Dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        input_items.append(
            {
                "role": role,
                "content": _build_input_content(message.get("content")),
            }
        )
    return input_items


def add_json_text_format(
    request_params: Dict[str, Any],
    enabled: bool,
) -> Dict[str, Any]:
    """按需附加 Responses API 的结构化 JSON 输出参数。"""
    next_params = dict(request_params)
    if not enabled:
        return next_params

    text_config = dict(next_params.get("text") or {})
    text_config["format"] = {"type": JSON_OUTPUT_TYPE}
    next_params["text"] = text_config
    return next_params


def is_json_output_unsupported_error(error: Exception) -> bool:
    """识别模型不支持结构化 JSON 输出参数的错误。"""
    message = str(error)
    return (
        "not supported" in message.lower()
        and any(marker in message for marker in UNSUPPORTED_JSON_OUTPUT_MARKERS)
    )


def is_temperature_unsupported_error(error: Exception) -> bool:
    """识别模型或中转站不支持 temperature 参数的错误。"""
    message = str(error).lower()
    return (
        "not supported" in message
        or "unsupported" in message
        or "invalid" in message
        or "参数错误" in message
    ) and any(marker in message for marker in UNSUPPORTED_TEMPERATURE_MARKERS)


def remove_temperature_param(request_params: Dict[str, Any]) -> Dict[str, Any]:
    """移除 temperature 参数，适配不支持采样温度的模型网关。"""
    next_params = dict(request_params)
    next_params.pop("temperature", None)
    return next_params


def _build_input_content(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": INPUT_TEXT_TYPE, "text": content}]
    if not isinstance(content, list):
        raise ValueError(f"AI消息内容类型不受支持: {type(content).__name__}")

    return [_coerce_content_item(item) for item in content]


def _coerce_content_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"AI消息片段类型不受支持: {type(item).__name__}")

    item_type = item.get("type")
    if item_type in {"text", INPUT_TEXT_TYPE}:
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError("文本消息片段缺少 text 字段。")
        return {"type": INPUT_TEXT_TYPE, "text": text}

    if item_type in {"image_url", INPUT_IMAGE_TYPE}:
        return _build_image_input_item(item)

    raise ValueError(f"不支持的 AI 消息片段类型: {item_type}")


def _build_image_input_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_image = item.get("image_url")
    if isinstance(raw_image, dict):
        image_url = raw_image.get("url")
    else:
        image_url = raw_image

    if not isinstance(image_url, str) or not image_url.strip():
        raise ValueError("图片消息片段缺少有效的 image_url。")

    return {
        "type": INPUT_IMAGE_TYPE,
        "image_url": image_url,
        "detail": item.get("detail", IMAGE_DETAIL_AUTO),
    }
