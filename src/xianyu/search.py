from urllib.parse import urlencode


def build_search_url(keyword: str) -> str:
    return f"https://www.goofish.com/search?{urlencode({'q': keyword})}"
