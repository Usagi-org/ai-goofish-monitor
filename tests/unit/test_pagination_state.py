from dataclasses import dataclass

from src.pipeline.pagination_state import (
    should_process_page,
    should_rest_before_next_page,
    should_skip_invalid_page_response,
    should_stop_after_page_advance,
    should_stop_for_empty_page_items,
)


@dataclass(frozen=True)
class DummyAdvanceResult:
    advanced: bool


@dataclass(frozen=True)
class DummyResponse:
    ok: bool


def test_should_process_page_stops_when_loop_flag_is_set() -> None:
    assert should_process_page(stop_scraping=False) is True
    assert should_process_page(stop_scraping=True) is False


def test_should_stop_after_page_advance_when_no_page_was_advanced() -> None:
    assert should_stop_after_page_advance(DummyAdvanceResult(advanced=True)) is False
    assert should_stop_after_page_advance(DummyAdvanceResult(advanced=False)) is True


def test_should_skip_invalid_page_response_for_missing_or_failed_response() -> None:
    assert should_skip_invalid_page_response(None) is True
    assert should_skip_invalid_page_response(DummyResponse(ok=False)) is True
    assert should_skip_invalid_page_response(DummyResponse(ok=True)) is False


def test_should_stop_for_empty_page_items_only_when_no_items() -> None:
    assert should_stop_for_empty_page_items([]) is True
    assert should_stop_for_empty_page_items([{"商品标题": "MacBook"}]) is False


def test_should_rest_before_next_page_only_when_more_pages_and_not_stopped() -> None:
    assert (
        should_rest_before_next_page(
            stop_scraping=False,
            page_num=1,
            max_pages=3,
        )
        is True
    )
    assert (
        should_rest_before_next_page(
            stop_scraping=True,
            page_num=1,
            max_pages=3,
        )
        is False
    )
    assert (
        should_rest_before_next_page(
            stop_scraping=False,
            page_num=3,
            max_pages=3,
        )
        is False
    )
