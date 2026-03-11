"""AI 请求兼容性辅助逻辑。"""

from typing import Any, Dict


UNSUPPORTED_RESPONSE_FORMAT_MARKERS = (
    "response_format.type",
    "json_object",
    "not supported by this model",
)


def add_json_response_format(
    request_params: Dict[str, Any],
    enabled: bool,
) -> Dict[str, Any]:
    """按需附加结构化输出参数，避免直接修改原始字典。"""
    next_params = dict(request_params)
    if enabled:
        next_params["response_format"] = {"type": "json_object"}
    return next_params


def is_response_format_unsupported_error(error: Exception) -> bool:
    """识别模型不支持 response_format=json_object 的错误。"""
    message = str(error)
    return all(marker in message for marker in UNSUPPORTED_RESPONSE_FORMAT_MARKERS)
