"""
进程管理服务
负责管理爬虫进程的启动和停止
"""

import asyncio
import contextlib
from dataclasses import dataclass
from functools import partial
import os
import signal
import threading
import sys
from datetime import datetime
from typing import Awaitable, Callable, Dict, Literal, TextIO

from src.ai_handler import send_ntfy_notification
from src.config import STATE_FILE
from src.domain.models.task import Task
from src.domain.repositories.task_repository import RunningTaskRename, TaskBusy
from src.failure_guard import FailureGuard
from src.infrastructure.persistence.sqlite_task_repository import find_task_by_name_sync
from src.utils import build_task_log_path

STOP_TIMEOUT_SECONDS = 20
SPIDER_DEBUG_LIMIT_ENV = "SPIDER_DEBUG_LIMIT"
LifecycleHook = Callable[[int], Awaitable[None] | None]


@dataclass(frozen=True)
class TaskStartResult:
    status: Literal["started", "already_running", "paused", "busy", "stale", "spawn_error"]
    reason: str | None = None
    paused_until: str | None = None
    consecutive_failures: int = 0


class ProcessService:
    """进程管理服务"""

    def __init__(self, task_loader: Callable[[int], Awaitable[Task | None]] | None = None):
        self._task_loader = task_loader
        self._transition_lock = threading.Lock()
        self._transitioning: set[int] = set()
        self.processes: Dict[int, asyncio.subprocess.Process] = {}
        self.log_paths: Dict[int, str] = {}
        self.log_handles: Dict[int, TextIO] = {}
        self.task_names: Dict[int, str] = {}
        self.exit_watchers: Dict[int, asyncio.Task] = {}
        self.failure_guard = FailureGuard()
        self._on_started: LifecycleHook | None = None
        self._on_stopped: LifecycleHook | None = None

    def set_lifecycle_hooks(
        self,
        *,
        on_started: LifecycleHook | None = None,
        on_stopped: LifecycleHook | None = None,
    ) -> None:
        self._on_started = on_started
        self._on_stopped = on_stopped

    async def _invoke_hook(self, hook: LifecycleHook | None, task_id: int) -> None:
        if hook is None:
            return
        result = hook(task_id)
        if asyncio.iscoroutine(result):
            await result

    def _resolve_cookie_path(self, task_name: str, task: Task | None = None) -> str | None:
        """Best-effort cookie/state path for a task."""
        if task is not None:
            if isinstance(task.account_state_file, str) and task.account_state_file.strip():
                return task.account_state_file.strip()
            return STATE_FILE if os.path.exists(STATE_FILE) else None

        try:
            found_task = find_task_by_name_sync(task_name)
            if (
                found_task
                and isinstance(found_task.account_state_file, str)
                and found_task.account_state_file.strip()
            ):
                return found_task.account_state_file.strip()
        except Exception:
            pass

        return STATE_FILE if os.path.exists(STATE_FILE) else None

    def _call_resolve_cookie_path(self, task_name: str, task: Task | None = None) -> str | None:
        if task is None:
            return self._resolve_cookie_path(task_name)
        try:
            return self._resolve_cookie_path(task_name, task=task)
        except TypeError:
            return self._resolve_cookie_path(task_name)

    def load_failure_guard_snapshot(self) -> dict:
        """一次性读取熔断器状态快照，供任务列表批量序列化复用。"""
        return self.failure_guard.load_snapshot()

    def get_failure_guard_state(
        self,
        task_name: str,
        *,
        task: Task | None = None,
        snapshot: dict | None = None,
    ) -> dict:
        """获取任务当前的熔断器只读状态"""
        return self.failure_guard.get_task_state(
            task_name,
            cookie_path=self._call_resolve_cookie_path(task_name, task=task),
            snapshot=snapshot,
        )

    def unpause_task(self, task_name: str) -> None:
        """解除任务熔断暂停并清除失败计数"""
        self.failure_guard.clear_task(task_name)

    @contextlib.contextmanager
    def _reserve_transition(self, task_id: int):
        # Starts run on the event loop; repository commits run in worker threads.
        with self._transition_lock:
            claimed = task_id not in self._transitioning
            if claimed:
                self._transitioning.add(task_id)
        try:
            yield claimed
        finally:
            if claimed:
                with self._transition_lock:
                    self._transitioning.remove(task_id)

    @contextlib.contextmanager
    def rename_task_guard(self, task_id: int, old_name: str, new_name: str, *, keep_old: bool = False):
        with self._reserve_transition(task_id) as claimed:
            if not claimed or self.is_running(task_id):
                raise RunningTaskRename()
            with self.failure_guard.change_task(old_name, new_name, keep_old=keep_old):
                yield

    @contextlib.asynccontextmanager
    async def stop_for_deletion(self, task_id: int, task_name: str, *, keep_old: bool):
        with self._reserve_transition(task_id) as claimed:
            if not claimed:
                raise TaskBusy("任务正在启动或修改，请稍后再删除")
            await self.stop_task(task_id)
            if self.is_running(task_id):
                raise TaskBusy("任务仍在运行，请稍后再删除")
            yield partial(self.failure_guard.change_task, task_name, keep_old=keep_old)

    def is_running(self, task_id: int) -> bool:
        """检查任务是否正在运行"""
        process = self.processes.get(task_id)
        return process is not None and process.returncode is None

    async def _drain_finished_process(self, task_id: int) -> None:
        process = self.processes.get(task_id)
        if process is None or process.returncode is None:
            return

        watcher = self.exit_watchers.get(task_id)
        if watcher is not None:
            await asyncio.shield(watcher)
            return

        self._cleanup_runtime(task_id, process)
        await self._invoke_hook(self._on_stopped, task_id)

    def _open_log_file(self, task_id: int, task_name: str) -> tuple[str, TextIO]:
        os.makedirs("logs", exist_ok=True)
        log_file_path = build_task_log_path(task_id, task_name)
        log_file_handle = open(log_file_path, "a", encoding="utf-8")
        return log_file_path, log_file_handle

    def _build_spawn_command(self, task_name: str) -> list[str]:
        command = [
            sys.executable,
            "-u",
            "spider_v2.py",
            "--task-name",
            task_name,
        ]
        debug_limit = str(os.getenv(SPIDER_DEBUG_LIMIT_ENV, "")).strip()
        if debug_limit.isdigit() and int(debug_limit) > 0:
            command.extend(["--debug-limit", debug_limit])
        return command

    async def _spawn_process(
        self,
        task_name: str,
        log_file_handle: TextIO,
    ) -> asyncio.subprocess.Process:
        preexec_fn = os.setsid if sys.platform != "win32" else None
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"
        return await asyncio.create_subprocess_exec(
            *self._build_spawn_command(task_name),
            stdout=log_file_handle,
            stderr=log_file_handle,
            preexec_fn=preexec_fn,
            env=child_env,
        )

    def _register_runtime(
        self,
        task_id: int,
        task_name: str,
        process: asyncio.subprocess.Process,
        log_file_path: str,
        log_file_handle: TextIO,
    ) -> None:
        self.processes[task_id] = process
        self.log_paths[task_id] = log_file_path
        self.log_handles[task_id] = log_file_handle
        self.task_names[task_id] = task_name
        self.exit_watchers[task_id] = asyncio.create_task(self._watch_process_exit(process))

    async def _start_task_core(
        self,
        task_id: int,
        task_name: str,
        *,
        task: Task | None = None,
        force_unpause: bool = False,
        notify_on_skip: bool = True,
    ) -> TaskStartResult:
        with self._reserve_transition(task_id) as claimed:
            if not claimed:
                return TaskStartResult(status="busy")
            if self._task_loader is not None:
                task = await self._task_loader(task_id)
                if task is None or task.task_name != task_name or not task.enabled:
                    return TaskStartResult(status="stale")
            return await self._start_reserved_task(task_id, task_name, task, force_unpause, notify_on_skip)

    async def _start_reserved_task(
        self, task_id: int, task_name: str, task: Task | None, force_unpause: bool, notify_on_skip: bool,
    ) -> TaskStartResult:
        await self._drain_finished_process(task_id)
        if self.is_running(task_id):
            print(f"任务 '{task_name}' (ID: {task_id}) 已在运行中")
            return TaskStartResult(status="already_running")
        if force_unpause:
            self.unpause_task(task_name)

        decision = self.failure_guard.should_skip_start(
            task_name,
            cookie_path=self._call_resolve_cookie_path(task_name, task=task),
            record_notification=notify_on_skip,
        )
        if decision.skip:
            if notify_on_skip:
                await self._notify_skip(task_name, decision)
            return TaskStartResult(
                status="paused",
                reason=decision.reason,
                paused_until=decision.paused_until.isoformat() if decision.paused_until else None,
                consecutive_failures=decision.consecutive_failures,
            )

        log_file_path = ""
        log_file_handle = None
        try:
            log_file_path, log_file_handle = self._open_log_file(task_id, task_name)
            process = await self._spawn_process(task_name, log_file_handle)
        except Exception as exc:
            self._close_log_handle(log_file_handle)
            print(f"启动任务 '{task_name}' 失败: {exc}")
            return TaskStartResult(status="spawn_error", reason=str(exc))

        self._register_runtime(task_id, task_name, process, log_file_path, log_file_handle)
        print(f"启动任务 '{task_name}' (PID: {process.pid})")
        await self._invoke_hook(self._on_started, task_id)
        return TaskStartResult(status="started")

    async def start_task(
        self,
        task_id: int,
        task_name: str,
        *,
        force_unpause: bool = False,
    ) -> bool:
        """启动任务进程"""
        result = await self._start_task_core(
            task_id,
            task_name,
            force_unpause=force_unpause,
            notify_on_skip=True,
        )
        return result.status == "started"

    async def start_task_manual(
        self,
        task: Task,
        *,
        force_unpause: bool = False,
    ) -> TaskStartResult:
        """手动启动任务进程，原子返回启动状态以避免预检竞态。"""
        if task.id is None:
            return TaskStartResult(status="spawn_error", reason="任务缺少有效 ID")
        return await self._start_task_core(
            task.id,
            task.task_name,
            task=task,
            force_unpause=force_unpause,
            notify_on_skip=False,
        )

    async def _notify_skip(self, task_name: str, decision) -> None:
        print(
            f"[FailureGuard] 跳过启动任务 '{task_name}'，已暂停重试 "
            f"(连续失败 {decision.consecutive_failures}/{self.failure_guard.threshold})"
        )
        if not decision.should_notify:
            return
        try:
            await send_ntfy_notification(
                {
                    "商品标题": f"[任务暂停] {task_name}",
                    "当前售价": "N/A",
                    "商品链接": "#",
                },
                "任务处于暂停状态，将跳过执行。\n"
                f"原因: {decision.reason}\n"
                f"连续失败: {decision.consecutive_failures}/{self.failure_guard.threshold}\n"
                f"暂停到: {decision.paused_until.strftime('%Y-%m-%d %H:%M:%S') if decision.paused_until else 'N/A'}\n"
                "修复方法: 更新登录态/cookies文件后会自动恢复。",
            )
        except Exception as exc:
            print(f"发送任务暂停通知失败: {exc}")

    async def _watch_process_exit(self, process: asyncio.subprocess.Process) -> None:
        await process.wait()
        task_id = self._find_task_id_by_process(process)
        if task_id is None:
            return
        self._cleanup_runtime(task_id, process)
        await self._invoke_hook(self._on_stopped, task_id)

    def _find_task_id_by_process(self, process: asyncio.subprocess.Process) -> int | None:
        for task_id, current_process in self.processes.items():
            if current_process is process:
                return task_id
        return None

    def _cleanup_runtime(
        self,
        task_id: int,
        process: asyncio.subprocess.Process,
    ) -> None:
        if self.processes.get(task_id) is not process:
            return
        self.processes.pop(task_id, None)
        self.log_paths.pop(task_id, None)
        self.task_names.pop(task_id, None)
        self._close_log_handle(self.log_handles.pop(task_id, None))
        self.exit_watchers.pop(task_id, None)

    def _close_log_handle(self, log_handle: TextIO | None) -> None:
        if log_handle is None:
            return
        with contextlib.suppress(Exception):
            log_handle.close()

    def _append_stop_marker(self, log_path: str | None) -> None:
        if not log_path:
            return
        try:
            timestamp = datetime.now().strftime(" %Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] !!! 任务已被终止 !!!\n")
        except Exception as exc:
            print(f"写入任务终止标记失败: {exc}")

    async def stop_task(self, task_id: int) -> bool:
        """停止任务进程"""
        await self._drain_finished_process(task_id)
        process = self.processes.get(task_id)
        if process is None:
            print(f"任务 ID {task_id} 没有正在运行的进程")
            return False
        if process.returncode is not None:
            await self._await_exit_watcher(task_id)
            print(f"任务进程 {process.pid} (ID: {task_id}) 已退出，略过停止")
            return False

        try:
            await self._terminate_process(process, task_id)
            self._append_stop_marker(self.log_paths.get(task_id))
            await self._await_exit_watcher(task_id)
            print(f"任务进程 {process.pid} (ID: {task_id}) 已终止")
            return True
        except ProcessLookupError:
            print(f"进程 (ID: {task_id}) 已不存在")
            return False
        except Exception as exc:
            print(f"停止任务进程 (ID: {task_id}) 时出错: {exc}")
            return False

    async def _terminate_process(
        self,
        process: asyncio.subprocess.Process,
        task_id: int,
    ) -> None:
        if sys.platform != "win32":
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

        try:
            await asyncio.wait_for(process.wait(), timeout=STOP_TIMEOUT_SECONDS)
            return
        except asyncio.TimeoutError:
            print(
                f"任务进程 {process.pid} (ID: {task_id}) 未在 "
                f"{STOP_TIMEOUT_SECONDS} 秒内退出，准备强制终止..."
            )

        if sys.platform != "win32":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
        await process.wait()

    async def _await_exit_watcher(self, task_id: int) -> None:
        watcher = self.exit_watchers.get(task_id)
        if watcher is None:
            return
        await asyncio.shield(watcher)

    def reindex_after_delete(self, deleted_task_id: int) -> None:
        """删除任务后同步重排运行时索引，避免任务下标漂移。"""
        self.processes = self._reindex_mapping(self.processes, deleted_task_id)
        self.log_paths = self._reindex_mapping(self.log_paths, deleted_task_id)
        self.log_handles = self._reindex_mapping(self.log_handles, deleted_task_id)
        self.task_names = self._reindex_mapping(self.task_names, deleted_task_id)
        self.exit_watchers = self._reindex_mapping(self.exit_watchers, deleted_task_id)

    def _reindex_mapping(self, mapping: Dict[int, object], deleted_task_id: int) -> Dict[int, object]:
        reindexed: Dict[int, object] = {}
        for task_id, value in mapping.items():
            if task_id == deleted_task_id:
                continue
            next_task_id = task_id - 1 if task_id > deleted_task_id else task_id
            reindexed[next_task_id] = value
        return reindexed

    async def stop_all(self) -> None:
        """停止所有任务进程"""
        task_ids = list(self.processes.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)
