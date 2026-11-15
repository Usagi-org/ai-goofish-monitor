"""
结果数据的 SQLite 读写服务。
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import os
from datetime import datetime

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.price_history_service import parse_price_value
from src.services.result_blacklist_service import (
    match_blacklist_keywords,
    normalize_blacklist_keywords,
)


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
    return f"(CASE WHEN status = 'active' THEN 0 ELSE 1 END), {column} {direction}, id {direction}"


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
    matched_keywords = match_blacklist_keywords(record, blacklist_keywords)
    hidden_reason = None
    if status == "expired":
        hidden_reason = "expired"
    elif status and status != "active":
        hidden_reason = "manual"
    elif matched_keywords:
        hidden_reason = "rule"

    record["_status"] = status or "active"
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
        if include_hidden or _is_record_visible(decorated):
            records.append(decorated)
    return records


DEFAULT_PRICE_DROP_MIN_AMOUNT = 10.0
DEFAULT_PRICE_DROP_MIN_RATIO = 0.02
AI_SKIPPED_MISSING_PROMPT_REASON = "任务未配置AI prompt，跳过分析。"


def _coerce_non_negative_finite(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _resolve_threshold_float(
    explicit_value: float | None,
    *,
    env_name: str,
    default: float,
) -> float:
    if explicit_value is not None:
        coerced = _coerce_non_negative_finite(explicit_value)
        return coerced if coerced is not None else default
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return default
    coerced = _coerce_non_negative_finite(raw.strip())
    return coerced if coerced is not None else default


def _parse_positive_price(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = parse_price_value(value)
    except (TypeError, ValueError):
        return None
    if parsed is None or not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _is_ai_analysis_failure(analysis: object) -> bool:
    if not isinstance(analysis, dict):
        return True
    if bool(analysis.get("error")):
        return True
    reason = str(analysis.get("reason") or "").strip()
    if (
        reason == AI_SKIPPED_MISSING_PROMPT_REASON
        or reason == "AI analysis returned None after retries."
        or reason.startswith("AI分析异常:")
    ):
        return True
    return False


def evaluate_price_drop(
    previous_state: dict | None,
    current_price_raw,
    *,
    min_amount: float | None = None,
    min_ratio: float | None = None,
) -> dict | None:
    if not previous_state or not isinstance(previous_state, dict):
        return None
    if (previous_state.get("status") or "active") != "active":
        return None

    previous_price = _parse_positive_price(previous_state.get("price"))
    current_price = _parse_positive_price(current_price_raw)
    if previous_price is None or current_price is None:
        return None
    if current_price >= previous_price:
        return None

    effective_min_amount = _resolve_threshold_float(
        min_amount,
        env_name="PRICE_DROP_MIN_AMOUNT",
        default=DEFAULT_PRICE_DROP_MIN_AMOUNT,
    )
    effective_min_ratio = _resolve_threshold_float(
        min_ratio,
        env_name="PRICE_DROP_MIN_RATIO",
        default=DEFAULT_PRICE_DROP_MIN_RATIO,
    )

    drop_amount = round(previous_price - current_price, 2)
    drop_ratio = round(drop_amount / previous_price, 9)
    if drop_amount < effective_min_amount or drop_ratio < effective_min_ratio:
        return None

    return {
        "previous_price": previous_price,
        "current_price": current_price,
        "drop_amount": drop_amount,
        "drop_ratio": round(drop_ratio, 4),
    }


async def save_result_record(record: dict, keyword: str) -> bool:
    return await asyncio.to_thread(_save_result_record_sync, record, keyword)


def _extract_old_item_fields(raw_json_text: object) -> dict:
    if not raw_json_text:
        return {}
    try:
        old_record = json.loads(str(raw_json_text))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if isinstance(old_record, dict) and isinstance(old_record.get("商品信息"), dict):
        return old_record["商品信息"]
    return {}


def _save_result_record_sync(record: dict, keyword: str) -> bool:
    bootstrap_sqlite_storage()
    record_to_save = copy.deepcopy(record)
    raw_item = record_to_save.get("商品信息")
    item = raw_item if isinstance(raw_item, dict) else {}
    record_to_save["商品信息"] = item
    analysis = record_to_save.get("ai_analysis", {}) or {}
    link = str(item.get("商品链接") or "")
    link_unique_key = _get_link_unique_key(link) if link else _fallback_unique_key(record_to_save, item)
    result_filename = build_result_filename(keyword)
    keyword_hit_count = analysis.get("keyword_hit_count", 0)
    try:
        keyword_hit_count = int(keyword_hit_count)
    except (TypeError, ValueError):
        keyword_hit_count = 0

    with sqlite_connection() as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                """
                SELECT id, price, status, publish_time, item_id, seller_nickname,
                       is_recommended, analysis_source, raw_json
                FROM result_items
                WHERE result_filename = ? AND link_unique_key = ?
                """,
                (result_filename, link_unique_key),
            ).fetchone()

            if existing is None:
                if record_to_save.get("降价信息") is not None:
                    conn.execute("ROLLBACK")
                    return False
                insert_price = _parse_positive_price(item.get("当前售价"))

                conn.execute(
                    """
                    INSERT INTO result_items (
                        result_filename, keyword, task_name, crawl_time, publish_time, price,
                        price_display, item_id, title, link, link_unique_key, seller_nickname,
                        is_recommended, analysis_source, keyword_hit_count, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_filename,
                        record_to_save.get("搜索关键字", keyword),
                        record_to_save.get("任务名称", ""),
                        record_to_save.get("爬取时间", ""),
                        item.get("发布时间"),
                        insert_price,
                        item.get("当前售价"),
                        item.get("商品ID"),
                        item.get("商品标题"),
                        link,
                        link_unique_key,
                        (record_to_save.get("卖家信息", {}) or {}).get("卖家昵称") or item.get("卖家昵称"),
                        1 if analysis.get("is_recommended") else 0,
                        analysis.get("analysis_source"),
                        keyword_hit_count,
                        json.dumps(record_to_save, ensure_ascii=False),
                    ),
                )
                conn.execute("COMMIT")
                return True

            if not isinstance(record_to_save.get("降价信息"), dict):
                conn.execute("ROLLBACK")
                return False

            if _is_ai_analysis_failure(analysis):
                conn.execute("ROLLBACK")
                return False

            new_price = _parse_positive_price(item.get("当前售价"))
            if new_price is None:
                conn.execute("ROLLBACK")
                return False

            committed_drop = evaluate_price_drop(
                {"price": existing["price"], "status": existing["status"]},
                new_price,
            )
            if committed_drop is None:
                conn.execute("ROLLBACK")
                return False

            record_to_save["降价信息"] = committed_drop
            record["降价信息"] = committed_drop
            old_item = _extract_old_item_fields(existing["raw_json"])

            publish_time = item.get("发布时间")
            if publish_time in (None, "", "未知时间"):
                preserved_publish_time = existing["publish_time"] or old_item.get("发布时间")
                if preserved_publish_time:
                    publish_time = preserved_publish_time
                    item["发布时间"] = preserved_publish_time

            item_id = item.get("商品ID")
            if item_id in (None, "", "未知ID"):
                preserved_item_id = existing["item_id"] or old_item.get("商品ID")
                if preserved_item_id:
                    item_id = preserved_item_id
                    item["商品ID"] = preserved_item_id

            seller_nickname = (
                (record_to_save.get("卖家信息", {}) or {}).get("卖家昵称")
                or item.get("卖家昵称")
                or existing["seller_nickname"]
            )

            cursor = conn.execute(
                """
                UPDATE result_items
                SET crawl_time = ?,
                    task_name = ?,
                    publish_time = ?,
                    price = ?,
                    price_display = ?,
                    item_id = ?,
                    title = ?,
                    link = ?,
                    seller_nickname = ?,
                    is_recommended = ?,
                    analysis_source = ?,
                    keyword_hit_count = ?,
                    raw_json = ?
                WHERE id = ? AND status = 'active'
                """,
                (
                    record_to_save.get("爬取时间", ""),
                    record_to_save.get("任务名称", ""),
                    publish_time,
                    new_price,
                    item.get("当前售价"),
                    item_id,
                    item.get("商品标题"),
                    link,
                    seller_nickname,
                    1 if analysis.get("is_recommended") else 0,
                    analysis.get("analysis_source"),
                    keyword_hit_count,
                    json.dumps(record_to_save, ensure_ascii=False),
                    existing["id"],
                ),
            )
            if int(cursor.rowcount or 0) <= 0:
                conn.execute("ROLLBACK")
                return False
            conn.execute("COMMIT")
            return True
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def load_processed_link_keys(keyword: str) -> set[str]:
    bootstrap_sqlite_storage()
    filename = build_result_filename(keyword)
    with sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT link_unique_key FROM result_items WHERE result_filename = ?",
            (filename,),
        ).fetchall()
    return {str(row["link_unique_key"]) for row in rows if row["link_unique_key"]}


