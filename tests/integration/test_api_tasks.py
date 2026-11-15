import asyncio
import time


def test_create_list_update_delete_task(api_client, api_context, sample_task_payload):
    response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert response.status_code == 200
    created = response.json()["task"]
    assert created["task_name"] == sample_task_payload["task_name"]
    assert created["analyze_images"] is True
    assert created["next_run_at"] == "2026-03-19T08:15:00+08:00"

    response = api_client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["keyword"] == sample_task_payload["keyword"]
    assert tasks[0]["analyze_images"] is True
    assert tasks[0]["next_run_at"] == "2026-03-19T08:15:00+08:00"

    response = api_client.patch("/api/tasks/0", json={"enabled": False, "analyze_images": False})
    assert response.status_code == 200
    updated = response.json()["task"]
    assert updated["enabled"] is False
    assert updated["analyze_images"] is False
    assert updated["next_run_at"] is None

    response = api_client.delete("/api/tasks/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_start_stop_task_updates_status(api_client, api_context, sample_task_payload):
    response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert response.status_code == 200

    response = api_client.post("/api/tasks/start/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks/0")
    assert response.status_code == 200
    assert response.json()["is_running"] is True

    response = api_client.post("/api/tasks/stop/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks/0")
    assert response.status_code == 200
    assert response.json()["is_running"] is False

    process_service = api_context["process_service"]
    assert process_service.started == [(0, sample_task_payload["task_name"])]
    assert process_service.stopped == [0]


def test_generate_keyword_mode_task_without_ai_criteria(api_client):
    payload = {
        "task_name": "A7M4 关键词筛选",
        "keyword": "sony a7m4",
        "description": "",
        "decision_mode": "keyword",
        "keyword_rules": ["a7m4", "验货宝"],
        "max_pages": 2,
        "personal_only": True,
    }

    response = api_client.post("/api/tasks/generate", json=payload)
    assert response.status_code == 200
    created = response.json()["task"]
    assert created["decision_mode"] == "keyword"
    assert created["ai_prompt_criteria_file"] == ""
    assert created["keyword_rules"] == ["a7m4", "验货宝"]


def test_generate_ai_task_returns_job_and_completes_async(api_client, api_context, monkeypatch):
    payload = {
        "task_name": "Apple Watch S10",
        "keyword": "apple watch s10",
        "description": "只看国行蜂窝版，电池健康高于 95%，拒绝维修机。",
        "analyze_images": False,
        "decision_mode": "ai",
        "max_pages": 2,
        "personal_only": True,
    }

    async def fake_generate_criteria(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return "[V6.3 核心升级]\\nApple Watch criteria"

    monkeypatch.setattr(
        "src.services.task_generation_runner.generate_criteria",
        fake_generate_criteria,
    )

    response = api_client.post("/api/tasks/generate", json=payload)

    assert response.status_code == 202
    job = response.json()["job"]
    assert isinstance(job["job_id"], str)
    assert job["status"] in {"queued", "running"}
    assert job["task"] is None

    status_response = api_client.get(f"/api/tasks/generate-jobs/{job['job_id']}")
    assert status_response.status_code == 200

    for _ in range(50):
        status_response = api_client.get(f"/api/tasks/generate-jobs/{job['job_id']}")
        latest_job = status_response.json()["job"]
        if latest_job["status"] == "completed":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("任务生成作业未在预期时间内完成")

    assert latest_job["task"]["task_name"] == payload["task_name"]
    assert latest_job["task"]["ai_prompt_criteria_file"].endswith("_criteria.txt")
    assert latest_job["task"]["analyze_images"] is False
    assert api_context["scheduler_service"].reload_calls == 1


def test_create_task_accepts_cron_alias(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["cron"] = "@daily"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 200
    assert response.json()["task"]["cron"] == "0 0 * * *"


def test_create_task_rejects_fixed_account_strategy_without_state_file(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["account_strategy"] = "fixed"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 422


def test_create_task_accepts_rotate_account_strategy(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["account_strategy"] = "rotate"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["account_strategy"] == "rotate"


def test_update_task_accepts_six_field_cron_expression(api_client, sample_task_payload):
    create_response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert create_response.status_code == 200

    response = api_client.patch("/api/tasks/0", json={"cron": "0 0 8 * * *"})

    assert response.status_code == 200

    task_response = api_client.get("/api/tasks/0")
    assert task_response.status_code == 200
    assert task_response.json()["cron"] == "0 0 8 * * *"


def test_create_task_rejects_invalid_cron_expression(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["cron"] = "every day at 8"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 422


def test_delete_task_stops_runtime_and_reindexes_process_state(
    api_client,
    api_context,
    sample_task_payload,
):
    second_payload = dict(sample_task_payload)
    second_payload["task_name"] = "Sony A7CR"
    second_payload["keyword"] = "sony a7cr"
    second_payload["ai_prompt_criteria_file"] = "prompts/sony_a7cr_criteria.txt"

    assert api_client.post("/api/tasks/", json=sample_task_payload).status_code == 200
    assert api_client.post("/api/tasks/", json=second_payload).status_code == 200
    assert api_client.post("/api/tasks/start/0").status_code == 200

    response = api_client.delete("/api/tasks/0")

    assert response.status_code == 200
    process_service = api_context["process_service"]
    assert process_service.stopped == [0]
    assert process_service.reindexed == []
    assert process_service.unpaused == [sample_task_payload["task_name"]]


def test_task_payload_exposes_failure_guard_and_supports_unpause_and_force_start(
    api_client,
    api_context,
    sample_task_payload,
):
    create_resp = api_client.post("/api/tasks/", json=sample_task_payload)
    assert create_resp.status_code == 200
    task_name = sample_task_payload["task_name"]
    assert create_resp.json()["task"]["failure_guard"]["paused"] is False

    process_service = api_context["process_service"]
    process_service.failure_guard_states[task_name] = {
        "paused": True,
        "paused_until": "2026-03-20T12:00:00+08:00",
        "consecutive_failures": 3,
        "threshold": 3,
        "reason": "登录态失效",
        "last_failure_at": "2026-03-19T12:00:00+08:00",
    }

    list_resp = api_client.get("/api/tasks")
    assert list_resp.status_code == 200
    guard_payload = list_resp.json()[0]["failure_guard"]
    assert guard_payload["paused"] is True
    assert guard_payload["reason"] == "登录态失效"
    assert guard_payload["paused_until"] == "2026-03-20T12:00:00+08:00"

    # Starting without force_unpause returns 409 Conflict with reason and recovery time
    blocked_resp = api_client.post("/api/tasks/start/0")
    assert blocked_resp.status_code == 409
    detail = blocked_resp.json()["detail"]
    assert "登录态失效" in detail
    assert "2026-03-20T12:00:00+08:00" in detail
    assert process_service.started == []

    # Explicit unpause endpoint clears pause state
    unpause_resp = api_client.post("/api/tasks/0/unpause")
    assert unpause_resp.status_code == 200
    assert unpause_resp.json()["task"]["failure_guard"]["paused"] is False
    assert process_service.unpaused == [task_name]

    # Re-trip circuit and test force_unpause=true on start endpoint
    process_service.failure_guard_states[task_name] = {
        "paused": True,
        "paused_until": "2026-03-21T08:00:00+08:00",
        "consecutive_failures": 4,
        "threshold": 3,
        "reason": "触发滑块风控",
        "last_failure_at": "2026-03-20T08:00:00+08:00",
    }
    forced_resp = api_client.post("/api/tasks/start/0?force_unpause=true")
    assert forced_resp.status_code == 200
    assert process_service.started == [(0, task_name)]
    assert process_service.get_failure_guard_state(task_name)["paused"] is False


def test_rejects_duplicate_task_names_across_create_generate_update_and_runner(
    api_client,
    api_context,
    sample_task_payload,
    monkeypatch,
):
    first_payload = dict(sample_task_payload)
    first_payload["task_name"] = "  Sony A7M4  "
    resp = api_client.post("/api/tasks/", json=first_payload)
    assert resp.status_code == 200
    assert resp.json()["task"]["task_name"] == "Sony A7M4"

    # Duplicate POST /api/tasks/
    dup_create = api_client.post("/api/tasks/", json=sample_task_payload)
    assert dup_create.status_code == 400
    assert dup_create.json()["detail"] == "任务名称 'Sony A7M4' 已存在，请使用唯一名称"

    # Duplicate POST /api/tasks/generate (keyword mode)
    dup_kw_gen = api_client.post(
        "/api/tasks/generate",
        json={
            "task_name": " Sony A7M4 ",
            "keyword": "sony a7m4",
            "decision_mode": "keyword",
            "keyword_rules": ["a7m4"],
        },
    )
    assert dup_kw_gen.status_code == 400
    assert dup_kw_gen.json()["detail"] == "任务名称 'Sony A7M4' 已存在，请使用唯一名称"

    # Duplicate POST /api/tasks/generate (AI mode) rejected BEFORE creating background job
    dup_ai_gen = api_client.post(
        "/api/tasks/generate",
        json={
            "task_name": "Sony A7M4",
            "keyword": "sony a7m4",
            "description": "国行在保",
            "decision_mode": "ai",
        },
    )
    assert dup_ai_gen.status_code == 400
    assert dup_ai_gen.json()["detail"] == "任务名称 'Sony A7M4' 已存在，请使用唯一名称"

    # Create a second task with distinct name, then PATCH rename to existing task_name -> 400
    second_payload = dict(sample_task_payload)
    second_payload["task_name"] = "Sony A7CR"
    second_payload["keyword"] = "sony a7cr"
    assert api_client.post("/api/tasks/", json=second_payload).status_code == 200

    dup_patch = api_client.patch("/api/tasks/1", json={"task_name": " Sony A7M4 "})
    assert dup_patch.status_code == 400
    assert dup_patch.json()["detail"] == "任务名称 'Sony A7M4' 已存在，请使用唯一名称"

    # Updating task 0 with its own name still succeeds
    same_patch = api_client.patch("/api/tasks/0", json={"task_name": " Sony A7M4 "})
    assert same_patch.status_code == 200
    assert same_patch.json()["task"]["task_name"] == "Sony A7M4"

    # Concurrent AI runner safety: if same-name task appears before runner persists, job fails safely
    import threading

    criteria_gate = threading.Event()

    async def slow_generate_criteria(*_args, **_kwargs):
        await asyncio.to_thread(criteria_gate.wait, 5.0)
        return "criteria content"

    monkeypatch.setattr(
        "src.services.task_generation_runner.generate_criteria",
        slow_generate_criteria,
    )
    race_gen = api_client.post(
        "/api/tasks/generate",
        json={
            "task_name": "Race Camera",
            "keyword": "race cam",
            "description": "成色好",
            "decision_mode": "ai",
        },
    )
    assert race_gen.status_code == 202
    job_id = race_gen.json()["job"]["job_id"]

    # Insert same-name task while AI job is paused in generate_criteria, then release gate
    race_conflict = dict(sample_task_payload)
    race_conflict["task_name"] = "Race Camera"
    assert api_client.post("/api/tasks/", json=race_conflict).status_code == 200
    criteria_gate.set()

    for _ in range(50):
        job_state = api_client.get(f"/api/tasks/generate-jobs/{job_id}").json()["job"]
        if job_state["status"] in {"failed", "completed"}:
            break
        time.sleep(0.02)
    assert job_state["status"] == "failed"
    assert "已存在" in (job_state["error"] or "")


def test_legacy_duplicate_task_names_protect_shared_failure_guard(
    api_client,
    api_context,
    sample_task_payload,
):
    from src.domain.models.task import Task

    repository = api_context["repository"]
    process_service = api_context["process_service"]

    # Seed two legacy tasks with identical task_name directly into SQLite
    base_task_data = {
        **sample_task_payload,
        "is_running": False,
    }
    asyncio.run(repository.save(Task(**base_task_data)))
    import sqlite3
    second = {**base_task_data, "task_name": "second"}
    asyncio.run(repository.save(Task(**second)))
    with sqlite3.connect(api_context["db_path"]) as conn:
        conn.execute("UPDATE tasks SET task_name = ? WHERE id = 1", (base_task_data["task_name"],))

    process_service.failure_guard_states["Sony A7M4"] = {
        "paused": True,
        "paused_until": "2026-03-25T10:00:00+08:00",
        "consecutive_failures": 3,
        "threshold": 3,
        "reason": "风控拦截",
        "last_failure_at": "2026-03-24T10:00:00+08:00",
    }

    # Unpause and force_unpause must return 409 when duplicate task_name exists
    unpause_conflict = api_client.post("/api/tasks/0/unpause")
    assert unpause_conflict.status_code == 409
    assert "存在多个同名任务 'Sony A7M4'，请先重命名后再解除熔断" == unpause_conflict.json()["detail"]

    force_conflict = api_client.post("/api/tasks/start/0?force_unpause=true")
    assert force_conflict.status_code == 409
    assert "存在多个同名任务 'Sony A7M4'，请先重命名后再解除熔断" == force_conflict.json()["detail"]

    # Deleting one of the duplicate tasks must NOT clear shared failure guard record
    del_first = api_client.delete("/api/tasks/0")
    assert del_first.status_code == 200
    assert process_service.unpaused == []
    assert process_service.get_failure_guard_state("Sony A7M4")["paused"] is True

    # Deleting the last remaining task with that name DOES clear failure guard record
    del_second = api_client.delete("/api/tasks/1")
    assert del_second.status_code == 200
    assert process_service.unpaused == ["Sony A7M4"]


def test_start_task_uses_atomic_manual_start_without_precheck_race(
    api_client,
    api_context,
    sample_task_payload,
    monkeypatch,
):
    assert api_client.post("/api/tasks/", json=sample_task_payload).status_code == 200
    process_service = api_context["process_service"]

    # Forbid route-level get_failure_guard_state pre-check during POST /api/tasks/start/{id}
    monkeypatch.setattr(
        process_service,
        "get_failure_guard_state",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("start_task route must not call get_failure_guard_state separately")
        ),
    )

    # Simulate circuit tripping right before atomic start_task_manual executes -> 409 (not 500!)
    process_service.failure_guard_states["Sony A7M4"] = {
        "paused": True,
        "paused_until": "2026-03-26T08:00:00+08:00",
        "consecutive_failures": 3,
        "threshold": 3,
        "reason": "并发触发熔断",
        "last_failure_at": "2026-03-25T08:00:00+08:00",
    }
    paused_resp = api_client.post("/api/tasks/start/0")
    assert paused_resp.status_code == 409
    assert "并发触发熔断" in paused_resp.json()["detail"]
    assert "2026-03-26T08:00:00+08:00" in paused_resp.json()["detail"]

    # Concurrent runtime already_running -> 400
    process_service.failure_guard_states.clear()
    process_service.running_ids.add(0)
    running_resp = api_client.post("/api/tasks/start/0")
    assert running_resp.status_code == 400
    assert running_resp.json()["detail"] == "任务已在运行中"

    # Spawn error -> 500
    process_service.running_ids.clear()
    process_service.spawn_error_ids.add(0)
    err_resp = api_client.post("/api/tasks/start/0")
    assert err_resp.status_code == 500
    assert err_resp.json()["detail"] == "启动任务失败"


def test_rename_paused_task_migrates_guard_state_and_does_not_leak_to_new_same_name_task(
    api_client,
    api_context,
    sample_task_payload,
):
    assert api_client.post("/api/tasks/", json=sample_task_payload).status_code == 200
    process_service = api_context["process_service"]
    process_service.failure_guard_states["Sony A7M4"] = {
        "paused": True,
        "paused_until": "2026-03-26T08:00:00+08:00",
        "consecutive_failures": 3,
        "threshold": 3,
        "reason": "登录态过期",
        "last_failure_at": "2026-03-25T08:00:00+08:00",
    }

    rename_resp = api_client.patch("/api/tasks/0", json={"task_name": "Sony A7M4 Renamed"})
    assert rename_resp.status_code == 200
    assert rename_resp.json()["task"]["failure_guard"]["paused"] is True

    # 新建原名任务 A，不应误继承已迁移走的暂停状态
    create_new_a = api_client.post("/api/tasks/", json=sample_task_payload)
    assert create_new_a.status_code == 200
    assert create_new_a.json()["task"]["failure_guard"]["paused"] is False

    # Cron 按新名称检查仍受熔断保护
    assert asyncio.run(process_service.start_task(0, "Sony A7M4 Renamed")) is False
    assert asyncio.run(process_service.start_task(1, "Sony A7M4")) is True


def test_concurrent_ai_generation_jobs_keep_winner_criteria_file_intact(
    api_client, api_context, tmp_path, monkeypatch,
):
    from threading import Barrier

    both_generating = Barrier(2)

    async def generate(*, user_description, **kwargs):
        await asyncio.to_thread(both_generating.wait, 5)
        return user_description

    monkeypatch.setattr("src.services.task_generation_runner.generate_criteria", generate)
    descriptions = ("criteria from first request", "criteria from second request")
    job_ids = []
    for description in descriptions:
        response = api_client.post("/api/tasks/generate", json={
            "task_name": "Concurrent Watch", "keyword": "watch", "description": description,
        })
        assert response.status_code == 202
        job_ids.append(response.json()["job"]["job_id"])

    for _ in range(250):
        jobs = [api_client.get(f"/api/tasks/generate-jobs/{job_id}").json()["job"] for job_id in job_ids]
        if all(job["status"] in {"completed", "failed"} for job in jobs):
            break
        time.sleep(0.02)

    assert sorted(job["status"] for job in jobs) == ["completed", "failed"]
    winner = next(i for i, job in enumerate(jobs) if job["status"] == "completed")
    tasks = asyncio.run(api_context["task_service"].get_all_tasks())
    assert len(tasks) == 1
    assert tasks[0].description == descriptions[winner]
    criteria = tmp_path / tasks[0].ai_prompt_criteria_file
    assert criteria.read_text(encoding="utf-8") == descriptions[winner]
    assert list(criteria.parent.iterdir()) == [criteria]


def test_rename_and_delete_require_guard_commit(api_client, api_context, sample_task_payload, tmp_path, monkeypatch):
    from src.api import dependencies as deps
    from src.failure_guard import FailureGuard
    from src.services.process_service import ProcessService

    process = ProcessService()
    process.failure_guard = FailureGuard(str(tmp_path / "guard.json"), threshold=1)
    api_context["app"].dependency_overrides[deps.get_process_service] = lambda: process
    original = api_client.post("/api/tasks/", json=sample_task_payload).json()["task"]
    task_url = f"/api/tasks/{original['id']}"
    process.failure_guard.record_failure(original["task_name"], "pause")

    def fail_write(_data):
        raise PermissionError("read-only guard")

    with monkeypatch.context() as m:
        m.setattr(process.failure_guard, "_save_unlocked", fail_write)
        assert api_client.patch(task_url, json={"task_name": "renamed"}).status_code == 500
        assert api_client.delete(task_url).status_code == 500
    row = api_client.get(task_url).json()
    assert row["task_name"] == original["task_name"]
    assert row["failure_guard"]["paused"]


def test_rename_rechecks_running_status_after_criteria_generation(api_client, api_context, sample_task_payload, monkeypatch, tmp_path):
    row = api_client.post("/api/tasks/", json=sample_task_payload).json()["task"]
    task_id = row["id"]

    async def generate(**kwargs):
        await api_context["task_service"].update_task_status(task_id, True)
        return "criteria from rejected update"

    monkeypatch.setattr("src.api.routes.tasks.generate_criteria", generate)
    response = api_client.patch(f"/api/tasks/{task_id}", json={"task_name": "new", "description": "new criteria"})
    assert response.status_code == 409
    current = api_client.get(f"/api/tasks/{task_id}").json()
    assert current["task_name"] == row["task_name"]
    assert current["is_running"]
    assert not (tmp_path / current["ai_prompt_criteria_file"]).exists()


def test_legacy_name_whitespace_and_running_rename(api_client, api_context, sample_task_payload, tmp_path):
    import sqlite3
    from src.api import dependencies as deps
    from src.failure_guard import FailureGuard
    from src.services.process_service import ProcessService

    process = ProcessService()
    process.failure_guard = FailureGuard(str(tmp_path / "guard.json"), threshold=1)
    api_context["app"].dependency_overrides[deps.get_process_service] = lambda: process
    row = api_client.post("/api/tasks/", json=sample_task_payload).json()["task"]
    name = row["task_name"]
    legacy = f"  {name}  "
    with sqlite3.connect(api_context["db_path"]) as conn:
        conn.execute("UPDATE tasks SET task_name = ?, is_running = 1 WHERE id = ?", (legacy, row["id"]))
    process.failure_guard.record_failure(legacy, "pause")
    path = f"/api/tasks/{row['id']}"
    assert api_client.patch(path, json={"task_name": name}).status_code == 409
    with sqlite3.connect(api_context["db_path"]) as conn:
        conn.execute("UPDATE tasks SET is_running = 0 WHERE id = ?", (row["id"],))
    response = api_client.patch(path, json={"task_name": name})
    assert response.status_code == 200
    assert response.json()["task"]["failure_guard"]["paused"]
    assert not process.failure_guard.get_task_state(legacy)["paused"]


def test_start_reserves_task_before_spawn_and_until_status_is_written(
    api_context, sample_task_payload, tmp_path, monkeypatch,
):
    import asyncio
    import sys
    import httpx
    from src.api import dependencies as deps
    from src.failure_guard import FailureGuard
    from src.services.process_service import ProcessService

    service = api_context["task_service"]
    process = ProcessService(task_loader=service.get_task)
    process.failure_guard = FailureGuard(str(tmp_path / "guard.json"))
    api_context["app"].dependency_overrides[deps.get_process_service] = lambda: process
    monkeypatch.setattr(process, "_build_spawn_command", lambda name: [sys.executable, "-c", "import time; time.sleep(30)"])

    async def scenario():
        spawn_entered, spawn_allowed = asyncio.Event(), asyncio.Event()
        hook_entered, hook_allowed = asyncio.Event(), asyncio.Event()
        spawn = process._spawn_process

        async def hold_spawn(name, log):
            spawn_entered.set()
            await spawn_allowed.wait()
            return await spawn(name, log)

        async def hold_hook(task_id):
            hook_entered.set()
            await hook_allowed.wait()
            await service.update_task_status(task_id, True)

        monkeypatch.setattr(process, "_spawn_process", hold_spawn)
        process.set_lifecycle_hooks(on_started=hold_hook, on_stopped=lambda i: service.update_task_status(i, False))
        transport = httpx.ASGITransport(app=api_context["app"])
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {**sample_task_payload, "account_strategy": "rotate"}
            task = (await client.post("/api/tasks/", json=payload)).json()["task"]
            task_id, old_name = task["id"], task["task_name"]
            url = f"/api/tasks/{task_id}"
            start_url = f"/api/tasks/start/{task_id}"
            pending = asyncio.create_task(client.post(start_url))
            try:
                await asyncio.wait_for(spawn_entered.wait(), 5)
                assert not process.is_running(task_id)
                assert (await client.patch(url, json={"task_name": "renamed"})).status_code == 409
                assert (await client.delete(url)).status_code == 423
                assert (await client.post(start_url + "?force_unpause=true")).status_code == 423
                spawn_allowed.set()
                await asyncio.wait_for(hook_entered.wait(), 5)
                assert process.is_running(task_id)
                assert not (await service.get_task(task_id)).is_running
                assert (await client.patch(url, json={"task_name": "renamed"})).status_code == 409
                assert (await client.delete(url)).status_code == 423
                assert process.is_running(task_id)
            finally:
                spawn_allowed.set()
                hook_allowed.set()
                result = await asyncio.wait_for(pending, 10)
                await process.stop_task(task_id)
            assert result.status_code == 200
            assert (await client.patch(url, json={"task_name": "renamed"})).status_code == 200
            assert not await process.start_task(task_id, old_name)
            updated = await service.get_task(task_id)
            assert (updated.task_name, updated.account_strategy) == ("renamed", "rotate")

            stop_entered, stop_allowed = asyncio.Event(), asyncio.Event()
            stop = process.stop_task

            async def hold_stop(i):
                stop_entered.set()
                await stop_allowed.wait()
                return await stop(i)

            monkeypatch.setattr(process, "stop_task", hold_stop)
            deletion = asyncio.create_task(client.delete(url))
            try:
                await asyncio.wait_for(stop_entered.wait(), 5)
                assert (await client.post(start_url + "?force_unpause=true")).status_code == 423
                assert not await process.start_task(task_id, "renamed")
            finally:
                stop_allowed.set()
                result = await asyncio.wait_for(deletion, 5)
            assert result.status_code == 200
            assert (await client.get(url)).status_code == 404

    asyncio.run(scenario())
