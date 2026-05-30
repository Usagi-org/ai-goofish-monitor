from src.pipeline.records import build_final_record


def test_build_final_record_adds_price_reference(monkeypatch) -> None:
    calls = []

    def fake_build_market_reference(**kwargs):
        calls.append(kwargs)
        return {"本商品价格位置": {"deal_score": 80}, "关键词": kwargs["keyword"]}

    monkeypatch.setattr(
        "src.pipeline.records.build_market_reference", fake_build_market_reference
    )
    item = {"商品标题": "相机"}
    current_market_items = [{"商品标题": "相机"}]
    historical_snapshots = [{"item_id": "1"}]

    record = build_final_record(
        "相机",
        "每日相机",
        item,
        current_market_items,
        historical_snapshots,
    )

    assert "爬取时间" in record
    assert record["搜索关键字"] == "相机"
    assert record["任务名称"] == "每日相机"
    assert record["商品信息"] is item
    assert record["卖家信息"] == {}
    assert record["价格参考"] == {"本商品价格位置": {"deal_score": 80}, "关键词": "相机"}
    assert record["price_insight"] == {"deal_score": 80}
    assert calls == [
        {
            "keyword": "相机",
            "item": item,
            "current_market_items": current_market_items,
            "historical_snapshots": historical_snapshots,
        }
    ]


def test_build_final_record_defaults_missing_price_insight(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.pipeline.records.build_market_reference",
        lambda **_kwargs: {"当前搜索样本": {}},
    )

    record = build_final_record("ipad", "task", {}, [], [])

    assert record["价格参考"] == {"当前搜索样本": {}}
    assert record["price_insight"] == {}
