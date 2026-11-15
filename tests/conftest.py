import json
from contextlib import asynccontextmanager, contextmanager
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Add repository root to the path so package imports work consistently
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.api import dependencies as deps
from src.api.routes import tasks
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository
from src.services.process_service import TaskStartResult
from src.services.task_service import TaskService
from src.services.task_generation_service import TaskGenerationService


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def load_json_fixture(fixtures_dir):
    def _load(name: str):
        return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture()
def sample_task_payload():
    return {
        "task_name": "Sony A7M4",
        "enabled": True,
        "keyword": "sony a7m4",
        "description": "Good condition body with accessories",
        "analyze_images": True,
        "max_pages": 2,
        "personal_only": True,
        "min_price": "8000",
        "max_price": "16000",
        "cron": "*/15 * * * *",
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": "prompts/sony_a7m4_criteria.txt",
        "decision_mode": "ai",
        "keyword_rules": [],
    }


class FakeProcessService:
    def __init__(self):
        self.started = []
        self.stopped = []
        self.reindexed = []
        self.unpaused = []
        self.failure_guard_states = {}
        self.running_ids = set()
        self.spawn_error_ids = set()
        self._on_started = None
        self._on_stopped = None

    def set_lifecycle_hooks(self, *, on_started=None, on_stopped=None):
        self._on_started = on_started
        self._on_stopped = on_stopped

    def load_failure_guard_snapshot(self) -> dict:
        return {"version": 1, "tasks": dict(self.failure_guard_states)}

    def _build_guard_state(self, task_name: str, snapshot=None) -> dict:
        default_state = {
            "paused": False,
            "paused_until": None,
            "consecutive_failures": 0,
            "threshold": 3,
            "reason": None,
            "last_failure_at": None,
        }
        source = (
            snapshot.get("tasks", {})
            if isinstance(snapshot, dict) and isinstance(snapshot.get("tasks"), dict)
            else self.failure_guard_states
        )
        state = source.get(task_name)
        if not isinstance(state, dict):
            return default_state
        return {**default_state, **state}

    def get_failure_guard_state(self, task_name: str, *, task=None, snapshot=None) -> dict:
        _ = task
        return self._build_guard_state(task_name, snapshot=snapshot)

    def unpause_task(self, task_name: str) -> None:
        self.unpaused.append(task_name)
        self.failure_guard_states.pop(task_name, None)

    def is_running(self, task_id: int) -> bool:
        return task_id in self.running_ids

    @contextmanager
    def rename_task_guard(self, task_id: int, old_name: str, new_name: str, *, keep_old: bool = False):
        if old_name in self.failure_guard_states:
            self.failure_guard_states[new_name] = dict(self.failure_guard_states[old_name])
            if not keep_old:
                self.failure_guard_states.pop(old_name)
        yield

    @asynccontextmanager
    async def stop_for_deletion(self, task_id: int, task_name: str, *, keep_old: bool):
        await self.stop_task(task_id)

        @contextmanager
        def clear_guard():
            if not keep_old:
                self.unpause_task(task_name)
            yield

        yield clear_guard

    async def start_task_manual(
        self,
        task,
        *,
        force_unpause: bool = False,
    ) -> TaskStartResult:
        task_id = task.id
        task_name = task.task_name
        if force_unpause:
            self.unpause_task(task_name)
        if task_id in self.running_ids:
            return TaskStartResult(status="already_running")
        guard_state = self._build_guard_state(task_name)
        if guard_state.get("paused"):
            return TaskStartResult(
                status="paused",
                reason=guard_state.get("reason"),
                paused_until=guard_state.get("paused_until"),
                consecutive_failures=int(guard_state.get("consecutive_failures") or 0),
            )
        if task_id in self.spawn_error_ids:
            return TaskStartResult(status="spawn_error", reason="spawn error")
        self.started.append((task_id, task_name))
        self.running_ids.add(task_id)
        if self._on_started:
            await self._on_started(task_id)
        return TaskStartResult(status="started")

    async def start_task(
        self,
        task_id: int,
        task_name: str,
        *,
        force_unpause: bool = False,
    ) -> bool:
        if force_unpause:
            self.unpause_task(task_name)
        elif self._build_guard_state(task_name).get("paused"):
            return False
        if task_id in self.running_ids or task_id in self.spawn_error_ids:
            return False
        self.started.append((task_id, task_name))
        self.running_ids.add(task_id)
        if self._on_started:
            await self._on_started(task_id)
        return True

    async def stop_task(self, task_id: int):
        self.stopped.append(task_id)
        self.running_ids.discard(task_id)
        if self._on_stopped:
            await self._on_stopped(task_id)

    def reindex_after_delete(self, deleted_task_id: int):
        self.reindexed.append(deleted_task_id)


class FakeSchedulerService:
    def __init__(self):
        self.reload_calls = 0
        self.next_run_times = {}

    async def reload_jobs(self, tasks):
        self.reload_calls += 1
        base = datetime(2026, 3, 19, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.next_run_times = {
            task.id: base + timedelta(minutes=(index + 1) * 15)
            for index, task in enumerate(tasks)
            if task.id is not None and task.enabled and task.cron
        }

    def get_next_run_time(self, task_id: int):
        return self.next_run_times.get(task_id)


@pytest.fixture()
def api_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "config.json"
    config_file.write_text("[]", encoding="utf-8")
    db_path = tmp_path / "app.sqlite3"
    monkeypatch.setenv("APP_DATABASE_FILE", str(db_path))
    bootstrap_sqlite_storage(str(db_path), legacy_config_file=None)

    repository = SqliteTaskRepository(
        db_path=str(db_path),
        legacy_config_file=None,
    )
    task_service = TaskService(repository)
    process_service = FakeProcessService()
    scheduler_service = FakeSchedulerService()
    task_generation_service = TaskGenerationService()

    app = FastAPI()
    app.include_router(tasks.router)

    def override_get_task_service():
        return task_service

    def override_get_process_service():
        return process_service

    def override_get_scheduler_service():
        return scheduler_service

    def override_get_task_generation_service():
        return task_generation_service

    async def mark_started(task_id: int):
        await task_service.update_task_status(task_id, True)

    async def mark_stopped(task_id: int):
        task = await task_service.get_task(task_id)
        if task:
            await task_service.update_task_status(task_id, False)

    process_service.set_lifecycle_hooks(on_started=mark_started, on_stopped=mark_stopped)

    app.dependency_overrides[deps.get_task_service] = override_get_task_service
    app.dependency_overrides[deps.get_process_service] = override_get_process_service
    app.dependency_overrides[deps.get_scheduler_service] = override_get_scheduler_service
    app.dependency_overrides[deps.get_task_generation_service] = override_get_task_generation_service

    return {
        "app": app,
        "config_file": config_file,
        "db_path": db_path,
        "repository": repository,
        "task_service": task_service,
        "process_service": process_service,
        "scheduler_service": scheduler_service,
        "task_generation_service": task_generation_service,
    }


@pytest.fixture()
def api_client(api_context):
    return TestClient(api_context["app"])
