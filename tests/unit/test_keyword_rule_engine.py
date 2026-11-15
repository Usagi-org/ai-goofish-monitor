import asyncio

from src.keyword_rule_engine import (
    build_search_text,
    evaluate_keyword_rules,
    match_exclude_keywords,
    match_exclude_keywords_in_fields,
    normalize_keyword_values,
)
from src.scraper import match_item_exclude_keywords, recheck_excluded_item
from src.services.result_storage_service import (
    load_all_result_records,
    load_excluded_item_records,
    load_processed_link_keys,
    save_result_record,
)


def _sample_record():
    return {
        "商品信息": {
            "商品标题": "Sony A7M4 全画幅相机",
            "当前售价": "10000",
            "商品标签": ["验货宝", "包邮"],
        },
        "卖家信息": {
            "卖家昵称": "摄影器材店",
            "卖家个性签名": "可验机，支持同城面交",
        },
    }


def test_build_search_text_contains_product_and_seller_fields():
    text = build_search_text(_sample_record())
    assert "sony a7m4" in text
    assert "摄影器材店" in text
    assert "支持同城面交" in text


def test_keyword_rules_or_match_any_keyword():
    text = build_search_text(_sample_record())
    result = evaluate_keyword_rules(["a7m4", "佳能"], text)
    assert result["is_recommended"] is True
    assert result["analysis_source"] == "keyword"
    assert result["keyword_hit_count"] == 1
    assert result["matched_keywords"] == ["a7m4"]


def test_keyword_rules_count_multiple_hits():
    text = build_search_text(_sample_record())
    result = evaluate_keyword_rules(["a7m4", "验货宝", "摄影器材店"], text)
    assert result["is_recommended"] is True
    assert result["keyword_hit_count"] == 3


def test_keyword_rules_case_insensitive_contains():
    text = build_search_text(_sample_record())
    result = evaluate_keyword_rules(["SONY", "A7M4"], text)
    assert result["is_recommended"] is True
    assert result["keyword_hit_count"] == 2


def test_keyword_rules_no_match():
    text = build_search_text(_sample_record())
    result = evaluate_keyword_rules(["佳能", "单反"], text)
    assert result["is_recommended"] is False
    assert result["keyword_hit_count"] == 0


def test_keyword_rules_do_not_partially_match_alphanumeric_prefixes():
    result = evaluate_keyword_rules(["q1"], "富士 q1r5 旗舰相机")
    assert result["is_recommended"] is False
    assert result["keyword_hit_count"] == 0


def test_keyword_rules_still_match_full_alphanumeric_token():
    result = evaluate_keyword_rules(["q1r5"], "富士 q1r5 旗舰相机")
    assert result["is_recommended"] is True
    assert result["keyword_hit_count"] == 1


def test_match_exclude_keywords_respects_ascii_word_boundary_and_dedups():
    assert match_exclude_keywords(["sata", "q1"], "三星 sata3 固态硬盘 q1r5") == []
    assert match_exclude_keywords(["sata", "q1"], "esata 转接卡") == []
    assert match_exclude_keywords("SATA, 瑕疵\nsata", "三星 sata接口 微瑕疵") == ["sata", "瑕疵"]


def test_evaluate_keyword_rules_short_circuits_on_exclude_keywords():
    text = build_search_text(_sample_record())
    result = evaluate_keyword_rules(["a7m4", "验货宝"], f"{text} 轻微拆修", exclude_keywords=["瑕疵", "拆修"])
    assert result["is_recommended"] is False
    assert result["matched_exclude_keywords"] == ["拆修"]
    assert result["matched_keywords"] == []
    assert result["keyword_hit_count"] == 0
    assert result["reason"] == "命中排除词：拆修"


def test_evaluate_keyword_rules_keeps_legacy_keys_when_exclude_not_passed():
    result = evaluate_keyword_rules(["a7m4"], "Sony A7M4 相机")
    assert "matched_exclude_keywords" not in result
    assert result["is_recommended"] is True


