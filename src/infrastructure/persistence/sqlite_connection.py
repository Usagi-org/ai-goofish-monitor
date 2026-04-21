"""
SQLite 连接与 schema 初始化。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH


BUSY_TIMEOUT_MS = 5000

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        task_name TEXT NOT NULL,
        task_type TEXT NOT NULL DEFAULT 'keyword',
        enabled INTEGER NOT NULL,
        keyword TEXT,
        item_id_list_json TEXT NOT NULL DEFAULT '[]',
        description TEXT,
        analyze_images INTEGER NOT NULL,
        max_pages INTEGER NOT NULL,
        personal_only INTEGER NOT NULL,
        min_price TEXT,
        max_price TEXT,
        cron TEXT,
        ai_prompt_base_file TEXT NOT NULL,
        ai_prompt_criteria_file TEXT NOT NULL,
        account_state_file TEXT,
        account_strategy TEXT NOT NULL,
        free_shipping INTEGER NOT NULL,
        new_publish_option TEXT,
        region TEXT,
        decision_mode TEXT NOT NULL,
        keyword_rules_json TEXT NOT NULL,
        is_running INTEGER NOT NULL,
        is_paused INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS result_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_filename TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        crawl_time TEXT NOT NULL,
        publish_time TEXT,
        price REAL,
        price_display TEXT,
        item_id TEXT,
        title TEXT,
        link TEXT,
        link_unique_key TEXT NOT NULL,
        seller_nickname TEXT,
        is_recommended INTEGER NOT NULL,
        analysis_source TEXT,
        keyword_hit_count INTEGER NOT NULL,
        raw_json TEXT NOT NULL,
        UNIQUE(result_filename, link_unique_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword_slug TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        snapshot_day TEXT NOT NULL,
        run_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT,
        price REAL NOT NULL,
        price_display TEXT,
        tags_json TEXT NOT NULL,
        region TEXT,
        seller TEXT,
        publish_time TEXT,
        link TEXT,
        UNIQUE(keyword_slug, run_id, item_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks(task_name)",
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_crawl
    ON result_items(result_filename, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_publish
    ON result_items(result_filename, publish_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_price
    ON result_items(result_filename, price DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_recommended
    ON result_items(result_filename, is_recommended, analysis_source, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_time
    ON price_snapshots(keyword_slug, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_item_time
    ON price_snapshots(keyword_slug, item_id, snapshot_time DESC)
    """,
    # ===== 新增表：卖家信息表 =====
    """
    CREATE TABLE IF NOT EXISTS seller_info (
        seller_id TEXT PRIMARY KEY,
        seller_nickname TEXT,
        seller_avatar TEXT,
        zhima_credit TEXT,
        registration_days INTEGER,
        good_rate TEXT,
        total_items INTEGER,
        total_ratings INTEGER,
        last_updated TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_seller_info_nickname ON seller_info(seller_nickname)
    """,
    # ===== 新增表：商品指标历史记录表 =====
    """
    CREATE TABLE IF NOT EXISTS item_metrics_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        title TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        price REAL,
        price_display TEXT,
        want_count INTEGER,
        browse_count INTEGER,
        seller_id TEXT,
        link TEXT,
        UNIQUE(item_id, snapshot_time)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_metrics_item_time ON item_metrics_history(item_id, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_metrics_seller_time ON item_metrics_history(seller_id, snapshot_time DESC)
    """,
    # ===== 新增表：卖家黑名单/白名单 =====
    """
    CREATE TABLE IF NOT EXISTS seller_list (
        seller_id TEXT PRIMARY KEY,
        list_type TEXT NOT NULL CHECK(list_type IN ('blacklist', 'whitelist')),
        reason TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_seller_list_type ON seller_list(list_type)
    """,
    # ===== 新增表：商品 ID 搜索历史 =====
    """
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_type TEXT NOT NULL DEFAULT 'item_id',
        search_value TEXT NOT NULL,
        result_json TEXT,
        searched_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_search_history_type_time ON search_history(search_type, searched_at DESC)
    """,
    # ===== 新增表：应用设置表 =====
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(key)
    """,
)


def get_database_path() -> str:
    return os.getenv("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH)


def _prepare_database_file(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def init_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    # 初始化 AI 开关默认值
    conn.execute("""
        INSERT OR IGNORE INTO app_settings (key, value, updated_at)
        VALUES ('ai_enabled', 'true', datetime('now'))
    """)
    conn.commit()


@contextmanager
def sqlite_connection(
    db_path: str | None = None,
) -> Iterator[sqlite3.Connection]:
    path = db_path or get_database_path()
    _prepare_database_file(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        yield conn
    finally:
        conn.close()
