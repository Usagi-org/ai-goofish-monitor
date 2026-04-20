"""
结果数据的 SQLite 读写服务。
"""
from __future__ import annotations

import asyncio
import hashlib
import json

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.price_history_service import parse_price_value


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


def _parse_raw_record(raw_json: str) -> dict:
    return json.loads(raw_json)


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
    return f"{column} {direction}, id {direction}"


async def save_result_record(record: dict, keyword: str) -> bool:
    return await asyncio.to_thread(_save_result_record_sync, record, keyword)


def _save_result_record_sync(record: dict, keyword: str) -> bool:
    bootstrap_sqlite_storage()
    item = record.get("商品信息", {}) or {}
    analysis = record.get("ai_analysis", {}) or {}
    link = str(item.get("商品链接") or "")
    link_unique_key = _get_link_unique_key(link) if link else _fallback_unique_key(record, item)
    keyword_hit_count = analysis.get("keyword_hit_count", 0)
    try:
        keyword_hit_count = int(keyword_hit_count)
    except (TypeError, ValueError):
        keyword_hit_count = 0

    with sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO result_items (
                result_filename, keyword, task_name, crawl_time, publish_time, price,
                price_display, item_id, title, link, link_unique_key, seller_nickname,
                is_recommended, analysis_source, keyword_hit_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                build_result_filename(keyword),
                record.get("搜索关键字", keyword),
                record.get("任务名称", ""),
                record.get("爬取时间", ""),
                item.get("发布时间"),
                parse_price_value(item.get("当前售价")),
                item.get("当前售价"),
                item.get("商品ID"),
                item.get("商品标题"),
                link,
                link_unique_key,
                (record.get("卖家信息", {}) or {}).get("卖家昵称") or item.get("卖家昵称"),
                1 if analysis.get("is_recommended") else 0,
                analysis.get("analysis_source"),
                keyword_hit_count,
                json.dumps(record, ensure_ascii=False),
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
    )


def _query_result_records_sync(
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
    page: int,
    limit: int,
) -> tuple[int, list[dict]]:
    bootstrap_sqlite_storage()
    where_clause, params = _build_query_conditions(
        filename=filename,
        ai_recommended_only=ai_recommended_only,
        keyword_recommended_only=keyword_recommended_only,
    )
    offset = max(page - 1, 0) * limit
    order_clause = _sort_expression(sort_by, sort_order)
    with sqlite_connection() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(1) AS total FROM result_items WHERE {where_clause}",
            tuple(params),
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT raw_json
            FROM result_items
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            tuple(params + [limit, offset]),
        ).fetchall()
    total = int(total_row["total"]) if total_row else 0
    return total, [_parse_raw_record(str(row["raw_json"])) for row in rows]


async def load_all_result_records(
    filename: str,
    *,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
) -> list[dict]:
    return await asyncio.to_thread(
        _load_all_result_records_sync,
        filename,
        ai_recommended_only,
        keyword_recommended_only,
        sort_by,
        sort_order,
    )


def _load_all_result_records_sync(
    filename: str,
    ai_recommended_only: bool,
    keyword_recommended_only: bool,
    sort_by: str,
    sort_order: str,
) -> list[dict]:
    bootstrap_sqlite_storage()
    where_clause, params = _build_query_conditions(
        filename=filename,
        ai_recommended_only=ai_recommended_only,
        keyword_recommended_only=keyword_recommended_only,
    )
    order_clause = _sort_expression(sort_by, sort_order)
    with sqlite_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT raw_json
            FROM result_items
            WHERE {where_clause}
            ORDER BY {order_clause}
            """,
            tuple(params),
        ).fetchall()
    return [_parse_raw_record(str(row["raw_json"])) for row in rows]


async def build_result_ndjson(filename: str) -> str:
    records = await load_all_result_records(
        filename,
        ai_recommended_only=False,
        keyword_recommended_only=False,
        sort_by="crawl_time",
        sort_order="asc",
    )
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records)


async def load_result_summary(filename: str) -> dict | None:
    return await asyncio.to_thread(_load_result_summary_sync, filename)


def _load_result_summary_sync(filename: str) -> dict | None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        aggregate_row = conn.execute(
            """
            SELECT
                COUNT(1) AS total_items,
                SUM(CASE WHEN is_recommended = 1 THEN 1 ELSE 0 END) AS recommended_items,
                SUM(CASE WHEN is_recommended = 1 AND analysis_source = 'ai' THEN 1 ELSE 0 END) AS ai_recommended_items,
                SUM(CASE WHEN is_recommended = 1 AND analysis_source = 'keyword' THEN 1 ELSE 0 END) AS keyword_recommended_items,
                MAX(crawl_time) AS latest_crawl_time
            FROM result_items
            WHERE result_filename = ?
            """,
            (filename,),
        ).fetchone()
        if aggregate_row is None or int(aggregate_row["total_items"] or 0) == 0:
            return None

        latest_record = conn.execute(
            """
            SELECT raw_json FROM result_items
            WHERE result_filename = ?
            ORDER BY crawl_time DESC, id DESC
            LIMIT 1
            """,
            (filename,),
        ).fetchone()
        latest_recommendation = conn.execute(
            """
            SELECT raw_json FROM result_items
            WHERE result_filename = ? AND is_recommended = 1
            ORDER BY crawl_time DESC, id DESC
            LIMIT 1
            """,
            (filename,),
        ).fetchone()
    return {
        "total_items": int(aggregate_row["total_items"] or 0),
        "recommended_items": int(aggregate_row["recommended_items"] or 0),
        "ai_recommended_items": int(aggregate_row["ai_recommended_items"] or 0),
        "keyword_recommended_items": int(aggregate_row["keyword_recommended_items"] or 0),
        "latest_crawl_time": aggregate_row["latest_crawl_time"],
        "latest_record": (
            _parse_raw_record(str(latest_record["raw_json"])) if latest_record else None
        ),
        "latest_recommendation": (
            _parse_raw_record(str(latest_recommendation["raw_json"]))
            if latest_recommendation
            else None
        ),
    }
