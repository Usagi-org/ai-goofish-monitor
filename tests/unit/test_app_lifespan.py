import asyncio

import src.app as app_module


class _FakeTaskService:
    def __init__(self, _repo):
        self.updated = []

    async def get_all_tasks(self):
        return []

    async def update_task_status(self, task_id, is_running):
        self.updated.append((task_id, is_running))


class _FakeSchedulerService:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.reload_payload = None

    async def reload_jobs(self, tasks):
        self.reload_payload = list(tasks)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class _FakeProcessService:
    def __init__(self):
        self.stop_all_called = False

    async def stop_all(self):
        self.stop_all_called = True


def test_lifespan_cleans_task_logs_on_startup(monkeypatch):
    called = {}
    fake_scheduler = _FakeSchedulerService()
    fake_process = _FakeProcessService()

    monkeypatch.setattr(app_module, "scheduler_service", fake_scheduler)
    monkeypatch.setattr(app_module, "process_service", fake_process)
    monkeypatch.setattr(app_module, "TaskService", _FakeTaskService)
    monkeypatch.setattr(app_module, "SqliteTaskRepository", lambda: object())
    monkeypatch.setattr(app_module, "bootstrap_sqlite_storage", lambda: called.setdefault("bootstrapped", True))
    monkeypatch.setattr(
        app_module,
        "cleanup_task_logs",
        lambda *args, **kwargs: called.setdefault("keep_days", kwargs.get("keep_days")),
    )
    monkeypatch.setattr(app_module.app_settings, "task_log_retention_days", 9)

    async def _run():
        async with app_module.lifespan(None):
            assert fake_scheduler.started is True
            assert fake_scheduler.reload_payload == []

    asyncio.run(_run())

    assert called["bootstrapped"] is True
    assert called["keep_days"] == 9
    assert fake_scheduler.stopped is True
    assert fake_process.stop_all_called is True
