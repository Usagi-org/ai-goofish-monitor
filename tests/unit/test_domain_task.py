import asyncio
import sqlite3
import threading

from src.domain.models.task import Task, TaskCreate, TaskGenerateRequest, TaskUpdate
from src.infrastructure.persistence.sqlite_connection import init_schema, sqlite_connection
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository


def test_task_can_start_and_stop():
    task = Task(
        id=1,
        task_name="Sony A7M4",
        enabled=True,
        keyword="sony a7m4",
        description="body",
        max_pages=2,
        personal_only=True,
        min_price=None,
        max_price=None,
        cron=None,
        ai_prompt_base_file="prompts/base_prompt.txt",
        ai_prompt_criteria_file="prompts/sony_a7m4_criteria.txt",
        is_running=False,
    )

    assert task.can_start() is True
    assert task.can_stop() is False

    running = task.model_copy(update={"is_running": True})
    assert running.can_start() is False
    assert running.can_stop() is True


def test_task_apply_update():
    task = Task(
        id=1,
        task_name="Sony A7M4",
        enabled=True,
        keyword="sony a7m4",
        description="body",
        max_pages=2,
        personal_only=True,
        min_price=None,
        max_price=None,
        cron=None,
        ai_prompt_base_file="prompts/base_prompt.txt",
        ai_prompt_criteria_file="prompts/sony_a7m4_criteria.txt",
        is_running=False,
    )

    update = TaskUpdate(enabled=False, max_pages=5)
    updated = task.apply_update(update)

    assert updated.enabled is False
    assert updated.max_pages == 5
    assert updated.task_name == task.task_name


def test_legacy_keyword_groups_are_flattened_to_keyword_rules():
    task = Task(
        id=1,
        task_name="Sony A7M4",
        enabled=True,
        keyword="sony a7m4",
        description="body",
        max_pages=2,
        personal_only=True,
        min_price=None,
        max_price=None,
        cron=None,
        ai_prompt_base_file="prompts/base_prompt.txt",
        ai_prompt_criteria_file="prompts/sony_a7m4_criteria.txt",
        decision_mode="keyword",
        keyword_rule_groups=[
            {"name": "组1", "include_keywords": ["a7m4", "验货宝"], "exclude_keywords": ["瑕疵"]},
            {"name": "组2", "include_keywords": ["全画幅", "a7m4"], "exclude_keywords": ["拆修"]},
        ],
        is_running=False,
    )

    assert task.keyword_rules == ["a7m4", "验货宝", "全画幅"]


def test_generate_request_accepts_legacy_group_payload():
    req = TaskGenerateRequest(
        task_name="legacy",
        keyword="sony a7m4",
        description="",
        decision_mode="keyword",
        keyword_rule_groups=[{"include_keywords": ["a7m4", "验货宝"], "exclude_keywords": ["瑕疵"]}],
    )
    assert req.keyword_rules == ["a7m4", "验货宝"]


def test_generate_request_enables_image_analysis_by_default():
    req = TaskGenerateRequest(
        task_name="Sony A7M4",
        keyword="sony a7m4",
        description="只看机身成色和卖家信用。",
        decision_mode="ai",
    )
    assert req.analyze_images is True


def test_generate_request_infers_fixed_account_strategy_from_state_file():
    req = TaskGenerateRequest(
        task_name="Sony A7M4",
        keyword="sony a7m4",
        description="只看机身成色和卖家信用。",
        decision_mode="ai",
        account_state_file="state/acc_1.json",
    )

    assert req.account_strategy == "fixed"


def test_generate_request_requires_state_file_for_fixed_account_strategy():
    try:
        TaskGenerateRequest(
            task_name="Sony A7M4",
            keyword="sony a7m4",
            description="只看机身成色和卖家信用。",
            decision_mode="ai",
            account_strategy="fixed",
        )
    except ValueError as exc:
        assert "固定账号模式下必须选择账号" in str(exc)
        return

    raise AssertionError("固定账号模式应要求 account_state_file")


