"""
基于JSON文件的任务仓储实现
"""
from typing import List, Optional
import json
import asyncio
from contextlib import nullcontext
from pathlib import Path
import os
import tempfile

from src.infrastructure.persistence.file_lock import FileLock
from src.domain.models.task import Task, TaskUpdate
from src.domain.repositories.task_repository import (
    RunningTaskRename, TaskChanged, TaskCommitScope, TaskRepository, ensure_available_task_name, resolve_task_write,
)


class JsonTaskRepository(TaskRepository):
    """基于JSON文件的任务仓储"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file

    async def find_all(self) -> List[Task]:
        """获取所有任务"""
        return await asyncio.to_thread(self._read_tasks)

    def _read_tasks(self) -> List[Task]:
        with FileLock(f"{self.config_file}.lock"):
            return self._read_unlocked()

    def _read_unlocked(self) -> List[Task]:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return []

                tasks_data = json.loads(content)
                tasks = []
                for i, task_data in enumerate(tasks_data):
                    task_data['id'] = i
                    tasks.append(Task(**task_data))
                return tasks
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            print(f"配置文件 {self.config_file} 格式错误")
            return []

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        """根据ID获取任务"""
        tasks = await self.find_all()
        if 0 <= task_id < len(tasks):
            return tasks[task_id]
        return None

    async def save(self, task: Task, *, on_commit: TaskCommitScope = nullcontext) -> Task:
        return await asyncio.to_thread(self._save_sync, task.id, task, None, on_commit)

    async def update(
        self, task_id: int, change: TaskUpdate, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> Task:
        return await asyncio.to_thread(self._save_sync, task_id, change, expected_name, on_commit)

    def _save_sync(
        self, task_id: int | None, change: Task | TaskUpdate, expected_name: str | None, on_commit: TaskCommitScope,
    ) -> Task:
        with FileLock(f"{self.config_file}.lock"):
            tasks = self._read_unlocked()
            current = tasks[task_id] if task_id is not None and 0 <= task_id < len(tasks) else None
            task = resolve_task_write(task_id, current, change, expected_name)
            if current is not None:
                if current.task_name != task.task_name:
                    if current.is_running:
                        raise RunningTaskRename()
                    ensure_available_task_name(task, (t.task_name for t in tasks if t.id != task.id))
                tasks[task.id] = task
            else:
                ensure_available_task_name(task, (t.task_name for t in tasks))
                task = task.model_copy(update={"id": len(tasks)})
                tasks.append(task)
            self._write_tasks(tasks, on_commit)
            return task

    async def delete(
        self, task_id: int, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> bool:
        return await asyncio.to_thread(self._delete_sync, task_id, expected_name, on_commit)

    def _delete_sync(self, task_id: int, expected_name: str | None, on_commit: TaskCommitScope) -> bool:
        with FileLock(f"{self.config_file}.lock"):
            tasks = self._read_unlocked()
            if not 0 <= task_id < len(tasks):
                return False
            if expected_name is not None and tasks[task_id].task_name != expected_name:
                raise TaskChanged("任务名称已更改，请刷新后重试")
            tasks.pop(task_id)
            self._write_tasks(tasks, on_commit)
            return True

    def _write_tasks(self, tasks: List[Task], on_commit: TaskCommitScope) -> None:
        tasks_data = [task.model_dump(exclude={"id"}) for task in tasks]
        fd, temp_name = tempfile.mkstemp(dir=Path(self.config_file).parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(tasks_data, output, ensure_ascii=False, indent=2)
            with on_commit():
                os.replace(temp_name, self.config_file)
        finally:
            Path(temp_name).unlink(missing_ok=True)
