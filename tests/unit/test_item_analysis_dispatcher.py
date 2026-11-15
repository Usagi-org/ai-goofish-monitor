import asyncio

from src.services.item_analysis_dispatcher import (
    ItemAnalysisDispatcher,
    ItemAnalysisJob,
)


def test_item_analysis_dispatcher_uses_bounded_concurrency():
    active_ai_calls = 0
    max_active_ai_calls = 0
    saved_records = []
    notifications = []

    async def seller_loader(user_id: str):
        await asyncio.sleep(0.005)
        return {"卖家ID": user_id}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        nonlocal active_ai_calls, max_active_ai_calls
        active_ai_calls += 1
        max_active_ai_calls = max(max_active_ai_calls, active_ai_calls)
        await asyncio.sleep(0.03)
        active_ai_calls -= 1
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": f"推荐 {record['商品信息']['商品ID']}",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((item_data["商品ID"], reason))

    async def saver(record: dict, keyword: str):
        saved_records.append((keyword, record))
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=2,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        for index in range(3):
            dispatcher.submit(
                ItemAnalysisJob(
                    keyword="demo",
                    task_name="Demo",
                    decision_mode="ai",
                    analyze_images=False,
                    prompt_text="prompt",
                    keyword_rules=(),
                    final_record={
                        "商品信息": {"商品ID": str(index), "商品图片列表": []},
                        "卖家信息": {},
                    },
                    seller_id=f"seller-{index}",
                    zhima_credit_text="优秀",
                    registration_duration_text="来闲鱼1年",
                )
            )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 3
    assert len(saved_records) == 3
    assert len(notifications) == 3
    assert max_active_ai_calls == 2
    assert saved_records[0][1]["卖家信息"]["卖家ID"].startswith("seller-")


def test_item_analysis_dispatcher_supports_keyword_mode_without_ai():
    saved_records = []

    async def seller_loader(user_id: str):
        return {"卖家标签": "个人闲置"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        raise AssertionError("关键词模式不应下载图片")

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        raise AssertionError("关键词模式不应调用 AI")

    async def notifier(item_data: dict, reason: str):
        return None

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="demo",
                task_name="Demo",
                decision_mode="keyword",
                analyze_images=False,
                prompt_text="",
                keyword_rules=("个人闲置",),
                final_record={
                    "商品信息": {"商品ID": "1", "商品标题": "演示商品"},
                    "卖家信息": {},
                },
                seller_id="seller-1",
                zhima_credit_text="优秀",
                registration_duration_text="来闲鱼1年",
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert saved_records[0]["ai_analysis"]["analysis_source"] == "keyword"
    assert saved_records[0]["ai_analysis"]["is_recommended"] is True


def test_item_analysis_dispatcher_prefixes_notification_on_price_drop():
    notifications = []
    saved_records = []

    async def seller_loader(user_id: str):
        return {"卖家昵称": "测试卖家"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        return {
            "analysis_source": "ai",
            "is_recommended": record["商品信息"]["商品ID"] == "drop-rec",
            "reason": "成色好且降价到位",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((dict(item_data), reason))

    async def saver(record: dict, keyword: str):
        saved_records.append(record)
        return True

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="demo",
                task_name="Demo",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "商品信息": {"商品ID": "drop-rec", "商品图片列表": []},
                    "卖家信息": {},
                    "降价信息": {
                        "previous_price": 1000.0,
                        "current_price": 880.0,
                        "drop_amount": 120.0,
                        "drop_ratio": 0.12,
                    },
                },
                seller_id="seller-1",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼3年",
            )
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="demo",
                task_name="Demo",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "商品信息": {"商品ID": "drop-not-rec", "商品图片列表": []},
                    "卖家信息": {},
                    "降价信息": {
                        "previous_price": 1000.0,
                        "current_price": 850.0,
                        "drop_amount": 150.0,
                        "drop_ratio": 0.15,
                    },
                },
                seller_id="seller-2",
                zhima_credit_text="优秀",
                registration_duration_text="来闲鱼2年",
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert len(saved_records) == 2
    assert "降价信息" not in saved_records[0]["商品信息"]
    assert len(notifications) == 1
    notified_item, notified_reason = notifications[0]
    assert notified_item["商品ID"] == "drop-rec"
    assert notified_item["降价信息"]["drop_amount"] == 120.0
    assert notified_reason == "📉 降价重评 (¥1000 → ¥880，直降 ¥120) | 成色好且降价到位"


def test_item_analysis_dispatcher_skips_count_and_notification_when_save_rejected():
    notifications = []

    async def seller_loader(user_id: str):
        return {"卖家昵称": "测试卖家"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "推荐商品",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((item_data, reason))

    async def saver(record: dict, keyword: str):
        return False

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=saver,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword="demo",
                task_name="Demo",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "商品信息": {"商品ID": "rejected-1", "商品图片列表": []},
                    "卖家信息": {},
                },
                seller_id="seller-1",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼3年",
            )
        )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 0
    assert notifications == []
