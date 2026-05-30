import asyncio

from src.domain.models.task import Task
from src.infrastructure.persistence.sqlite_connection import init_schema, sqlite_connection
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository


def _task(**overrides):
    values = {
        "id": None,
        "task_name": "Sony A7M4",
        "enabled": True,
        "keyword": "sony a7m4",
        "description": "body",
        "max_pages": 2,
        "personal_only": True,
        "min_price": None,
        "max_price": None,
        "cron": None,
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": "prompts/sony_a7m4_criteria.txt",
        "is_running": False,
    }
    values.update(overrides)
    return Task(**values)


def test_sqlite_task_repository_persists_notification_targets(tmp_path):
    db_path = str(tmp_path / "tasks.db")
    repo = SqliteTaskRepository(db_path=db_path, legacy_config_file=None)
    task = _task(
        notification_targets=[
            {"channel": "telegram", "recipient": "123", "label": "owner"},
            {"channel": "wecom_app", "recipient": "@all"},
        ]
    )

    saved = asyncio.run(repo.save(task))
    loaded = asyncio.run(repo.find_by_id(saved.id))

    assert loaded.notification_targets == [
        {"channel": "telegram", "recipient": "123", "label": "owner"},
        {"channel": "wecom_app", "recipient": "@all"},
    ]


def test_sqlite_schema_migrates_existing_tasks_table(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    with sqlite_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                task_name TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                description TEXT,
                analyze_images INTEGER NOT NULL,
                max_pages INTEGER NOT NULL,
                personal_only INTEGER NOT NULL,
                min_price TEXT,
                max_price TEXT,
                cron TEXT,
                ai_prompt_base_file TEXT NOT NULL,
                ai_prompt_criteria_file TEXT NOT NULL,
                account_state_file TEXT,
                account_strategy TEXT NOT NULL,
                free_shipping INTEGER NOT NULL,
                new_publish_option TEXT,
                region TEXT,
                decision_mode TEXT NOT NULL,
                keyword_rules_json TEXT NOT NULL,
                is_running INTEGER NOT NULL
            )
            """
        )
        init_schema(conn)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]

    assert "notification_targets_json" in columns
