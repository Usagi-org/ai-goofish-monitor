import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event

import pytest

from src.domain.models.task import TaskCreate, TaskUpdate
from src.domain.repositories.task_repository import TaskChanged
from src.infrastructure.persistence.file_lock import FileLock
from src.infrastructure.persistence.json_task_repository import JsonTaskRepository
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository
from src.services.task_service import TaskService


@pytest.fixture(params=["sqlite", "json"])
def repository(request, tmp_path):
    if request.param == "sqlite":
        return SqliteTaskRepository(str(tmp_path / "tasks.sqlite"), legacy_config_file=None)
    return JsonTaskRepository(str(tmp_path / "tasks.json"))


def test_partial_writes_merge_and_deleted_tasks_stay_deleted(repository):
    async def run():
        service = TaskService(repository)
        task = await service.create_task(TaskCreate(
            task_name="first", keyword="camera", description="clean",
            account_strategy="fixed", account_state_file="bound.json",
        ))
        await asyncio.gather(
            service.update_task(task.id, TaskUpdate(max_pages=9)),
            service.update_task_status(task.id, True),
        )
        current = await service.get_task(task.id)
        assert (current.max_pages, current.is_running) == (9, True)
        assert (current.account_strategy, current.account_state_file) == ("fixed", "bound.json")
        await service.update_task_status(task.id, False)
        await service.update_task(task.id, TaskUpdate(task_name="new-name"))
        with pytest.raises(TaskChanged):
            await service.update_task(task.id, TaskUpdate(max_pages=3), expected_name="first")
        with pytest.raises(TaskChanged):
            await service.delete_task(task.id, expected_name="first")
        assert await service.delete_task(task.id)
        with pytest.raises(ValueError, match="不存在"):
            await repository.save(task)
        with pytest.raises(ValueError, match="不存在"):
            await service.update_task(task.id, TaskUpdate(is_running=True))
        replacement = await service.create_task(TaskCreate(task_name="replacement", keyword="k", description="d"))
        if isinstance(repository, SqliteTaskRepository):
            assert replacement.id > task.id
        assert [t.task_name for t in await service.get_all_tasks()] == ["replacement"]

    asyncio.run(run())


def test_json_reader_holds_sidecar_until_file_is_closed(tmp_path, monkeypatch):
    repository = JsonTaskRepository(str(tmp_path / "tasks.json"))
    service = TaskService(repository)
    task = asyncio.run(service.create_task(TaskCreate(task_name="first", keyword="k", description="d")))
    reader_open, release, writer_at_lock = Event(), Event(), Event()
    real_open, enter = open, FileLock.__enter__

    @contextmanager
    def hold_reader(*args, **kwargs):
        with real_open(*args, **kwargs) as stream:
            if not reader_open.is_set():
                reader_open.set()
                assert release.wait(5)
            yield stream

    def enter_lock(lock):
        if reader_open.is_set():
            writer_at_lock.set()
        return enter(lock)

    monkeypatch.setattr("src.infrastructure.persistence.json_task_repository.open", hold_reader, raising=False)
    monkeypatch.setattr(FileLock, "__enter__", enter_lock)
    with ThreadPoolExecutor(2) as pool:
        reader = pool.submit(asyncio.run, service.get_task(task.id))
        assert reader_open.wait(5)
        writer = pool.submit(asyncio.run, service.update_task(task.id, TaskUpdate(max_pages=7)))
        try:
            assert writer_at_lock.wait(5)
            assert not writer.done()
        finally:
            release.set()
        assert reader.result().max_pages == task.max_pages
        assert writer.result().max_pages == 7
    assert asyncio.run(service.get_task(task.id)).max_pages == 7
