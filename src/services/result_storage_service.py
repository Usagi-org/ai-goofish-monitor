"""
结果数据的 SQLite 读写服务。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.item_detail_parser import (
    ItemDetailSnapshot,
    apply_detail_to_item_data,
)
from src.services.price_history_service import parse_price_value
from src.services.result_blacklist_service import (
    match_blacklist_keywords,
    normalize_blacklist_keywords,
)


VALID_ITEM_STATUSES = {"active", "sold", "expired", "hidden"}

SORT_COLUMN_MAP = {
    "crawl_time": "crawl_time",
    "publish_time": "COALESCE(publish_time, '')",
    "price": "COALESCE(price, 0)",
    "keyword_hit_count": "keyword_hit_count",
}


def _get_link_unique_key(link: str) -> str:
    return link.split("&", 1)[0]


def _fallback_unique_key(record: dict, item: dict) -> str:
    item_id = str(item.get("商品ID") or "").strip()
    if item_id:
        return f"item:{item_id}"
    digest = hashlib.sha1(
        json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"hash:{digest}"


def _parse_raw_record(raw_json: str, *, status: str | None = None) -> dict:
    record = json.loads(raw_json)
    if status is not None:
        record["_status"] = status
    return record


def _build_query_conditions(
    *,
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
) -> tuple[str, list]:
    conditions = ["result_filename = ?"]
    params: list = [filename]
    if ai_recommended_only:
        conditions.append("is_recommended = 1")
        conditions.append("analysis_source = ?")
        params.append("ai")
    if keyword_recommended_only:
        conditions.append("is_recommended = 1")
        conditions.append("analysis_source = ?")
        params.append("keyword")
    return " AND ".join(conditions), params


def _sort_expression(sort_by: str, sort_order: str) -> str:
    column = SORT_COLUMN_MAP.get(sort_by, SORT_COLUMN_MAP["crawl_time"])
    direction = "ASC" if sort_order == "asc" else "DESC"
    return (
        f"(CASE status WHEN 'active' THEN 0 WHEN 'sold' THEN 1 ELSE 2 END), "
        f"{column} {direction}, id {direction}"
    )


def _load_blacklist_keywords_from_conn(conn, filename: str) -> list[str]:
    row = conn.execute(
        """
        SELECT blacklist_keywords_json
        FROM result_blacklist_rules
        WHERE result_filename = ?
        """,
        (filename,),
    ).fetchone()
    if row is None:
        return []
    try:
        payload = json.loads(row["blacklist_keywords_json"] or "[]")
    except json.JSONDecodeError:
        return []
    return normalize_blacklist_keywords(payload)


def _decorate_record_visibility(record: dict, status: str | None, blacklist_keywords: list[str]) -> dict:
    normalized_status = status or "active"
    matched_keywords = match_blacklist_keywords(record, blacklist_keywords)
    if normalized_status == "expired":
        hidden_reason = "expired"
    elif normalized_status == "hidden":
        hidden_reason = "manual"
    elif matched_keywords:
        hidden_reason = "rule"
    else:
        hidden_reason = None

    record["_status"] = normalized_status
    record["_is_sold"] = normalized_status == "sold"
    record["_matched_blacklist_keywords"] = matched_keywords
    record["_hidden_reason"] = hidden_reason
    record["_effective_hidden"] = hidden_reason is not None
    return record


def _is_record_visible(record: dict) -> bool:
    return record.get("_effective_hidden") is not True


def _load_filtered_records_from_conn(
    conn,
    *,
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    include_hidden: bool,
    include_sold: bool = True,
) -> list[dict]:
    where_clause, params = _build_query_conditions(
        filename=filename,
        ai_recommended_only=ai_recommended_only,
        keyword_recommended_only=keyword_recommended_only,
    )
    order_clause = _sort_expression(sort_by, sort_order)
    rows = conn.execute(
        f"""
        SELECT raw_json, status
        FROM result_items
        WHERE {where_clause}
        ORDER BY {order_clause}
        """,
        tuple(params),
    ).fetchall()
    blacklist_keywords = _load_blacklist_keywords_from_conn(conn, filename)

    records: list[dict] = []
    for row in rows:
        record = _parse_raw_record(str(row["raw_json"]), status=row["status"])
        decorated = _decorate_record_visibility(record, row["status"], blacklist_keywords)
        if (include_hidden or not decorated["_effective_hidden"]) and (
            include_sold or decorated["_status"] != "sold"
        ):
            records.append(decorated)
    return records


async def save_result_record(record: dict, keyword: str) -> bool:
    return await asyncio.to_thread(_save_result_record_sync, record, keyword)


def _save_result_record_sync(record: dict, keyword: str) -> bool:
    bootstrap_sqlite_storage()
    record_to_store = dict(record)
    raw_initial_status = record_to_store.pop("_initial_status", None)
    initial_status = (
        raw_initial_status
        if isinstance(raw_initial_status, str) and raw_initial_status in VALID_ITEM_STATUSES
        else "active"
    )
    item = record_to_store.get("商品信息", {}) or {}
    analysis = record_to_store.get("ai_analysis", {}) or {}
    link = str(item.get("商品链接") or "")
    link_unique_key = (
        _get_link_unique_key(link) if link else _fallback_unique_key(record_to_store, item)
    )
    keyword_hit_count = analysis.get("keyword_hit_count", 0)
    try:
        keyword_hit_count = int(keyword_hit_count)
    except (TypeError, ValueError):
        keyword_hit_count = 0

    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO result_items (
                result_filename, keyword, task_name, crawl_time, publish_time, price,
                price_display, item_id, title, link, link_unique_key, seller_nickname,
                is_recommended, analysis_source, keyword_hit_count, status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                build_result_filename(keyword),
                record_to_store.get("搜索关键字", keyword),
                record_to_store.get("任务名称", ""),
                record_to_store.get("爬取时间", ""),
                item.get("发布时间"),
                parse_price_value(item.get("当前售价")),
                item.get("当前售价"),
                item.get("商品ID"),
                item.get("商品标题"),
                link,
                link_unique_key,
                (record_to_store.get("卖家信息", {}) or {}).get("卖家昵称") or item.get("卖家昵称"),
                1 if analysis.get("is_recommended") else 0,
                analysis.get("analysis_source"),
                keyword_hit_count,
                initial_status,
                json.dumps(record_to_store, ensure_ascii=False),
            ),
        )
        conn.commit()
    return True


def load_processed_link_keys(keyword: str) -> set[str]:
    bootstrap_sqlite_storage()
    filename = build_result_filename(keyword)
    with sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT link_unique_key FROM result_items WHERE result_filename = ?",
            (filename,),
        ).fetchall()
    return {str(row["link_unique_key"]) for row in rows if row["link_unique_key"]}


async def list_result_filenames() -> list[str]:
    return await asyncio.to_thread(_list_result_filenames_sync)


def _list_result_filenames_sync() -> list[str]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        rows = conn.execute(
            """
            SELECT result_filename, MAX(crawl_time) AS latest_crawl_time
            FROM result_items
            GROUP BY result_filename
            ORDER BY latest_crawl_time DESC, result_filename DESC
            """
        ).fetchall()
    return [str(row["result_filename"]) for row in rows]


async def result_file_exists(filename: str) -> bool:
    return await asyncio.to_thread(_result_file_exists_sync, filename)


def _result_file_exists_sync(filename: str) -> bool:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM result_items WHERE result_filename = ? LIMIT 1",
            (filename,),
        ).fetchone()
    return row is not None


async def delete_result_file_records(filename: str) -> int:
    return await asyncio.to_thread(_delete_result_file_records_sync, filename)


def _delete_result_file_records_sync(filename: str) -> int:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM result_items WHERE result_filename = ?",
            (filename,),
        )
        conn.commit()
    return int(cursor.rowcount or 0)


async def query_result_records(
    filename: str,
    *,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    page: int,
    limit: int,
    include_hidden: bool = False,
    include_sold: bool = True,
) -> tuple[int, list[dict]]:
    return await asyncio.to_thread(
        _query_result_records_sync,
        filename,
        ai_recommended_only,
        keyword_recommended_only,
        sort_by,
        sort_order,
        page,
        limit,
        include_hidden,
        include_sold,
    )


def _query_result_records_sync(
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    page: int,
    limit: int,
    include_hidden: bool,
    include_sold: bool = True,
) -> tuple[int, list[dict]]:
    bootstrap_sqlite_storage()
    offset = max(page - 1, 0) * limit
    with sqlite_connection() as conn:
        records = _load_filtered_records_from_conn(
            conn,
            filename=filename,
            ai_recommended_only=ai_recommended_only,
            keyword_recommended_only=keyword_recommended_only,
            sort_by=sort_by,
            sort_order=sort_order,
            include_hidden=include_hidden,
            include_sold=include_sold,
        )
    total = len(records)
    return total, records[offset: offset + limit]


async def load_all_result_records(
    filename: str,
    *,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    include_hidden: bool = False,
    include_sold: bool = True,
) -> list[dict]:
    return await asyncio.to_thread(
        _load_all_result_records_sync,
        filename,
        ai_recommended_only,
        keyword_recommended_only,
        sort_by,
        sort_order,
        include_hidden,
        include_sold,
    )


def _load_all_result_records_sync(
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    include_hidden: bool,
    include_sold: bool = True,
) -> list[dict]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        return _load_filtered_records_from_conn(
            conn,
            filename=filename,
            ai_recommended_only=ai_recommended_only,
            keyword_recommended_only=keyword_recommended_only,
            sort_by=sort_by,
            sort_order=sort_order,
            include_hidden=include_hidden,
            include_sold=include_sold,
        )


async def build_result_ndjson(filename: str) -> str:
    return await asyncio.to_thread(_build_result_ndjson_sync, filename)


def _build_result_ndjson_sync(filename: str) -> str:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT raw_json FROM result_items WHERE result_filename = ? ORDER BY id ASC",
            (filename,),
        ).fetchall()
    return "\n".join(str(row["raw_json"]) for row in rows)


async def load_result_summary(filename: str) -> dict | None:
    return await asyncio.to_thread(_load_result_summary_sync, filename)


def _load_result_summary_sync(filename: str) -> dict | None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        visible_records = _load_filtered_records_from_conn(
            conn,
            filename=filename,
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            include_hidden=False,
            include_sold=False,
        )
        if not visible_records:
            sold_records = _load_filtered_records_from_conn(
                conn,
                filename=filename,
                ai_recommended_only=False,
                keyword_recommended_only=False,
                sort_by="crawl_time",
                sort_order="desc",
                include_hidden=False,
                include_sold=True,
            )
            if not sold_records:
                return None
            return {
                "total_items": 0,
                "recommended_items": 0,
                "ai_recommended_items": 0,
                "keyword_recommended_items": 0,
                "latest_crawl_time": sold_records[0].get("爬取时间"),
                "latest_record": None,
                "latest_recommendation": None,
            }

    recommended_records = [
        record
        for record in visible_records
        if (record.get("ai_analysis", {}) or {}).get("is_recommended") is True
    ]
    ai_recommended_items = 0
    keyword_recommended_items = 0
    for record in recommended_records:
        source = (record.get("ai_analysis", {}) or {}).get("analysis_source")
        if source == "ai":
            ai_recommended_items += 1
        elif source == "keyword":
            keyword_recommended_items += 1

    return {
        "total_items": len(visible_records),
        "recommended_items": len(recommended_records),
        "ai_recommended_items": ai_recommended_items,
        "keyword_recommended_items": keyword_recommended_items,
        "latest_crawl_time": visible_records[0].get("爬取时间"),
        "latest_record": visible_records[0],
        "latest_recommendation": recommended_records[0] if recommended_records else None,
    }


async def update_item_status(filename: str, item_id: str, status: str) -> bool:
    if status not in VALID_ITEM_STATUSES:
        raise ValueError(f"status must be one of {VALID_ITEM_STATUSES}")
    return await asyncio.to_thread(_update_item_status_sync, filename, item_id, status)


def _update_item_status_sync(filename: str, item_id: str, status: str) -> bool:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        cursor = conn.execute(
            "UPDATE result_items SET status = ? WHERE result_filename = ? AND item_id = ?",
            (status, filename, item_id),
        )
        conn.commit()
        return cursor.rowcount > 0


async def load_items_for_status_check_async(
    filename: str,
    item_ids: list[str] | None = None,
    *,
    limit: int = 10,
) -> list[dict]:
    return await asyncio.to_thread(
        load_items_for_status_check,
        filename,
        item_ids,
        limit=limit,
    )


def load_items_for_status_check(
    filename: str,
    item_ids: list[str] | None = None,
    *,
    limit: int = 10,
) -> list[dict]:
    bootstrap_sqlite_storage()
    target_limit = max(0, int(limit))
    if target_limit <= 0:
        return []

    with sqlite_connection() as conn:
        if item_ids is not None:
            normalized_ids = [
                str(item_id).strip() for item_id in item_ids if str(item_id).strip()
            ]
            if not normalized_ids:
                return []
            placeholders = ", ".join("?" for _ in normalized_ids)
            rows = conn.execute(
                f"""
                SELECT id, crawl_time, item_id, link, status, raw_json
                FROM result_items
                WHERE result_filename = ? AND item_id IN ({placeholders})
                ORDER BY crawl_time DESC, id DESC
                """,
                (filename, *normalized_ids),
            ).fetchall()
            items: list[dict] = []
            seen_ids: set[str] = set()
            for row in rows:
                raw_record = json.loads(str(row["raw_json"]))
                product = raw_record.get("商品信息", {}) or {}
                resolved_id = str(row["item_id"] or product.get("商品ID") or "").strip()
                if resolved_id and resolved_id in seen_ids:
                    continue
                if resolved_id:
                    seen_ids.add(resolved_id)
                items.append(
                    {
                        "item_id": resolved_id,
                        "link": str(row["link"] or product.get("商品链接") or "").strip(),
                        "status": str(row["status"] or "active"),
                        "raw_record": raw_record,
                    }
                )
                if len(items) >= target_limit:
                    break
            return items

        blacklist_keywords = _load_blacklist_keywords_from_conn(conn, filename)
        rows = conn.execute(
            """
            SELECT id, crawl_time, item_id, link, status, raw_json
            FROM result_items
            WHERE result_filename = ? AND status = 'active'
            ORDER BY crawl_time DESC, id DESC
            """,
            (filename,),
        ).fetchall()
        unchecked: list[dict] = []
        checked: list[tuple[str, int, dict]] = []
        seen_ids: set[str] = set()
        for idx, row in enumerate(rows):
            raw_record = json.loads(str(row["raw_json"]))
            if blacklist_keywords and match_blacklist_keywords(raw_record, blacklist_keywords):
                continue
            product = raw_record.get("商品信息", {}) or {}
            resolved_id = str(row["item_id"] or product.get("商品ID") or "").strip()
            if resolved_id and resolved_id in seen_ids:
                continue
            if resolved_id:
                seen_ids.add(resolved_id)
            entry = {
                "item_id": resolved_id,
                "link": str(row["link"] or product.get("商品链接") or "").strip(),
                "status": str(row["status"] or "active"),
                "raw_record": raw_record,
            }
            checked_at = str(product.get("状态检查时间") or "").strip()
            if not checked_at:
                unchecked.append(entry)
            else:
                checked.append((checked_at, idx, entry))

        checked.sort(key=lambda pair: (pair[0], pair[1]))
        ordered = unchecked + [entry for _, _, entry in checked]
        return ordered[:target_limit]


async def update_item_detail_and_status_async(
    filename: str,
    item_id: str,
    *,
    status: str | None = None,
    detail_snapshot: ItemDetailSnapshot | None = None,
    checked_at: str | None = None,
    preserve_hidden: bool = True,
) -> dict | None:
    return await asyncio.to_thread(
        update_item_detail_and_status,
        filename,
        item_id,
        status=status,
        detail_snapshot=detail_snapshot,
        checked_at=checked_at,
        preserve_hidden=preserve_hidden,
    )


def update_item_detail_and_status(
    filename: str,
    item_id: str,
    *,
    status: str | None = None,
    detail_snapshot: ItemDetailSnapshot | None = None,
    checked_at: str | None = None,
    preserve_hidden: bool = True,
) -> dict | None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, status, title, raw_json
            FROM result_items
            WHERE result_filename = ? AND item_id = ?
            ORDER BY id DESC
            """,
            (filename, item_id),
        ).fetchall()
        if not rows:
            return None

        primary_old_status = str(rows[0]["status"] or "active")
        primary_new_status = primary_old_status
        primary_item_info: dict = {}
        any_changed = False
        any_description_updated = False

        for index, row in enumerate(rows):
            old_status = str(row["status"] or "active")
            raw_record = json.loads(str(row["raw_json"]))
            raw_item = raw_record.get("商品信息")
            old_item_data = raw_item if isinstance(raw_item, dict) else {}
            old_description = str(old_item_data.get("商品描述") or "").strip()

            detail_changed = False
            description_updated = False
            if detail_snapshot is not None:
                updated_item_data, detail_changed = apply_detail_to_item_data(
                    old_item_data,
                    detail_snapshot,
                    checked_at=checked_at,
                )
                raw_record["商品信息"] = updated_item_data
                new_description = str(updated_item_data.get("商品描述") or "").strip()
                description_updated = bool(new_description) and new_description != old_description

            if preserve_hidden and old_status == "hidden":
                new_status = old_status
            elif status is not None and status in VALID_ITEM_STATUSES:
                new_status = status
            else:
                new_status = old_status

            item_info = raw_record.get("商品信息") or {}
            new_title = item_info.get("商品标题") or row["title"]
            changed = (
                new_status != old_status
                or detail_changed
                or new_title != row["title"]
            )
            if changed:
                conn.execute(
                    """
                    UPDATE result_items
                    SET status = ?, title = ?, raw_json = ?
                    WHERE id = ?
                    """,
                    (
                        new_status,
                        new_title,
                        json.dumps(raw_record, ensure_ascii=False),
                        row["id"],
                    ),
                )
                any_changed = True
            if description_updated:
                any_description_updated = True
            if index == 0:
                primary_new_status = new_status
                primary_item_info = item_info if isinstance(item_info, dict) else {}

        if any_changed:
            conn.commit()

        return {
            "previous_status": primary_old_status,
            "status": primary_new_status,
            "description_updated": any_description_updated,
            "changed": any_changed,
            "item_info": primary_item_info,
        }


