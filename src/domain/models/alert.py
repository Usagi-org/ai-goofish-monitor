"""
预警领域模型
定义预警实体及其业务逻辑
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AlertType(str, Enum):
    """预警类型枚举"""

    PRICE_DROP = "price_drop"
    PRICE_SURGE = "price_surge"
    LOW_STOCK = "low_stock"
    NEW_LISTING = "new_listing"


class AlertLevel(str, Enum):
    """预警级别枚举"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """预警状态枚举"""

    ACTIVE = "active"
    READ = "read"
    DISMISSED = "dismissed"


class PriceTrendInfo(BaseModel):
    """价格趋势信息"""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    snapshot_time: str
    avg_price: float
    sample_count: int
    median_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None


class PriceDropAlertDetails(BaseModel):
    """价格下跌预警详情"""

    model_config = ConfigDict(extra="ignore")

    keyword: str
    task_name: str
    consecutive_scans: int
    threshold_percent: float
    baseline_avg_price: float
    current_avg_price: float
    actual_drop_percent: float
    trend_history: List[PriceTrendInfo] = Field(default_factory=list)


class Alert(BaseModel):
    """预警实体"""

    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: Optional[int] = None
    task_name: str
    keyword: str
    alert_type: AlertType
    alert_level: AlertLevel
    message: str
    previous_avg_price: Optional[float] = None
    current_avg_price: Optional[float] = None
    drop_percentage: Optional[float] = None
    consecutive_scans: int = 0
    snapshot_time: str
    is_read: bool = False
    is_dismissed: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def status(self) -> AlertStatus:
        """获取预警状态"""
        if self.is_dismissed:
            return AlertStatus.DISMISSED
        if self.is_read:
            return AlertStatus.READ
        return AlertStatus.ACTIVE

    def mark_as_read(self) -> None:
        """标记为已读"""
        self.is_read = True
        self.updated_at = datetime.now().isoformat()

    def dismiss(self) -> None:
        """忽略/解除预警"""
        self.is_dismissed = True
        self.updated_at = datetime.now().isoformat()


class AlertCreate(BaseModel):
    """创建预警的 DTO"""

    model_config = ConfigDict(extra="ignore")

    task_name: str
    keyword: str
    alert_type: AlertType = AlertType.PRICE_DROP
    alert_level: AlertLevel = AlertLevel.WARNING
    message: str
    previous_avg_price: Optional[float] = None
    current_avg_price: Optional[float] = None
    drop_percentage: Optional[float] = None
    consecutive_scans: int = 0
    snapshot_time: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AlertUpdate(BaseModel):
    """更新预警的 DTO"""

    model_config = ConfigDict(extra="ignore")

    is_read: Optional[bool] = None
    is_dismissed: Optional[bool] = None


class AlertSummary(BaseModel):
    """预警摘要（用于任务列表和概览页）"""

    model_config = ConfigDict(extra="ignore")

    task_name: str
    has_active_alert: bool
    active_alert_count: int
    latest_alert_level: Optional[AlertLevel] = None
    latest_alert_message: Optional[str] = None
    latest_alert_time: Optional[str] = None


class PriceTrendAnalysisResult(BaseModel):
    """价格趋势分析结果"""

    model_config = ConfigDict(extra="ignore")

    keyword: str
    task_name: str
    has_significant_drop: bool
    consecutive_drop_count: int
    drop_percentage: float
    threshold_percent: float
    baseline_avg_price: Optional[float] = None
    current_avg_price: Optional[float] = None
    trend_history: List[PriceTrendInfo] = Field(default_factory=list)
    should_alert: bool = False
