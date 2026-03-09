from src.infrastructure.external.ai_client import AIClient


def test_build_messages_without_images_uses_text_only_content():
    client = AIClient.__new__(AIClient)

    messages = client._build_messages(
        {"商品信息": {"商品标题": "MacBook Pro M2"}, "卖家信息": {"卖家信用等级": "优秀"}},
        [],
        "只分析文字描述和卖家资质。",
    )

    content = messages[0]["content"]
    assert isinstance(content, str)
    assert "MacBook Pro M2" in content
    assert "未提供商品图片" in content


def test_build_messages_with_images_uses_multimodal_content(monkeypatch):
    client = AIClient.__new__(AIClient)
    monkeypatch.setattr(AIClient, "encode_image", staticmethod(lambda _path: "ZmFrZQ=="))

    messages = client._build_messages(
        {"商品信息": {"商品标题": "MacBook Pro M2"}},
        ["fake-image.jpg"],
        "结合图片和文字综合判断。",
    )

    content = messages[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "image_url"
    assert content[-1]["type"] == "text"
