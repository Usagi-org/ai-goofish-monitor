"""
基于 SQLite 的任务仓储实现。
"""
from __future__ import annotations

import asyncio
import json
from contextlib import nullcontext
from typing import List, Optional

from src.domain.models.task import Task, TaskUpdate
from src.domain.repositories.task_repository import (
    RunningTaskRename, TaskChanged, TaskCommitScope, TaskRepository, ensure_available_task_name, resolve_task_write,
)
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


def _row_to_task(row) -> Task:
    payload = dict(row)
    payload["enabled"] = bool(payload["enabled"])
    payload["analyze_images"] = bool(payload["analyze_images"])
    payload["personal_only"] = bool(payload["personal_only"])
    payload["free_shipping"] = bool(payload["free_shipping"])
    payload["is_running"] = bool(payload["is_running"])
    payload["keyword_rules"] = json.loads(payload.pop("keyword_rules_json") or "[]")
    return Task(**payload)


def find_task_by_name_sync(task_name: str) -> Task | None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_name = ? ORDER BY id ASC LIMIT 1",
            (task_name,),
        ).fetchone()
    return _row_to_task(row) if row else None


class SqliteTaskRepository(TaskRepository):
    """基于 SQLite 的任务仓储"""

    def __init__(
        self,
        db_path: str | None = None,
        legacy_config_file: str | None = "config.json",
    ):
        self.db_path = db_path
        self.legacy_config_file = legacy_config_file

    async def find_all(self) -> List[Task]:
        return await asyncio.to_thread(self._find_all_sync)

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        return await asyncio.to_thread(self._find_by_id_sync, task_id)

    async def save(self, task: Task, *, on_commit: TaskCommitScope = nullcontext) -> Task:
        return await asyncio.to_thread(self._save_sync, task.id, task, None, on_commit)

    async def update(
        self, task_id: int, change: TaskUpdate, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> Task:
        return await asyncio.to_thread(self._save_sync, task_id, change, expected_name, on_commit)

    async def delete(
        self, task_id: int, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> bool:
        return await asyncio.to_thread(self._delete_sync, task_id, expected_name, on_commit)

    def _find_all_sync(self) -> List[Task]:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        return [_row_to_task(row) for row in rows]

    def _find_by_id_sync(self, task_id: int) -> Optional[Task]:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def _save_sync(
        self, task_id: int | None, change: Task | TaskUpdate, expected_name: str | None, on_commit: TaskCommitScope,
    ) -> Task:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            current = _row_to_task(row) if row is not None else None
            task = resolve_task_write(task_id, current, change, expected_name)
            if current is None or current.task_name != task.task_name:
                if current is not None and current.is_running:
                    raise RunningTaskRename()
                rows = conn.execute("SELECT task_name FROM tasks WHERE id IS NOT ?", (task_id,))
                ensure_available_task_name(task, (row["task_name"] for row in rows))
            if task_id is None:
                task_id = self._next_task_id(conn)
            payload = self._task_values(task.model_copy(update={"id": task_id}))
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, task_name, enabled, keyword, description, analyze_images,
                    max_pages, personal_only, min_price, max_price, cron,
                    ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
                    account_strategy, free_shipping, new_publish_option, region,
                    decision_mode, keyword_rules_json, is_running
                ) VALUES (
                    :id, :task_name, :enabled, :keyword, :description, :analyze_images,
                    :max_pages, :personal_only, :min_price, :max_price, :cron,
                    :ai_prompt_base_file, :ai_prompt_criteria_file, :account_state_file,
                    :account_strategy, :free_shipping, :new_publish_option, :region,
                    :decision_mode, :keyword_rules_json, :is_running
                )
                """,
                payload,
            )
            with on_commit():
                conn.commit()
        return task.model_copy(update={"id": task_id})

    def _delete_sync(self, task_id: int, expected_name: str | None, on_commit: TaskCommitScope) -> bool:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT task_name FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return False
            if expected_name is not None and row["task_name"] != expected_name:
                raise TaskChanged("任务名称已更改，请刷新后重试")
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            # Keep stale requests from addressing a new task after deleting the largest id.
            conn.execute(
                """INSERT INTO app_metadata(key, value) VALUES ('last_deleted_task_id', ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value
                   WHERE CAST(app_metadata.value AS INTEGER) < CAST(excluded.value AS INTEGER)""",
                (str(task_id),),
            )
            with on_commit():
                conn.commit()
        return True

    def _next_task_id(self, conn) -> int:
        row = conn.execute(
            """SELECT MAX(COALESCE((SELECT MAX(id) FROM tasks), -1),
                          COALESCE((SELECT CAST(value AS INTEGER) FROM app_metadata
                                    WHERE key = 'last_deleted_task_id'), -1)) AS max_id"""
        ).fetchone()
        return int(row["max_id"]) + 1

    def _task_values(self, task: Task) -> dict:
        values = task.model_dump()
        values["enabled"] = int(task.enabled)
        values["analyze_images"] = int(task.analyze_images)
        values["personal_only"] = int(task.personal_only)
        values["free_shipping"] = int(task.free_shipping)
        values["is_running"] = int(task.is_running)
        values["keyword_rules_json"] = json.dumps(task.keyword_rules or [], ensure_ascii=False)
        values.pop("keyword_rules", None)
        return values
