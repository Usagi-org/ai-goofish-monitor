import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import results
from src.services.price_history_service import record_market_snapshots


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_results_filter_and_sort_for_keyword_recommendations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    target_file = jsonl_dir / "demo_full_data.jsonl"

    records = [
        {
            "爬取时间": "2026-01-01T01:00:00",
            "商品信息": {"当前售价": "¥1000", "发布时间": "2026-01-01 10:00"},
            "ai_analysis": {
                "analysis_source": "keyword",
                "is_recommended": True,
                "keyword_hit_count": 3,
                "reason": "命中 3 个关键词",
            },
        },
        {
            "爬取时间": "2026-01-01T02:00:00",
            "商品信息": {"当前售价": "¥2000", "发布时间": "2026-01-01 11:00"},
            "ai_analysis": {
                "analysis_source": "keyword",
                "is_recommended": True,
                "keyword_hit_count": 1,
                "reason": "命中 1 个关键词",
            },
        },
        {
            "爬取时间": "2026-01-01T03:00:00",
            "商品信息": {"当前售价": "¥3000", "发布时间": "2026-01-01 12:00"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "AI推荐",
            },
        },
    ]
    _write_jsonl(target_file, records)

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    resp = client.get(
        "/api/results/demo_full_data.jsonl",
        params={"keyword_recommended_only": True, "sort_by": "keyword_hit_count", "sort_order": "desc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 2
    assert data["items"][0]["ai_analysis"]["keyword_hit_count"] == 3
    assert data["items"][1]["ai_analysis"]["keyword_hit_count"] == 1

    resp = client.get(
        "/api/results/demo_full_data.jsonl",
        params={"ai_recommended_only": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 1
    assert data["items"][0]["ai_analysis"]["analysis_source"] == "ai"

    resp = client.get(
        "/api/results/demo_full_data.jsonl",
        params={"ai_recommended_only": True, "keyword_recommended_only": True},
    )
    assert resp.status_code == 400


def test_results_insights_and_export_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    target_file = jsonl_dir / "demo_full_data.jsonl"

    records = [
        {
            "爬取时间": "2026-01-02T09:00:00",
            "搜索关键字": "demo",
            "任务名称": "Demo 任务",
            "商品信息": {
                "商品ID": "1001",
                "商品标题": "Demo One",
                "商品链接": "https://www.goofish.com/item?id=1001",
                "当前售价": "¥950",
                "发布时间": "2026-01-02 08:30",
            },
            "卖家信息": {"卖家昵称": "卖家A"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "价格低于近期均价",
            },
        },
        {
            "爬取时间": "2026-01-02T09:05:00",
            "搜索关键字": "demo",
            "任务名称": "Demo 任务",
            "商品信息": {
                "商品ID": "1002",
                "商品标题": "Demo Two",
                "商品链接": "https://www.goofish.com/item?id=1002",
                "当前售价": "¥1200",
                "发布时间": "2026-01-02 08:45",
            },
            "卖家信息": {"卖家昵称": "卖家B"},
            "ai_analysis": {
                "analysis_source": "keyword",
                "is_recommended": False,
                "reason": "未命中",
                "keyword_hit_count": 0,
            },
        },
    ]
    _write_jsonl(target_file, records)

    record_market_snapshots(
        keyword="demo",
        task_name="Demo 任务",
        items=[
            {
                "商品ID": "1001",
                "商品标题": "Demo One",
                "当前售价": "¥1000",
                "商品链接": "https://www.goofish.com/item?id=1001",
            },
            {
                "商品ID": "1002",
                "商品标题": "Demo Two",
                "当前售价": "¥1200",
                "商品链接": "https://www.goofish.com/item?id=1002",
            },
        ],
        run_id="run-1",
        snapshot_time="2026-01-01T10:00:00",
        seen_item_ids=set(),
    )
    record_market_snapshots(
        keyword="demo",
        task_name="Demo 任务",
        items=[
            {
                "商品ID": "1001",
                "商品标题": "Demo One",
                "当前售价": "¥950",
                "商品链接": "https://www.goofish.com/item?id=1001",
            },
            {
                "商品ID": "1002",
                "商品标题": "Demo Two",
                "当前售价": "¥1180",
                "商品链接": "https://www.goofish.com/item?id=1002",
            },
        ],
        run_id="run-2",
        snapshot_time="2026-01-02T10:00:00",
        seen_item_ids=set(),
    )

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    insights_resp = client.get("/api/results/demo_full_data.jsonl/insights")
    assert insights_resp.status_code == 200
    insights = insights_resp.json()
    assert insights["market_summary"]["sample_count"] == 2
    assert len(insights["daily_trend"]) == 2

    list_resp = client.get("/api/results/demo_full_data.jsonl")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert items[0]["price_insight"]["observation_count"] >= 1

    export_resp = client.get(
        "/api/results/demo_full_data.jsonl/export",
        params={"sort_by": "price", "sort_order": "asc"},
    )
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    text = export_resp.text
    assert "任务名称,搜索关键字,商品ID,商品标题" in text
    assert "Demo One" in text


def test_results_export_csv_supports_unicode_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    target_file = jsonl_dir / "演示_full_data.jsonl"

    records = [
        {
            "爬取时间": "2026-01-02T09:00:00",
            "搜索关键字": "演示",
            "任务名称": "演示任务",
            "商品信息": {
                "商品ID": "1001",
                "商品标题": "演示商品",
                "商品链接": "https://www.goofish.com/item?id=1001",
                "当前售价": "¥950",
                "发布时间": "2026-01-02 08:30",
            },
            "卖家信息": {"卖家昵称": "卖家A"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "价格合理",
            },
        }
    ]
    _write_jsonl(target_file, records)

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    export_resp = client.get("/api/results/演示_full_data.jsonl/export")
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    disposition = export_resp.headers["content-disposition"]
    assert 'filename="export.csv"' in disposition
    assert "filename*=UTF-8''%E6%BC%94%E7%A4%BA_full_data.csv" in disposition


def test_results_blacklist_rules_hide_items_from_view_and_insights(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    target_file = jsonl_dir / "macbook_air_m1_full_data.jsonl"

    records = [
        {
            "爬取时间": "2026-01-03T09:00:00",
            "搜索关键字": "MacBook Air M1",
            "任务名称": "MacBook Air M1 监控",
            "商品信息": {
                "商品ID": "2001",
                "商品标题": "MacBook Air M1 8+256",
                "商品链接": "https://www.goofish.com/item?id=2001",
                "当前售价": "¥4200",
                "发布时间": "2026-01-03 08:30",
            },
            "卖家信息": {"卖家昵称": "卖家A"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "符合目标机型",
            },
        },
        {
            "爬取时间": "2026-01-03T09:05:00",
            "搜索关键字": "MacBook Air M1",
            "任务名称": "MacBook Air M1 监控",
            "商品信息": {
                "商品ID": "2002",
                "商品标题": "MacBook Air Intel i5 8+256",
                "商品链接": "https://www.goofish.com/item?id=2002",
                "当前售价": "¥3100",
                "发布时间": "2026-01-03 08:35",
            },
            "卖家信息": {"卖家昵称": "卖家B"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": False,
                "reason": "不是目标机型",
            },
        },
        {
            "爬取时间": "2026-01-03T09:10:00",
            "搜索关键字": "MacBook Air M1",
            "任务名称": "MacBook Air M1 监控",
            "商品信息": {
                "商品ID": "2003",
                "商品标题": "MacBook Pro Intel 13寸",
                "商品链接": "https://www.goofish.com/item?id=2003",
                "当前售价": "¥3600",
                "发布时间": "2026-01-03 08:40",
            },
            "卖家信息": {"卖家昵称": "卖家C"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": False,
                "reason": "不是 Air M1",
            },
        },
    ]
    _write_jsonl(target_file, records)

    record_market_snapshots(
        keyword="MacBook Air M1",
        task_name="MacBook Air M1 监控",
        items=[
            {
                "商品ID": "2001",
                "商品标题": "MacBook Air M1 8+256",
                "当前售价": "¥4300",
                "商品链接": "https://www.goofish.com/item?id=2001",
            },
            {
                "商品ID": "2002",
                "商品标题": "MacBook Air Intel i5 8+256",
                "当前售价": "¥3200",
                "商品链接": "https://www.goofish.com/item?id=2002",
            },
            {
                "商品ID": "2003",
                "商品标题": "MacBook Pro Intel 13寸",
                "当前售价": "¥3700",
                "商品链接": "https://www.goofish.com/item?id=2003",
            },
        ],
        run_id="run-1",
        snapshot_time="2026-01-02T10:00:00",
        seen_item_ids=set(),
    )
    record_market_snapshots(
        keyword="MacBook Air M1",
        task_name="MacBook Air M1 监控",
        items=[
            {
                "商品ID": "2001",
                "商品标题": "MacBook Air M1 8+256",
                "当前售价": "¥4200",
                "商品链接": "https://www.goofish.com/item?id=2001",
            },
            {
                "商品ID": "2002",
                "商品标题": "MacBook Air Intel i5 8+256",
                "当前售价": "¥3100",
                "商品链接": "https://www.goofish.com/item?id=2002",
            },
            {
                "商品ID": "2003",
                "商品标题": "MacBook Pro Intel 13寸",
                "当前售价": "¥3600",
                "商品链接": "https://www.goofish.com/item?id=2003",
            },
        ],
        run_id="run-2",
        snapshot_time="2026-01-03T10:00:00",
        seen_item_ids=set(),
    )

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    update_rules_resp = client.put(
        "/api/results/macbook_air_m1_full_data.jsonl/blacklist-rules",
        json={"keywords": ["intel"]},
    )
    assert update_rules_resp.status_code == 200
    assert update_rules_resp.json()["keywords"] == ["intel"]

    rules_resp = client.get("/api/results/macbook_air_m1_full_data.jsonl/blacklist-rules")
    assert rules_resp.status_code == 200
    assert rules_resp.json()["keywords"] == ["intel"]

    filtered_resp = client.get("/api/results/macbook_air_m1_full_data.jsonl")
    assert filtered_resp.status_code == 200
    filtered_payload = filtered_resp.json()
    assert filtered_payload["total_items"] == 1
    assert [item["商品信息"]["商品ID"] for item in filtered_payload["items"]] == ["2001"]

    include_hidden_resp = client.get(
        "/api/results/macbook_air_m1_full_data.jsonl",
        params={"include_hidden": True},
    )
    assert include_hidden_resp.status_code == 200
    include_hidden_payload = include_hidden_resp.json()
    assert include_hidden_payload["total_items"] == 3
    hidden_item = next(
        item for item in include_hidden_payload["items"]
        if item["商品信息"]["商品ID"] == "2002"
    )
    assert hidden_item["_hidden_reason"] == "rule"
    assert hidden_item["_matched_blacklist_keywords"] == ["intel"]

    insights_resp = client.get("/api/results/macbook_air_m1_full_data.jsonl/insights")
    assert insights_resp.status_code == 200
    insights = insights_resp.json()
    assert insights["market_summary"]["sample_count"] == 1
    assert insights["market_summary"]["avg_price"] == 4200.0
    assert all(point["sample_count"] == 1 for point in insights["daily_trend"])

    list_resp = client.get("/api/results/macbook_air_m1_full_data.jsonl")
    assert list_resp.status_code == 200
    visible_item = list_resp.json()["items"][0]
    assert visible_item["price_insight"]["market_avg_price"] == 4200.0

    export_resp = client.get("/api/results/macbook_air_m1_full_data.jsonl/export")
    assert export_resp.status_code == 200
    assert "MacBook Air M1 8+256" in export_resp.text
    assert "MacBook Air Intel i5 8+256" not in export_resp.text
    assert "MacBook Pro Intel 13寸" not in export_resp.text

    download_resp = client.get("/api/results/files/macbook_air_m1_full_data.jsonl")
    assert download_resp.status_code == 200
    assert "MacBook Air Intel i5 8+256" in download_resp.text
    assert "MacBook Pro Intel 13寸" in download_resp.text

def test_results_sold_status_sorting_filtering_insights_and_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.services.result_storage_service import (
        _load_result_summary_sync,
        _save_result_record_sync,
    )

    records = [
        {
            "爬取时间": "2026-01-05T09:00:00",
            "搜索关键字": "camera",
            "任务名称": "相机监控",
            "商品信息": {
                "商品ID": "3001",
                "商品标题": "Sony A7C 黑色在售",
                "商品链接": "https://www.goofish.com/item?id=3001",
                "当前售价": "¥8500",
                "发布时间": "2026-01-05 08:00",
            },
            "卖家信息": {"卖家昵称": "卖家1"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "成色很好",
            },
        },
        {
            "爬取时间": "2026-01-05T09:10:00",
            "搜索关键字": "camera",
            "任务名称": "相机监控",
            "商品信息": {
                "商品ID": "3002",
                "商品标题": "Sony A7C 银色稍后售出",
                "商品链接": "https://www.goofish.com/item?id=3002",
                "当前售价": "¥7800",
                "发布时间": "2026-01-05 08:10",
            },
            "卖家信息": {"卖家昵称": "卖家2"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "性价比高",
            },
        },
        {
            "爬取时间": "2026-01-05T09:20:00",
            "搜索关键字": "camera",
            "任务名称": "相机监控",
            "商品信息": {
                "商品ID": "3003",
                "商品标题": "Sony A7C 已手动隐藏",
                "商品链接": "https://www.goofish.com/item?id=3003",
                "当前售价": "¥9200",
                "发布时间": "2026-01-05 08:20",
            },
            "卖家信息": {"卖家昵称": "卖家3"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": False,
                "reason": "偏贵",
            },
        },
        {
            "爬取时间": "2026-01-05T09:30:00",
            "搜索关键字": "camera",
            "任务名称": "相机监控",
            "商品信息": {
                "商品ID": "3004",
                "商品标题": "Sony A7C 抓取时已售",
                "商品链接": "https://www.goofish.com/item?id=3004",
                "当前售价": "¥7600",
                "发布时间": "2026-01-05 08:30",
            },
            "卖家信息": {"卖家昵称": "卖家4"},
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "好价",
            },
            "_initial_status": "sold",
        },
    ]

    for record in records:
        _save_result_record_sync(record, "camera")

    assert records[3]["_initial_status"] == "sold"

    record_market_snapshots(
        keyword="camera",
        task_name="相机监控",
        items=[
            {
                "商品ID": "3001",
                "商品标题": "Sony A7C 黑色在售",
                "当前售价": "¥8500",
                "商品链接": "https://www.goofish.com/item?id=3001",
            },
            {
                "商品ID": "3002",
                "商品标题": "Sony A7C 银色稍后售出",
                "当前售价": "¥7800",
                "商品链接": "https://www.goofish.com/item?id=3002",
            },
            {
                "商品ID": "3004",
                "商品标题": "Sony A7C 抓取时已售",
                "当前售价": "¥7600",
                "商品链接": "https://www.goofish.com/item?id=3004",
            },
        ],
        run_id="run-1",
        snapshot_time="2026-01-05T10:00:00",
        seen_item_ids=set(),
    )

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    patch_sold = client.patch(
        "/api/results/camera_full_data.jsonl/items/3002/status",
        json={"status": "sold"},
    )
    assert patch_sold.status_code == 200
    assert patch_sold.json()["status"] == "sold"

    patch_hidden = client.patch(
        "/api/results/camera_full_data.jsonl/items/3003/status",
        json={"status": "hidden"},
    )
    assert patch_hidden.status_code == 200

    default_resp = client.get("/api/results/camera_full_data.jsonl")
    assert default_resp.status_code == 200
    default_data = default_resp.json()
    assert default_data["total_items"] == 3
    assert [item["商品信息"]["商品ID"] for item in default_data["items"]] == [
        "3001",
        "3004",
        "3002",
    ]
    sold_item = default_data["items"][1]
    assert sold_item["_status"] == "sold"
    assert sold_item["_is_sold"] is True
    assert sold_item["_effective_hidden"] is False
    assert sold_item["_hidden_reason"] is None
    assert "_initial_status" not in sold_item

    all_resp = client.get(
        "/api/results/camera_full_data.jsonl",
        params={"include_hidden": True},
    )
    assert all_resp.status_code == 200
    assert [item["商品信息"]["商品ID"] for item in all_resp.json()["items"]] == [
        "3001",
        "3004",
        "3002",
        "3003",
    ]

    no_sold_resp = client.get(
        "/api/results/camera_full_data.jsonl",
        params={"include_sold": False},
    )
    assert no_sold_resp.status_code == 200
    assert no_sold_resp.json()["total_items"] == 1
    assert [item["商品信息"]["商品ID"] for item in no_sold_resp.json()["items"]] == [
        "3001"
    ]

    insights_resp = client.get("/api/results/camera_full_data.jsonl/insights")
    assert insights_resp.status_code == 200
    insights = insights_resp.json()
    assert insights["market_summary"]["sample_count"] == 1
    assert insights["market_summary"]["avg_price"] == 8500.0

    summary = _load_result_summary_sync("camera_full_data.jsonl")
    assert summary is not None
    assert summary["total_items"] == 1
    assert summary["recommended_items"] == 1

    export_default = client.get("/api/results/camera_full_data.jsonl/export")
    assert export_default.status_code == 200
    assert "Sony A7C 黑色在售" in export_default.text
    assert "Sony A7C 银色稍后售出" in export_default.text
    assert "Sony A7C 已手动隐藏" not in export_default.text

    export_no_sold = client.get(
        "/api/results/camera_full_data.jsonl/export",
        params={"include_sold": False},
    )
    assert export_no_sold.status_code == 200
    assert "Sony A7C 黑色在售" in export_no_sold.text
    assert "Sony A7C 银色稍后售出" not in export_no_sold.text
    assert "Sony A7C 抓取时已售" not in export_no_sold.text


def test_results_check_status_updates_sold_and_backfills_detail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.services import item_status_service
    from src.services.result_storage_service import _save_result_record_sync

    _save_result_record_sync(
        {
            "爬取时间": "2026-01-06T09:00:00",
            "搜索关键字": "ipad",
            "任务名称": "iPad 监控",
            "商品信息": {
                "商品ID": "4001",
                "商品标题": "iPad Pro",
                "商品链接": "https://www.goofish.com/item?id=4001",
                "当前售价": "¥4500",
                "发布时间": "2026-01-06 08:00",
            },
            "卖家信息": {"卖家昵称": "卖家A"},
        },
        "ipad",
    )
    _save_result_record_sync(
        {
            "爬取时间": "2026-01-06T09:10:00",
            "搜索关键字": "ipad",
            "任务名称": "iPad 监控",
            "商品信息": {
                "商品ID": "4002",
                "商品标题": "iPad Air",
                "商品链接": "https://www.goofish.com/item?id=4002",
                "当前售价": "¥3200",
                "发布时间": "2026-01-06 08:10",
            },
            "卖家信息": {"卖家昵称": "卖家B"},
        },
        "ipad",
    )

    real_check = item_status_service.check_result_items_status

    async def fake_fetcher(item: dict) -> dict:
        if item["item_id"] == "4002":
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {
                    "itemDO": {
                        "title": "iPad Air M2 256G 星光色 国行",
                        "desc": "九九新无磕碰，支持验机",
                        "imageInfos": [
                            {"url": "https://img.example.com/ipad4002-1.jpg"},
                            {"url": "https://img.example.com/ipad4002-2.jpg"},
                        ],
                        "itemStatus": 1,
                        "wantCnt": 25,
                        "browseCnt": 510,
                    },
                    "sellerDO": {},
                },
            }
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "itemDO": {
                    "title": "iPad Pro M4 256G",
                    "desc": "仅拆封激活，带原装笔",
                    "imageInfos": [
                        {"url": "https://img.example.com/ipad4001-1.jpg"},
                    ],
                    "itemStatus": 0,
                    "wantCnt": 9,
                    "browseCnt": 120,
                },
                "sellerDO": {},
            },
        }

    async def patched_check(filename: str, *, item_ids=None, limit: int = 10):
        return await real_check(
            filename,
            item_ids=item_ids,
            limit=limit,
            detail_fetcher=fake_fetcher,
        )

    monkeypatch.setattr(results, "check_result_items_status", patched_check)

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    resp = client.post(
        "/api/results/ipad_full_data.jsonl/check-status",
        json={"limit": 10},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["checked"] == 2
    assert payload["updated"] == 2
    assert payload["sold_count"] == 1
    assert payload["active_count"] == 1
    assert payload["expired_count"] == 0
    assert payload["unknown_count"] == 0
    assert payload["failed_count"] == 0
    assert payload["stopped_reason"] is None

    by_id = {entry["item_id"]: entry for entry in payload["results"]}
    assert by_id["4002"]["item_id"] == "4002"
    assert by_id["4002"]["previous_status"] == "active"
    assert by_id["4002"]["status"] == "sold"
    assert by_id["4002"]["mapped_status"] == "sold"
    assert by_id["4002"]["status_label"] == "已售出"
    assert by_id["4002"]["description_updated"] is True
    assert by_id["4002"]["title"] == "iPad Air M2 256G 星光色 国行"
    assert by_id["4002"]["description"] == "九九新无磕碰，支持验机"
    assert by_id["4002"]["image_urls"] == [
        "https://img.example.com/ipad4002-1.jpg",
        "https://img.example.com/ipad4002-2.jpg",
    ]
    assert by_id["4002"]["checked_at"]
    assert by_id["4002"]["error"] is None
    assert by_id["4001"]["status"] == "active"
    assert by_id["4001"]["description_updated"] is True

    list_resp = client.get("/api/results/ipad_full_data.jsonl")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert [item["商品信息"]["商品ID"] for item in items] == ["4001", "4002"]

    sold_record = items[1]
    assert sold_record["_status"] == "sold"
    assert sold_record["_is_sold"] is True
    assert sold_record["商品信息"]["商品标题"] == "iPad Air M2 256G 星光色 国行"
    assert sold_record["商品信息"]["商品描述"] == "九九新无磕碰，支持验机"
    assert sold_record["商品信息"]["商品图片列表"] == [
        "https://img.example.com/ipad4002-1.jpg",
        "https://img.example.com/ipad4002-2.jpg",
    ]
    assert sold_record["商品信息"]["商品主图链接"] == "https://img.example.com/ipad4002-1.jpg"
    assert sold_record["商品信息"]["商品状态"] == "已售出"
    assert sold_record["商品信息"]["商品状态码"] == 1
    assert sold_record["商品信息"]["状态检查时间"]


def test_results_check_status_risk_control_early_stop_and_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.services import item_status_service
    from src.services.result_storage_service import _save_result_record_sync

    for idx, crawl_time in enumerate(
        ["2026-01-07T09:00:00", "2026-01-07T09:10:00", "2026-01-07T09:20:00"],
        start=1,
    ):
        _save_result_record_sync(
            {
                "爬取时间": crawl_time,
                "搜索关键字": "switch",
                "任务名称": "Switch 监控",
                "商品信息": {
                    "商品ID": f"500{idx}",
                    "商品标题": f"Switch OLED #{idx}",
                    "商品链接": f"https://www.goofish.com/item?id=500{idx}",
                    "当前售价": "¥1600",
                    "发布时间": "2026-01-07 08:00",
                },
                "卖家信息": {"卖家昵称": f"卖家{idx}"},
            },
            "switch",
        )

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)

    no_state_resp = client.post(
        "/api/results/switch_full_data.jsonl/check-status",
        json={"limit": 3},
    )
    assert no_state_resp.status_code == 400
    assert "登录状态文件" in no_state_resp.json()["detail"]

    missing_item_resp = client.post(
        "/api/results/switch_full_data.jsonl/check-status",
        json={"item_ids": ["9999"]},
    )
    assert missing_item_resp.status_code == 404

    real_check = item_status_service.check_result_items_status
    fetched_ids: list[str] = []

    async def risk_fetcher(item: dict) -> dict:
        fetched_ids.append(item["item_id"])
        if item["item_id"] == "5003":
            return {
                "ret": ["SUCCESS::调用成功"],
                "data": {
                    "itemDO": {
                        "desc": "已出给本地买家",
                        "itemStatus": 1,
                    },
                    "sellerDO": {},
                },
            }
        return {
            "ret": ["FAIL_SYS_USER_VALIDATE::触发风控验证"],
            "data": {},
        }

    async def patched_check(filename: str, *, item_ids=None, limit: int = 10):
        return await real_check(
            filename,
            item_ids=item_ids,
            limit=limit,
            detail_fetcher=risk_fetcher,
        )

    monkeypatch.setattr(results, "check_result_items_status", patched_check)

    risk_resp = client.post(
        "/api/results/switch_full_data.jsonl/check-status",
        json={"limit": 3},
    )
    assert risk_resp.status_code == 200
    risk_payload = risk_resp.json()
    assert fetched_ids == ["5003", "5002"]
    assert risk_payload["checked"] == 2
    assert risk_payload["sold_count"] == 1
    assert risk_payload["failed_count"] == 1
    assert risk_payload["stopped_reason"]
    assert "FAIL_SYS_USER_VALIDATE" in risk_payload["stopped_reason"]
    assert len(risk_payload["results"]) == 2
    assert risk_payload["results"][0]["item_id"] == "5003"
    assert risk_payload["results"][0]["status"] == "sold"
    assert risk_payload["results"][1]["item_id"] == "5002"
    assert risk_payload["results"][1]["error"] == "FAIL_SYS_USER_VALIDATE"

    import asyncio
    import httpx

    started = asyncio.Event()
    release = asyncio.Event()

    async def blocking_fetcher(item: dict) -> dict:
        started.set()
        await release.wait()
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {"itemDO": {"itemStatus": 0}, "sellerDO": {}},
        }

    async def patched_blocking_check(filename: str, *, item_ids=None, limit: int = 10):
        return await real_check(
            filename,
            item_ids=item_ids,
            limit=limit,
            detail_fetcher=blocking_fetcher,
        )

    monkeypatch.setattr(results, "check_result_items_status", patched_blocking_check)

    async def _run_concurrent_requests():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as async_client:
            first_task = asyncio.create_task(
                async_client.post(
                    "/api/results/switch_full_data.jsonl/check-status",
                    json={"item_ids": ["5001"]},
                )
            )
            await started.wait()
            second_resp = await async_client.post(
                "/api/results/switch_full_data.jsonl/check-status",
                json={"item_ids": ["5002"]},
            )
            release.set()
            first_resp = await first_task
            return first_resp, second_resp

    first_resp, second_resp = asyncio.run(_run_concurrent_requests())
    assert first_resp.status_code == 200
    assert second_resp.status_code == 409


