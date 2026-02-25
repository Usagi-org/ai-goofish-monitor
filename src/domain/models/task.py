"""
任务领域模型
定义任务实体及其业务逻辑
"""
import re
from pydantic import BaseModel, Field, root_validator, validator
from typing import List, Literal, Optional
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    SCHEDULED = "scheduled"


def _normalize_keyword_values(value) -> List[str]:
    if value is None:
        return []

    raw_values = []
    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    elif isinstance(value, str):
        raw_values = re.split(r"[\n,]+", value)
    else:
        raw_values = [value]

    normalized: List[str] = []
    seen = set()
    for item in raw_values:
        text = str(item).strip()
        if not text:
            continue
        dedup_key = text.lower()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        normalized.append(text)
    return normalized


def _has_valid_keyword_groups(groups) -> bool:
    if not groups:
        return False
    for group in groups:
        include_keywords = getattr(group, "include_keywords", None)
        if include_keywords:
            return True
    return False


class KeywordRuleGroup(BaseModel):
    """关键词规则分组。组内 include 为 AND，exclude 为 NOT。"""
    name: Optional[str] = None
    include_keywords: List[str] = Field(default_factory=list)
    exclude_keywords: List[str] = Field(default_factory=list)

    @validator("name", pre=True)
    def normalize_name(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @validator("include_keywords", "exclude_keywords", pre=True)
    def normalize_keyword_list(cls, v):
        return _normalize_keyword_values(v)


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
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rule_groups: List[KeywordRuleGroup] = Field(default_factory=list)
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
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rule_groups: List[KeywordRuleGroup] = Field(default_factory=list)

    @validator('min_price', 'max_price', pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @root_validator(skip_on_failure=True)
    def validate_decision_mode_payload(cls, values):
        mode = (values.get("decision_mode") or "ai").lower()
        description = str(values.get("description") or "").strip()
        keyword_groups = values.get("keyword_rule_groups") or []

        if mode == "ai" and not description:
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        if mode == "keyword" and not _has_valid_keyword_groups(keyword_groups):
            raise ValueError("关键词判断模式下，至少需要一个包含关键词。")
        return values


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
    free_shipping: Optional[bool] = None
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Optional[Literal["ai", "keyword"]] = None
    keyword_rule_groups: Optional[List[KeywordRuleGroup]] = None
    is_running: Optional[bool] = None
    
    @validator('min_price', 'max_price', pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @root_validator(skip_on_failure=True)
    def validate_partial_keyword_payload(cls, values):
        mode = values.get("decision_mode")
        groups = values.get("keyword_rule_groups")
        description = values.get("description")

        if mode == "keyword" and groups is not None and not _has_valid_keyword_groups(groups):
            raise ValueError("关键词判断模式下，至少需要一个包含关键词。")
        if mode == "ai" and description is not None and not str(description).strip():
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        return values


class TaskGenerateRequest(BaseModel):
    """AI生成任务的请求DTO"""
    task_name: str
    keyword: str
    description: Optional[str] = ""
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    account_state_file: Optional[str] = None
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rule_groups: List[KeywordRuleGroup] = Field(default_factory=list)

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

    @validator('new_publish_option', 'region', pre=True)
    def empty_str_to_none_for_strings(cls, v):
        if v == "" or v == "null" or v == "undefined":
            return None
        return v

    @root_validator(skip_on_failure=True)
    def validate_decision_mode_payload(cls, values):
        mode = (values.get("decision_mode") or "ai").lower()
        description = str(values.get("description") or "").strip()
        keyword_groups = values.get("keyword_rule_groups") or []

        if mode == "ai" and not description:
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        if mode == "keyword" and not _has_valid_keyword_groups(keyword_groups):
            raise ValueError("关键词判断模式下，至少需要一个包含关键词。")
        return values
