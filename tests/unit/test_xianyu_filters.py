from src.pipeline.task_runtime import TaskRuntimeConfig
from src.xianyu.filters import SearchFilterOptions, parse_region_parts


def test_search_filter_options_from_runtime_config() -> None:
    runtime_config = TaskRuntimeConfig.from_dict(
        {
            "keyword": "MacBook Air M1",
            "new_publish_option": "一天内",
            "personal_only": True,
            "free_shipping": True,
            "region": "上海/上海市",
            "min_price": "1000",
            "max_price": "3000",
        }
    )

    options = SearchFilterOptions.from_runtime_config(runtime_config)

    assert options == SearchFilterOptions(
        new_publish_option="一天内",
        personal_only=True,
        free_shipping=True,
        region_filter="上海/上海市",
        min_price="1000",
        max_price="3000",
    )


def test_parse_region_parts_trims_and_ignores_empty_segments() -> None:
    assert parse_region_parts(" 上海 / 上海市 // 浦东新区 ") == [
        "上海",
        "上海市",
        "浦东新区",
    ]
    assert parse_region_parts("") == []
