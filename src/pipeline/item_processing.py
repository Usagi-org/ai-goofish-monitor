from dataclasses import dataclass
from typing import Optional

from src.utils import get_link_unique_key


@dataclass(frozen=True)
class ItemCandidate:
    item_data: dict
    unique_key: str
    is_processed: bool

    @property
    def title(self):
        return self.item_data["商品标题"]

    @property
    def link(self):
        return self.item_data["商品链接"]


def should_stop_for_debug_limit(debug_limit: int, processed_item_count: int) -> bool:
    return debug_limit > 0 and processed_item_count >= debug_limit


def normalize_item_candidate(item_data: dict, processed_links: set[str]) -> ItemCandidate:
    unique_key = get_link_unique_key(item_data["商品链接"])
    return ItemCandidate(
        item_data=item_data,
        unique_key=unique_key,
        is_processed=unique_key in processed_links,
    )


def is_processed_item(item_data: dict, processed_links: set[str]) -> bool:
    return normalize_item_candidate(item_data, processed_links).is_processed


def prepare_detail_analysis_job_kwargs(
    *,
    keyword: str,
    task_name: str,
    detail_enrichment: dict,
    current_market_items: list[dict],
    historical_snapshots: list[dict],
    decision_mode: str,
    analyze_images: bool,
    prompt_text: str,
    keyword_rules: Optional[list] = None,
    notification_targets: Optional[list[dict]] = None,
) -> dict:
    return {
        "keyword": keyword,
        "task_name": task_name,
        "detail_enrichment": detail_enrichment,
        "current_market_items": current_market_items,
        "historical_snapshots": historical_snapshots,
        "decision_mode": decision_mode,
        "analyze_images": analyze_images,
        "prompt_text": prompt_text,
        "keyword_rules": keyword_rules,
        "notification_targets": notification_targets,
    }


def build_item_progress_message(index, total, title, *, skipped=False) -> str:
    if skipped:
        return f"[页内进度 {index}/{total}] 商品 '{title[:20]}...' 已存在，跳过。"
    return f"[页内进度 {index}/{total}] 发现新商品，获取详情: {title[:30]}..."
