"""
任务领域模型
定义任务实体及其业务逻辑
"""
import re
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, root_validator, validator


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


def _extract_keywords_from_legacy_groups(groups) -> List[str]:
    if not groups:
        return []

    merged: List[str] = []
    for group in groups:
        include_keywords = []
        if isinstance(group, dict):
            include_keywords = group.get("include_keywords") or []
        else:
            include_keywords = getattr(group, "include_keywords", []) or []
        merged.extend(_normalize_keyword_values(include_keywords))
    return _normalize_keyword_values(merged)


def _normalize_payload_keywords(payload: dict) -> dict:
    if payload is None:
        return {}
    values = dict(payload)
    if "keyword_rules" in values:
        keyword_rules = values.get("keyword_rules")
        values["keyword_rules"] = _normalize_keyword_values(keyword_rules)
    elif "keyword_rule_groups" in values:
        legacy_groups = values.get("keyword_rule_groups")
        values["keyword_rules"] = _extract_keywords_from_legacy_groups(legacy_groups)
    return values


def _has_keyword_rules(keyword_rules: List[str]) -> bool:
    return bool(keyword_rules and len(keyword_rules) > 0)


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
    keyword_rules: List[str] = Field(default_factory=list)
    is_running: bool = False

    class Config:
        use_enum_values = True
        extra = "ignore"

    @root_validator(pre=True)
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @validator("keyword_rules", pre=True)
    def normalize_keyword_rules(cls, v):
        return _normalize_keyword_values(v)

    def can_start(self) -> bool:
        """检查任务是否可以启动"""
        return self.enabled and not self.is_running

    def can_stop(self) -> bool:
        """检查任务是否可以停止"""
        return self.is_running

    def apply_update(self, update: "TaskUpdate") -> "Task":
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
    ai_prompt_criteria_file: str = ""
    account_state_file: Optional[str] = None
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rules: List[str] = Field(default_factory=list)

    class Config:
        extra = "ignore"

    @root_validator(pre=True)
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @validator("min_price", "max_price", pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @validator("keyword_rules", pre=True)
    def normalize_keyword_rules(cls, v):
        return _normalize_keyword_values(v)

    @root_validator(skip_on_failure=True)
    def validate_decision_mode_payload(cls, values):
        mode = (values.get("decision_mode") or "ai").lower()
        description = str(values.get("description") or "").strip()
        keyword_rules = values.get("keyword_rules") or []

        if mode == "ai" and not description:
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        if mode == "keyword" and not _has_keyword_rules(keyword_rules):
            raise ValueError("关键词判断模式下，至少需要一个关键词。")
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
    keyword_rules: Optional[List[str]] = None
    is_running: Optional[bool] = None

    class Config:
        extra = "ignore"

    @root_validator(pre=True)
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @validator("min_price", "max_price", pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @validator("keyword_rules", pre=True)
    def normalize_keyword_rules(cls, v):
        return _normalize_keyword_values(v)

    @root_validator(skip_on_failure=True)
    def validate_partial_keyword_payload(cls, values):
        mode = values.get("decision_mode")
        rules = values.get("keyword_rules")
        description = values.get("description")

        if mode == "keyword" and rules is not None and not _has_keyword_rules(rules):
            raise ValueError("关键词判断模式下，至少需要一个关键词。")
        if mode == "ai" and description is not None and not str(description).strip():
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        return values


class TaskGenerateRequest(BaseModel):
    """任务创建请求DTO（AI模式支持自动生成标准）"""
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
    keyword_rules: List[str] = Field(default_factory=list)

    class Config:
        extra = "ignore"

    @root_validator(pre=True)
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @validator("min_price", "max_price", pre=True)
    def convert_price_to_str(cls, v):
        """将价格转换为字符串，处理空字符串和数字"""
        if v == "" or v == "null" or v == "undefined" or v is None:
            return None
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @validator("cron", pre=True)
    def empty_str_to_none(cls, v):
        """将空字符串转换为 None"""
        if v == "" or v == "null" or v == "undefined":
            return None
        return v

    @validator("account_state_file", pre=True)
    def empty_account_to_none(cls, v):
        if v == "" or v == "null" or v == "undefined":
            return None
        return v

    @validator("new_publish_option", "region", pre=True)
    def empty_str_to_none_for_strings(cls, v):
        if v == "" or v == "null" or v == "undefined":
            return None
        return v

    @validator("keyword_rules", pre=True)
    def normalize_keyword_rules(cls, v):
        return _normalize_keyword_values(v)

    @root_validator(skip_on_failure=True)
    def validate_decision_mode_payload(cls, values):
        mode = (values.get("decision_mode") or "ai").lower()
        description = str(values.get("description") or "").strip()
        keyword_rules = values.get("keyword_rules") or []

        if mode == "ai" and not description:
            raise ValueError("AI 判断模式下，详细需求(description)不能为空。")
        if mode == "keyword" and not _has_keyword_rules(keyword_rules):
            raise ValueError("关键词判断模式下，至少需要一个关键词。")
        return values
