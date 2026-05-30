from typing import Any


def should_process_page(stop_scraping: bool) -> bool:
    return not stop_scraping


def should_stop_after_page_advance(page_advance_result: Any) -> bool:
    return not page_advance_result.advanced


def should_skip_invalid_page_response(response: Any) -> bool:
    return not (response and response.ok)


def should_stop_for_empty_page_items(items: list[dict]) -> bool:
    return not items


def should_rest_before_next_page(
    *,
    stop_scraping: bool,
    page_num: int,
    max_pages: int,
) -> bool:
    return not stop_scraping and page_num < max_pages