def test_exclude_keywords_normalized_across_task_dtos():
    created = TaskCreate(
        task_name="SSD 监控",
        keyword="固态硬盘 1t",
        description="只要 NVMe 正常健康度",
        decision_mode="ai",
        exclude_keywords="SATA, 坏盘\nsata , 扩容盘",
    )
    assert created.exclude_keywords == ["SATA", "坏盘", "扩容盘"]

    gen_req = TaskGenerateRequest(
        task_name="SSD 关键词",
        keyword="固态硬盘 1t",
        decision_mode="keyword",
        keyword_rules=["980 pro"],
        exclude_keywords=["sata", "  坏盘 ", "SATA"],
    )
    assert gen_req.exclude_keywords == ["sata", "坏盘"]

    task = Task(**created.model_dump(), id=1, is_running=False)
    omitted_patch = TaskUpdate.model_validate({"max_pages": 5})
    assert "exclude_keywords" not in omitted_patch.model_dump(exclude_unset=True)
    untouched = task.apply_update(omitted_patch)
    assert untouched.exclude_keywords == ["SATA", "坏盘", "扩容盘"]

    explicit_null_patch = TaskUpdate.model_validate({"exclude_keywords": None})
    assert explicit_null_patch.model_dump(exclude_unset=True)["exclude_keywords"] == []
    cleared_by_null = task.apply_update(explicit_null_patch)
    assert cleared_by_null.exclude_keywords == []

    cleared = task.apply_update(TaskUpdate(exclude_keywords=""))
    assert cleared.exclude_keywords == []


def test_sqlite_migrates_legacy_tasks_table_missing_exclude_keywords_column(tmp_path):
    db_path = tmp_path / "legacy_tasks.sqlite3"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
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
        conn.execute(
            """
            INSERT INTO tasks (
                id, task_name, enabled, keyword, description, analyze_images,
                max_pages, personal_only, min_price, max_price, cron,
                ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
                account_strategy, free_shipping, new_publish_option, region,
                decision_mode, keyword_rules_json, is_running
            ) VALUES (
                0, 'Legacy Task', 1, 'macbook', 'm1 air', 1,
                3, 1, NULL, NULL, NULL,
                'prompts/base_prompt.txt', 'prompts/macbook_criteria.txt', NULL,
                'auto', 1, NULL, NULL,
                'ai', '[]', 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = SqliteTaskRepository(db_path=str(db_path), legacy_config_file=None)
    tasks = asyncio.run(repo.find_all())
    assert len(tasks) == 1
    assert tasks[0].exclude_keywords == []

    updated = tasks[0].model_copy(update={"exclude_keywords": ["有锁", "sata"]})
    asyncio.run(repo.save(updated))
    reloaded = asyncio.run(repo.find_by_id(0))
    assert reloaded is not None
    assert reloaded.exclude_keywords == ["有锁", "sata"]

    check_conn = sqlite3.connect(str(db_path))
    try:
        cols = [r[1] for r in check_conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "exclude_keywords_json" in cols
        meta = check_conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'migration:tasks_exclude_keywords'"
        ).fetchone()
        assert meta == ("done",)
    finally:
        check_conn.close()


def test_sqlite_concurrent_legacy_tasks_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "concurrent_legacy.sqlite3"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO app_metadata(key, value) VALUES ('migration:result_items_status', 'done')"
        )
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
        conn.commit()
    finally:
        conn.close()

    barrier = threading.Barrier(4)
    errors: list[Exception] = []

    def worker():
        try:
            with sqlite_connection(str(db_path)) as worker_conn:
                barrier.wait(timeout=5)
                init_schema(worker_conn)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == []
    with sqlite_connection(str(db_path)) as verify_conn:
        cols = [r[1] for r in verify_conn.execute("PRAGMA table_info(tasks)").fetchall()]
        assert "exclude_keywords_json" in cols

    # 同时验证多个旧库在首次并发切换 WAL（无前置打开）时不会抛出 database is locked
    wal_errors: list[Exception] = []
    for idx in range(12):
        legacy_db = tmp_path / f"legacy_wal_{idx}.sqlite3"
        raw_conn = sqlite3.connect(str(legacy_db))
        try:
            raw_conn.execute(
                "CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            raw_conn.execute(
                "INSERT INTO app_metadata(key, value) VALUES ('migration:result_items_status', 'done')"
            )
            raw_conn.execute(
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
            raw_conn.commit()
        finally:
            raw_conn.close()

        open_barrier = threading.Barrier(4)

        def concurrent_open_and_migrate(target_db=legacy_db):
            try:
                open_barrier.wait(timeout=5)
                with sqlite_connection(str(target_db)) as c:
                    init_schema(c)
            except Exception as exc:
                wal_errors.append(exc)

        open_threads = [threading.Thread(target=concurrent_open_and_migrate) for _ in range(4)]
        for t in open_threads:
            t.start()
        for t in open_threads:
            t.join(timeout=10)

    assert wal_errors == []
