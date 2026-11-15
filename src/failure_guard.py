"""Task-level failure circuit breaker.

目标:
- 当登录态失效/风控导致任务持续失败时，避免无限重试、避免高频请求。
- 失败达到阈值后暂停任务一段时间。
- 暂停期间最多每天通知一次，直到用户更新 cookies / 登录态文件后自动恢复。

说明:
- 仅使用标准库，既可被 API 主进程使用，也可被爬虫子进程使用。
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from src.infrastructure.persistence.file_lock import FileLock as _FileLock


try:
    from zoneinfo import ZoneInfo  # py3.9+

    def _load_tz(name: str):
        return ZoneInfo(name)


except Exception:  # pragma: no cover

    def _load_tz(name: str):
        return None


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _now(tz_name: str, now: Optional[datetime] = None) -> datetime:
    if now is not None:
        return now
    tz = _load_tz(tz_name)
    if tz is None:
        return datetime.now()
    return datetime.now(tz)


def _today_str(tz_name: str, now: Optional[datetime] = None) -> str:
    return _now(tz_name, now=now).date().isoformat()


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_mtime(path: Optional[str]) -> Optional[float]:
    if not path:
        return None
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _cookie_changed(
    cookie_path: Optional[str], previous_mtime: Optional[float]
) -> bool:
    if not cookie_path:
        return False
    current = _get_mtime(cookie_path)
    if current is None or previous_mtime is None:
        return False
    return current > (previous_mtime + 1e-6)


def _resolve_entry_cookie_path(
    entry: dict, fallback_cookie_path: Optional[str]
) -> Optional[str]:
    recorded = entry.get("cookie_path")
    if isinstance(recorded, str) and recorded.strip():
        return recorded.strip()
    if isinstance(fallback_cookie_path, str) and fallback_cookie_path.strip():
        return fallback_cookie_path.strip()
    return None


def _parse_cookie_mtime(entry: dict) -> Optional[float]:
    raw_mtime = entry.get("cookie_mtime")
    if raw_mtime is None:
        return None
    try:
        return float(raw_mtime)
    except (TypeError, ValueError):
        return None


def _has_cookie_recovered(
    entry: dict, fallback_cookie_path: Optional[str]
) -> bool:
    effective_cookie_path = _resolve_entry_cookie_path(entry, fallback_cookie_path)
    previous_mtime = _parse_cookie_mtime(entry)
    return _cookie_changed(effective_cookie_path, previous_mtime)


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _quarantine_corrupt_file(path: str) -> None:
    try:
        ts = str(int(time.time()))
        os.replace(path, f"{path}.corrupt.{ts}")
    except OSError:
        pass


def _read_json_file_unlocked(path: str, *, quarantine_corrupt: bool = True) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        if quarantine_corrupt:
            # 仅在确认 JSON 解析或编码损坏时隔离现场；I/O 或权限异常需向上抛出，避免覆盖其它任务状态。
            _quarantine_corrupt_file(path)
        return {}
    if not isinstance(data, dict):
        if quarantine_corrupt:
            _quarantine_corrupt_file(path)
        return {}
    return data


def _atomic_write_json(path: str, data: dict) -> None:
    _ensure_parent_dir(path)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class SkipDecision:
    skip: bool
    should_notify: bool
    reason: str
    paused_until: Optional[datetime]
    consecutive_failures: int


class FailureGuard:
    def __init__(
        self,
        path: Optional[str] = None,
        *,
        threshold: Optional[int] = None,
        pause_seconds: Optional[int] = None,
        tz_name: Optional[str] = None,
    ):
        self.path = (
            path
            or os.getenv("TASK_FAILURE_GUARD_PATH")
            or "logs/task-failure-guard.json"
        )
        self.threshold = max(
            1, threshold or _as_int(os.getenv("TASK_FAILURE_THRESHOLD"), 3)
        )
        self.pause_seconds = max(
            60,
            pause_seconds
            or _as_int(os.getenv("TASK_FAILURE_PAUSE_SECONDS"), 24 * 60 * 60),
        )
        self.tz_name = tz_name or os.getenv("TASK_FAILURE_TZ") or "Asia/Shanghai"

    def _lock_path(self) -> str:
        return f"{self.path}.lock"

    def _load_unlocked(self, *, quarantine_corrupt: bool = True) -> dict:
        data = _read_json_file_unlocked(
            self.path, quarantine_corrupt=quarantine_corrupt
        )
        if "tasks" not in data or not isinstance(data.get("tasks"), dict):
            data = {"version": 1, "tasks": {}}
        data.setdefault("version", 1)
        return data

    def _save_unlocked(self, data: dict) -> None:
        _atomic_write_json(self.path, data)

    def _load(self, *, quarantine_corrupt: bool = True) -> dict:
        with _FileLock(self._lock_path()):
            return self._load_unlocked(quarantine_corrupt=quarantine_corrupt)

    def _save(self, data: dict) -> None:
        with _FileLock(self._lock_path()):
            self._save_unlocked(data)

    def _update_task(self, task_key: str, updater) -> dict:
        _ensure_parent_dir(self.path)
        with _FileLock(self._lock_path()):
            data = self._load_unlocked()
            tasks = data.setdefault("tasks", {})
            entry = tasks.get(task_key) or {}
            if not isinstance(entry, dict):
                entry = {}
            entry = updater(entry) or entry
            tasks[task_key] = entry
            self._save_unlocked(data)
            return entry

    @staticmethod
    def _build_reset_entry(current: datetime) -> dict:
        return {
            "consecutive_failures": 0,
            "paused_until": None,
            "last_notified_date": None,
            "last_failure_reason": None,
            "last_failure_at": None,
            "last_success_at": _dt_to_str(current),
            "cookie_path": None,
            "cookie_mtime": None,
        }

    def load_snapshot(self) -> dict:
        with _FileLock(self._lock_path()):
            return self._load_unlocked(quarantine_corrupt=False)

    def get_task_state(
        self,
        task_key: str,
        *,
        cookie_path: Optional[str] = None,
        now: Optional[datetime] = None,
        snapshot: Optional[dict] = None,
    ) -> dict:
        current = _now(self.tz_name, now=now)
        data = snapshot if isinstance(snapshot, dict) else self.load_snapshot()
        entry = (data.get("tasks") or {}).get(task_key) or {}
        if not isinstance(entry, dict):
            entry = {}

        paused_until = _str_to_dt(entry.get("paused_until"))
        consecutive = _as_int(entry.get("consecutive_failures"), 0)
        raw_reason = entry.get("last_failure_reason")
        reason = raw_reason.strip() if isinstance(raw_reason, str) and raw_reason.strip() else None
        raw_last_failure_at = entry.get("last_failure_at")
        last_failure_at = (
            raw_last_failure_at.strip()
            if isinstance(raw_last_failure_at, str) and raw_last_failure_at.strip()
            else None
        )

        has_failure_state = consecutive > 0 or bool(paused_until and current < paused_until)
        cookie_recovered = has_failure_state and _has_cookie_recovered(entry, cookie_path)
        paused = bool(
            paused_until and current < paused_until and not cookie_recovered
        )

        return {
            "paused": paused,
            "paused_until": _dt_to_str(paused_until) if paused else None,
            "consecutive_failures": 0 if cookie_recovered else consecutive,
            "threshold": self.threshold,
            "reason": None if cookie_recovered else reason,
            "last_failure_at": None if cookie_recovered else last_failure_at,
        }

    @contextmanager
    def change_task(self, old_key: str, new_key: str | None = None, *, keep_old: bool = False):
        """Hold the guard lock until the corresponding task change commits."""
        with _FileLock(self._lock_path()):
            original = self._load_unlocked()
            tasks = dict(original["tasks"])
            if new_key is not None and new_key != old_key:
                if old_key in tasks:
                    tasks[new_key] = tasks[old_key]
                else:
                    tasks.pop(new_key, None)
            if not keep_old and old_key != new_key:
                tasks.pop(old_key, None)

            changed = tasks != original["tasks"]
            if changed:
                self._save_unlocked({**original, "tasks": tasks})
            try:
                yield
            except BaseException:
                if changed:
                    self._save_unlocked(original)
                raise

    def clear_task(self, task_key: str) -> None:
        with self.change_task(task_key):
            pass

    def rename_task(self, old_key: str, new_key: str, *, keep_old: bool = False) -> None:
        with self.change_task(old_key, new_key, keep_old=keep_old):
            pass

    def record_success(self, task_key: str, *, now: Optional[datetime] = None) -> None:
        current = _now(self.tz_name, now=now)
        self._update_task(task_key, lambda _: self._build_reset_entry(current))

    def should_skip_start(
        self,
        task_key: str,
        *,
        cookie_path: Optional[str] = None,
        now: Optional[datetime] = None,
        record_notification: bool = True,
    ) -> SkipDecision:
        current = _now(self.tz_name, now=now)
        today = _today_str(self.tz_name, now=current)

        with _FileLock(self._lock_path()):
            data = self._load_unlocked()
            tasks = data.setdefault("tasks", {})
            entry = tasks.get(task_key) or {}
            if not isinstance(entry, dict):
                entry = {}

            paused_until = _str_to_dt(entry.get("paused_until"))
            consecutive = _as_int(entry.get("consecutive_failures"), 0)
            last_reason = (entry.get("last_failure_reason") or "").strip() or "未知错误"
            last_notified_date = entry.get("last_notified_date")

            has_failure_state = consecutive > 0 or bool(
                paused_until and paused_until > current
            )
            if has_failure_state and _has_cookie_recovered(entry, cookie_path):
                # cookies / 登录态更新 => 在同一把锁内重置恢复
                tasks[task_key] = self._build_reset_entry(current)
                self._save_unlocked(data)
                return SkipDecision(
                    skip=False,
                    should_notify=False,
                    reason="cookie_updated",
                    paused_until=None,
                    consecutive_failures=0,
                )

            if paused_until and current < paused_until:
                if record_notification:
                    should_notify = last_notified_date != today
                    if should_notify:
                        updated_entry = dict(entry)
                        updated_entry["last_notified_date"] = today
                        tasks[task_key] = updated_entry
                        self._save_unlocked(data)
                else:
                    should_notify = False

                return SkipDecision(
                    skip=True,
                    should_notify=should_notify,
                    reason=last_reason,
                    paused_until=paused_until,
                    consecutive_failures=consecutive,
                )

            return SkipDecision(
                skip=False,
                should_notify=False,
                reason="not_paused",
                paused_until=None,
                consecutive_failures=consecutive,
            )

    def record_failure(
        self,
        task_key: str,
        reason: str,
        *,
        cookie_path: Optional[str] = None,
        min_failures_to_pause: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> dict:
        current = _now(self.tz_name, now=now)
        today = _today_str(self.tz_name, now=current)
        cookie_mtime = _get_mtime(cookie_path)

        effective_threshold = max(1, int(min_failures_to_pause or self.threshold))

        result = {
            "should_notify": False,
            "opened_circuit": False,
            "paused_until": None,
            "consecutive_failures": 0,
        }

        def _apply(entry: dict) -> dict:
            entry = dict(entry or {})
            previous_paused_until = _str_to_dt(entry.get("paused_until"))
            was_paused = bool(previous_paused_until and current < previous_paused_until)

            if _has_cookie_recovered(entry, cookie_path):
                entry["consecutive_failures"] = 0
                entry["paused_until"] = None
                entry["last_notified_date"] = None

            consecutive = _as_int(entry.get("consecutive_failures"), 0) + 1
            entry["consecutive_failures"] = consecutive
            entry["last_failure_reason"] = (reason or "未知错误")[:1000]
            entry["last_failure_at"] = _dt_to_str(current)
            if cookie_path:
                entry["cookie_path"] = cookie_path
                if cookie_mtime is not None:
                    entry["cookie_mtime"] = cookie_mtime

            opened = False
            if consecutive >= effective_threshold:
                paused_until = current + timedelta(seconds=self.pause_seconds)
                entry["paused_until"] = _dt_to_str(paused_until)
                opened = not was_paused

                if entry.get("last_notified_date") != today:
                    entry["last_notified_date"] = today
                    result["should_notify"] = True

                result["paused_until"] = paused_until
            else:
                entry["paused_until"] = None

            result["opened_circuit"] = opened
            result["consecutive_failures"] = consecutive
            return entry

        self._update_task(task_key, _apply)
        return result
