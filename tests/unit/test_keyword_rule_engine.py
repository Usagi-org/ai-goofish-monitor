from src.keyword_rule_engine import build_search_text, evaluate_keyword_rules


def _sample_record():
    return {
        "商品信息": {
            "商品标题": "Sony A7M4 全画幅相机",
            "当前售价": "10000",
            "商品标签": ["验货宝", "包邮"],
        },
        "卖家信息": {
            "卖家昵称": "摄影器材店",
            "卖家个性签名": "可验机，支持同城面交",
        },
    }


def test_build_search_text_contains_product_and_seller_fields():
    text = build_search_text(_sample_record())
    assert "sony a7m4" in text
    assert "摄影器材店" in text
    assert "支持同城面交" in text


def test_keyword_rules_group_and_or_match():
    text = build_search_text(_sample_record())
    groups = [
        {"name": "组1", "include_keywords": ["a7m4", "佳能"], "exclude_keywords": []},
        {"name": "组2", "include_keywords": ["a7m4", "验货宝"], "exclude_keywords": []},
    ]
    result = evaluate_keyword_rules(groups, text)
    assert result["is_recommended"] is True
    assert result["analysis_source"] == "keyword"
    assert result["matched_groups"] == ["组2"]


def test_keyword_rules_not_keyword_blocks_group():
    text = build_search_text(_sample_record())
    groups = [
        {"name": "组1", "include_keywords": ["a7m4"], "exclude_keywords": ["面交"]},
    ]
    result = evaluate_keyword_rules(groups, text)
    assert result["is_recommended"] is False
    assert "排除词" in result["reason"]


def test_keyword_rules_case_insensitive_contains():
    text = build_search_text(_sample_record())
    groups = [
        {"name": "组1", "include_keywords": ["SONY", "A7M4"], "exclude_keywords": []},
    ]
    result = evaluate_keyword_rules(groups, text)
    assert result["is_recommended"] is True
