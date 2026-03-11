import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.utils import log_time, random_sleep

NEXT_PAGE_SELECTOR = "[class*='search-pagination-arrow-right']:not([class*='disabled'])"
PAGE_REQUEST_TIMEOUT_MS = 20_000
PAGE_RETRY_DELAY_SECONDS = 5
PAGE_RETRY_COUNT = 2
PAGE_CLICK_SLEEP_MIN_SECONDS = 2
PAGE_CLICK_SLEEP_MAX_SECONDS = 5


@dataclass(frozen=True)
class PageAdvanceResult:
    advanced: bool
    response: Optional[Any] = None
    stop_reason: Optional[str] = None


async def advance_search_page(
    *,
    page: Any,
    page_num: int,
    api_url_pattern: str,
    logger: Callable[[str], None] = log_time,
    wait_after_click: Callable[[float, float], Awaitable[None]] = random_sleep,
    retry_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_retries: int = PAGE_RETRY_COUNT,
) -> PageAdvanceResult:
    next_button = page.locator(NEXT_PAGE_SELECTOR)
    if not await next_button.count():
        logger("已到达最后一页，未找到可用的'下一页'按钮，停止翻页。")
        return PageAdvanceResult(advanced=False, stop_reason="no_next_button")

    for retry_index in range(max_retries):
        try:
            async with page.expect_response(
                lambda response: api_url_pattern in response.url,
                timeout=PAGE_REQUEST_TIMEOUT_MS,
            ) as response_info:
                await next_button.click()
                await wait_after_click(
                    PAGE_CLICK_SLEEP_MIN_SECONDS,
                    PAGE_CLICK_SLEEP_MAX_SECONDS,
                )
            return PageAdvanceResult(
                advanced=True,
                response=await response_info.value,
            )
        except PlaywrightTimeoutError:
            if retry_index < max_retries - 1:
                logger(
                    f"翻页到第 {page_num} 页超时，"
                    f"{PAGE_RETRY_DELAY_SECONDS}秒后重试..."
                )
                await retry_sleep(PAGE_RETRY_DELAY_SECONDS)
                continue

            logger(f"翻页到第 {page_num} 页超时 {max_retries} 次，停止翻页。")
            return PageAdvanceResult(advanced=False, stop_reason="timeout")

    return PageAdvanceResult(advanced=False, stop_reason="unknown")
