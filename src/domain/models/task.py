"""
任务领域模型
定义任务实体及其业务逻辑
"""
import re
from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.cron_utils import validate_cron_expression
from src.services.account_strategy_service import (
    clean_account_state_file,
    normalize_account_strategy,
)


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
    for group in groups or []:
        if isinstance(group, dict):
            include_keywords = []
            if isinstance(group, dict):
                include_keywords = group.get("include_keywords") or []
            else:
                include_keywords = getattr(group, "include_keywords", []) or []
            merged.extend(_normalize_keyword_values(include_keywords))
    return _normalize_keyword_values(merged)


def _normalize_payload_keywords(payload: Any) -> Any:
    if payload is None or not isinstance(payload, dict):
        return payload
    values = dict(payload)
    values["account_state_file"] = clean_account_state_file(values.get("account_state_file"))
    values["account_strategy"] = normalize_account_strategy(
        values.get("account_strategy"),
        values.get("account_state_file"),
    )
    if "keyword_rules" in values:
        values["keyword_rules"] = _normalize_keyword_values(values.get("keyword_rules"))
    elif "keyword_rule_groups" in values:
        values["keyword_rules"] = _extract_keywords_from_legacy_groups(
            values.get("keyword_rule_groups")
        )
    return values


def _has_keyword_rules(keyword_rules: List[str]) -> bool:
    return bool(keyword_rules and len(keyword_rules) > 0)


def _normalize_optional_string(value):
    if value == "" or value == "null" or value == "undefined" or value is None:
        return None
    return value


def _validate_cron_expression(value: Optional[str]) -> Optional[str]:
    return validate_cron_expression(value)


def _normalize_price_value(value):
    if _normalize_optional_string(value) is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    return value


class Task(BaseModel):
    """任务实体"""

    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: Optional[int] = None
    task_name: str
    task_type: Literal["keyword", "item_id"] = "keyword"  # 任务类型：关键词搜索 / 商品 ID 监控
    enabled: bool
    keyword: Optional[str] = None  # 关键词模式必填，item_id 模式可选（用于备注）
    item_id_list: List[str] = Field(default_factory=list)  # 商品 ID 列表（item_id 模式使用）
    description: Optional[str] = ""
    analyze_images: bool = True
    max_pages: int = 3
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str = "prompts/base_prompt.txt"
    ai_prompt_criteria_file: str = ""
    account_state_file: Optional[str] = None
    account_strategy: Literal["auto", "fixed", "rotate"] = "auto"
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rules: List[str] = Field(default_factory=list)
    is_running: bool = False
    is_paused: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @field_validator("keyword_rules", mode="before")
    @classmethod
    def normalize_keyword_rules(cls, value):
        return _normalize_keyword_values(value)

    def can_start(self) -> bool:
        """检查任务是否可以启动"""
        return self.enabled and not self.is_running

    def can_stop(self) -> bool:
        """检查任务是否可以停止"""
        return self.is_running

    def apply_update(self, update: "TaskUpdate") -> "Task":
        """应用更新并返回新的任务实例"""
        update_data = update.model_dump(exclude_unset=True)
        return self.model_copy(update=update_data)


class TaskCreate(BaseModel):
    """创建任务的 DTO"""

    model_config = ConfigDict(extra="ignore")

    task_name: str
    task_type: Literal["keyword", "item_id"] = "keyword"  # 任务类型：关键词搜索 / 商品 ID 监控
    enabled: bool = True
    keyword: Optional[str] = None  # 关键词模式必填，item_id 模式可选（用于备注）
    item_id_list: List[str] = Field(default_factory=list)  # 商品 ID 列表（item_id 模式使用）
    description: Optional[str] = ""
    analyze_images: bool = True
    max_pages: int = 3
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str = "prompts/base_prompt.txt"
    ai_prompt_criteria_file: str = ""
    account_state_file: Optional[str] = None
    account_strategy: Literal["auto", "fixed", "rotate"] = "auto"
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rules: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @field_validator("min_price", "max_price", mode="before")
    @classmethod
    def convert_price_to_str(cls, value):
        return _normalize_price_value(value)

    @field_validator("cron", mode="before")
    @classmethod
    def normalize_cron(cls, value):
        return _normalize_optional_string(value)

    @field_validator("account_state_file", mode="before")
    @classmethod
    def normalize_account_state_file(cls, value):
        return clean_account_state_file(value)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value):
        return _validate_cron_expression(value)

    @field_validator("keyword_rules", mode="before")
    @classmethod
    def normalize_keyword_rules(cls, value):
        return _normalize_keyword_values(value)

    @model_validator(mode="after")
    def validate_decision_mode_payload(self):
        # 商品 ID 监控模式验证
        if self.task_type == "item_id":
            if not self.item_id_list:
                raise ValueError("商品 ID 监控模式下，必须提供至少一个商品 ID。")
            # 验证商品 ID 格式（纯数字）
            for item_id in self.item_id_list:
                if not str(item_id).strip().isdigit():
                    raise ValueError(f"商品 ID 必须是数字：{item_id}")
        # 关键词模式验证
        elif self.task_type == "keyword":
            if not self.keyword or not str(self.keyword).strip():
                raise ValueError("关键词模式下，必须提供搜索关键词。")
            if self.decision_mode == "ai" and not str(self.description or "").strip():
                raise ValueError("AI 判断模式下，详细需求 (description) 不能为空。")
            if self.decision_mode == "keyword" and not _has_keyword_rules(self.keyword_rules):
                raise ValueError("关键词判断模式下，至少需要一个关键词。")

        if self.account_strategy == "fixed" and not self.account_state_file:
            raise ValueError("固定账号模式下必须选择账号。")
        return self


