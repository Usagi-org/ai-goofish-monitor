"""
结果记录富化与文件名校验服务
"""

from src.infrastructure.persistence.storage_names import normalize_keyword_from_filename
from src.services.price_history_service import (
    build_item_price_context,
    load_price_snapshots,
)
from src.services.result_storage_service import load_visible_result_item_ids


def validate_result_filename(filename: str) -> None:
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise ValueError("无效的文件名")


def enrich_records_with_price_insight(records: list[dict], filename: str) -> list[dict]:
    snapshots = load_price_snapshots(normalize_keyword_from_filename(filename))
    if not snapshots:
        return records

    visible_item_ids = load_visible_result_item_ids(filename)
    visible_snapshots = [
        snapshot
        for snapshot in snapshots
        if str(snapshot.get("item_id") or "") in visible_item_ids
    ]
    enriched = []
    for record in records:
        info = record.get("商品信息", {}) or {}
        clone = dict(record)
        clone["price_insight"] = build_item_price_context(
            snapshots,
            item_id=str(info.get("商品ID") or ""),
            current_price=None,
            market_snapshots=visible_snapshots,
            include_history=True,
        )
        enriched.append(clone)
    return enriched
