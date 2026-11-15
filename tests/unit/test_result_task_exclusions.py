import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.scraper import _build_exclude_aware_saver
from src.services.result_storage_service import (
    delete_result_file_records, has_task_exclusion, load_processed_link_ids, save_result_record_id,
)
from src.utils import get_link_unique_key, save_result_with_id


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "results.sqlite"
    monkeypatch.setenv("APP_DATABASE_FILE", str(path))
    return path


def exclusion(task, price):
    return {
        "任务名称": task,
        "商品信息": {"商品链接": "https://www.goofish.com/item?id=201", "当前售价": price},
        "ai_analysis": {"analysis_source": "exclude_rule", "is_recommended": False},
    }


@pytest.mark.parametrize(
    "observed,equivalent,changed",
    [("¥100.00", 100, 90), ("1万-2万", " 1万-2万 ", "2万-3万"), (0, "0", -1),
     (" -1 ", -1, 0), (None, "", "待议"), ("面议", " 面议 ", "")],
)
def test_price_display_and_legacy_task_name_share_a_cache_key(database, observed, equivalent, changed):
    assert not has_task_exclusion(1, "  B  ", observed, "rules")
    row_id = asyncio.run(save_result_record_id(exclusion("A", observed), "watch"))
    assert row_id is not None
    other = asyncio.run(save_result_record_id(
        exclusion("  B  ", observed), "watch", expected_result_id=row_id, exclusion_rules_key="rules",
    ))
    assert other is None
    assert has_task_exclusion(row_id, "  B  ", equivalent, "rules")
    assert not has_task_exclusion(row_id, "B", changed, "rules")
    assert not has_task_exclusion(row_id, "B", observed, "new rules")


def test_first_lookup_upgrades_old_prices_and_preserves_cascade(database):
    row_id = asyncio.run(save_result_record_id(exclusion("A", 100), "watch"))
    with sqlite3.connect(database) as conn:
        conn.execute("DROP TABLE result_task_exclusions")
        conn.execute("""CREATE TABLE result_task_exclusions (
            result_id INTEGER REFERENCES result_items(id) ON DELETE CASCADE,
            task_name TEXT NOT NULL, observed_price REAL NOT NULL, rules_key TEXT NOT NULL,
            PRIMARY KEY(result_id, task_name))""")
        conn.execute("DELETE FROM app_metadata WHERE key = 'migration:exclusion_price_key'")
        conn.execute("INSERT INTO result_task_exclusions VALUES (?, 'B', 100.5, 'rules')", (row_id,))
    def lookup(_):
        return has_task_exclusion(row_id, " B ", "¥100.50", "rules")
    with ThreadPoolExecutor(4) as pool:
        assert all(pool.map(lookup, range(4)))
    assert asyncio.run(delete_result_file_records("watch_full_data.jsonl")) == 1
    assert not has_task_exclusion(row_id, "B", 100.5, "rules")


def test_same_scan_save_uses_the_committed_row_id(database):
    record = exclusion("A", 100)
    key = get_link_unique_key(record["商品信息"]["商品链接"])
    ids = {}
    save = _build_exclude_aware_saver(
        saver_fn=save_result_with_id, processed_links=set(), processed_link_ids=ids,
        excluded_item_map={}, in_flight_links=set(),
    )
    assert asyncio.run(save(record, "watch"))
    assert ids[key] == load_processed_link_ids("watch")[key]
    assert asyncio.run(delete_result_file_records("watch_full_data.jsonl")) == 1
    replacement = asyncio.run(save_result_record_id(exclusion("B", 80), "watch"))
    assert replacement != ids[key]
    assert not asyncio.run(save(record, "watch"))
    assert ids[key] != replacement
