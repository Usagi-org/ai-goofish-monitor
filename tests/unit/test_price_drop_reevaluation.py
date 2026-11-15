import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api.routes import results
from src.infrastructure.persistence.storage_names import build_result_filename
from src.scraper import build_dispatcher_saver
from src.services.item_analysis_dispatcher import (
    ItemAnalysisDispatcher,
    ItemAnalysisJob,
)
from src.services.result_storage_service import (
    _save_result_record_sync,
    delete_result_file_records,
    evaluate_price_drop,
    load_all_result_records,
    load_processed_item_states,
    load_processed_link_keys,
    save_result_record,
    update_item_status,
)


@pytest.fixture(autouse=True)
def _isolated_sqlite_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "app.sqlite3"))


def _make_record(
    *,
    keyword: str = "MacBook Air M1",
    item_id: str | None = "1001",
    price_display="¥3000",
    crawl_time: str = "2026-11-15T10:00:00",
    publish_time: str | None = "2026-11-15 09:00",
    title: str = "MacBook Air M1 8+256",
    link_id: str = "1001",
    is_recommended: bool = False,
    reason: str = "价格偏高",
    error: str | None = None,
    price_drop_info: dict | None = None,
) -> dict:
    item_info: dict = {
        "商品标题": title,
        "商品链接": f"https://www.goofish.com/item?id={link_id}&spm=a21ybx.search",
        "当前售价": price_display,
    }
    if item_id is not None:
        item_info["商品ID"] = item_id
    if publish_time is not None:
        item_info["发布时间"] = publish_time

    analysis: dict = {
        "analysis_source": "ai",
        "is_recommended": is_recommended,
        "reason": reason,
        "keyword_hit_count": 0,
    }
    if error is not None:
        analysis["error"] = error

    record: dict = {
        "爬取时间": crawl_time,
        "搜索关键字": keyword,
        "任务名称": "MacBook 监控",
        "商品信息": item_info,
        "卖家信息": {"卖家昵称": "个人卖家"},
        "ai_analysis": analysis,
    }
    if price_drop_info is not None:
        record["降价信息"] = price_drop_info
    return record


def test_database_isolation_never_touches_external_database_path(tmp_path):
    # 1. 验证当前测试由 autouse fixture 自动定向到 tmp_path/app.sqlite3
    assert _save_result_record_sync(_make_record(), "MacBook Air M1") is True
    assert (tmp_path / "app.sqlite3").exists()

    # 2. 先在外层设置外部哨兵路径，再调用真实 _isolated_sqlite_db fixture，确保若 fixture 失效必写入哨兵库并失败
    sentinel_external_db = tmp_path / "external_dir" / "prod.sqlite3"
    case_tmp = tmp_path / "case_dir"
    case_tmp.mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("APP_DATABASE_FILE", str(sentinel_external_db))
        _isolated_sqlite_db.__wrapped__(case_tmp, mp)
        assert _save_result_record_sync(_make_record(link_id="1002", item_id="1002"), "MacBook Air M1") is True

    assert (case_tmp / "app.sqlite3").exists()
    assert not sentinel_external_db.exists()


def test_evaluate_price_drop_default_thresholds_and_precision(monkeypatch):
    monkeypatch.delenv("PRICE_DROP_MIN_AMOUNT", raising=False)
    monkeypatch.delenv("PRICE_DROP_MIN_RATIO", raising=False)

    state = {"price": 1000.0, "status": "active", "is_recommended": False}

    # 闲鱼卖家改低 1 分钱擦亮：不触发
    assert evaluate_price_drop(state, "¥999.99") is None

    # 仅满足金额(>=10)但不满足比例(<2%)：2000 -> 1990 (0.5%)
    assert evaluate_price_drop({"price": 2000.0, "status": "active"}, "¥1990") is None

    # 仅满足比例(>=2%)但不满足金额(<10)：100 -> 95 (5%, 5元)
    assert evaluate_price_drop({"price": 100.0, "status": "active"}, "¥95") is None

    # 同时满足金额与比例：1000 -> 950 (直降 50 元，5%)
    result = evaluate_price_drop(state, "¥950")
    assert result == {
        "previous_price": 1000.0,
        "current_price": 950.0,
        "drop_amount": 50.0,
        "drop_ratio": 0.05,
    }

    # 浮点数精度边界：100.1 - 90.1 恰为 10.0；510 -> 499.8 恰为 2%
    assert evaluate_price_drop({"price": 100.1, "status": "active"}, "¥90.1") == {
        "previous_price": 100.1,
        "current_price": 90.1,
        "drop_amount": 10.0,
        "drop_ratio": round(10.0 / 100.1, 4),
    }
    assert evaluate_price_drop({"price": 510.0, "status": "active"}, "¥499.8") == {
        "previous_price": 510.0,
        "current_price": 499.8,
        "drop_amount": 10.2,
        "drop_ratio": 0.02,
    }


