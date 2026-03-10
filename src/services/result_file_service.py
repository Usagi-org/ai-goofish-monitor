"""
结果文件读取与富化服务
"""
import json
import os

import aiofiles

from src.services.price_history_service import (
    build_item_price_context,
    load_price_snapshots,
    parse_price_value,
)


def validate_result_filename(filename: str) -> None:
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise ValueError("无效的文件名")


def normalize_keyword_from_filename(filename: str) -> str:
    return filename.replace("_full_data.jsonl", "")


def _sort_key(sort_by: str, item: dict):
    info = item.get("商品信息", {}) or {}
    if sort_by == "publish_time":
        return info.get("发布时间", "0000-00-00 00:00")
    if sort_by == "price":
        return parse_price_value(info.get("当前售价")) or 0.0
    if sort_by == "keyword_hit_count":
        raw_count = item.get("ai_analysis", {}).get("keyword_hit_count", 0)
        try:
            return int(raw_count)
        except (TypeError, ValueError):
            return 0
    return item.get("爬取时间", "")


async def load_result_records(filename: str) -> list[dict]:
    filepath = os.path.join("jsonl", filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError("结果文件未找到")

    results = []
    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
        async for line in f:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results


def filter_and_sort_records(
    records: list[dict],
    *,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
) -> list[dict]:
    filtered = []
    for record in records:
        ai_analysis = record.get("ai_analysis", {}) or {}
        is_recommended = ai_analysis.get("is_recommended") is True
        source = ai_analysis.get("analysis_source")
        if ai_recommended_only and not (is_recommended and source == "ai"):
            continue
        if keyword_recommended_only and not (is_recommended and source == "keyword"):
            continue
        filtered.append(record)

    filtered.sort(key=lambda item: _sort_key(sort_by, item), reverse=(sort_order == "desc"))
    return filtered


def enrich_records_with_price_insight(records: list[dict], filename: str) -> list[dict]:
    snapshots = load_price_snapshots(normalize_keyword_from_filename(filename))
    if not snapshots:
        return records

    enriched = []
    for record in records:
        info = record.get("商品信息", {}) or {}
        clone = dict(record)
        clone["price_insight"] = build_item_price_context(
            snapshots,
            item_id=str(info.get("商品ID") or ""),
            current_price=parse_price_value(info.get("当前售价")),
        )
        enriched.append(clone)
    return enriched
