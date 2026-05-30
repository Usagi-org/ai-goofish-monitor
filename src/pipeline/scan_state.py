from dataclasses import dataclass
from datetime import datetime

from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.price_history_service import load_price_snapshots
from src.services.result_storage_service import load_processed_link_keys


@dataclass
class ScanState:
    keyword: str
    history_run_id: str
    history_seen_item_ids: set[str]
    historical_snapshots: list[dict]
    result_filename: str
    processed_links: set[str]


def build_scan_state(keyword: str) -> ScanState:
    return ScanState(
        keyword=keyword,
        history_run_id=datetime.now().strftime("%Y%m%d%H%M%S"),
        history_seen_item_ids=set(),
        historical_snapshots=load_price_snapshots(keyword),
        result_filename=build_result_filename(keyword),
        processed_links=load_processed_link_keys(keyword),
    )
