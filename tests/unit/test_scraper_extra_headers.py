from src.scraper import _build_extra_headers


def test_build_extra_headers_drops_fetch_metadata_that_blanks_document():
    headers = _build_extra_headers(
        {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": "secret=1",
            "Referer": "https://www.goofish.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0",
            "sec-ch-ua": '"Chromium"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "Content-Length": "0",
        }
    )

    assert headers == {
        "Accept-Language": "zh-CN,zh;q=0.9",
        "sec-ch-ua": '"Chromium"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
