from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.services.task_log_cleanup_service import cleanup_task_logs


def _write_file(path: Path, content: str = "log") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _set_mtime(path: Path, when: datetime) -> None:
    timestamp = when.timestamp()
    path.touch()
    path.chmod(0o644)
    import os

    os.utime(path, (timestamp, timestamp))


def test_cleanup_task_logs_removes_only_expired_top_level_logs(tmp_path):
    logs_dir = tmp_path / "logs"
    old_log = logs_dir / "old_task.log"
    recent_log = logs_dir / "recent_task.log"
    nested_ai_log = logs_dir / "ai" / "old_ai.log"
    state_file = logs_dir / "task-failure-guard.json"

    _write_file(old_log)
    _write_file(recent_log)
    _write_file(nested_ai_log)
    _write_file(state_file, "{}")

    now = datetime(2026, 3, 19, 12, 0, 0)
    _set_mtime(old_log, datetime(2026, 3, 1, 0, 0, 0))
    _set_mtime(recent_log, datetime(2026, 3, 18, 23, 0, 0))
    _set_mtime(nested_ai_log, datetime(2026, 3, 1, 0, 0, 0))
    _set_mtime(state_file, datetime(2026, 3, 1, 0, 0, 0))

    removed = cleanup_task_logs(str(logs_dir), keep_days=7, now=now)

    assert removed == [str(old_log)]
    assert not old_log.exists()
    assert recent_log.exists()
    assert nested_ai_log.exists()
    assert state_file.exists()


def test_cleanup_task_logs_skips_when_retention_is_invalid(tmp_path):
    logs_dir = tmp_path / "logs"
    task_log = logs_dir / "task.log"
    _write_file(task_log)

    removed = cleanup_task_logs(str(logs_dir), keep_days=0, now=datetime(2026, 3, 19, 12, 0, 0))

    assert removed == []
    assert task_log.exists()