def test_match_item_exclude_keywords_checks_card_fields_only():
    card = {
        "商品ID": "10001",
        "商品标题": "iPhone 15 Pro 国行",
        "商品标签": ["Max容量", "Max", "包邮", "仅自提"],
        "商品链接": "https://www.goofish.com/item?id=10001",
        "商品图片列表": ["https://img.alicdn.com/item_10001.jpg"],
    }
    assert match_item_exclude_keywords(card, ["仅自提"]) == ["仅自提"]
    assert match_item_exclude_keywords(card, ["id", "jpg", "goofish", "10001", "pro max"]) == []
    assert match_item_exclude_keywords({"商品标题": "三星 1T 固态 sata3"}, ["sata"]) == []


def test_normalize_keyword_values_and_field_isolation():
    assert normalize_keyword_values("SATA, 坏盘\nsata ,  Pro   Max , pro max") == [
        "SATA",
        "坏盘",
        "Pro   Max",
    ]
    assert normalize_keyword_values(None) == []
    assert match_exclude_keywords_in_fields(["pro max"], ["iPhone 15 Pro", ["Max", "包邮"]]) == []
    assert match_exclude_keywords_in_fields(["pro max"], [["Pro", "Max"]]) == []
    assert match_exclude_keywords_in_fields(["pro max"], ["iPhone 15 Pro Max"]) == ["pro max"]


def test_excluded_item_recheck_and_upsert_replaces_exclude_rule_record(tmp_path, monkeypatch):
    db_file = tmp_path / "results.sqlite3"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(db_file))

    link = "https://www.goofish.com/item?id=10088&spm=a21ybx"
    unique_key = "https://www.goofish.com/item?id=10088"

    excluded_record = {
        "爬取时间": "2026-11-15T10:05:00",
        "搜索关键字": "固态硬盘",
        "任务名称": "任务A-排SATA",
        "商品信息": {
            "商品ID": "10088",
            "商品标题": "三星 1T 固态硬盘",
            "商品描述": "闲置接口为 SATA 协议",
            "当前售价": "¥399",
            "发布时间": "2026-11-15 10:00",
            "商品链接": link,
        },
        "卖家信息": {"卖家芝麻信用": "极好", "卖家注册时长": "来闲鱼3年"},
        "ai_analysis": {
            "analysis_source": "exclude_rule",
            "is_recommended": False,
            "reason": "命中前置排除词：sata",
            "matched_exclude_keywords": ["sata"],
            "keyword_hit_count": 0,
        },
    }
    assert asyncio.run(save_result_record(excluded_record, "固态硬盘")) is True
    assert unique_key in load_processed_link_keys("固态硬盘")

    excluded_map = load_excluded_item_records("固态硬盘")
    assert unique_key in excluded_map

    list_card = {
        "商品ID": "10088",
        "商品标题": "三星 1T 固态硬盘",
        "商品标签": ["包邮"],
        "商品链接": link,
    }
    # 同一排除词任务复核仍命中缓存描述，跳过详情采集
    assert recheck_excluded_item(excluded_map[unique_key], list_card, ["sata"]) == ["sata"]
    # 无排除词的同关键词任务或删除排除词后复核不再命中，允许重抓
    assert recheck_excluded_item(excluded_map[unique_key], list_card, []) == []

    reanalyzed_record = {
        "爬取时间": "2026-11-15T10:15:00",
        "搜索关键字": "固态硬盘",
        "任务名称": "任务B-不排SATA",
        "商品信息": {
            "商品ID": "未知ID",
            "商品标题": "三星 1T 固态硬盘",
            "商品描述": "闲置接口为 SATA 协议",
            "当前售价": "¥380",
            "发布时间": "未知时间",
            "商品链接": link,
        },
        "卖家信息": {"卖家昵称": "靠谱个人卖家"},
        "ai_analysis": {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "价格实惠，推荐购买",
            "keyword_hit_count": 0,
        },
    }
    assert asyncio.run(save_result_record(reanalyzed_record, "固态硬盘")) is True
    assert load_excluded_item_records("固态硬盘") == {}

    records = asyncio.run(
        load_all_result_records(
            "固态硬盘_full_data.jsonl",
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
        )
    )
    assert len(records) == 1
    assert records[0]["ai_analysis"]["analysis_source"] == "ai"
    assert records[0]["ai_analysis"]["is_recommended"] is True
    assert records[0]["商品信息"]["发布时间"] == "2026-11-15 10:00"
    assert records[0]["商品信息"]["商品ID"] == "10088"

    # 已成为正常 AI 分析结果后，后续 exclude_rule 记录不应反向覆盖，且返回 False
    assert asyncio.run(save_result_record(excluded_record, "固态硬盘")) is False
    records_after = asyncio.run(
        load_all_result_records(
            "固态硬盘_full_data.jsonl",
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
        )
    )
    assert len(records_after) == 1
    assert records_after[0]["ai_analysis"]["analysis_source"] == "ai"


