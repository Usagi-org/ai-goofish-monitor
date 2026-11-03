"""Price parsing and persistence regressions, runnable without network services."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.price_history_service import (
    build_item_price_context,
    build_price_history_insights,
    load_price_snapshots,
    parse_price_value,
    record_market_snapshots,
)


class TestPriceValueValidation(unittest.TestCase):
    def test_valid_prices_keep_existing_formats(self):
        for value, expected in [(0, 0.0), (12.345, 12.35), ("¥1,234.50", 1234.5),
                                (" 1.25万 ", 12500.0), ("2e2", 200.0)]:
            with self.subTest(value=value):
                self.assertEqual(parse_price_value(value), expected)

    def test_malformed_wan_values_are_missing_prices(self):
        for value in ["万", "约1万", "1.2.3万", "暂无万"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_price_value(value))

    def test_nonfinite_and_overflow_values_are_missing_prices(self):
        for value in [float("nan"), float("inf"), float("-inf"), "NaN", "Infinity",
                      "-Infinity", "1e309", "1e308万", 10 ** 400]:
            with self.subTest(value=str(value)[:30]):
                self.assertIsNone(parse_price_value(value))

    def test_existing_missing_prices_remain_missing(self):
        for value in [None, "", "-", "N/A", "暂无", "价格异常", "not a price"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_price_value(value))

    def test_invalid_prices_do_not_abort_or_pollute_snapshot_batch(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"APP_DATABASE_FILE": str(Path(directory) / "test.sqlite3")}
        ):
            try:
                os.chdir(directory)
                seen = set()
                records = record_market_snapshots(
                    keyword="camera", task_name="camera", run_id="run-1",
                    snapshot_time="2026-01-01T12:00:00",
                    seen_item_ids=seen,
                    items=[{"商品ID": str(index), "当前售价": price}
                           for index, price in enumerate(["约1万", "NaN", "Infinity", "¥100", "1.2万"])],
                )
                self.assertEqual([record["price"] for record in records], [100.0, 12000.0])
                self.assertEqual(seen, {"3", "4"})
                saved = load_price_snapshots("camera")
                self.assertEqual([record["price"] for record in saved], [100.0, 12000.0])
                summary = build_price_history_insights("camera")["market_summary"]
                self.assertEqual(summary["sample_count"], 2)
                self.assertEqual(summary["avg_price"], 6050.0)
            finally:
                os.chdir(previous)

    def test_all_invalid_history_returns_no_data(self):
        snapshots = [{"item_id": "1", "price": price} for price in [float("inf"), float("nan")]]
        context = build_item_price_context(snapshots, item_id="1", current_price=None)
        self.assertEqual(context, {"observation_count": 0, "deal_score": None, "deal_label": "暂无数据"})

    def test_mixed_history_excludes_invalid_observations(self):
        snapshots = [
            {"item_id": "1", "price": 100, "run_id": "1", "snapshot_time": "2026-01-01"},
            {"item_id": "1", "price": float("inf"), "run_id": "2", "snapshot_time": "2026-01-02"},
            {"item_id": "1", "price": 80, "run_id": "3", "snapshot_time": "2026-01-03"},
        ]
        context = build_item_price_context(snapshots, item_id="1", current_price=80)
        self.assertEqual(context["observation_count"], 2)
        self.assertEqual(context["avg_price"], 90.0)
        self.assertEqual(context["price_change_amount"], -20.0)

    def test_formatted_history_reuses_parsed_prices(self):
        snapshots = [{"item_id": "1", "price": "¥1,000", "run_id": "1"},
                     {"item_id": "1", "price": "0.08万", "run_id": "2"}]
        context = build_item_price_context(snapshots, item_id="1", current_price=None)
        self.assertEqual(context["current_price"], 800.0)
        self.assertEqual(context["market_avg_price"], 800.0)
        self.assertEqual(context["avg_price"], 900.0)

    def test_nonfinite_current_price_is_not_used_in_scoring(self):
        snapshots = [{"item_id": "1", "price": 100, "run_id": "1"}]
        for value in [float("nan"), float("inf")]:
            with self.subTest(value=value):
                context = build_item_price_context(snapshots, item_id="1", current_price=value)
                self.assertIsNone(context["current_price"])
                self.assertIsNone(context["price_change_amount"])
                self.assertEqual(context["deal_score"], 50)


if __name__ == "__main__":
    unittest.main()
