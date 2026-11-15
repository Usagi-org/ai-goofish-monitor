import asyncio
from datetime import datetime, timedelta
import sys
from zoneinfo import ZoneInfo
from types import SimpleNamespace

from src.services.process_service import ProcessService


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = None
        self._done = asyncio.Event()

    async def wait(self):
        await self._done.wait()
        return self.returncode

    def finish(self, returncode: int = 0):
        self.returncode = returncode
        self._done.set()

    def terminate(self):
        self.finish(-15)

    def kill(self):
        self.finish(-9)


def test_process_service_marks_task_stopped_when_process_exits(monkeypatch, tmp_path):
    fake_process = FakeProcess(pid=4321)
    events = []

    async def run_scenario():
        service = ProcessService()
        service.failure_guard.should_skip_start = lambda *args, **kwargs: SimpleNamespace(
            skip=False,
            should_notify=False,
            reason="",
            consecutive_failures=0,
            paused_until=None,
        )

        stopped = asyncio.Event()

        async def on_started(task_id: int):
            events.append(("started", task_id))

        async def on_stopped(task_id: int):
            events.append(("stopped", task_id))
            stopped.set()

        service.set_lifecycle_hooks(on_started=on_started, on_stopped=on_stopped)

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr(
            "src.services.process_service.build_task_log_path",
            lambda task_id, _task_name: str(tmp_path / f"task-{task_id}.log"),
        )
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        started = await service.start_task(0, "task-a")
        assert started is True
        assert events == [("started", 0)]
        assert service.is_running(0) is True

        fake_process.finish(0)
        await asyncio.wait_for(stopped.wait(), timeout=1)

        assert ("stopped", 0) in events
        assert service.is_running(0) is False

    asyncio.run(run_scenario())


def test_process_service_reindexes_runtime_maps_after_delete():
    service = ProcessService()
    proc_a = object()
    proc_c = object()
    watcher_a = object()
    watcher_c = object()

    service.processes = {0: proc_a, 2: proc_c}
    service.log_paths = {0: "a.log", 2: "c.log"}
    service.task_names = {0: "A", 2: "C"}
    service.exit_watchers = {0: watcher_a, 2: watcher_c}

    service.reindex_after_delete(1)

    assert service.processes == {0: proc_a, 1: proc_c}
    assert service.log_paths == {0: "a.log", 1: "c.log"}
    assert service.task_names == {0: "A", 1: "C"}
    assert service.exit_watchers == {0: watcher_a, 1: watcher_c}


def test_process_service_adds_debug_limit_arg_when_env_enabled(monkeypatch):
    monkeypatch.setenv("SPIDER_DEBUG_LIMIT", "1")
    service = ProcessService()

    command = service._build_spawn_command("task-a")

    assert command == [
        sys.executable,
        "-u",
        "spider_v2.py",
        "--task-name",
        "task-a",
        "--debug-limit",
        "1",
    ]


