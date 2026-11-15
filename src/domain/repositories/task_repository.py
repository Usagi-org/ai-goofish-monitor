"""
任务仓储层
负责任务数据的持久化操作
"""
from typing import List, Optional
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager, nullcontext
from src.domain.models.task import Task, TaskUpdate


TaskCommitScope = Callable[[], AbstractContextManager]


class TaskNameConflict(ValueError):
    pass


class TaskChanged(ValueError):
    pass


class TaskBusy(ValueError):
    pass


class RunningTaskRename(ValueError):
    def __init__(self):
        super().__init__("请先停止任务再改名")


def resolve_task_write(
    task_id: int | None, current: Task | None, change: Task | TaskUpdate, expected_name: str | None,
) -> Task:
    if current is None:
        if task_id is None and isinstance(change, Task):
            return change
        raise ValueError(f"任务 {task_id} 不存在")
    if expected_name is not None and current.task_name != expected_name:
        raise TaskChanged("任务名称已更改，请刷新后重试")
    return current.apply_update(change) if isinstance(change, TaskUpdate) else change


def ensure_available_task_name(task: Task, other_names: Iterable[str]) -> None:
    name = task.task_name.strip()
    if any(other.strip() == name for other in other_names):
        raise TaskNameConflict(f"任务名称 '{name}' 已存在，请使用唯一名称")


class TaskRepository(ABC):
    """任务仓储接口"""

    @abstractmethod
    async def find_all(self) -> List[Task]:
        """获取所有任务"""
        pass

    @abstractmethod
    async def find_by_id(self, task_id: int) -> Optional[Task]:
        """根据ID获取任务"""
        pass

    @abstractmethod
    async def save(self, task: Task, *, on_commit: TaskCommitScope = nullcontext) -> Task:
        """保存任务（创建或更新）"""
        pass

    @abstractmethod
    async def update(
        self, task_id: int, change: TaskUpdate, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> Task:
        """在写事务中将部分更新应用到最新任务。"""
        pass

    @abstractmethod
    async def delete(
        self, task_id: int, *, expected_name: str | None = None,
        on_commit: TaskCommitScope = nullcontext,
    ) -> bool:
        """删除任务"""
        pass