async def load_result_blacklist_keywords(filename: str) -> list[str]:
    return await asyncio.to_thread(_load_result_blacklist_keywords_sync, filename)


def _load_result_blacklist_keywords_sync(filename: str) -> list[str]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        return _load_blacklist_keywords_from_conn(conn, filename)


async def save_result_blacklist_keywords(filename: str, keywords: list[str]) -> list[str]:
    return await asyncio.to_thread(_save_result_blacklist_keywords_sync, filename, keywords)


def _save_result_blacklist_keywords_sync(filename: str, keywords: list[str]) -> list[str]:
    bootstrap_sqlite_storage()
    normalized_keywords = normalize_blacklist_keywords(keywords)
    now = datetime.now().isoformat()
    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT INTO result_blacklist_rules (
                result_filename, blacklist_keywords_json, updated_at
            ) VALUES (?, ?, ?)
            ON CONFLICT(result_filename) DO UPDATE SET
                blacklist_keywords_json = excluded.blacklist_keywords_json,
                updated_at = excluded.updated_at
            """,
            (filename, json.dumps(normalized_keywords, ensure_ascii=False), now),
        )
        conn.commit()
    return normalized_keywords


def load_visible_result_item_ids(filename: str) -> set[str]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        visible_records = _load_filtered_records_from_conn(
            conn,
            filename=filename,
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            include_hidden=False,
            include_sold=False,
        )
    item_ids: set[str] = set()
    for record in visible_records:
        product = record.get("商品信息", {}) or {}
        item_id = str(product.get("商品ID") or "").strip()
        if item_id:
            item_ids.add(item_id)
    return item_ids
