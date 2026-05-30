from src.xianyu.browser_session import (
    build_launch_kwargs,
    build_context_overrides,
    build_extra_headers,
    default_context_options,
    is_login_url,
    looks_like_mobile,
)


def test_is_login_url_detects_passport_and_mini_login() -> None:
    assert is_login_url("https://passport.goofish.com/login") is True
    assert is_login_url("https://www.goofish.com/mini_login.htm") is True
    assert is_login_url("https://www.goofish.com/search?q=ipad") is False


def test_default_context_options_keeps_mobile_defaults() -> None:
    options = default_context_options()

    assert options["is_mobile"] is True
    assert options["has_touch"] is True
    assert options["locale"] == "zh-CN"
    assert options["timezone_id"] == "Asia/Shanghai"


def test_build_context_overrides_uses_snapshot_environment() -> None:
    overrides = build_context_overrides(
        {
            "headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "env": {
                "screen": {"width": 390, "height": 844, "devicePixelRatio": 3},
                "navigator": {"maxTouchPoints": 5},
                "intl": {"timeZone": "Asia/Shanghai"},
            },
        }
    )

    assert overrides["is_mobile"] is True
    assert overrides["viewport"] == {"width": 390, "height": 844}
    assert overrides["device_scale_factor"] == 3.0
    assert overrides["locale"] == "zh-CN"


def test_build_extra_headers_filters_cookie_and_none_values() -> None:
    assert build_extra_headers(
        {"Cookie": "secret", "Accept": "text/html", "X-Empty": None}
    ) == {"Accept": "text/html"}


def test_looks_like_mobile_returns_none_for_unknown_user_agent() -> None:
    assert looks_like_mobile("") is None
    assert looks_like_mobile("Mozilla/5.0 Windows NT 10.0") is False
    assert looks_like_mobile("Mozilla/5.0 Android Mobile") is True


def test_build_launch_kwargs_preserves_scraper_launch_args(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.xianyu.browser_session.resolve_browser_channel", lambda: "chromium"
    )

    kwargs = build_launch_kwargs(True, "http://127.0.0.1:7890")

    assert kwargs == {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
        "channel": "chromium",
        "proxy": {"server": "http://127.0.0.1:7890"},
    }


def test_build_launch_kwargs_omits_proxy_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.xianyu.browser_session.resolve_browser_channel", lambda: "chrome"
    )

    kwargs = build_launch_kwargs(False, None)

    assert kwargs["headless"] is False
    assert kwargs["channel"] == "chrome"
    assert "proxy" not in kwargs
