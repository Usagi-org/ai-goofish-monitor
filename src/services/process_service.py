"""
进程管理服务
负责管理爬虫进程的启动和停止
"""

import asyncio
import contextlib
import json
import sys
import os
import signal
from datetime import datetime
from typing import Dict
from src.utils import build_task_log_path
from src.failure_guard import FailureGuard
from src.config import STATE_FILE
from src.ai_handler import send_ntfy_notification


class ProcessService:
    """进程管理服务"""

    def __init__(self):
        self.processes: Dict[int, asyncio.subprocess.Process] = {}
        self.log_paths: Dict[int, str] = {}
        self.failure_guard = FailureGuard()

    def _resolve_cookie_path(self, task_name: str) -> str | None:
        """Best-effort cookie/state path for a task.

        - Prefer task-specific account_state_file from config.json
        - Fall back to global STATE_FILE (xianyu_state.json)
        """
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                if isinstance(tasks, list):
                    for t in tasks:
                        if isinstance(t, dict) and t.get("task_name") == task_name:
                            val = t.get("account_state_file")
                            if isinstance(val, str) and val.strip():
                                return val.strip()
        except Exception:
            pass

        return STATE_FILE if os.path.exists(STATE_FILE) else None

    def is_running(self, task_id: int) -> bool:
        """检查任务是否正在运行"""
        process = self.processes.get(task_id)
        return process is not None and process.returncode is None

    async def start_task(self, task_id: int, task_name: str) -> bool:
        """启动任务进程"""
        if self.is_running(task_id):
            print(f"任务 '{task_name}' (ID: {task_id}) 已在运行中")
            return False

        cookie_path = self._resolve_cookie_path(task_name)
        decision = self.failure_guard.should_skip_start(
            task_name,
            cookie_path=cookie_path,
        )
        if decision.skip:
            print(
                f"[FailureGuard] 跳过启动任务 '{task_name}'，已暂停重试 (连续失败 {decision.consecutive_failures}/{self.failure_guard.threshold})"
            )
            if decision.should_notify:
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
                except Exception as e:
                    print(f"发送任务暂停通知失败: {e}")
            return False

        try:
            os.makedirs("logs", exist_ok=True)
            log_file_path = build_task_log_path(task_id, task_name)
            log_file_handle = open(log_file_path, "a", encoding="utf-8")

            preexec_fn = os.setsid if sys.platform != "win32" else None
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"

            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "spider_v2.py",
                "--task-name",
                task_name,
                stdout=log_file_handle,
                stderr=log_file_handle,
                preexec_fn=preexec_fn,
                env=child_env,
            )

            self.processes[task_id] = process
            self.log_paths[task_id] = log_file_path
            print(f"启动任务 '{task_name}' (PID: {process.pid})")
            return True

        except Exception as e:
            if task_id in self.log_paths:
                del self.log_paths[task_id]
            print(f"启动任务 '{task_name}' 失败: {e}")
            return False

    def _append_stop_marker(self, log_path: str | None) -> None:
        if not log_path:
            return
        try:
            ts = datetime.now().strftime(" %Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] !!! 任务已被终止 !!!\n")
        except Exception as e:
            print(f"写入任务终止标记失败: {e}")

    async def stop_task(self, task_id: int) -> bool:
        """停止任务进程"""
        process = self.processes.pop(task_id, None)
        log_path = self.log_paths.pop(task_id, None)
        if not process:
            print(f"任务 ID {task_id} 没有正在运行的进程")
            return False
        if process.returncode is not None:
            print(f"任务进程 {process.pid} (ID: {task_id}) 已退出，略过停止")
            return False

        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            try:
                await asyncio.wait_for(process.wait(), timeout=20)
            except asyncio.TimeoutError:
                print(
                    f"任务进程 {process.pid} (ID: {task_id}) 未在 20 秒内退出，准备强制终止..."
                )
                if sys.platform != "win32":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                await process.wait()

            self._append_stop_marker(log_path)
            print(f"任务进程 {process.pid} (ID: {task_id}) 已终止")
            return True

        except ProcessLookupError:
            print(f"进程 (ID: {task_id}) 已不存在")
            return False
        except Exception as e:
            print(f"停止任务进程 (ID: {task_id}) 时出错: {e}")
            return False

    async def stop_all(self):
        """停止所有任务进程"""
        task_ids = list(self.processes.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)
