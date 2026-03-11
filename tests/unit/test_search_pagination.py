import asyncio

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.services.search_pagination import advance_search_page


class FakeResponse:
    def __init__(self, url: str, ok: bool = True):
        self.url = url
        self.ok = ok


class FakeLocator:
    def __init__(self, count: int):
        self._count = count
        self.clicks = 0

    async def count(self) -> int:
        return self._count

    async def click(self) -> None:
        self.clicks += 1


class FakeResponseContext:
    def __init__(self, outcome):
        self._outcome = outcome
        self.value = self._resolve()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def _resolve(self):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class FakePage:
    def __init__(self, next_button_count: int, outcomes: list[object]):
        self.locator_stub = FakeLocator(next_button_count)
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
            api_url_pattern="mtop.goofish.search",
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
            api_url_pattern="mtop.goofish.search",
            logger=logs.append,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is False
    assert result.response is None
    assert result.stop_reason == "timeout"
    assert page.locator_stub.clicks == 2
    assert logs == [
        "翻页到第 2 页超时，5秒后重试...",
        "翻页到第 2 页超时 2 次，停止翻页。",
    ]


def test_advance_search_page_returns_new_response_on_success() -> None:
    response = FakeResponse(url="https://example.com/mtop.goofish.search?page=2")
    page = FakePage(next_button_count=1, outcomes=[response])

    result = asyncio.run(
        advance_search_page(
            page=page,
            page_num=2,
            api_url_pattern="mtop.goofish.search",
            logger=lambda _message: None,
            wait_after_click=_noop_random_sleep,
            retry_sleep=_noop_sleep,
        )
    )

    assert result.advanced is True
    assert result.response is response
    assert result.stop_reason is None
    assert page.locator_stub.clicks == 1
