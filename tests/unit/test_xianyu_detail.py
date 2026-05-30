import asyncio

from src.xianyu.detail import build_detail_analysis_job, enrich_item_from_detail


def test_enrich_item_from_detail_applies_detail_fields() -> None:
    item = {
        "商品标题": "iPad Pro",
        "商品主图链接": "old",
        "“想要”人数": "3",
    }
    detail_json = {
        "data": {
            "itemDO": {
                "imageInfos": [
                    {"url": "https://example.com/1.jpg"},
                    {"url": ""},
                    {"url": "https://example.com/2.jpg"},
                ],
                "wantCnt": 8,
                "browseCnt": 120,
            },
            "sellerDO": {
                "sellerId": "seller-1",
                "userRegDay": 400,
                "zhimaLevelInfo": {"levelName": "优秀"},
            },
        }
    }

    result = asyncio.run(enrich_item_from_detail(item, detail_json))

    assert result["item_data"] is item
    assert item["商品图片列表"] == [
        "https://example.com/1.jpg",
        "https://example.com/2.jpg",
    ]
    assert item["商品主图链接"] == "https://example.com/1.jpg"
    assert item["“想要”人数"] == 8
    assert item["浏览量"] == 120
    assert result["seller_do"]["sellerId"] == "seller-1"
    assert result["user_id"] == "seller-1"
    assert result["zhima_credit_text"] == "优秀"
    assert result["registration_duration_text"].startswith("来闲鱼1年")


def test_enrich_item_from_detail_preserves_existing_want_default() -> None:
    item = {"“想要”人数": "existing"}

    result = asyncio.run(enrich_item_from_detail(item, {"data": {"itemDO": {}}}))

    assert result["item_data"]["“想要”人数"] == "existing"
    assert result["item_data"]["浏览量"] == "-"
    assert result["seller_do"] == {}
    assert result["user_id"] == "暂无"
    assert result["zhima_credit_text"] == "暂无"
    assert result["registration_duration_text"] == "未知"


def test_build_detail_analysis_job_uses_enriched_detail_fields(monkeypatch) -> None:
    calls = []

    def fake_build_final_record(**kwargs):
        calls.append(kwargs)
        return {"商品信息": kwargs["item_data"], "价格参考": {"透传": True}}

    monkeypatch.setattr(
        "src.xianyu.detail.build_final_record", fake_build_final_record
    )
    item = {"商品标题": "A7M4", "商品价格": "12000"}
    current_market_items = [{"商品标题": "A7M4"}]
    historical_snapshots = [{"item_id": "1"}]
    notification_targets = [{"channel": "wecom-app", "agent_id": "1000001"}]

    job = build_detail_analysis_job(
        keyword="相机",
        task_name="相机任务",
        detail_enrichment={
            "item_data": item,
            "user_id": 12345,
            "zhima_credit_text": "极好",
            "registration_duration_text": "来闲鱼2年",
        },
        current_market_items=current_market_items,
        historical_snapshots=historical_snapshots,
        decision_mode="keyword",
        analyze_images=True,
        prompt_text="prompt",
        keyword_rules=["A7M4", "验货宝"],
        notification_targets=notification_targets,
    )

    assert job.keyword == "相机"
    assert job.task_name == "相机任务"
    assert job.decision_mode == "keyword"
    assert job.analyze_images is True
    assert job.prompt_text == "prompt"
    assert job.keyword_rules == ("A7M4", "验货宝")
    assert job.final_record == {"商品信息": item, "价格参考": {"透传": True}}
    assert job.seller_id == "12345"
    assert job.zhima_credit_text == "极好"
    assert job.registration_duration_text == "来闲鱼2年"
    assert job.notification_targets is notification_targets
    assert calls == [
        {
            "keyword": "相机",
            "task_name": "相机任务",
            "item_data": item,
            "current_market_items": current_market_items,
            "historical_snapshots": historical_snapshots,
        }
    ]


def test_build_detail_analysis_job_defaults_missing_optional_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.xianyu.detail.build_final_record",
        lambda **kwargs: {"商品信息": kwargs["item_data"]},
    )

    job = build_detail_analysis_job(
        keyword="ipad",
        task_name="task",
        detail_enrichment={
            "item_data": {},
            "user_id": None,
            "zhima_credit_text": None,
            "registration_duration_text": "未知",
        },
        current_market_items=[],
        historical_snapshots=[],
        decision_mode="ai",
        analyze_images=False,
        prompt_text="",
    )

    assert job.keyword_rules == ()
    assert job.seller_id is None
    assert job.notification_targets is None
