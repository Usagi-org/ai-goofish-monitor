import asyncio

from src.parsers import (
    _parse_search_results_json,
    _parse_user_items_data,
    calculate_reputation_from_ratings,
    parse_ratings_data,
    parse_user_head_data,
)


def test_parse_search_results(load_json_fixture):
    raw = load_json_fixture("search_results.json")
    items = asyncio.run(_parse_search_results_json(raw, source="search"))
    assert len(items) == 1
    item = items[0]
    assert item["商品标题"] == "Sony A7M4 Body"
    assert item["当前售价"].startswith("¥")
    assert "包邮" in item["商品标签"]
    assert "验货宝" in item["商品标签"]
    assert item["商品链接"].startswith("https://www.goofish.com/")


def test_range_price_preserves_valid_neighbors(load_json_fixture):
    from copy import deepcopy
    from src.domain.price import parse_price_value

    raw = load_json_fixture("search_results.json")
    cards = raw["data"]["resultList"]
    template = cards[0]
    cards.clear()
    for price in ("¥100", "1万-2万", "2.3万", "¥80"):
        card = deepcopy(template)
        card["data"]["item"]["main"]["exContent"]["price"] = [{"text": price}]
        cards.append(card)
    rows = asyncio.run(_parse_search_results_json(raw, source="search"))
    prices = [row["当前售价"] for row in rows]
    assert prices == ["¥100", "1万-2万", "¥23000", "¥80"]
    assert [parse_price_value(price) for price in prices] == [100, None, 23000, 80]


def test_parse_user_head_and_items(load_json_fixture):
    head_json = load_json_fixture("user_head.json")
    items_json = load_json_fixture("user_items.json")

    head = asyncio.run(parse_user_head_data(head_json))
    assert head["卖家昵称"] == "seller_01"
    assert head["卖家收到的评价总数"] == 88

    items = asyncio.run(_parse_user_items_data(items_json))
    assert items[0]["商品状态"] == "在售"
    assert items[1]["商品状态"] == "已售"


def test_parse_ratings_and_reputation(load_json_fixture):
    ratings_json = load_json_fixture("ratings.json")
    ratings = asyncio.run(parse_ratings_data(ratings_json))
    assert ratings[0]["评价类型"] == "好评"

    reputation = asyncio.run(calculate_reputation_from_ratings(ratings_json))
    assert reputation["作为卖家的好评数"].startswith("1/")
    assert reputation["作为买家的好评数"].startswith("1/")