def test_excluded_item_hidden_expired_and_ai_failure_protections(tmp_path, monkeypatch):
    from src.services.item_analysis_dispatcher import (
        ItemAnalysisDispatcher,
        ItemAnalysisJob,
    )
    from src.services.result_storage_service import (
        load_all_result_records,
        load_excluded_item_records,
        save_result_record,
        update_item_status,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "app.sqlite3"))

    def make_excluded(item_id: str, price: str = "¥100") -> dict:
        return {
            "爬取时间": "2026-11-15T10:05:00",
            "搜索关键字": "固态硬盘",
            "任务名称": "SSD 监控",
            "商品信息": {
                "商品ID": item_id,
                "商品标题": f"固态硬盘 {item_id}",
                "商品描述": "闲置 SATA 接口",
                "当前售价": price,
                "发布时间": "2026-11-15 10:00",
                "商品链接": f"https://www.goofish.com/item?id={item_id}&spm=a21ybx.search",
            },
            "卖家信息": {},
            "ai_analysis": {
                "analysis_source": "exclude_rule",
                "is_recommended": False,
                "reason": "命中前置排除词：sata",
                "matched_exclude_keywords": ["sata"],
                "keyword_hit_count": 0,
            },
        }

    # 1. hidden 与 expired 的历史 exclude_rule 记录不应进入候选查询，更不应被改写或触发通知
    for idx, status in enumerate(("hidden", "expired"), start=1):
        item_id = f"200{idx}"
        assert asyncio.run(save_result_record(make_excluded(item_id), "固态硬盘")) is True
        assert asyncio.run(update_item_status("固态硬盘_full_data.jsonl", item_id, status)) == 1

    assert load_excluded_item_records("固态硬盘") == {}

    notifications = []

    async def run_dispatcher_for(item_id: str, ai_payload: dict | None):
        async def seller_loader(_uid: str):
            return {}

        async def image_downloader(_pid: str, _urls: list[str], _task: str):
            return []

        async def ai_analyzer(_rec: dict, _imgs: list[str], _prompt: str):
            return ai_payload

        async def notifier(item_data: dict, reason: str):
            notifications.append((item_data["商品ID"], reason))

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
                keyword="固态硬盘",
                task_name="SSD 监控",
                decision_mode="ai",
                analyze_images=False,
                prompt_text="prompt",
                keyword_rules=(),
                exclude_keywords=(),
                final_record={
                    "爬取时间": "2026-11-15T11:00:00",
                    "搜索关键字": "固态硬盘",
                    "任务名称": "SSD 监控",
                    "商品信息": {
                        "商品ID": item_id,
                        "商品标题": f"固态硬盘 {item_id}",
                        "商品描述": "闲置 SATA 接口",
                        "当前售价": "¥80",
                        "商品链接": f"https://www.goofish.com/item?id={item_id}&spm=a21ybx.search",
                        "商品图片列表": [],
                    },
                    "卖家信息": {},
                },
                seller_id="s1",
                zhima_credit_text="极好",
                registration_duration_text="3年",
            )
        )
        await dispatcher.join()
        return dispatcher

    for item_id in ("2001", "2002"):
        d = asyncio.run(
            run_dispatcher_for(
                item_id,
                {
                    "analysis_source": "ai",
                    "is_recommended": True,
                    "reason": "超值好价",
                    "keyword_hit_count": 0,
                },
            )
        )
        assert d.completed_count == 0

    assert notifications == []
    all_rows = asyncio.run(
        load_all_result_records(
            "固态硬盘_full_data.jsonl",
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            include_hidden=True,
        )
    )
    assert {r["ai_analysis"]["analysis_source"] for r in all_rows} == {"exclude_rule"}
    assert all(r["ai_analysis"]["is_recommended"] is False for r in all_rows)

    # 2. 移除排除词后若 AI 暂时失败，保留原 exclude_rule 记录及重试资格
    assert asyncio.run(save_result_record(make_excluded("2003"), "固态硬盘")) is True
    assert len(load_excluded_item_records("固态硬盘")) == 1

    d_fail = asyncio.run(run_dispatcher_for("2003", None))
    assert d_fail.completed_count == 0
    assert len(load_excluded_item_records("固态硬盘")) == 1

    d_ok = asyncio.run(
        run_dispatcher_for(
            "2003",
            {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "重试成功推荐",
                "keyword_hit_count": 0,
            },
        )
    )
    assert d_ok.completed_count == 1
    assert load_excluded_item_records("固态硬盘") == {}
    assert len(notifications) == 1
    assert notifications[0][0] == "2003"