def test_evaluate_price_drop_env_override_and_non_finite_fallbacks(monkeypatch):
    monkeypatch.setenv("PRICE_DROP_MIN_AMOUNT", "50")
    monkeypatch.setenv("PRICE_DROP_MIN_RATIO", "0.05")

    state = {"price": 1000.0, "status": "active"}
    assert evaluate_price_drop(state, "¥960") is None
    assert evaluate_price_drop(state, "¥950") == {
        "previous_price": 1000.0,
        "current_price": 950.0,
        "drop_amount": 50.0,
        "drop_ratio": 0.05,
    }

    # 显式传参优先于环境变量
    assert evaluate_price_drop(state, "¥985", min_amount=10.0, min_ratio=0.01) == {
        "previous_price": 1000.0,
        "current_price": 985.0,
        "drop_amount": 15.0,
        "drop_ratio": 0.015,
    }

    # NaN / inf / 负数环境变量与显式阈值一律回退默认值 (10元 + 2%)
    for invalid_val in ("NaN", "inf", "-inf", "-0.05", "invalid"):
        monkeypatch.setenv("PRICE_DROP_MIN_AMOUNT", invalid_val)
        monkeypatch.setenv("PRICE_DROP_MIN_RATIO", invalid_val)
        assert evaluate_price_drop(state, "¥995") is None
        assert evaluate_price_drop(state, "¥980") == {
            "previous_price": 1000.0,
            "current_price": 980.0,
            "drop_amount": 20.0,
            "drop_ratio": 0.02,
        }

    assert (
        evaluate_price_drop(
            state,
            "¥995",
            min_amount=float("nan"),
            min_ratio=float("-inf"),
        )
        is None
    )
    assert (
        evaluate_price_drop(
            state,
            "¥995",
            min_amount=-10.0,
            min_ratio=-0.5,
        )
        is None
    )

    # 空状态、无法解析价格、<=0、同价、涨价均返回 None
    assert evaluate_price_drop(None, "¥900") is None
    assert evaluate_price_drop({}, "¥900") is None
    assert evaluate_price_drop({"price": None, "status": "active"}, "¥900") is None
    assert evaluate_price_drop({"price": 0, "status": "active"}, "¥900") is None
    assert evaluate_price_drop({"price": -10, "status": "active"}, "¥900") is None
    assert evaluate_price_drop(state, "暂无") is None
    assert evaluate_price_drop(state, "¥0") is None
    assert evaluate_price_drop(state, "¥1000") is None
    assert evaluate_price_drop(state, "¥1050") is None


def test_evaluate_price_drop_ignores_hidden_or_expired_items():
    assert (
        evaluate_price_drop(
            {"price": 3000.0, "status": "hidden", "is_recommended": False},
            "¥2000",
        )
        is None
    )
    assert (
        evaluate_price_drop(
            {"price": 3000.0, "status": "expired", "is_recommended": True},
            "¥2000",
        )
        is None
    )


