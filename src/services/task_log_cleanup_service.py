"""
任务运行日志清理服务。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path


def cleanup_task_logs(
    logs_dir: str = "logs",
    *,
    keep_days: int = 7,
    now: datetime | None = None,
) -> list[str]:
    if keep_days < 1:
        print(f"任务日志清理已跳过：保留天数配置无效 ({keep_days})")
        return []

    root = Path(logs_dir)
    if not root.exists():
        return []

    current_time = now or datetime.now()
    cutoff = current_time - timedelta(days=keep_days)
    removed_files: list[str] = []

    for path in root.glob("*.log"):
        if not path.is_file():
            continue
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError as exc:
            print(f"读取任务日志时间失败，已跳过: {path} ({exc})")
            continue

        if modified_at >= cutoff:
            continue

        try:
            path.unlink()
            removed_files.append(str(path))
        except OSError as exc:
            print(f"删除历史任务日志失败，已跳过: {path} ({exc})")

    if removed_files:
        print(
            f"任务日志清理完成：已删除 {len(removed_files)} 个超过 {keep_days} 天的历史日志文件。"
        )

    return removed_files
