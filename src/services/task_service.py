"""
任务管理服务
封装任务相关的业务逻辑
"""
from typing import List, Optional
from contextlib import nullcontext
from src.domain.models.task import Task, TaskCreate, TaskUpdate
from src.domain.repositories.task_repository import TaskCommitScope, TaskRepository


class TaskService:
    """任务管理服务"""

    def __init__(self, repository: TaskRepository):
        self.repository = repository

    async def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return await self.repository.find_all()

    async def get_task(self, task_id: int) -> Optional[Task]:
        """获取单个任务"""
        return await self.repository.find_by_id(task_id)

    async def create_task(self, task_create: TaskCreate, *, on_commit: TaskCommitScope = nullcontext) -> Task:
        """创建新任务"""
        task = Task(**task_create.model_dump(), is_running=False)
        return await self.repository.save(task, on_commit=on_commit)

    async def update_task(
        self, task_id: int, task_update: TaskUpdate, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> Task:
        return await self.repository.update(task_id, task_update, expected_name=expected_name, on_commit=on_commit)

    async def delete_task(
        self, task_id: int, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> bool:
        """删除任务"""
        return await self.repository.delete(task_id, expected_name=expected_name, on_commit=on_commit)

    async def update_task_status(self, task_id: int, is_running: bool) -> Task:
        """更新任务运行状态"""
        task_update = TaskUpdate(is_running=is_running)
        return await self.update_task(task_id, task_update)
