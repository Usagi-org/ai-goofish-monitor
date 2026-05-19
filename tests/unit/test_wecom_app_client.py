import asyncio

from src.infrastructure.external.notification_clients.wecom_app_client import WeComAppClient
from src.utils import convert_goofish_link


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"errcode": 0, "errmsg": "ok"}


def test_wecom_app_textcard_description_uses_card_url_without_anchor(monkeypatch):
    captured = {}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)

    client = WeComAppClient(
        corpid="corp",
        corpsecret="secret",
        agentid="100001",
        touser="user1",
        pcurl_to_mobile=True,
    )
    client._access_token = "cached-token"
    client._token_expires_at = 9999999999

    desktop_link = "https://www.goofish.com/item?id=123456&spm=test"
    expected_mobile_link = convert_goofish_link(desktop_link)

    asyncio.run(
        client.send(
            {
                "商品标题": "MacBook <验货宝>",
                "当前售价": "3900",
                "商品链接": desktop_link,
            },
            "命中1个关键词:<验货宝>",
        )
    )

    payload = captured["payload"]
    textcard = payload["textcard"]
    description = textcard["description"]

    assert payload["msgtype"] == "textcard"
    assert textcard["url"] == expected_mobile_link
    assert textcard["btntxt"] == "查看详情"
    assert "<div" not in description
    assert "</div>" not in description
    assert "class=" not in description
    assert "<a " not in description
    assert "href=" not in description
    assert "goofish.com" not in description
    assert "点击卡片或下方按钮查看详情" in description
    assert "MacBook &lt;验货宝&gt;" in description
    assert "命中1个关键词:&lt;验货宝&gt;" in description