def test_sqlite_price_drop_upsert_prevents_same_price_loop_and_respects_hidden():
    keyword = "MacBook Air M1"
    filename = build_result_filename(keyword)
    unique_key = "https://www.goofish.com/item?id=1001"

    first_record = _make_record(
        keyword=keyword,
        item_id="1001",
        price_display="¥3000",
        crawl_time="2026-11-15T10:00:00",
        publish_time="2026-11-15 09:00",
        is_recommended=False,
        reason="价格偏高",
    )
    assert _save_result_record_sync(first_record, keyword) is True
    assert load_processed_link_keys(keyword) == {unique_key}
    assert load_processed_item_states(keyword) == {
        unique_key: {
            "price": 3000.0,
            "status": "active",
            "is_recommended": False,
        }
    }

    # 普通重复提交（即使价格写低，但无降价信息）与同价/涨价一律返回 False 不覆盖
    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="1001",
                price_display="¥2500",
                crawl_time="2026-11-15T11:00:00",
                is_recommended=True,
                reason="缺少降价标记的普通重复提交",
            ),
            keyword,
        )
        is False
    )
    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="1001",
                price_display="¥3000",
                crawl_time="2026-11-15T11:10:00",
                is_recommended=True,
                price_drop_info={
                    "previous_price": 3000.0,
                    "current_price": 3000.0,
                    "drop_amount": 0.0,
                    "drop_ratio": 0.0,
                },
            ),
            keyword,
        )
        is False
    )

    states_after_noop = load_processed_item_states(keyword)
    assert states_after_noop[unique_key]["price"] == 3000.0
    assert states_after_noop[unique_key]["is_recommended"] is False

    # 真实降价重评（¥3000 -> ¥2650）
    drop_info = evaluate_price_drop(states_after_noop[unique_key], "¥2650")
    assert drop_info == {
        "previous_price": 3000.0,
        "current_price": 2650.0,
        "drop_amount": 350.0,
        "drop_ratio": 0.1167,
    }
    dropped_record = _make_record(
        keyword=keyword,
        item_id=None,
        price_display="¥2650",
        crawl_time="2026-11-15T12:00:00",
        publish_time=None,
        title="MacBook Air M1 急出降价",
        is_recommended=True,
        reason="降价后性价比突出",
        price_drop_info=drop_info,
    )
    assert _save_result_record_sync(dropped_record, keyword) is True

    states_after_drop = load_processed_item_states(keyword)
    assert states_after_drop[unique_key] == {
        "price": 2650.0,
        "status": "active",
        "is_recommended": True,
    }
    assert evaluate_price_drop(states_after_drop[unique_key], "¥2650") is None

    # 手动标为 hidden 后，再次降价也不得更新，返回 False
    assert asyncio.run(update_item_status(filename, "1001", "hidden")) is True
    hidden_drop_attempt = _make_record(
        keyword=keyword,
        item_id="1001",
        price_display="¥2000",
        crawl_time="2026-11-15T13:00:00",
        is_recommended=False,
        reason="隐藏商品不应被覆盖",
        price_drop_info={
            "previous_price": 2650.0,
            "current_price": 2000.0,
            "drop_amount": 650.0,
            "drop_ratio": 0.2453,
        },
    )
    assert _save_result_record_sync(hidden_drop_attempt, keyword) is False

    final_records = asyncio.run(
        load_all_result_records(
            filename,
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            include_hidden=True,
        )
    )
    assert len(final_records) == 1
    assert final_records[0]["爬取时间"] == "2026-11-15T12:00:00"
    assert json.dumps(final_records[0]["降价信息"], sort_keys=True) == json.dumps(
        drop_info, sort_keys=True
    )


