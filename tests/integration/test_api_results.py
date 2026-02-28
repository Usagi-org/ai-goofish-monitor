import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import results


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
