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


def test_item_analysis_dispatcher_exclude_keywords_skips_seller_images_and_ai():
    saved_records = []

    async def seller_loader(user_id: str):
        raise AssertionError("命中前置排除词时不应采集卖家信息")

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        raise AssertionError("命中前置排除词时不应下载商品图片")

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        raise AssertionError("命中前置排除词时不应调用 AI 分析")

    async def notifier(item_data: dict, reason: str):
        raise AssertionError("命中前置排除词时不应发送推荐通知")

    async def saver(record: dict, keyword: str):
        saved_records.append((keyword, record))
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
                keyword="固态硬盘",
                task_name="SSD 监控",
                decision_mode="ai",
                analyze_images=True,
                prompt_text="prompt",
                keyword_rules=(),
                exclude_keywords=("sata", "暗病"),
                final_record={
                    "商品信息": {
                        "商品ID": "99",
                        "商品标题": "三星 1T 固态硬盘",
                        "商品描述": "闲置出，接口为 SATA 协议，正常读写",
                        "商品图片列表": ["https://example.com/1.jpg"],
                    },
                    "卖家信息": {},
                },
                seller_id="seller-99",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼3年",
            )
        )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 1
    assert len(saved_records) == 1
    saved_keyword, saved_record = saved_records[0]
    assert saved_keyword == "固态硬盘"
    assert saved_record["卖家信息"] == {
        "卖家芝麻信用": "极好",
        "卖家注册时长": "来闲鱼3年",
    }
    assert saved_record["ai_analysis"] == {
        "analysis_source": "exclude_rule",
        "is_recommended": False,
        "reason": "命中前置排除词：sata",
        "matched_exclude_keywords": ["sata"],
        "keyword_hit_count": 0,
    }


def test_item_analysis_dispatcher_exclude_word_boundary_does_not_block_longer_token():
    ai_called = False
    saved_records = []

    async def seller_loader(user_id: str):
        return {"卖家ID": user_id}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        nonlocal ai_called
        ai_called = True
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "NVMe 正常好价",
            "keyword_hit_count": 0,
        }

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
                keyword="固态硬盘",
                task_name="SSD 监控",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                exclude_keywords=("sata",),
                final_record={
                    "商品信息": {
                        "商品ID": "100",
                        "商品标题": "三星 980 Pro NVMe",
                        "商品描述": "附赠一根主板 sata3 数据线",
                        "商品图片列表": [],
                    },
                    "卖家信息": {},
                },
                seller_id="seller-100",
                zhima_credit_text="优秀",
                registration_duration_text="来闲鱼2年",
            )
        )
        await dispatcher.join()

    asyncio.run(run())
    assert ai_called is True
    assert saved_records[0]["ai_analysis"]["analysis_source"] == "ai"
    assert saved_records[0]["ai_analysis"]["is_recommended"] is True


def test_item_analysis_dispatcher_ignores_urls_images_and_cross_field_phrases():
    saved_records = []

    async def seller_loader(user_id: str):
        return {"卖家昵称": "正常个人卖家"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "未误触发排除词",
            "keyword_hit_count": 0,
        }

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
        for mode in ("ai", "keyword"):
            dispatcher.submit(
                ItemAnalysisJob(
                    keyword="iphone",
                    task_name="iPhone 监控",
                    decision_mode=mode,
                    analyze_images=False,
                    prompt_text="prompt",
                    keyword_rules=("iphone",),
                    exclude_keywords=("id", "jpg", "goofish", "101", "pro max"),
                    final_record={
                        "商品信息": {
                            "商品ID": "101",
                            "商品标题": "iPhone 15 Pro",
                            "商品标签": ["Max", "包邮"],
                            "商品描述": "自用国行无拆修",
                            "商品链接": "https://www.goofish.com/item?id=101",
                            "商品图片列表": ["https://img.alicdn.com/photo_101.jpg"],
                        },
                        "卖家信息": {},
                    },
                    seller_id="seller-101",
                    zhima_credit_text="极好",
                    registration_duration_text="来闲鱼4年",
                )
            )
        await dispatcher.join()

    asyncio.run(run())
    assert len(saved_records) == 2
    assert {r["ai_analysis"]["analysis_source"] for r in saved_records} == {"ai", "keyword"}
    assert all(r["ai_analysis"]["is_recommended"] is True for r in saved_records)
