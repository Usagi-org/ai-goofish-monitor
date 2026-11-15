"""
关键词判断引擎：单组 OR 逻辑，命中任意关键词即推荐。
纯英数字关键词按完整词匹配，避免 Q1 误命中 Q1R5。
"""
import re
from typing import Any, Dict, Iterable, List, Optional


_ASCII_TOKEN_KEYWORD_PATTERN = re.compile(r"^[a-z0-9 ]+$")
_ASCII_TOKEN_BOUNDARY = r"[a-z0-9]"


def normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _collect_text_fragments(value: Any, bucket: List[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            bucket.append(text)
        return
    if isinstance(value, (int, float, bool)):
        bucket.append(str(value))
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_text_fragments(item, bucket)
        return
    if isinstance(value, list):
        for item in value:
            _collect_text_fragments(item, bucket)


def build_search_text(record: Dict[str, Any]) -> str:
    fragments: List[str] = []
    product_info = record.get("商品信息", {})
    seller_info = record.get("卖家信息", {})

    _collect_text_fragments(product_info.get("商品标题"), fragments)
    _collect_text_fragments(product_info, fragments)
    _collect_text_fragments(seller_info, fragments)

    return normalize_text(" ".join(fragments))


def normalize_keyword_values(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    elif isinstance(value, str):
        raw_values = re.split(r"[\n,]+", value)
    else:
        raw_values = [value]

    normalized: List[str] = []
    seen = set()
    for item in raw_values:
        text = str(item).strip()
        if not text:
            continue
        dedup_key = normalize_text(text)
        if not dedup_key or dedup_key in seen:
            continue
        seen.add(dedup_key)
        normalized.append(text)
    return normalized


def _normalize_keywords(values: Any) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in normalize_keyword_values(values):
        text = normalize_text(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _uses_ascii_token_match(keyword: str) -> bool:
    return bool(keyword) and _ASCII_TOKEN_KEYWORD_PATTERN.fullmatch(keyword) is not None


def _keyword_matches(keyword: str, normalized_text: str) -> bool:
    if not _uses_ascii_token_match(keyword):
        return keyword in normalized_text
    pattern = rf"(?<!{_ASCII_TOKEN_BOUNDARY}){re.escape(keyword)}(?!{_ASCII_TOKEN_BOUNDARY})"
    return re.search(pattern, normalized_text) is not None


def _iter_field_texts(fields: Iterable[Any]) -> Iterable[str]:
    for field in fields or []:
        if field is None:
            continue
        if isinstance(field, str):
            norm = normalize_text(field)
            if norm:
                yield norm
        elif isinstance(field, (list, tuple, set)):
            for item in field:
                if item is None:
                    continue
                norm = normalize_text(str(item))
                if norm:
                    yield norm
        elif isinstance(field, (int, float, bool)):
            norm = normalize_text(str(field))
            if norm:
                yield norm


def match_exclude_keywords_in_fields(
    exclude_keywords: Any,
    fields: Iterable[Any],
) -> List[str]:
    normalized_excludes = _normalize_keywords(exclude_keywords)
    if not normalized_excludes or fields is None:
        return []
    segments = list(_iter_field_texts(fields))
    if not segments:
        return []
    return [
        kw
        for kw in normalized_excludes
        if any(_keyword_matches(kw, segment) for segment in segments)
    ]


def match_exclude_keywords(
    exclude_keywords: Optional[Iterable[str]],
    search_text: str,
) -> List[str]:
    return match_exclude_keywords_in_fields(exclude_keywords, [search_text])


def evaluate_keyword_rules(
    keywords: List[str],
    search_text: str,
    exclude_keywords: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    normalized_text = normalize_text(search_text)
    normalized_keywords = _normalize_keywords(keywords)

    if not normalized_text:
        result: Dict[str, Any] = {
            "analysis_source": "keyword",
            "is_recommended": False,
            "reason": "可匹配文本为空，关键词规则无法执行。",
            "matched_keywords": [],
            "keyword_hit_count": 0,
        }
        if exclude_keywords is not None:
            result["matched_exclude_keywords"] = []
        return result

    matched_exclude_keywords = match_exclude_keywords(exclude_keywords, normalized_text)
    if matched_exclude_keywords:
        return {
            "analysis_source": "keyword",
            "is_recommended": False,
            "reason": f"命中排除词：{', '.join(matched_exclude_keywords)}",
            "matched_keywords": [],
            "matched_exclude_keywords": matched_exclude_keywords,
            "keyword_hit_count": 0,
        }

    if not normalized_keywords:
        result = {
            "analysis_source": "keyword",
            "is_recommended": False,
            "reason": "未配置关键词规则。",
            "matched_keywords": [],
            "keyword_hit_count": 0,
        }
        if exclude_keywords is not None:
            result["matched_exclude_keywords"] = []
        return result

    matched_keywords = [kw for kw in normalized_keywords if _keyword_matches(kw, normalized_text)]
    hit_count = len(matched_keywords)
    is_recommended = hit_count > 0

    if is_recommended:
        reason = f"命中 {hit_count} 个关键词：{', '.join(matched_keywords)}"
    else:
        reason = "未命中任何关键词。"

    result = {
        "analysis_source": "keyword",
        "is_recommended": is_recommended,
        "reason": reason,
        "matched_keywords": matched_keywords,
        "keyword_hit_count": hit_count,
    }
    if exclude_keywords is not None:
        result["matched_exclude_keywords"] = []
    return result