class TaskUpdate(BaseModel):
    """更新任务的 DTO"""

    model_config = ConfigDict(extra="ignore")

    task_name: Optional[str] = None
    task_type: Optional[Literal["keyword", "item_id"]] = None
    enabled: Optional[bool] = None
    keyword: Optional[str] = None
    item_id_list: Optional[List[str]] = None
    description: Optional[str] = None
    analyze_images: Optional[bool] = None
    max_pages: Optional[int] = None
    personal_only: Optional[bool] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: Optional[str] = None
    ai_prompt_criteria_file: Optional[str] = None
    account_state_file: Optional[str] = None
    account_strategy: Optional[Literal["auto", "fixed", "rotate"]] = None
    free_shipping: Optional[bool] = None
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Optional[Literal["ai", "keyword"]] = None
    keyword_rules: Optional[List[str]] = None
    is_running: Optional[bool] = None
    is_paused: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @field_validator("min_price", "max_price", mode="before")
    @classmethod
    def convert_price_to_str(cls, value):
        return _normalize_price_value(value)

    @field_validator("cron", mode="before")
    @classmethod
    def normalize_cron(cls, value):
        return _normalize_optional_string(value)

    @field_validator("account_state_file", mode="before")
    @classmethod
    def normalize_account_state_file(cls, value):
        return clean_account_state_file(value)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value):
        return _validate_cron_expression(value)

    @field_validator("keyword_rules", mode="before")
    @classmethod
    def normalize_keyword_rules(cls, value):
        return _normalize_keyword_values(value)

    @model_validator(mode="after")
    def validate_partial_keyword_payload(self):
        # 只在明确设置了 keyword_rules 时才验证关键词规则
        if self.decision_mode == "keyword" and self.keyword_rules is not None:
            if not _has_keyword_rules(self.keyword_rules):
                raise ValueError("关键词判断模式下，至少需要一个关键词。")
        # 编辑模式下，允许 description 为空字符串（用户可能只是修改其他字段）
        # 只有当 description 被明确设置为空且 decision_mode 为 ai 时，不抛出错误
        return self


class TaskGenerateRequest(BaseModel):
    """任务创建请求 DTO（AI 模式支持自动生成标准）"""

    model_config = ConfigDict(extra="ignore")

    task_name: str
    task_type: Literal["keyword", "item_id"] = "keyword"  # 新增：任务类型
    keyword: Optional[str] = None  # 改为可选
    item_id_list: List[str] = Field(default_factory=list)  # 新增：商品 ID 列表
    description: Optional[str] = ""
    analyze_images: bool = True
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    account_state_file: Optional[str] = None
    account_strategy: Literal["auto", "fixed", "rotate"] = "auto"
    free_shipping: bool = True
    new_publish_option: Optional[str] = None
    region: Optional[str] = None
    decision_mode: Literal["ai", "keyword"] = "ai"
    keyword_rules: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_keyword_payload(cls, values):
        return _normalize_payload_keywords(values)

    @field_validator("min_price", "max_price", mode="before")
    @classmethod
    def convert_price_to_str(cls, value):
        return _normalize_price_value(value)

    @field_validator("cron", mode="before")
    @classmethod
    def empty_str_to_none(cls, value):
        return _normalize_optional_string(value)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value):
        return _validate_cron_expression(value)

    @field_validator("account_state_file", mode="before")
    @classmethod
    def empty_account_to_none(cls, value):
        return _normalize_optional_string(value)

    @field_validator("new_publish_option", "region", mode="before")
    @classmethod
    def empty_str_to_none_for_strings(cls, value):
        return _normalize_optional_string(value)

    @field_validator("keyword_rules", mode="before")
    @classmethod
    def normalize_keyword_rules(cls, value):
        return _normalize_keyword_values(value)

    @model_validator(mode="after")
    def validate_decision_mode_payload(self):
        # 商品 ID 监控模式：只验证 item_id_list
        if self.task_type == "item_id":
            if not self.item_id_list:
                raise ValueError("商品 ID 监控模式下，必须提供至少一个商品 ID。")
            for item_id in self.item_id_list:
                if not str(item_id).strip().isdigit():
                    raise ValueError(f"商品 ID 必须是数字：{item_id}")
            # 商品 ID 模式不需要 description 和 keyword
            return self

        # 关键词模式验证（原有逻辑）
        description = str(self.description or "").strip()
        if self.decision_mode == "ai" and not description:
            raise ValueError("AI 判断模式下，详细需求 (description) 不能为空。")
        if self.decision_mode == "keyword" and not _has_keyword_rules(self.keyword_rules):
            raise ValueError("关键词判断模式下，至少需要一个关键词。")
        if self.account_strategy == "fixed" and not self.account_state_file:
            raise ValueError("固定账号模式下必须选择账号。")
        return self