def test_deleted_or_recreated_exclusion_cannot_be_updated_by_old_job(tmp_path, monkeypatch):
    from src.scraper import _build_exclude_aware_saver
    from src.services.result_storage_service import (
        delete_result_file_records, load_processed_link_ids, save_result_record,
    )
    from src.utils import get_link_unique_key, save_result_with_id

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "results.sqlite3"))
    keyword = "watch"
    link = "https://www.goofish.com/item?id=217"
    key = get_link_unique_key(link)
    excluded = {
        "商品信息": {"商品链接": link, "商品标题": "watch", "当前售价": "¥100"},
        "ai_analysis": {"analysis_source": "exclude_rule", "is_recommended": False},
    }
    assert asyncio.run(save_result_record(excluded, keyword))
    original_ids = load_processed_link_ids(keyword)
    save_job = _build_exclude_aware_saver(
        saver_fn=save_result_with_id, processed_links={key}, processed_link_ids=original_ids,
        excluded_item_map={}, in_flight_links={key},
    )
    incoming = {**excluded, "ai_analysis": {"analysis_source": "ai", "is_recommended": True}}
    assert asyncio.run(delete_result_file_records("watch_full_data.jsonl")) == 1
    assert not asyncio.run(save_job(incoming, keyword))
    assert not load_processed_link_ids(keyword)
    assert asyncio.run(save_result_record(excluded, keyword))
    assert load_processed_link_ids(keyword)[key] != original_ids[key]
    assert not asyncio.run(save_job(incoming, keyword))


def test_repeated_detail_exclusion_refreshes_snapshot_at_same_price(tmp_path, monkeypatch):
    from src.services.result_storage_service import load_processed_link_ids
    from src.utils import get_link_unique_key

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "results.sqlite3"))
    link = "https://www.goofish.com/item?id=218"
    key = get_link_unique_key(link)
    record = {
        "任务名称": "A",
        "商品信息": {"商品链接": link, "当前售价": "¥100", "商品描述": "SATA"},
        "ai_analysis": {"analysis_source": "exclude_rule", "is_recommended": False},
    }
    assert asyncio.run(save_result_record(record, "watch"))
    original_id = load_processed_link_ids("watch")[key]
    record["商品信息"]["商品描述"] = "进水"
    assert asyncio.run(save_result_record(record, "watch", expected_result_id=original_id))
    snapshot = load_excluded_item_records("watch")[key]
    assert recheck_excluded_item(snapshot, {}, ["进水"]) == ["进水"]


def test_shared_keyword_keeps_task_exclusions_separate(tmp_path, monkeypatch):
    from src.services.result_storage_service import has_task_exclusion, load_processed_link_ids
    from src.utils import get_link_unique_key

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "results.sqlite3"))
    link = "https://www.goofish.com/item?id=219"
    original = {
        "任务名称": "A",
        "商品信息": {"商品链接": link, "当前售价": "¥100", "商品描述": "SATA"},
        "ai_analysis": {"analysis_source": "exclude_rule", "is_recommended": False},
    }
    assert asyncio.run(save_result_record(original, "watch"))
    key = get_link_unique_key(link)
    original_id = load_processed_link_ids("watch")[key]
    other = {**original, "任务名称": "B", "商品信息": {**original["商品信息"], "商品描述": "进水"}}
    rules = '["进水"]'
    assert not asyncio.run(save_result_record(other, "watch", expected_result_id=original_id, exclusion_rules_key=rules))
    assert load_excluded_item_records("watch")[key]["商品描述"] == "SATA"
    assert has_task_exclusion(original_id, "B", "¥100", rules)
    assert not has_task_exclusion(original_id, "B", "¥80", rules)
    assert not has_task_exclusion(original_id, "B", "¥100", '["拆修"]')
