"""
任务接口响应序列化辅助。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models.task import Task


def serialize_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_task(task: Task, scheduler_service) -> dict[str, Any]:
    payload = task.model_dump()
    next_run_time = None
    if task.id is not None and scheduler_service is not None:
        next_run_time = scheduler_service.get_next_run_time(task.id)
    payload["next_run_at"] = serialize_timestamp(next_run_time)
    return payload


def serialize_tasks(tasks: list[Task], scheduler_service) -> list[dict[str, Any]]:
    return [serialize_task(task, scheduler_service) for task in tasks]
