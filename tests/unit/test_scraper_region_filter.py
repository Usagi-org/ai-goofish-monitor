from src.scraper import (
    REGION_AREA_WRAP_SELECTOR,
    REGION_OPTION_SELECTOR,
    REGION_SUBMIT_SELECTOR,
    REGION_SUBMIT_TEXT,
)


def test_region_selectors_ignore_stale_css_module_hashes():
    assert "areaWrap" in REGION_AREA_WRAP_SELECTOR
    assert "FaZHsn8E" not in REGION_AREA_WRAP_SELECTOR
    assert "provItem" in REGION_OPTION_SELECTOR
    assert "QAdOx8nD" not in REGION_OPTION_SELECTOR
    assert "searchBtn" in REGION_SUBMIT_SELECTOR
    assert "Ic6RKcAb" not in REGION_SUBMIT_SELECTOR


def test_region_submit_text_matches_live_button_label():
    assert REGION_SUBMIT_TEXT.search("查看18件宝贝")
    assert REGION_SUBMIT_TEXT.search("查看999+件宝贝")
    assert REGION_SUBMIT_TEXT.search("筛选中...") is None
