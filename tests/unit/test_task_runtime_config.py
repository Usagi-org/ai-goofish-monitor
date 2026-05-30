from src.pipeline.task_runtime import TaskRuntimeConfig


def test_task_runtime_config_defaults_and_normalization() -> None:
    config = TaskRuntimeConfig.from_dict(
        {
            "keyword": "MacBook Air M1",
            "decision_mode": "unexpected",
            "analyze_images": "false",
            "new_publish_option": "__none__",
            "region": " 上海 ",
        }
    )

    assert config.keyword == "MacBook Air M1"
    assert config.max_pages == 1
    assert config.decision_mode == "ai"
    assert config.analyze_images is False
    assert config.new_publish_option == ""
    assert config.region_filter == "上海"
    assert config.keyword_rules == []
    assert config.notification_targets == []


def test_task_runtime_config_preserves_keyword_mode_lists_and_flags() -> None:
    config = TaskRuntimeConfig.from_dict(
        {
            "keyword": "ipad",
            "max_pages": 3,
            "personal_only": True,
            "decision_mode": " keyword ",
            "keyword_rules": [{"include": "pro"}],
            "notification_targets": ["wecom-app"],
            "free_shipping": True,
            "new_publish_option": "1h",
            "ai_prompt_text": "good deal",
        }
    )

    assert config.max_pages == 3
    assert config.personal_only is True
    assert config.decision_mode == "keyword"
    assert config.keyword_rules == [{"include": "pro"}]
    assert config.notification_targets == ["wecom-app"]
    assert config.free_shipping is True
    assert config.new_publish_option == "1h"
    assert config.ai_prompt_text == "good deal"
