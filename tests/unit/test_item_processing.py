from src.pipeline.item_processing import (
    build_item_progress_message,
    is_processed_item,
    normalize_item_candidate,
    prepare_detail_analysis_job_kwargs,
    should_stop_for_debug_limit,
)
from src.utils import get_link_unique_key


def test_should_stop_for_debug_limit_only_when_positive_limit_reached() -> None:
    assert should_stop_for_debug_limit(0, 10) is False
    assert should_stop_for_debug_limit(3, 2) is False
    assert should_stop_for_debug_limit(3, 3) is True
    assert should_stop_for_debug_limit(3, 4) is True


def test_is_processed_item_uses_link_unique_key() -> None:
    item_data = {"商品链接": "https://www.goofish.com/item?id=123&spm=a"}
    processed_links = {get_link_unique_key(item_data["商品链接"])}

    assert is_processed_item(item_data, processed_links) is True
    assert is_processed_item({"商品链接": "https://www.goofish.com/item?id=456"}, processed_links) is False


def test_normalize_item_candidate_preserves_representative_fields() -> None:
    item_data = {
        "商品链接": "https://www.goofish.com/item?id=123&spm=a",
        "商品标题": "MacBook Air M1",
        "商品ID": "123",
        "商品价格": "2999",
        "“想要”人数": "8",
    }

    candidate = normalize_item_candidate(item_data, processed_links=set())

    assert candidate.item_data is item_data
    assert candidate.item_data == item_data
    assert candidate.unique_key == "https://www.goofish.com/item?id=123"
    assert candidate.is_processed is False
    assert candidate.title == "MacBook Air M1"
    assert candidate.link == "https://www.goofish.com/item?id=123&spm=a"


def test_normalize_item_candidate_missing_link_keeps_old_key_error_semantics() -> None:
    try:
        normalize_item_candidate({"商品标题": "缺少链接"}, processed_links=set())
    except KeyError as exc:
        assert exc.args == ("商品链接",)
    else:
        raise AssertionError("expected missing 商品链接 to raise KeyError")


def test_normalize_item_candidate_marks_processed_with_same_unique_key_behavior() -> None:
    item_data = {"商品链接": "https://www.goofish.com/item?id=123&spm=a"}
    processed_links = {"https://www.goofish.com/item?id=123"}

    candidate = normalize_item_candidate(item_data, processed_links)

    assert candidate.unique_key == get_link_unique_key(item_data["商品链接"])
    assert candidate.is_processed is True


def test_prepare_detail_analysis_job_kwargs_preserves_notification_targets() -> None:
    detail_enrichment = {"item_data": {"商品标题": "A7M4"}}
    current_market_items = [{"商品标题": "A7M4"}]
    historical_snapshots = [{"item_id": "1"}]
    keyword_rules = [{"include": "验货宝"}]
    notification_targets = [{"channel": "wecom-app", "agent_id": "1000001"}]

    kwargs = prepare_detail_analysis_job_kwargs(
        keyword="相机",
        task_name="相机任务",
        detail_enrichment=detail_enrichment,
        current_market_items=current_market_items,
        historical_snapshots=historical_snapshots,
        decision_mode="keyword",
        analyze_images=True,
        prompt_text="prompt",
        keyword_rules=keyword_rules,
        notification_targets=notification_targets,
    )

    assert kwargs == {
        "keyword": "相机",
        "task_name": "相机任务",
        "detail_enrichment": detail_enrichment,
        "current_market_items": current_market_items,
        "historical_snapshots": historical_snapshots,
        "decision_mode": "keyword",
        "analyze_images": True,
        "prompt_text": "prompt",
        "keyword_rules": keyword_rules,
        "notification_targets": notification_targets,
    }
    assert kwargs["notification_targets"] is notification_targets


def test_build_item_progress_message_preserves_existing_formats() -> None:
    title = "这是一个很长很长的商品标题用于测试截断逻辑"

    assert build_item_progress_message(1, 5, title, skipped=True) == (
        "[页内进度 1/5] 商品 '这是一个很长很长的商品标题用于测试截断逻...' 已存在，跳过。"
    )
    assert build_item_progress_message(2, 5, title) == (
        "[页内进度 2/5] 发现新商品，获取详情: 这是一个很长很长的商品标题用于测试截断逻辑..."
    )
