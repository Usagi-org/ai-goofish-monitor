from dataclasses import dataclass, field
from typing import Any, Optional


def _should_analyze_images(task_config: dict) -> bool:
    raw_value = task_config.get("analyze_images", True)
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() not in {"false", "0", "no", "off"}


@dataclass(frozen=True)
class TaskRuntimeConfig:
    keyword: str
    max_pages: int = 1
    personal_only: bool = False
    min_price: Optional[Any] = None
    max_price: Optional[Any] = None
    analyze_images: bool = True
    decision_mode: str = "ai"
    keyword_rules: list = field(default_factory=list)
    notification_targets: list = field(default_factory=list)
    free_shipping: bool = False
    new_publish_option: str = ""
    region_filter: str = ""
    ai_prompt_text: str = ""

    @classmethod
    def from_dict(cls, task_config: dict) -> "TaskRuntimeConfig":
        decision_mode = str(task_config.get("decision_mode", "ai")).strip().lower()
        if decision_mode not in {"ai", "keyword"}:
            decision_mode = "ai"

        new_publish_option = str(task_config.get("new_publish_option") or "").strip()
        if new_publish_option == "__none__":
            new_publish_option = ""

        return cls(
            keyword=task_config["keyword"],
            max_pages=task_config.get("max_pages", 1),
            personal_only=task_config.get("personal_only", False),
            min_price=task_config.get("min_price"),
            max_price=task_config.get("max_price"),
            analyze_images=_should_analyze_images(task_config),
            decision_mode=decision_mode,
            keyword_rules=task_config.get("keyword_rules") or [],
            notification_targets=task_config.get("notification_targets") or [],
            free_shipping=task_config.get("free_shipping", False),
            new_publish_option=new_publish_option,
            region_filter=(task_config.get("region") or "").strip(),
            ai_prompt_text=task_config.get("ai_prompt_text", ""),
        )
