import asyncio

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.services.search_pagination import advance_search_page
from src.services.search_pagination import is_search_results_response


class FakeRequest:
    def __init__(self, method: str = "POST"):
        self.method = method


class FakeResponse:
    def __init__(self, url: str, ok: bool = True, method: str = "POST"):
        self.url = url
        self.ok = ok
        self.request = FakeRequest(method)


class FakeLocator:
    def __init__(self, count: int, click_error: Exception | None = None):
        self._count = count
        self.clicks = 0
        self.scrolls = 0
        self.click_timeout = None
        self._click_error = click_error

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return self._count

    async def scroll_into_view_if_needed(self) -> None:
        self.scrolls += 1

    async def click(self, timeout: int | None = None) -> None:
        self.clicks += 1
        self.click_timeout = timeout
        if self._click_error is not None:
            raise self._click_error


class FakeResponseContext:
    def __init__(self, outcome):
        self._outcome = outcome

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @property
    def value(self):
        return self._resolve()

    async def _resolve(self):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class FakePage:
    def __init__(
        self,
        next_button_count: int,
        outcomes: list[object],
        click_error: Exception | None = None,
    ):
        self.locator_stub = FakeLocator(next_button_count, click_error=click_error)
        self._outcomes = list(outcomes)

    def locator(self, _selector: str) -> FakeLocator:
        return self.locator_stub

    def expect_response(self, _predicate, timeout: int):
        assert timeout == 20000
        if not self._outcomes:
            raise AssertionError("missing fake response outcome")
        return FakeResponseContext(self._outcomes.pop(0))


async def _noop_random_sleep(_min_seconds: float, _max_seconds: float) -> None:
    return None


async def _noop_sleep(_seconds: float) -> None:
    return None


def test_advance_search_page_stops_when_no_next_button() -> None:
    page = FakePage(next_button_count=0, outcomes=[])
    logs: list[str] = []

    result = asyncio.run(
        advance_search_page(
            page=page,
            page_num=2,
            logger=logs.append,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is False
    assert result.response is None
    assert result.stop_reason == "no_next_button"
    assert page.locator_stub.clicks == 0
    assert logs == ["已到达最后一页，未找到可用的'下一页'按钮，停止翻页。"]


def test_advance_search_page_stops_after_timeout_retries() -> None:
    page = FakePage(
        next_button_count=1,
        outcomes=[
            PlaywrightTimeoutError("page 2 timeout"),
            PlaywrightTimeoutError("page 2 timeout"),
        ],
    )
    logs: list[str] = []

    result = asyncio.run(
        advance_search_page(
            page=page,
            page_num=2,
            logger=logs.append,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is False
    assert result.response is None
    assert result.stop_reason == "response_timeout"
    assert page.locator_stub.clicks == 2
    assert page.locator_stub.scrolls == 2
    assert logs == [
        "等待第 2 页搜索响应超时，5秒后重试...",
        "等待第 2 页搜索响应超时 2 次，停止翻页。",
    ]


def test_advance_search_page_returns_new_response_on_success() -> None:
    response = FakeResponse(
        url="https://example.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/?page=2"
    )
    page = FakePage(next_button_count=1, outcomes=[response])

    result = asyncio.run(
        advance_search_page(
            page=page,
            page_num=2,
            logger=lambda _message: None,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is True
    assert result.response is response
    assert result.stop_reason is None
    assert page.locator_stub.clicks == 1
    assert page.locator_stub.scrolls == 1
    assert page.locator_stub.click_timeout == 10000


def test_advance_search_page_stops_when_click_times_out() -> None:
    page = FakePage(
        next_button_count=1,
        outcomes=[FakeResponse(url="https://example.com/unused")],
        click_error=PlaywrightTimeoutError("click timeout"),
    )
    logs: list[str] = []

    result = asyncio.run(
        advance_search_page(
            page=page,
            page_num=2,
            logger=logs.append,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is False
    assert result.response is None
    assert result.stop_reason == "click_timeout"
    assert page.locator_stub.clicks == 1
    assert logs == ["第 2 页下一页按钮点击超时，停止翻页。"]


def test_is_search_results_response_matches_exact_search_api() -> None:
    response = FakeResponse(
        url="https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/?foo=bar",
        method="POST",
    )

    assert is_search_results_response(response) is True


def test_is_search_results_response_rejects_search_shade_api() -> None:
    response = FakeResponse(
        url="https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search.shade/1.0/?foo=bar",
        method="POST",
    )

    assert is_search_results_response(response) is False


def test_is_search_results_response_rejects_non_post_request() -> None:
    response = FakeResponse(
        url="https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/?foo=bar",
        method="GET",
    )

    assert is_search_results_response(response) is False
