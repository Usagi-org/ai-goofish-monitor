from typing import Optional

from src.pipeline.records import build_final_record
from src.services.item_analysis_dispatcher import ItemAnalysisJob
from src.utils import format_registration_days, safe_get


async def enrich_item_from_detail(item_data: dict, detail_json: dict) -> dict:
    item_do = await safe_get(detail_json, "data", "itemDO", default={})
    seller_do = await safe_get(detail_json, "data", "sellerDO", default={})

    reg_days_raw = await safe_get(seller_do, "userRegDay", default=0)
    registration_duration_text = format_registration_days(reg_days_raw)
    zhima_credit_text = await safe_get(seller_do, "zhimaLevelInfo", "levelName")

    image_infos = await safe_get(item_do, "imageInfos", default=[])
    if image_infos:
        all_image_urls = [img.get("url") for img in image_infos if img.get("url")]
        if all_image_urls:
            item_data["商品图片列表"] = all_image_urls
            item_data["商品主图链接"] = all_image_urls[0]

    item_data["“想要”人数"] = await safe_get(
        item_do,
        "wantCnt",
        default=item_data.get("“想要”人数", "NaN"),
    )
    item_data["浏览量"] = await safe_get(item_do, "browseCnt", default="-")
    user_id = await safe_get(seller_do, "sellerId")

    return {
        "item_data": item_data,
        "seller_do": seller_do,
        "user_id": user_id,
        "zhima_credit_text": zhima_credit_text,
        "registration_duration_text": registration_duration_text,
    }


def build_detail_analysis_job(
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
) -> ItemAnalysisJob:
    item_data = detail_enrichment["item_data"]
    final_record = build_final_record(
        keyword=keyword,
        task_name=task_name,
        item_data=item_data,
        current_market_items=current_market_items,
        historical_snapshots=historical_snapshots,
    )
    user_id = detail_enrichment["user_id"]

    return ItemAnalysisJob(
        keyword=keyword,
        task_name=task_name,
        decision_mode=decision_mode,
        analyze_images=analyze_images,
        prompt_text=prompt_text,
        keyword_rules=tuple(keyword_rules or []),
        final_record=final_record,
        seller_id=str(user_id) if user_id else None,
        zhima_credit_text=detail_enrichment["zhima_credit_text"],
        registration_duration_text=detail_enrichment[
            "registration_duration_text"
        ],
        notification_targets=notification_targets,
    )
