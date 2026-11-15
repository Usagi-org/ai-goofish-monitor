"""
任务接口响应序列化辅助。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models.task import Task


def serialize_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def default_failure_guard_state(threshold: int = 3) -> dict[str, Any]:
    return {
        "paused": False,
        "paused_until": None,
        "consecutive_failures": 0,
        "threshold": threshold,
        "reason": None,
        "last_failure_at": None,
    }


def _resolve_guard_state_for_task(
    task: Task,
    process_service,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    get_guard_state = getattr(process_service, "get_failure_guard_state", None)
    if not callable(get_guard_state):
        return default_failure_guard_state()
    try:
        return get_guard_state(task.task_name, task=task, snapshot=snapshot)
    except TypeError:
        return get_guard_state(task.task_name)


def serialize_task(
    task: Task,
    scheduler_service,
    process_service=None,
    *,
    guard_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = task.model_dump()
    next_run_time = None
    if task.id is not None and scheduler_service is not None:
        next_run_time = scheduler_service.get_next_run_time(task.id)
    payload["next_run_at"] = serialize_timestamp(next_run_time)
    payload["failure_guard"] = _resolve_guard_state_for_task(
        task,
        process_service,
        snapshot=guard_snapshot,
    )
    return payload


def serialize_tasks(
    tasks: list[Task],
    scheduler_service,
    process_service=None,
) -> list[dict[str, Any]]:
    if not tasks:
        return []
    snapshot = None
    load_snapshot = getattr(process_service, "load_failure_guard_snapshot", None)
    if callable(load_snapshot):
        snapshot = load_snapshot()
    return [
        serialize_task(
            task,
            scheduler_service,
            process_service=process_service,
            guard_snapshot=snapshot,
        )
        for task in tasks
    ]
