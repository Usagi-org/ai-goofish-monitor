"""
日志管理路由
"""
import os
from typing import Optional, Tuple, List
import aiofiles
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from src.api.dependencies import get_task_service
from src.services.task_service import TaskService
from src.utils import resolve_task_log_path


router = APIRouter(prefix="/api/logs", tags=["logs"])


async def _read_tail_lines(
    log_file_path: str,
    offset_lines: int,
    limit_lines: int,
    chunk_size: int = 8192
) -> Tuple[List[str], bool, int]:
    async with aiofiles.open(log_file_path, 'rb') as f:
        await f.seek(0, os.SEEK_END)
        file_size = await f.tell()

        if file_size == 0 or limit_lines <= 0:
            return [], False, file_size

        offset_lines = max(0, int(offset_lines))
        limit_lines = max(0, int(limit_lines))
        lines_needed = offset_lines + limit_lines

        pos = file_size
        buffer = b""
        lines: List[bytes] = []

        while pos > 0 and len(lines) < lines_needed:
            read_size = min(chunk_size, pos)
            pos -= read_size
            await f.seek(pos)
            chunk = await f.read(read_size)
            buffer = chunk + buffer
            lines = buffer.splitlines()

        start = max(0, len(lines) - lines_needed)
        end = max(0, len(lines) - offset_lines)
        selected = lines[start:end] if end > start else []

        has_more = pos > 0 or len(lines) > lines_needed
        decoded = [line.decode('utf-8', errors='replace') for line in selected]
        return decoded, has_more, file_size


@router.get("")
async def get_logs(
    from_pos: int = 0,
    task_id: Optional[int] = Query(default=None, ge=0),
    task_service: TaskService = Depends(get_task_service),
):
    """获取日志内容（增量读取）"""
    if task_id is None:
        return JSONResponse(content={
            "new_content": "请选择任务后查看日志。",
            "new_pos": 0
        })

    task = await task_service.get_task(task_id)
    if not task:
        return JSONResponse(status_code=404, content={
            "new_content": "任务不存在或已删除。",
            "new_pos": 0
        })

    log_file_path = resolve_task_log_path(task_id, task.task_name)

    if not os.path.exists(log_file_path):
        return JSONResponse(content={
            "new_content": "",
            "new_pos": 0
        })

    try:
        async with aiofiles.open(log_file_path, 'rb') as f:
            await f.seek(0, os.SEEK_END)
            file_size = await f.tell()

            if from_pos >= file_size:
                return {"new_content": "", "new_pos": file_size}

            await f.seek(from_pos)
            new_bytes = await f.read()

        new_content = new_bytes.decode('utf-8', errors='replace')
        return {"new_content": new_content, "new_pos": file_size}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"new_content": f"\n读取日志文件时出错: {e}", "new_pos": from_pos}
        )  


@router.get("/tail")
async def get_logs_tail(
    task_id: Optional[int] = Query(default=None, ge=0),
    offset_lines: int = Query(default=0, ge=0),
    limit_lines: int = Query(default=50, ge=1, le=1000),
    task_service: TaskService = Depends(get_task_service),
):
    """获取日志尾部内容（按行分页）"""
    if task_id is None:
        return JSONResponse(content={
            "content": "",
            "has_more": False,
            "next_offset": 0,
            "new_pos": 0
        })

    task = await task_service.get_task(task_id)
    if not task:
        return JSONResponse(status_code=404, content={
            "content": "",
            "has_more": False,
            "next_offset": 0,
            "new_pos": 0
        })

    log_file_path = resolve_task_log_path(task_id, task.task_name)

    if not os.path.exists(log_file_path):
        return JSONResponse(content={
            "content": "",
            "has_more": False,
            "next_offset": 0,
            "new_pos": 0
        })

    try:
        lines, has_more, file_size = await _read_tail_lines(
            log_file_path,
            offset_lines=offset_lines,
            limit_lines=limit_lines
        )
        next_offset = offset_lines + len(lines)
        return {
            "content": "\n".join(lines),
            "has_more": has_more,
            "next_offset": next_offset,
            "new_pos": file_size
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "content": f"读取日志文件时出错: {e}",
                "has_more": False,
                "next_offset": offset_lines,
                "new_pos": 0
            }
        )


@router.delete("", response_model=dict)
async def clear_logs(
    task_id: Optional[int] = Query(default=None, ge=0),
    task_service: TaskService = Depends(get_task_service),
):
    """清空日志文件"""
    if task_id is None:
        return {"message": "未指定任务，无法清空日志。"}

    task = await task_service.get_task(task_id)
    if not task:
        return {"message": "任务不存在或已删除。"}

    log_file_path = resolve_task_log_path(task_id, task.task_name)

    if not os.path.exists(log_file_path):
        return {"message": "日志文件不存在，无需清空。"}

    try:
        async with aiofiles.open(log_file_path, 'w', encoding='utf-8') as f:
            await f.write("")
        return {"message": "日志已成功清空。"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"清空日志文件时出错: {e}"}
        )

    if not os.path.exists(log_file_path):
        return {"message": "日志文件不存在，无需清空。"}

    try:
        async with aiofiles.open(log_file_path, 'w', encoding='utf-8') as f:
            await f.write("")
        return {"message": "日志已成功清空。"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"清空日志文件时出错: {e}"}
        )
