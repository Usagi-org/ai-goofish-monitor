"""
预警管理路由
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.domain.models.alert import Alert, AlertCreate, AlertUpdate, AlertSummary, AlertStatus
from src.services.alert_service import AlertService, build_alert_service


router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_alert_service() -> AlertService:
    """获取预警服务实例"""
    return build_alert_service()


@router.get("", response_model=List[dict])
async def get_alerts(
    include_dismissed: bool = Query(False, description="是否包含已忽略的预警"),
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """获取所有预警记录"""
    try:
        alerts = alert_service.get_all_alerts(
            include_dismissed=include_dismissed,
            limit=limit,
        )
        return [alert.model_dump() for alert in alerts]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取预警列表失败: {exc}")


@router.get("/task/{task_name}", response_model=List[dict])
async def get_task_alerts(
    task_name: str,
    include_dismissed: bool = Query(False, description="是否包含已忽略的预警"),
    include_read: bool = Query(True, description="是否包含已读的预警"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """获取指定任务的预警记录"""
    try:
        alerts = alert_service.get_alerts_by_task(
            task_name=task_name,
            include_dismissed=include_dismissed,
            include_read=include_read,
            limit=limit,
        )
        return [alert.model_dump() for alert in alerts]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取任务预警失败: {exc}")


@router.get("/summary/{task_name}", response_model=dict)
async def get_task_alert_summary(
    task_name: str,
    alert_service: AlertService = Depends(get_alert_service),
):
    """获取指定任务的预警摘要"""
    try:
        summary = alert_service.get_task_alert_summary(task_name)
        return summary.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取预警摘要失败: {exc}")


@router.post("/summary/batch", response_model=dict)
async def get_batch_alert_summaries(
    task_names: List[str],
    alert_service: AlertService = Depends(get_alert_service),
):
    """批量获取多个任务的预警摘要"""
    try:
        summaries = alert_service.get_all_task_alert_summaries(task_names)
        return {name: summary.model_dump() for name, summary in summaries.items()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"批量获取预警摘要失败: {exc}")


@router.get("/{alert_id}", response_model=dict)
async def get_alert(
    alert_id: int,
    alert_service: AlertService = Depends(get_alert_service),
):
    """获取单个预警详情"""
    try:
        alert = alert_service.get_alert_by_id(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="预警不存在")
        return alert.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取预警详情失败: {exc}")


@router.patch("/{alert_id}", response_model=dict)
async def update_alert(
    alert_id: int,
    alert_update: AlertUpdate,
    alert_service: AlertService = Depends(get_alert_service),
):
    """更新预警状态（标记为已读、忽略等）"""
    try:
        alert = alert_service.update_alert(alert_id, alert_update)
        if not alert:
            raise HTTPException(status_code=404, detail="预警不存在")
        return {"message": "预警状态已更新", "alert": alert.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新预警失败: {exc}")


@router.post("/{alert_id}/read", response_model=dict)
async def mark_alert_as_read(
    alert_id: int,
    alert_service: AlertService = Depends(get_alert_service),
):
    """标记预警为已读"""
    try:
        alert = alert_service.mark_alert_as_read(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="预警不存在")
        return {"message": "已标记为已读", "alert": alert.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"标记预警失败: {exc}")


@router.post("/{alert_id}/dismiss", response_model=dict)
async def dismiss_alert(
    alert_id: int,
    alert_service: AlertService = Depends(get_alert_service),
):
    """忽略/解除预警"""
    try:
        alert = alert_service.dismiss_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="预警不存在")
        return {"message": "预警已忽略", "alert": alert.model_dump()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"忽略预警失败: {exc}")


@router.post("/task/{task_name}/dismiss-all", response_model=dict)
async def dismiss_all_alerts_for_task(
    task_name: str,
    alert_service: AlertService = Depends(get_alert_service),
):
    """忽略任务的所有活跃预警"""
    try:
        count = alert_service.dismiss_all_alerts_for_task(task_name)
        return {
            "message": f"已忽略 {count} 条预警",
            "dismissed_count": count,
            "task_name": task_name,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"忽略预警失败: {exc}")


@router.post("/check", response_model=dict)
async def check_price_trend(
    task_name: str,
    keyword: str,
    consecutive_scans: int = Query(3, ge=1, le=10, description="连续扫描次数阈值"),
    drop_threshold: float = Query(10.0, ge=1.0, le=50.0, description="下跌百分比阈值"),
    force_create: bool = Query(False, description="是否强制创建预警（即使已有活跃预警）"),
    send_notification: bool = Query(False, description="是否发送通知"),
    alert_service: AlertService = Depends(get_alert_service),
):
    """
    手动触发价格趋势检测
    
    用于调试或手动检查。连续 X 次扫描发现均价下跌超 Y% 时创建预警。
    """
    try:
        alert = alert_service.check_and_create_price_drop_alert(
            task_name=task_name,
            keyword=keyword,
            consecutive_scans_threshold=consecutive_scans,
            drop_percentage_threshold=drop_threshold,
            force_create=force_create,
        )

        if alert is None:
            return {
                "message": "未触发预警条件",
                "task_name": task_name,
                "keyword": keyword,
                "alert_created": False,
            }

        result = {
            "message": "预警已创建",
            "task_name": task_name,
            "keyword": keyword,
            "alert_created": True,
            "alert": alert.model_dump(),
        }

        if send_notification:
            notification_results = await alert_service.send_alert_notification(alert)
            result["notification_results"] = notification_results

        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"价格趋势检测失败: {exc}")