def test_check_status_rotates_batches_respects_limit_preserves_hidden_and_syncs_duplicates(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    from src.services import item_status_service
    from src.services.result_storage_service import (
        _save_result_record_sync,
        load_all_result_records,
        load_result_summary,
        update_item_status,
    )
    import asyncio

    for idx in range(1, 13):
        _save_result_record_sync(
            {
                "爬取时间": f"2026-01-08T10:{idx:02d}:00",
                "搜索关键字": "camera",
                "任务名称": "Camera 任务",
                "商品信息": {
                    "商品ID": f"c{idx:02d}",
                    "商品标题": f"Camera #{idx:02d}",
                    "商品链接": f"https://www.goofish.com/item?id=c{idx:02d}",
                    "当前售价": "¥2000",
                },
                "卖家信息": {"卖家昵称": "卖家"},
            },
            "camera",
        )
    # Add duplicate item_id row with different query order
    _save_result_record_sync(
        {
            "爬取时间": "2026-01-08T09:00:00",
            "搜索关键字": "camera",
            "任务名称": "Camera 任务",
            "商品信息": {
                "商品ID": "c12",
                "商品标题": "Camera #12 old link",
                "商品链接": "https://www.goofish.com/item?spm=1&id=c12",
                "当前售价": "¥2000",
            },
            "卖家信息": {"卖家昵称": "卖家"},
        },
        "camera",
    )
    asyncio.run(update_item_status("camera_full_data.jsonl", "c01", "hidden"))

    app = FastAPI()
    app.include_router(results.router)
    client = TestClient(app)
    real_check = item_status_service.check_result_items_status

    fetched_batches: list[list[str]] = []

    async def batch_fetcher(item: dict) -> dict:
        fetched_batches[-1].append(item["item_id"])
        status = 1 if item["item_id"] == "c12" else 0
        return {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "itemDO": {
                    "desc": f"desc-{item['item_id']}",
                    "imageInfos": [{"url": f"https://img.example.com/{item['item_id']}.jpg"}],
                    "itemStatus": status,
                },
                "sellerDO": {},
            },
        }

    async def patched_check(filename: str, *, item_ids=None, limit: int = 10):
        fetched_batches.append([])
        return await real_check(
            filename, item_ids=item_ids, limit=limit, detail_fetcher=batch_fetcher
        )

    monkeypatch.setattr(results, "check_result_items_status", patched_check)

    # 1. Repeated batch check rotates to remaining unchecked active items and deduplicates c12
    resp1 = client.post("/api/results/camera_full_data.jsonl/check-status", json={"limit": 8})
    assert resp1.status_code == 200
    assert len(fetched_batches[-1]) == 8
    assert fetched_batches[-1].count("c12") == 1

    resp2 = client.post("/api/results/camera_full_data.jsonl/check-status", json={"limit": 8})
    assert resp2.status_code == 200
    assert "c02" in fetched_batches[-1]
    assert "c03" in fetched_batches[-1]

    # All duplicate rows for c12 were updated to sold
    all_rows = asyncio.run(
        load_all_result_records(
            "camera_full_data.jsonl",
            ai_recommended_only=False,
            keyword_recommended_only=False,
            sort_by="crawl_time",
            sort_order="desc",
            include_hidden=True,
            include_sold=True,
        )
    )
    c12_rows = [r for r in all_rows if r["商品信息"]["商品ID"] == "c12"]
    assert len(c12_rows) == 2
    assert all(r["_status"] == "sold" for r in c12_rows)
    assert all(r["商品信息"].get("商品描述") == "desc-c12" for r in c12_rows)

    # 2. Explicit item_ids still enforces limit
    resp_limited = client.post(
        "/api/results/camera_full_data.jsonl/check-status",
        json={"item_ids": ["c02", "c03", "c04", "c05"], "limit": 2},
    )
    assert resp_limited.status_code == 200
    assert resp_limited.json()["checked"] == 2

    # 3. Single-item check on manually hidden item preserves hidden status while backfilling description
    resp_hidden = client.post(
        "/api/results/camera_full_data.jsonl/check-status",
        json={"item_ids": ["c01"], "limit": 1},
    )
    assert resp_hidden.status_code == 200
    hidden_entry = resp_hidden.json()["results"][0]
    assert hidden_entry["status"] == "hidden"
    assert hidden_entry["mapped_status"] == "active"
    assert hidden_entry["description"] == "desc-c01"
    assert hidden_entry["image_urls"] == ["https://img.example.com/c01.jpg"]

    # 4. Sold-only result file still produces a non-None dashboard summary
    _save_result_record_sync(
        {
            "爬取时间": "2026-01-09T12:00:00",
            "搜索关键字": "soldonly",
            "任务名称": "SoldOnly",
            "商品信息": {
                "商品ID": "s1",
                "商品标题": "Sold Only Item",
                "商品链接": "https://www.goofish.com/item?id=s1",
                "当前售价": "¥100",
            },
            "_initial_status": "sold",
        },
        "soldonly",
    )
    sold_summary = asyncio.run(load_result_summary("soldonly_full_data.jsonl"))
    assert sold_summary is not None
    assert sold_summary["total_items"] == 0
    assert sold_summary["latest_crawl_time"] == "2026-01-09T12:00:00"



