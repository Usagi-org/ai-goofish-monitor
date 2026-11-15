"""
SQLite 连接与 schema 初始化。
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH


BUSY_TIMEOUT_MS = 5000
_DB_LOCKS_GUARD = threading.Lock()
_DB_LOCKS: dict[str, threading.Lock] = {}


def _get_db_lock(path: str) -> threading.Lock:
    key = os.path.abspath(path)
    with _DB_LOCKS_GUARD:
        lock = _DB_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _DB_LOCKS[key] = lock
        return lock


def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


def _run_with_busy_retry(fn, *, timeout_ms: int = BUSY_TIMEOUT_MS):
    deadline = time.monotonic() + max(0.1, timeout_ms / 1000.0)
    attempt = 0
    while True:
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(min(0.05, 0.002 * (attempt + 1)))
            attempt += 1

RESULT_TASK_EXCLUSIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS result_task_exclusions (
        result_id INTEGER NOT NULL REFERENCES result_items(id) ON DELETE CASCADE,
        task_name TEXT NOT NULL,
        observed_price_key TEXT NOT NULL,
        rules_key TEXT NOT NULL,
        PRIMARY KEY (result_id, task_name)
    )
    """

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
        enabled INTEGER NOT NULL,
        keyword TEXT NOT NULL,
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
        exclude_keywords_json TEXT NOT NULL DEFAULT '[]',
        is_running INTEGER NOT NULL
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
        status TEXT NOT NULL DEFAULT 'active',
        raw_json TEXT NOT NULL,
        UNIQUE(result_filename, link_unique_key)
    )
    """,
    RESULT_TASK_EXCLUSIONS_SCHEMA,
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
    """
    CREATE TABLE IF NOT EXISTS result_blacklist_rules (
        result_filename TEXT PRIMARY KEY,
        blacklist_keywords_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
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
)


def get_database_path() -> str:
    return os.getenv("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH)


def _prepare_database_file(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection, path: str | None = None) -> None:
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    if path:
        with _get_db_lock(path):
            _run_with_busy_retry(lambda: conn.execute("PRAGMA journal_mode=WAL"))
    else:
        _run_with_busy_retry(lambda: conn.execute("PRAGMA journal_mode=WAL"))


def _all_migrations_done(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute(
            """
            SELECT key FROM app_metadata
            WHERE key IN ('migration:result_items_status', 'migration:tasks_exclude_keywords',
                          'migration:exclusion_price_key')
              AND value = 'done'
            """
        ).fetchall()
        return len(rows) == 3
    except sqlite3.OperationalError:
        return False


def init_schema(conn: sqlite3.Connection) -> None:
    def _do_init() -> None:
        try:
            if not _all_migrations_done(conn) and not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            _migrate_result_items_status(conn)
            _migrate_tasks_exclude_keywords(conn)
            _migrate_exclusion_price_key(conn)
            if conn.in_transaction:
                conn.commit()
        except sqlite3.OperationalError:
            if conn.in_transaction:
                conn.rollback()
            raise

    _run_with_busy_retry(_do_init)


def _migrate_exclusion_price_key(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM app_metadata WHERE key = 'migration:exclusion_price_key'").fetchone():
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(result_task_exclusions)")}
    if "observed_price" in columns:
        conn.execute("ALTER TABLE result_task_exclusions RENAME TO result_task_exclusions_legacy")
        conn.execute(RESULT_TASK_EXCLUSIONS_SCHEMA)
        conn.execute(
            """
            INSERT INTO result_task_exclusions(result_id, task_name, observed_price_key, rules_key)
            SELECT result_id, task_name, 'n:' || printf('%.2f', observed_price), rules_key
            FROM result_task_exclusions_legacy
            """
        )
        conn.execute("DROP TABLE result_task_exclusions_legacy")
    conn.execute("INSERT INTO app_metadata(key, value) VALUES ('migration:exclusion_price_key', 'done')")


def _migrate_result_items_status(conn: sqlite3.Connection) -> None:
    """为 result_items 表添加 status 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:result_items_status'"
    ).fetchone()
    if row is not None:
        return
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:result_items_status'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(result_items)").fetchall()]
    if "status" not in cols:
        try:
            conn.execute(
                "ALTER TABLE result_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:result_items_status', 'done')"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_results_filename_status_crawl"
        " ON result_items(result_filename, status, crawl_time DESC)"
    )


def _migrate_tasks_exclude_keywords(conn: sqlite3.Connection) -> None:
    """为 tasks 表添加 exclude_keywords_json 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_exclude_keywords'"
    ).fetchone()
    if row is not None:
        return
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_exclude_keywords'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "exclude_keywords_json" not in cols:
        try:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN exclude_keywords_json TEXT NOT NULL DEFAULT '[]'"
            )
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_exclude_keywords', 'done')"
    )


@contextmanager
def sqlite_connection(
    db_path: str | None = None,
) -> Iterator[sqlite3.Connection]:
    path = db_path or get_database_path()
    _prepare_database_file(path)
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn, path)
        yield conn
    finally:
        conn.close()
