"""
任务接口响应序列化辅助。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models.task import Task


def serialize_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _get_alert_summary_for_task(task_name: str) -> dict[str, Any]:
    """获取任务的预警摘要"""
    try:
        from src.services.alert_service import build_alert_service
        alert_service = build_alert_service()
        summary = alert_service.get_task_alert_summary(task_name)
        return summary.model_dump()
    except Exception:
        return {
            "task_name": task_name,
            "has_active_alert": False,
            "active_alert_count": 0,
            "latest_alert_level": None,
            "latest_alert_message": None,
            "latest_alert_time": None,
        }


def serialize_task(task: Task, scheduler_service) -> dict[str, Any]:
    payload = task.model_dump()
    next_run_time = None
    if task.id is not None and scheduler_service is not None:
        next_run_time = scheduler_service.get_next_run_time(task.id)
    payload["next_run_at"] = serialize_timestamp(next_run_time)
    payload["alert_summary"] = _get_alert_summary_for_task(task.task_name)
    return payload


def serialize_tasks(tasks: list[Task], scheduler_service) -> list[dict[str, Any]]:
    if not tasks:
        return []
    
    task_names = [task.task_name for task in tasks]
    
    try:
        from src.services.alert_service import build_alert_service
        alert_service = build_alert_service()
        alert_summaries = alert_service.get_all_task_alert_summaries(task_names)
    except Exception:
        alert_summaries = {}
    
    result = []
    for task in tasks:
        payload = task.model_dump()
        next_run_time = None
        if task.id is not None and scheduler_service is not None:
            next_run_time = scheduler_service.get_next_run_time(task.id)
        payload["next_run_at"] = serialize_timestamp(next_run_time)
        
        summary = alert_summaries.get(task.task_name)
        if summary:
            payload["alert_summary"] = summary.model_dump()
        else:
            payload["alert_summary"] = {
                "task_name": task.task_name,
                "has_active_alert": False,
                "active_alert_count": 0,
                "latest_alert_level": None,
                "latest_alert_message": None,
                "latest_alert_time": None,
            }
        result.append(payload)
    
    return result