def test_sqlite_revalidates_concurrent_1000_to_900_to_899_and_recomputes_true_drop():
    keyword = "Sony A7M4"
    unique_key = "https://www.goofish.com/item?id=2001"
    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="2001",
                link_id="2001",
                price_display="¥1000",
                is_recommended=False,
            ),
            keyword,
        )
        is True
    )

    # 任务 A 先把价格从 1000 更新到 900
    drop_a = _make_record(
        keyword=keyword,
        item_id="2001",
        link_id="2001",
        price_display="¥900",
        crawl_time="2026-11-15T11:00:00",
        is_recommended=True,
        reason="降到900可入",
        price_drop_info={
            "previous_price": 1000.0,
            "current_price": 900.0,
            "drop_amount": 100.0,
            "drop_ratio": 0.1,
        },
    )
    assert _save_result_record_sync(drop_a, keyword) is True

    # 并发任务 B 仍基于旧快照 1000 尝试提交 899（相对库内最新 900 仅降 1 元，未达双阈值）-> 拦截！
    stale_899 = _make_record(
        keyword=keyword,
        item_id="2001",
        link_id="2001",
        price_display="¥899",
        crawl_time="2026-11-15T11:01:00",
        is_recommended=True,
        reason="擦亮降1元",
        price_drop_info={
            "previous_price": 1000.0,
            "current_price": 899.0,
            "drop_amount": 101.0,
            "drop_ratio": 0.101,
        },
    )
    assert _save_result_record_sync(stale_899, keyword) is False
    assert load_processed_item_states(keyword)[unique_key]["price"] == 900.0

    # 并发任务 C 仍携带旧快照 1000，但真实现价为 850（相对 900 仍满足 >=10 且 >=2%）-> 放行并重写为 900->850
    stale_850 = _make_record(
        keyword=keyword,
        item_id="2001",
        link_id="2001",
        price_display="¥850",
        crawl_time="2026-11-15T11:02:00",
        is_recommended=True,
        reason="继续大降",
        price_drop_info={
            "previous_price": 1000.0,
            "current_price": 850.0,
            "drop_amount": 150.0,
            "drop_ratio": 0.15,
        },
    )
    assert _save_result_record_sync(stale_850, keyword) is True
    assert stale_850["降价信息"] == {
        "previous_price": 900.0,
        "current_price": 850.0,
        "drop_amount": 50.0,
        "drop_ratio": 0.0556,
    }


def test_sqlite_rejects_zero_negative_and_nan_prices():
    keyword = "iPad Pro"
    unique_key = "https://www.goofish.com/item?id=3001"
    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="3001",
                link_id="3001",
                price_display="¥2000",
                is_recommended=True,
            ),
            keyword,
        )
        is True
    )

    for bad_price in ("¥0", 0, -1, "¥-1", float("nan"), "暂无", None):
        attempt = _make_record(
            keyword=keyword,
            item_id="3001",
            link_id="3001",
            price_display=bad_price,
            crawl_time="2026-11-15T12:00:00",
            is_recommended=False,
            price_drop_info={
                "previous_price": 2000.0,
                "current_price": 1500.0,
                "drop_amount": 500.0,
                "drop_ratio": 0.25,
            },
        )
        assert _save_result_record_sync(attempt, keyword) is False

    assert load_processed_item_states(keyword)[unique_key] == {
        "price": 2000.0,
        "status": "active",
        "is_recommended": True,
    }


def test_ai_failure_preserves_previous_recommendation_and_allows_next_round_retry():
    keyword = "Mac mini M4"
    unique_key = "https://www.goofish.com/item?id=4001"

    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="4001",
                link_id="4001",
                price_display="¥3500",
                is_recommended=True,
                reason="首轮优质推荐",
            ),
            keyword,
        )
        is True
    )

    notifications = []
    should_fail_ai = True

    async def seller_loader(user_id: str):
        return {"卖家昵称": "靠谱卖家"}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        if should_fail_ai:
            raise RuntimeError("upstream 502")
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "恢复后复评超值",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((dict(item_data), reason))

    async def run_once(prompt_text: str = "prompt"):
        states = load_processed_item_states(keyword)
        drop_info = evaluate_price_drop(states[unique_key], "¥3100")
        assert drop_info is not None

        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=save_result_record,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword=keyword,
                task_name="Mac mini 监控",
                decision_mode="ai",
                analyze_images=False,
                prompt_text=prompt_text,
                keyword_rules=(),
                final_record={
                    "爬取时间": "2026-11-15T14:00:00",
                    "搜索关键字": keyword,
                    "任务名称": "Mac mini 监控",
                    "商品信息": {
                        "商品ID": "4001",
                        "商品标题": "Mac mini M4 16+256",
                        "商品链接": f"{unique_key}&spm=a21ybx.search",
                        "当前售价": "¥3100",
                        "商品图片列表": [],
                    },
                    "卖家信息": {},
                    "降价信息": drop_info,
                },
                seller_id="seller-4001",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼4年",
            )
        )
        await dispatcher.join()
        return dispatcher

    # 第 1 次重评：AI 抛异常 -> 不覆盖原推荐、原价格仍保持 3500
    d1 = asyncio.run(run_once(prompt_text="prompt"))
    assert d1.completed_count == 0
    assert notifications == []
    assert load_processed_item_states(keyword)[unique_key] == {
        "price": 3500.0,
        "status": "active",
        "is_recommended": True,
    }

    # 第 2 次重评：未配置 prompt -> 同样不覆盖
    d2 = asyncio.run(run_once(prompt_text=""))
    assert d2.completed_count == 0
    assert notifications == []
    assert load_processed_item_states(keyword)[unique_key]["price"] == 3500.0

    # 第 3 次重评：AI 恢复正常 -> 成功针对 3500 -> 3100 重评更新并推送降价通知
    should_fail_ai = False
    d3 = asyncio.run(run_once(prompt_text="prompt"))
    assert d3.completed_count == 1
    assert load_processed_item_states(keyword)[unique_key] == {
        "price": 3100.0,
        "status": "active",
        "is_recommended": True,
    }
    assert len(notifications) == 1
    assert (
        notifications[0][1]
        == "📉 降价重评 (¥3500 → ¥3100，直降 ¥400) | 恢复后复评超值"
    )


