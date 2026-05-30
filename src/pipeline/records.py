from datetime import datetime

from src.services.price_history_service import build_market_reference


def build_final_record(
    keyword: str,
    task_name: str,
    item_data: dict,
    current_market_items: list[dict],
    historical_snapshots: list[dict],
) -> dict:
    final_record = {
        "爬取时间": datetime.now().isoformat(),
        "搜索关键字": keyword,
        "任务名称": task_name,
        "商品信息": item_data,
        "卖家信息": {},
    }
    price_reference = build_market_reference(
        keyword=keyword,
        item=item_data,
        current_market_items=current_market_items,
        historical_snapshots=historical_snapshots,
    )
    final_record["价格参考"] = price_reference
    final_record["price_insight"] = price_reference.get("本商品价格位置", {})
    return final_record
