"""
AI 响应解析工具
"""
import json
from typing import Any


class EmptyAIResponseError(ValueError):
    """AI 返回了空内容。"""


class IncompleteAIResponseError(ValueError):
    """模型未完成正式回答；不得把部分内容当作成功结果。"""


def extract_ai_response_content(response: Any) -> str:
    """从不同形态的 AI 响应中提取文本内容。"""
    if response is None:
        raise EmptyAIResponseError("AI响应对象为空。")

    if isinstance(response, (bytes, bytearray)):
        text = response.decode("utf-8", errors="replace")
        return _normalize_text_content(text)

    if isinstance(response, str):
        return _normalize_text_content(response)

    status = getattr(response, "status", None)
    if status is not None and status != "completed":
        raise IncompleteAIResponseError(f"AI回答未完成（status={status}），请提高输出上限或减少模型思考预算。")

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return _normalize_text_content(output_text)

    choices = getattr(response, "choices", None)
    if choices:
        reason = getattr(choices[0], "finish_reason", None)
        if reason is not None and reason != "stop":
            raise IncompleteAIResponseError(f"AI回答未完成或被拒绝（finish_reason={reason}），请提高输出上限或减少模型思考预算。")
        message = getattr(choices[0], "message", None)
        if message is None:
            raise EmptyAIResponseError("AI响应缺少 message。")
        content = getattr(message, "content", None)

        # reasoning_content 是推理过程，不能替代正式答案。
        return _normalize_text_content(_coerce_content_parts(content))

    raise ValueError(f"无法识别的AI响应类型: {type(response).__name__}")


def parse_ai_response_json(content: str) -> dict:
    """解析 AI 文本响应中的 JSON。"""
    cleaned = _strip_code_fences(content)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        # 只从第一个对象起点解析，避免将编号 [1] 或截断对象内的子对象当成结果。
        start = cleaned.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    if not isinstance(value, dict):
        raise ValueError("AI分析结果必须是 JSON 对象。")
    return value


def _coerce_content_parts(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8", errors="replace")
    if not isinstance(content, list):
        raise ValueError(f"AI响应内容类型不受支持: {type(content).__name__}")

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
            continue
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _normalize_text_content(content: str) -> str:
    text = str(content).strip()
    if not text:
        raise EmptyAIResponseError("AI响应内容为空。")
    return text


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
