"""
结果记录富化与文件名校验服务
"""

from src.infrastructure.persistence.storage_names import normalize_keyword_from_filename
from src.services.price_history_service import (
    build_item_price_context,
    load_price_snapshots,
    parse_price_value,
)


def validate_result_filename(filename: str) -> None:
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise ValueError("无效的文件名")


def enrich_records_with_price_insight(records: list[dict], filename: str) -> list[dict]:
    snapshots = load_price_snapshots(normalize_keyword_from_filename(filename))
    if not snapshots:
        return records

    enriched = []
    for record in records:
        info = record.get("商品信息", {}) or {}
        item_id = str(info.get("商品 ID") or "")

        # 优先从价格快照中获取最新价格，而不是使用结果文件中的旧价格
        price_from_snapshot = None
        if snapshots and item_id:
            item_snapshots = [s for s in snapshots if str(s.get("item_id")) == item_id]
            if item_snapshots:
                price_from_snapshot = item_snapshots[-1].get("price")

        clone = dict(record)
        clone["price_insight"] = build_item_price_context(
            snapshots,
            item_id=item_id,
            current_price=price_from_snapshot,
        )
        enriched.append(clone)
    return enriched
