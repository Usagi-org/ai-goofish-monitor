"""
任务生成作业模型
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.domain.models.task import Task


TaskGenerationStatus = Literal["queued", "running", "completed", "failed"]
TaskGenerationStepStatus = Literal["pending", "running", "completed", "failed"]


class TaskGenerationStep(BaseModel):
    """单个任务生成步骤"""

    key: str
    label: str
    status: TaskGenerationStepStatus = "pending"
    message: str = ""


class TaskGenerationJob(BaseModel):
    """任务生成作业"""

    job_id: str
    task_name: str
    status: TaskGenerationStatus = "queued"
    message: str = "任务已排队，等待开始。"
    current_step: Optional[str] = None
    steps: List[TaskGenerationStep] = Field(default_factory=list)
    task: Optional[Task] = None
    error: Optional[str] = None