def test_process_service_force_unpause_clears_guard_before_starting(monkeypatch, tmp_path):
    fake_process = FakeProcess(pid=8765)

    async def run_scenario():
        service = ProcessService()
        service.failure_guard.path = str(tmp_path / "guard.json")
        service.failure_guard.threshold = 2
        service.failure_guard.pause_seconds = 3600

        monkeypatch.setattr(service, "_resolve_cookie_path", lambda _name: None)
        monkeypatch.setattr(
            "src.services.process_service.build_task_log_path",
            lambda task_id, _task_name: str(tmp_path / f"task-{task_id}.log"),
        )

        async def fake_notify(*_args, **_kwargs):
            return None

        monkeypatch.setattr("src.services.process_service.send_ntfy_notification", fake_notify)

        async def fake_create_subprocess_exec(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        service.failure_guard.record_failure("task-a", "risk-control")
        service.failure_guard.record_failure("task-a", "risk-control")
        assert service.get_failure_guard_state("task-a")["paused"] is True

        # Default start_task (e.g. Cron) skips paused task
        skipped = await service.start_task(0, "task-a")
        assert skipped is False
        assert service.get_failure_guard_state("task-a")["paused"] is True

        # force_unpause=True clears guard and starts task
        started = await service.start_task(0, "task-a", force_unpause=True)
        assert started is True
        assert service.get_failure_guard_state("task-a")["paused"] is False

        fake_process.finish(0)
        await service._drain_finished_process(0)

    asyncio.run(run_scenario())


def test_start_task_manual_returns_structured_status_without_sending_skip_notification(
    monkeypatch, tmp_path
):
    from src.domain.models.task import Task

    fake_process = FakeProcess(pid=9999)
    notify_calls = []

    def make_task(task_id: int = 0, name: str = "task-manual") -> Task:
        return Task(
            id=task_id,
            task_name=name,
            enabled=True,
            keyword="k",
            description="d",
            analyze_images=False,
            max_pages=1,
            personal_only=True,
            ai_prompt_base_file="prompts/base_prompt.txt",
            ai_prompt_criteria_file="prompts/c.txt",
            account_state_file=str(tmp_path / "acc.json"),
        )

    async def run_scenario():
        service = ProcessService()
        service.failure_guard.path = str(tmp_path / "guard.json")
        service.failure_guard.threshold = 2
        service.failure_guard.pause_seconds = 3600

        async def fake_notify(*args, **kwargs):
            notify_calls.append((args, kwargs))

        monkeypatch.setattr("src.services.process_service.send_ntfy_notification", fake_notify)
        monkeypatch.setattr(
            "src.services.process_service.build_task_log_path",
            lambda task_id, _task_name: str(tmp_path / f"task-{task_id}.log"),
        )
        monkeypatch.setattr(
            "src.services.process_service.find_task_by_name_sync",
            lambda _name: (_ for _ in ()).throw(AssertionError("Must not query SQLite when Task provided")),
        )

        task = make_task()
        service.failure_guard.record_failure(task.task_name, "滑块验证")
        service.failure_guard.record_failure(task.task_name, "滑块验证")

        # Manual start when paused -> structured paused result, NO ntfy skip notification
        paused_res = await service.start_task_manual(task, force_unpause=False)
        assert paused_res.status == "paused"
        assert paused_res.reason == "滑块验证"
        assert paused_res.paused_until is not None
        assert paused_res.consecutive_failures == 2
        assert notify_calls == []

        # 跨日后先手动启动得到 paused(409)，随后 Cron 启动仍必须正常发送当天的暂停通知
        tz = ZoneInfo("Asia/Shanghai")
        day1 = datetime(2026, 3, 4, 12, 0, 0, tzinfo=tz)
        day2 = day1 + timedelta(days=1, minutes=5)
        service.unpause_task(task.task_name)
        service.failure_guard.pause_seconds = 3 * 24 * 3600
        service.failure_guard.record_failure(task.task_name, "滑块验证", now=day1)
        service.failure_guard.record_failure(task.task_name, "滑块验证", now=day1)
        monkeypatch.setattr(
            "src.failure_guard._now",
            lambda _tz, now=None: now or day2,
        )

        manual_next_day = await service.start_task_manual(task, force_unpause=False)
        assert manual_next_day.status == "paused"
        assert notify_calls == []

        cron_skipped = await service.start_task(task.id, task.task_name)
        assert cron_skipped is False
        assert len(notify_calls) == 1
        notify_calls.clear()

        # Spawn failure -> spawn_error
        async def broken_spawn(*_args, **_kwargs):
            raise OSError("boom")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", broken_spawn)
        err_res = await service.start_task_manual(task, force_unpause=True)
        assert err_res.status == "spawn_error"

        # Normal start -> started, second call -> already_running
        async def ok_spawn(*_args, **_kwargs):
            return fake_process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", ok_spawn)
        started_res = await service.start_task_manual(task, force_unpause=False)
        assert started_res.status == "started"

        running_res = await service.start_task_manual(task, force_unpause=False)
        assert running_res.status == "already_running"

        fake_process.finish(0)
        await service._drain_finished_process(task.id)

    asyncio.run(run_scenario())


def test_serialize_tasks_loads_snapshot_once_and_avoids_sqlite_n_plus_one(
    monkeypatch, tmp_path
):
    from src.domain.models.task import Task
    from src.services.task_payloads import serialize_tasks

    service = ProcessService()
    service.failure_guard.path = str(tmp_path / "guard.json")
    service.failure_guard.threshold = 2
    service.failure_guard.record_failure("task-1", "expired")
    service.failure_guard.record_failure("task-1", "expired")

    monkeypatch.setattr(
        "src.services.process_service.find_task_by_name_sync",
        lambda _name: (_ for _ in ()).throw(AssertionError("N+1 SQLite query triggered")),
    )

    snapshot_calls = 0
    orig_load_snapshot = service.failure_guard.load_snapshot

    def counted_load_snapshot():
        nonlocal snapshot_calls
        snapshot_calls += 1
        return orig_load_snapshot()

    monkeypatch.setattr(service.failure_guard, "load_snapshot", counted_load_snapshot)

    tasks = [
        Task(
            id=i,
            task_name=f"task-{i}",
            enabled=True,
            keyword="k",
            description="d",
            analyze_images=False,
            max_pages=1,
            personal_only=True,
            ai_prompt_base_file="prompts/base_prompt.txt",
            ai_prompt_criteria_file="prompts/c.txt",
            account_state_file=str(tmp_path / f"acc-{i}.json"),
        )
        for i in range(5)
    ]

    payloads = serialize_tasks(tasks, scheduler_service=None, process_service=service)
    assert len(payloads) == 5
    assert snapshot_calls == 1
    assert payloads[1]["failure_guard"]["paused"] is True
    assert payloads[0]["failure_guard"]["paused"] is False