def test_mid_flight_hidden_item_sends_zero_notifications():
    keyword = "Nintendo Switch"
    filename = build_result_filename(keyword)
    unique_key = "https://www.goofish.com/item?id=5001"

    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="5001",
                link_id="5001",
                price_display="¥1200",
                is_recommended=False,
            ),
            keyword,
        )
        is True
    )

    notifications = []
    drop_info = evaluate_price_drop(
        load_processed_item_states(keyword)[unique_key],
        "¥999",
    )
    assert drop_info is not None

    async def seller_loader(user_id: str):
        return {}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        # 模拟用户在后台 AI 分析期间手动隐藏了该商品
        await update_item_status(filename, "5001", "hidden")
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "虽然便宜但用户刚隐藏",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((item_data, reason))

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=save_result_record,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword=keyword,
                task_name="Switch 监控",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "爬取时间": "2026-11-15T15:00:00",
                    "搜索关键字": keyword,
                    "任务名称": "Switch 监控",
                    "商品信息": {
                        "商品ID": "5001",
                        "商品标题": "Switch OLED",
                        "商品链接": f"{unique_key}&spm=a21ybx.search",
                        "当前售价": "¥999",
                        "商品图片列表": [],
                    },
                    "卖家信息": {},
                    "降价信息": drop_info,
                },
                seller_id="seller-5001",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼2年",
            )
        )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 0
    assert notifications == []
    assert load_processed_item_states(keyword)[unique_key] == {
        "price": 1200.0,
        "status": "hidden",
        "is_recommended": False,
    }