def load_processed_item_states(keyword: str) -> dict[str, dict]:
    bootstrap_sqlite_storage()
    filename = build_result_filename(keyword)
    with sqlite_connection() as conn:
        rows = conn.execute(
            """
            SELECT link_unique_key, price, status, is_recommended
            FROM result_items
            WHERE result_filename = ?
            """,
            (filename,),
        ).fetchall()
    return {
        str(row["link_unique_key"]): {
            "price": row["price"],
            "status": row["status"] or "active",
            "is_recommended": bool(row["is_recommended"]),
        }
        for row in rows
        if row["link_unique_key"]
    }


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
) -> list[dict]:
    return await asyncio.to_thread(
        _load_all_result_records_sync,
        filename,
        ai_recommended_only,
        keyword_recommended_only,
        sort_by,
        sort_order,
        include_hidden,
    )


def _load_all_result_records_sync(
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    include_hidden: bool,
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
        )
    if not visible_records:
        return None

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
    valid = {"active", "hidden", "expired"}
    if status not in valid:
        raise ValueError(f"status must be one of {valid}")
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
        )
    item_ids: set[str] = set()
    for record in visible_records:
        product = record.get("商品信息", {}) or {}
        item_id = str(product.get("商品ID") or "").strip()
        if item_id:
            item_ids.add(item_id)
    return item_ids
