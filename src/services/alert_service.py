"""
预警服务
负责预警检测、记录和通知
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.domain.models.alert import (
    Alert,
    AlertCreate,
    AlertUpdate,
    AlertSummary,
    AlertType,
    AlertLevel,
    PriceDropAlertDetails,
)
from src.infrastructure.external.notification_clients.base import AlertNotificationData
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.price_history_service import analyze_price_trend
from src.services.notification_service import NotificationService, build_notification_service


DEFAULT_CONSECUTIVE_SCANS = 3
DEFAULT_DROP_THRESHOLD = 10.0


class AlertService:
    """预警服务"""

    def __init__(
        self,
        consecutive_scans_threshold: int = DEFAULT_CONSECUTIVE_SCANS,
        drop_percentage_threshold: float = DEFAULT_DROP_THRESHOLD,
        notification_service: Optional[NotificationService] = None,
    ):
        self.consecutive_scans_threshold = consecutive_scans_threshold
        self.drop_percentage_threshold = drop_percentage_threshold
        self._notification_service = notification_service

    @property
    def notification_service(self) -> NotificationService:
        if self._notification_service is None:
            self._notification_service = build_notification_service()
        return self._notification_service

    def _row_to_alert(self, row) -> Alert:
        """将数据库行转换为 Alert 对象"""
        details = None
        if row.get("details_json"):
            try:
                details = json.loads(row["details_json"])
            except (json.JSONDecodeError, TypeError):
                details = None

        return Alert(
            id=row["id"],
            task_name=row["task_name"],
            keyword=row["keyword"],
            alert_type=AlertType(row["alert_type"]) if row.get("alert_type") else AlertType.PRICE_DROP,
            alert_level=AlertLevel(row["alert_level"]) if row.get("alert_level") else AlertLevel.WARNING,
            message=row["message"],
            previous_avg_price=row["previous_avg_price"],
            current_avg_price=row["current_avg_price"],
            drop_percentage=row["drop_percentage"],
            consecutive_scans=row["consecutive_scans"] or 0,
            snapshot_time=row["snapshot_time"],
            is_read=bool(row["is_read"]),
            is_dismissed=bool(row["is_dismissed"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            details=details,
        )

    def get_alert_by_id(self, alert_id: int) -> Optional[Alert]:
        """根据 ID 获取预警"""
        bootstrap_sqlite_storage()
        with sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM alert_records WHERE id = ?",
                (alert_id,),
            ).fetchone()
            if row:
                return self._row_to_alert(row)
        return None

    def get_alerts_by_task(
        self,
        task_name: str,
        *,
        include_dismissed: bool = False,
        include_read: bool = True,
        limit: int = 100,
    ) -> List[Alert]:
        """获取任务的预警记录"""
        bootstrap_sqlite_storage()
        query = "SELECT * FROM alert_records WHERE task_name = ?"
        params: list[Any] = [task_name]

        if not include_dismissed:
            query += " AND is_dismissed = 0"
        if not include_read:
            query += " AND is_read = 0"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_alert(row) for row in rows]

    def get_all_alerts(
        self,
        *,
        include_dismissed: bool = False,
        limit: int = 200,
    ) -> List[Alert]:
        """获取所有预警记录"""
        bootstrap_sqlite_storage()
        query = "SELECT * FROM alert_records"
        params: list[Any] = []

        if not include_dismissed:
            query += " WHERE is_dismissed = 0"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_alert(row) for row in rows]

    def get_active_alerts_for_task(self, task_name: str) -> List[Alert]:
        """获取任务的活跃预警（未忽略的）"""
        return self.get_alerts_by_task(task_name, include_dismissed=False, include_read=True)

    def has_active_alert(self, task_name: str) -> bool:
        """检查任务是否有活跃预警"""
        bootstrap_sqlite_storage()
        with sqlite_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as cnt 
                FROM alert_records 
                WHERE task_name = ? AND is_dismissed = 0
                """,
                (task_name,),
            ).fetchone()
            return row and row["cnt"] > 0

    def get_task_alert_summary(self, task_name: str) -> AlertSummary:
        """获取任务的预警摘要"""
        bootstrap_sqlite_storage()
        with sqlite_connection() as conn:
            active_row = conn.execute(
                """
                SELECT COUNT(*) as cnt, MAX(created_at) as latest_time
                FROM alert_records 
                WHERE task_name = ? AND is_dismissed = 0
                """,
                (task_name,),
            ).fetchone()

            active_count = active_row["cnt"] if active_row else 0
            latest_time = active_row["latest_time"] if active_row else None

            latest_alert = None
            if active_count > 0:
                latest_row = conn.execute(
                    """
                    SELECT * FROM alert_records 
                    WHERE task_name = ? AND is_dismissed = 0
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (task_name,),
                ).fetchone()
                if latest_row:
                    latest_alert = self._row_to_alert(latest_row)

        return AlertSummary(
            task_name=task_name,
            has_active_alert=active_count > 0,
            active_alert_count=active_count,
            latest_alert_level=latest_alert.alert_level if latest_alert else None,
            latest_alert_message=latest_alert.message if latest_alert else None,
            latest_alert_time=latest_time,
        )

    def get_all_task_alert_summaries(self, task_names: List[str]) -> Dict[str, AlertSummary]:
        """批量获取多个任务的预警摘要"""
        result = {}
        for task_name in task_names:
            result[task_name] = self.get_task_alert_summary(task_name)
        return result

    def create_alert(self, alert_create: AlertCreate) -> Alert:
        """创建预警记录"""
        bootstrap_sqlite_storage()
        now = datetime.now().isoformat()
        snapshot_time = alert_create.snapshot_time or now

        details_json = None
        if alert_create.details:
            try:
                details_json = json.dumps(alert_create.details, ensure_ascii=False)
            except (TypeError, ValueError):
                details_json = None

        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alert_records (
                    task_name, keyword, alert_type, alert_level, message,
                    previous_avg_price, current_avg_price, drop_percentage,
                    consecutive_scans, snapshot_time, is_read, is_dismissed,
                    created_at, updated_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_create.task_name,
                    alert_create.keyword,
                    alert_create.alert_type.value,
                    alert_create.alert_level.value,
                    alert_create.message,
                    alert_create.previous_avg_price,
                    alert_create.current_avg_price,
                    alert_create.drop_percentage,
                    alert_create.consecutive_scans,
                    snapshot_time,
                    0,
                    0,
                    now,
                    now,
                    details_json,
                ),
            )
            conn.commit()
            alert_id = cursor.lastrowid

        alert = self.get_alert_by_id(alert_id)
        if alert is None:
            raise ValueError("Failed to create alert")
        return alert

    def update_alert(self, alert_id: int, alert_update: AlertUpdate) -> Optional[Alert]:
        """更新预警状态"""
        bootstrap_sqlite_storage()
        alert = self.get_alert_by_id(alert_id)
        if alert is None:
            return None

        updates: list[str] = []
        params: list[Any] = []
        now = datetime.now().isoformat()

        if alert_update.is_read is not None:
            updates.append("is_read = ?")
            params.append(1 if alert_update.is_read else 0)

        if alert_update.is_dismissed is not None:
            updates.append("is_dismissed = ?")
            params.append(1 if alert_update.is_dismissed else 0)

        if not updates:
            return alert

        updates.append("updated_at = ?")
        params.append(now)
        params.append(alert_id)

        with sqlite_connection() as conn:
            conn.execute(
                f"UPDATE alert_records SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

        return self.get_alert_by_id(alert_id)

    def mark_alert_as_read(self, alert_id: int) -> Optional[Alert]:
        """标记预警为已读"""
        return self.update_alert(alert_id, AlertUpdate(is_read=True))

    def dismiss_alert(self, alert_id: int) -> Optional[Alert]:
        """忽略/解除预警"""
        return self.update_alert(alert_id, AlertUpdate(is_dismissed=True))

    def dismiss_all_alerts_for_task(self, task_name: str) -> int:
        """忽略任务的所有预警"""
        bootstrap_sqlite_storage()
        now = datetime.now().isoformat()
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE alert_records 
                SET is_dismissed = 1, updated_at = ?
                WHERE task_name = ? AND is_dismissed = 0
                """,
                (now, task_name),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def check_and_create_price_drop_alert(
        self,
        task_name: str,
        keyword: str,
        *,
        consecutive_scans_threshold: Optional[int] = None,
        drop_percentage_threshold: Optional[float] = None,
        force_create: bool = False,
    ) -> Optional[Alert]:
        """
        检测价格趋势并创建预警（如果符合条件）
        
        Args:
            task_name: 任务名称
            keyword: 搜索关键词
            consecutive_scans_threshold: 连续扫描次数阈值（覆盖默认值）
            drop_percentage_threshold: 下跌百分比阈值（覆盖默认值）
            force_create: 是否强制创建（即使已有活跃预警）
        
        Returns:
            如果创建了预警则返回 Alert 对象，否则返回 None
        """
        scans_threshold = consecutive_scans_threshold or self.consecutive_scans_threshold
        drop_threshold = drop_percentage_threshold or self.drop_percentage_threshold

        if not force_create and self.has_active_alert(task_name):
            return None

        trend_result = analyze_price_trend(
            keyword=keyword,
            task_name=task_name,
            consecutive_scans_threshold=scans_threshold,
            drop_percentage_threshold=drop_threshold,
        )

        if not trend_result.get("should_alert", False):
            return None

        baseline_price = trend_result.get("baseline_avg_price")
        current_price = trend_result.get("current_avg_price")
        drop_percent = trend_result.get("drop_percentage", 0.0)
        consecutive_count = trend_result.get("consecutive_drop_count", 0)

        alert_level = AlertLevel.WARNING
        if drop_percent >= 20.0:
            alert_level = AlertLevel.CRITICAL

        message = (
            f"价格下跌预警：任务 '{task_name}' 已连续 {consecutive_count} 次扫描发现均价下跌。"
            f"基准均价 ¥{baseline_price:.2f}，当前均价 ¥{current_price:.2f}，"
            f"累计下跌 {drop_percent:.1f}%。"
        )

        details = PriceDropAlertDetails(
            keyword=keyword,
            task_name=task_name,
            consecutive_scans=consecutive_count,
            threshold_percent=drop_threshold,
            baseline_avg_price=baseline_price or 0.0,
            current_avg_price=current_price or 0.0,
            actual_drop_percent=drop_percent,
        )

        alert_create = AlertCreate(
            task_name=task_name,
            keyword=keyword,
            alert_type=AlertType.PRICE_DROP,
            alert_level=alert_level,
            message=message,
            previous_avg_price=baseline_price,
            current_avg_price=current_price,
            drop_percentage=drop_percent,
            consecutive_scans=consecutive_count,
            details=details.model_dump(),
        )

        return self.create_alert(alert_create)

    async def send_alert_notification(self, alert: Alert) -> Dict[str, Dict[str, str | bool]]:
        """
        发送预警通知
        
        Args:
            alert: 预警对象
        
        Returns:
            各渠道发送结果
        """
        alert_data = AlertNotificationData(
            task_name=alert.task_name,
            keyword=alert.keyword,
            alert_level=alert.alert_level.value,
            previous_avg_price=alert.previous_avg_price,
            current_avg_price=alert.current_avg_price,
            drop_percentage=alert.drop_percentage,
            consecutive_scans=alert.consecutive_scans,
            message=alert.message,
        )

        return await self.notification_service.send_price_drop_alert(alert_data)


def build_alert_service(
    consecutive_scans_threshold: int = DEFAULT_CONSECUTIVE_SCANS,
    drop_percentage_threshold: float = DEFAULT_DROP_THRESHOLD,
) -> AlertService:
    """构建预警服务实例"""
    return AlertService(
        consecutive_scans_threshold=consecutive_scans_threshold,
        drop_percentage_threshold=drop_percentage_threshold,
    )
