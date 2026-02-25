"""
关键词规则判断引擎。
组内 include_keywords 为 AND，exclude_keywords 为 NOT，组间为 OR。
"""
from typing import Any, Dict, Iterable, List


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


def _normalize_keywords(values: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in values or []:
        text = normalize_text(str(raw).strip())
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _extract_group_fields(group: Any, fallback_name: str) -> Dict[str, Any]:
    if isinstance(group, dict):
        name = group.get("name")
        include_keywords = group.get("include_keywords") or []
        exclude_keywords = group.get("exclude_keywords") or []
    else:
        name = getattr(group, "name", None)
        include_keywords = getattr(group, "include_keywords", []) or []
        exclude_keywords = getattr(group, "exclude_keywords", []) or []

    group_name = str(name).strip() if name else fallback_name
    return {
        "name": group_name,
        "include_keywords": _normalize_keywords(include_keywords),
        "exclude_keywords": _normalize_keywords(exclude_keywords),
    }


def evaluate_keyword_rules(groups: List[Any], search_text: str) -> Dict[str, Any]:
    normalized_text = normalize_text(search_text)
    if not normalized_text:
        return {
            "analysis_source": "keyword",
            "is_recommended": False,
            "reason": "可匹配文本为空，关键词规则无法执行。",
            "matched_groups": [],
            "matched_keywords": [],
            "blocked_keywords": [],
        }

    if not groups:
        return {
            "analysis_source": "keyword",
            "is_recommended": False,
            "reason": "未配置关键词规则分组。",
            "matched_groups": [],
            "matched_keywords": [],
            "blocked_keywords": [],
        }

    group_fail_reasons: List[str] = []
    for index, raw_group in enumerate(groups, start=1):
        group = _extract_group_fields(raw_group, fallback_name=f"规则组{index}")
        include_keywords = group["include_keywords"]
        exclude_keywords = group["exclude_keywords"]
        group_name = group["name"]

        if not include_keywords:
            group_fail_reasons.append(f"{group_name}: 缺少包含关键词")
            continue

        missing = [kw for kw in include_keywords if kw not in normalized_text]
        blocked = [kw for kw in exclude_keywords if kw in normalized_text]
        if missing or blocked:
            detail_parts = []
            if missing:
                detail_parts.append(f"缺少 {', '.join(missing)}")
            if blocked:
                detail_parts.append(f"命中排除词 {', '.join(blocked)}")
            group_fail_reasons.append(f"{group_name}: {'; '.join(detail_parts)}")
            continue

        return {
            "analysis_source": "keyword",
            "is_recommended": True,
            "reason": f"命中关键词规则：{group_name}（包含词全部满足，且未触发排除词）。",
            "matched_groups": [group_name],
            "matched_keywords": include_keywords,
            "blocked_keywords": [],
        }

    reason = "；".join(group_fail_reasons[:3]) if group_fail_reasons else "所有关键词规则组均未命中。"
    return {
        "analysis_source": "keyword",
        "is_recommended": False,
        "reason": reason,
        "matched_groups": [],
        "matched_keywords": [],
        "blocked_keywords": [],
    }
