from src.scraper import _item_matches_region_filter, _parse_region_filters


def test_parse_region_filters_supports_multi_region():
    values = _parse_region_filters("河北/全石家庄, 北京, 天津")
    assert values == ["石家庄", "北京", "天津"]


def test_item_matches_region_filter_handles_city_alias():
    keywords = _parse_region_filters("河北/全石家庄")
    assert _item_matches_region_filter("石家庄", keywords)
    assert _item_matches_region_filter("河北石家庄", keywords)
    assert not _item_matches_region_filter("杭州市", keywords)
