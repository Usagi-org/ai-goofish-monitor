"""
任务领域模型
定义任务实体及其业务逻辑
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    SCHEDULED = "scheduled"


class Task(BaseModel):
    """任务实体"""
    id: Optional[int] = None
    task_name: str
    enabled: bool
    keyword: str
    description: Optional[str] = ""
    max_pages: int
    personal_only: bool
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str
    ai_prompt_criteria_file: str
    account_state_file: Optional[str] = None
    is_running: bool = False

    class Config:
        use_enum_values = True

    def can_start(self) -> bool:
        """检查任务是否可以启动"""
        return self.enabled and not self.is_running

    def can_stop(self) -> bool:
        """检查任务是否可以停止"""
        return self.is_running

    def apply_update(self, update: 'TaskUpdate') -> 'Task':
        """应用更新并返回新的任务实例"""
        update_data = update.dict(exclude_unset=True)
        return self.copy(update=update_data)


class TaskCreate(BaseModel):
    """创建任务的DTO"""
    task_name: str
    enabled: bool = True
    keyword: str
    description: Optional[str] = ""
    max_pages: int = 3
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str = "prompts/base_prompt.txt"
    ai_prompt_criteria_file: str
    account_state_file: Optional[str] = None


class TaskUpdate(BaseModel):
    """更新任务的DTO"""
    task_name: Optional[str] = None
    enabled: Optional[bool] = None
    keyword: Optional[str] = None
    description: Optional[str] = None
    max_pages: Optional[int] = None
    personal_only: Optional[bool] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: Optional[str] = None
    ai_prompt_criteria_file: Optional[str] = None
    account_state_file: Optional[str] = None
    is_running: Optional[bool] = None


class TaskGenerateRequest(BaseModel):
    """AI生成任务的请求DTO"""
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    account_state_file: Optional[str] = None

    @validator('min_price', 'max_price', pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        # 如果是数字，转换为字符串
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @validator('cron', pre=True)
    def empty_str_to_none(cls, v):
        """将空字符串转换为 None"""
        if v == "" or v == "null" or v == "undefined":
            return None
        return v

    @validator('account_state_file', pre=True)
    def empty_account_to_none(cls, v):
        if v == "" or v == "null" or v == "undefined":
            return None
        return v
