"""
指标历史查询 API
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.services.metrics_tracking_service import get_metrics_service

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/item/{item_id}/price-history")
async def get_price_history(
    item_id: str,
    days: int = Query(default=30, ge=1, le=90, description="查询天数"),
):
    """获取商品价格历史"""
    service = get_metrics_service()
    history = service.get_price_history(item_id, days=days)
    return {"item_id": item_id, "days": days, "history": history}


@router.get("/item/{item_id}/want-history")
async def get_want_history(
    item_id: str,
    days: int = Query(default=30, ge=1, le=90, description="查询天数"),
):
    """获取商品想要数历史"""
    service = get_metrics_service()
    history = service.get_want_count_history(item_id, days=days)
    return {"item_id": item_id, "days": days, "history": history}


@router.get("/item/{item_id}/latest")
async def get_latest_snapshot(item_id: str):
    """获取商品最新指标快照"""
    service = get_metrics_service()
    snapshot = service.get_last_snapshot(item_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="商品指标记录不存在")
    return {"item_id": item_id, "snapshot": snapshot}
