from src.pipeline.scan_state import build_scan_state


def test_build_scan_state_loads_keyword_scoped_run_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.pipeline.scan_state.load_price_snapshots",
        lambda keyword: [{"keyword": keyword}],
    )
    monkeypatch.setattr(
        "src.pipeline.scan_state.load_processed_link_keys",
        lambda keyword: {f"{keyword}-seen"},
    )
    monkeypatch.setattr(
        "src.pipeline.scan_state.build_result_filename",
        lambda keyword: f"{keyword}.jsonl",
    )

    state = build_scan_state("ipad")

    assert state.keyword == "ipad"
    assert len(state.history_run_id) == 14
    assert state.history_run_id.isdigit()
    assert state.history_seen_item_ids == set()
    assert state.historical_snapshots == [{"keyword": "ipad"}]
    assert state.result_filename == "ipad.jsonl"
    assert state.processed_links == {"ipad-seen"}