def test_publish_time_and_item_id_consistent_between_sql_sort_and_results_api():
    keyword = "demo"
    filename = build_result_filename(keyword)

    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="6001",
                link_id="6001",
                price_display="¥2000",
                publish_time="2026-11-15 10:30",
                crawl_time="2026-11-15T10:35:00",
            ),
            keyword,
        )
        is True
    )
    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="6002",
                link_id="6002",
                price_display="¥1900",
                publish_time="2026-11-15 09:30",
                crawl_time="2026-11-15T10:40:00",
            ),
            keyword,
        )
        is True
    )

    # 6001 降价重评时，真实列表解析器缺失字段会产生占位符 '未知ID' / '未知时间'
    dropped_6001 = _make_record(
        keyword=keyword,
        item_id="未知ID",
        link_id="6001",
        price_display="¥1750",
        publish_time="未知时间",
        crawl_time="2026-11-15T12:00:00",
        is_recommended=True,
        reason="降价可入",
        price_drop_info={
            "previous_price": 2000.0,
            "current_price": 1750.0,
            "drop_amount": 250.0,
            "drop_ratio": 0.125,
        },
    )
    assert _save_result_record_sync(dropped_6001, keyword) is True

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    resp = client.get(
        f"/api/results/{filename}",
        params={"sort_by": "publish_time", "sort_order": "desc"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [it["商品信息"]["商品ID"] for it in items] == ["6001", "6002"]
    assert items[0]["商品信息"]["发布时间"] == "2026-11-15 10:30"
    assert items[0]["商品信息"]["当前售价"] == "¥1750"

    # 按保留的原商品 ID 隐藏仍可正常命中
    assert asyncio.run(update_item_status(filename, "6001", "hidden")) == 1


def test_mid_flight_deleted_results_are_not_resurrected_by_price_drop_reevaluation():
    keyword = "PS5 Pro"
    filename = build_result_filename(keyword)
    unique_key = "https://www.goofish.com/item?id=8801"

    assert (
        _save_result_record_sync(
            _make_record(
                keyword=keyword,
                item_id="8801",
                link_id="8801",
                price_display="¥100",
                is_recommended=False,
            ),
            keyword,
        )
        is True
    )
    drop_info = evaluate_price_drop(
        load_processed_item_states(keyword)[unique_key],
        "¥80",
    )
    assert drop_info is not None
    notifications = []

    async def seller_loader(user_id: str):
        return {}

    async def image_downloader(product_id: str, image_urls: list[str], task_name: str):
        return []

    async def ai_analyzer(record: dict, image_paths: list[str], prompt_text: str):
        # 模拟用户在 AI 重评期间删除了整个结果集
        deleted = await delete_result_file_records(filename)
        assert deleted == 1
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "降价好价",
            "keyword_hit_count": 0,
        }

    async def notifier(item_data: dict, reason: str):
        notifications.append((item_data, reason))

    async def run():
        dispatcher = ItemAnalysisDispatcher(
            concurrency=1,
            skip_ai_analysis=False,
            seller_loader=seller_loader,
            image_downloader=image_downloader,
            ai_analyzer=ai_analyzer,
            notifier=notifier,
            saver=save_result_record,
        )
        dispatcher.submit(
            ItemAnalysisJob(
                keyword=keyword,
                task_name="PS5 监控",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                final_record={
                    "爬取时间": "2026-11-15T16:00:00",
                    "搜索关键字": keyword,
                    "任务名称": "PS5 监控",
                    "商品信息": {
                        "商品ID": "8801",
                        "商品标题": "PS5 光驱版",
                        "商品链接": f"{unique_key}&spm=a21ybx.search",
                        "当前售价": "¥80",
                        "商品图片列表": [],
                    },
                    "卖家信息": {},
                    "降价信息": drop_info,
                },
                seller_id="seller-8801",
                zhima_credit_text="极好",
                registration_duration_text="来闲鱼3年",
            )
        )
        await dispatcher.join()
        return dispatcher

    dispatcher = asyncio.run(run())
    assert dispatcher.completed_count == 0
    assert notifications == []
    assert load_processed_item_states(keyword) == {}
    assert load_processed_link_keys(keyword) == set()


def test_build_dispatcher_saver_updates_memory_only_when_db_save_succeeds():
    unique_key = "https://www.goofish.com/item?id=7001"
    processed_links = {unique_key}
    processed_item_states = {
        unique_key: {"price": 1000.0, "status": "active", "is_recommended": False}
    }
    in_flight_links = {unique_key}
    should_save = False

    async def fake_saver(rec: dict, kw: str) -> bool:
        return should_save

    wrapped_saver = build_dispatcher_saver(
        saver_fn=fake_saver,
        processed_links=processed_links,
        processed_item_states=processed_item_states,
        in_flight_links=in_flight_links,
    )

    candidate = _make_record(
        item_id="7001",
        link_id="7001",
        price_display="¥850",
        is_recommended=True,
    )

    # 保存返回 False：内存旧价格保持 1000 不变，但 in_flight 正常释放
    assert asyncio.run(wrapped_saver(candidate, "MacBook Air M1")) is False
    assert unique_key not in in_flight_links
    assert processed_item_states[unique_key] == {
        "price": 1000.0,
        "status": "active",
        "is_recommended": False,
    }

    # 保存返回 True：内存价格与推荐状态才同步更新，且 in_flight 释放
    in_flight_links.add(unique_key)
    should_save = True
    assert asyncio.run(wrapped_saver(candidate, "MacBook Air M1")) is True
    assert unique_key not in in_flight_links
    assert processed_item_states[unique_key] == {
        "price": 850.0,
        "status": "active",
        "is_recommended": True,
    }
