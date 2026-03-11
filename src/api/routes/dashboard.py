"""
Dashboard 概览路由
"""
from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_task_service
from src.services.dashboard_service import build_dashboard_snapshot
from src.services.task_service import TaskService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    task_service: TaskService = Depends(get_task_service),
):
    try:
        tasks = await task_service.get_all_tasks()
        return await build_dashboard_snapshot(tasks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"加载 dashboard 数据失败: {exc}")
