"""
任务管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import os
from contextlib import contextmanager, nullcontext
from functools import partial
from src.domain.repositories.task_repository import RunningTaskRename, TaskBusy, TaskChanged, TaskNameConflict
from src.api.dependencies import (
    get_process_service,
    get_scheduler_service,
    get_task_generation_service,
    get_task_service,
)
from src.services.task_service import TaskService
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.services.task_generation_service import TaskGenerationService
from src.services.task_generation_runner import (
    build_criteria_filename,
    build_task_create,
    publish_generated_criteria,
    run_ai_generation_job,
)
from src.services.task_payloads import serialize_task, serialize_tasks
from src.domain.models.task import TaskCreate, TaskUpdate, TaskGenerateRequest
from src.prompt_utils import generate_criteria
from src.utils import resolve_task_log_path
from src.services.account_strategy_service import normalize_account_strategy
from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.price_history_service import delete_price_snapshots
from src.services.result_storage_service import delete_result_file_records
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

async def _reload_scheduler_if_needed(
    task_service: TaskService,
    scheduler_service: SchedulerService,
):
    tasks = await task_service.get_all_tasks()
    await scheduler_service.reload_jobs(tasks)


def _has_keyword_rules(rules) -> bool:
    return bool(rules and len(rules) > 0)


def _validate_final_account_strategy(existing_task, task_update: TaskUpdate) -> None:
    if task_update.model_fields_set.isdisjoint({"account_state_file", "account_strategy"}):
        return
    account_state_file = (
        task_update.account_state_file
        if task_update.account_state_file is not None
        else existing_task.account_state_file
    )
    account_strategy = normalize_account_strategy(
        task_update.account_strategy,
        account_state_file,
    )
    task_update.account_strategy = account_strategy
    if account_strategy == "fixed" and not account_state_file:
        raise HTTPException(status_code=400, detail="固定账号模式下必须选择账号。")


def _ensure_unique_task_name(
    all_tasks,
    task_name: str,
    *,
    exclude_task_id: int | None = None,
) -> str:
    clean_name = (task_name or "").strip()
    for existing in all_tasks:
        if exclude_task_id is not None and existing.id == exclude_task_id:
            continue
        if (existing.task_name or "").strip() == clean_name:
            raise HTTPException(
                status_code=400,
                detail=f"任务名称 '{clean_name}' 已存在，请使用唯一名称",
            )
    return clean_name


def _ensure_no_duplicate_task_name_for_unpause(all_tasks, task) -> None:
    clean_name = (task.task_name or "").strip()
    duplicate_count = sum(
        1 for item in all_tasks if (item.task_name or "").strip() == clean_name
    )
    if duplicate_count > 1:
        raise HTTPException(
            status_code=409,
            detail=f"存在多个同名任务 '{task.task_name}'，请先重命名后再解除熔断",
        )
@router.get("", response_model=List[dict])
async def get_tasks(
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """获取所有任务"""
    tasks = await service.get_all_tasks()
    return serialize_tasks(tasks, scheduler_service, process_service)
@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """获取单个任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    return serialize_task(task, scheduler_service, process_service)
@router.post("/", response_model=dict)
async def create_task(
    task_create: TaskCreate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """创建新任务"""
    all_tasks = await service.get_all_tasks()
    _ensure_unique_task_name(all_tasks, task_create.task_name)
    try:
        task = await service.create_task(task_create)
    except TaskNameConflict as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _reload_scheduler_if_needed(service, scheduler_service)
    return {"message": "任务创建成功", "task": serialize_task(task, scheduler_service, process_service)}
@router.post("/generate", response_model=dict)
async def generate_task(
    req: TaskGenerateRequest,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    process_service: ProcessService = Depends(get_process_service),
    generation_service: TaskGenerationService = Depends(get_task_generation_service),
):
    """创建任务。AI模式会生成分析标准，关键词模式直接保存规则。"""
    print(f"收到任务生成请求: {req.task_name}，模式: {req.decision_mode}")

    try:
        all_tasks = await service.get_all_tasks()
        _ensure_unique_task_name(all_tasks, req.task_name)
        mode = req.decision_mode or "ai"
        if mode == "ai":
            job = await generation_service.create_job(req.task_name)
            generation_service.track(
                run_ai_generation_job(
                    job_id=job.job_id,
                    req=req,
                    task_service=service,
                    scheduler_service=scheduler_service,
                    generation_service=generation_service,
                )
            )
            return JSONResponse(
                status_code=202,
                content={
                    "message": "AI 任务生成已开始。",
                    "job": job.model_dump(mode="json"),
                },
            )

        task = await service.create_task(build_task_create(req, ""))
        await _reload_scheduler_if_needed(service, scheduler_service)
        return {"message": "任务创建成功。", "task": serialize_task(task, scheduler_service, process_service)}

    except TaskNameConflict as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"AI任务生成API发生未知错误: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)
@router.get("/generate-jobs/{job_id}", response_model=dict)
async def get_task_generation_job(
    job_id: str,
    generation_service: TaskGenerationService = Depends(get_task_generation_service),
):
    """获取任务生成作业状态"""
    job = await generation_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务生成作业未找到")
    return {"job": job.model_dump(mode="json")}
@router.patch("/{task_id}", response_model=dict)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """更新任务"""
    try:
        existing_task = await service.get_task(task_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="任务未找到")
        old_task_name = existing_task.task_name
        guard_change = nullcontext
        criteria_change = nullcontext
        if task_update.task_name is not None and task_update.task_name != old_task_name:
            if existing_task.is_running or process_service.is_running(task_id):
                raise RunningTaskRename()
            all_tasks = await service.get_all_tasks()
            _ensure_unique_task_name(
                all_tasks,
                task_update.task_name,
                exclude_task_id=task_id,
            )
            old_name_shared = any(
                item.id != task_id and item.task_name == old_task_name for item in all_tasks
            )
            guard_change = partial(
                process_service.rename_task_guard, task_id, old_task_name, task_update.task_name,
                keep_old=old_name_shared,
            )
        _validate_final_account_strategy(existing_task, task_update)

        current_mode = getattr(existing_task, "decision_mode", "ai") or "ai"
        target_mode = task_update.decision_mode or current_mode
        description_changed = (
            task_update.description is not None
            and task_update.description != existing_task.description
        )
        switched_to_ai = current_mode != "ai" and target_mode == "ai"

        if target_mode == "keyword":
            final_rules = (
                task_update.keyword_rules
                if task_update.keyword_rules is not None
                else getattr(existing_task, "keyword_rules", [])
            )
            if not _has_keyword_rules(final_rules):
                raise HTTPException(status_code=400, detail="关键词模式下至少需要一个关键词。")
        if target_mode == "ai" and (description_changed or switched_to_ai):
            print(f"检测到任务 {task_id} 需要刷新 AI 标准文件，开始重新生成...")
            try:
                description_for_ai = (
                    task_update.description
                    if task_update.description is not None
                    else existing_task.description
                )
                if not str(description_for_ai or "").strip():
                    raise HTTPException(status_code=400, detail="AI 模式下详细需求不能为空。")
                output_filename = build_criteria_filename(existing_task.keyword)
                print("开始调用 AI 生成新的分析标准...")
                generated_criteria = await generate_criteria(
                    user_description=description_for_ai,
                    reference_file_path="prompts/macbook_criteria.txt"
                )
                if not generated_criteria or len(generated_criteria.strip()) == 0:
                    print("AI 返回的内容为空")
                    raise HTTPException(status_code=500, detail="AI 未能生成分析标准，返回内容为空。")
                criteria_change = partial(publish_generated_criteria, output_filename, generated_criteria)
                task_update.ai_prompt_criteria_file = output_filename
                print(f"已更新 ai_prompt_criteria_file 字段为: {output_filename}")
            except HTTPException:
                raise
            except Exception as e:
                error_msg = f"重新生成 criteria 文件时出错: {str(e)}"
                print(error_msg)
                import traceback
                print(traceback.format_exc())
                raise HTTPException(status_code=500, detail=error_msg)
        @contextmanager
        def commit_changes():
            with guard_change(), criteria_change():
                yield

        task = await service.update_task(
            task_id, task_update, expected_name=old_task_name, on_commit=commit_changes,
        )
        await _reload_scheduler_if_needed(service, scheduler_service)
        return {"message": "任务更新成功", "task": serialize_task(task, scheduler_service, process_service)}
    except (RunningTaskRename, TaskChanged) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskNameConflict as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="任务更新写入失败，请检查存储权限后重试") from exc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """删除任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    all_tasks = await service.get_all_tasks()
    same_name_in_use = any(t.id != task_id and t.task_name == task.task_name for t in all_tasks)
    try:
        async with process_service.stop_for_deletion(task_id, task.task_name, keep_old=same_name_in_use) as on_commit:
            success = await service.delete_task(task_id, expected_name=task.task_name, on_commit=on_commit)
    except TaskBusy as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except TaskChanged as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="任务删除写入失败，请检查存储权限后重试") from exc
    if not success:
        raise HTTPException(status_code=404, detail="任务未找到")
    remaining_tasks = await service.get_all_tasks()
    await scheduler_service.reload_jobs(remaining_tasks)
    try:
        keyword = (task.keyword or "").strip()
        if keyword:
            keyword_still_in_use = any(
                (remaining_task.keyword or "").strip() == keyword
                for remaining_task in remaining_tasks
            )
            if not keyword_still_in_use:
                await delete_result_file_records(build_result_filename(keyword))
                delete_price_snapshots(keyword)
    except Exception as e:
        print(f"删除任务结果文件时出错: {e}")

    try:
        log_file_path = resolve_task_log_path(task_id, task.task_name)
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
    except Exception as e:
        print(f"删除任务日志文件时出错: {e}")
    return {"message": "任务删除成功"}
@router.post("/{task_id}/unpause", response_model=dict)
async def unpause_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """解除单个任务的熔断暂停状态"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    all_tasks = await service.get_all_tasks()
    _ensure_no_duplicate_task_name_for_unpause(all_tasks, task)
    process_service.unpause_task(task.task_name)
    return {
        "message": f"任务 '{task.task_name}' 已解除熔断暂停",
        "task": serialize_task(task, scheduler_service, process_service),
    }
@router.post("/start/{task_id}", response_model=dict)
async def start_task(
    task_id: int,
    force_unpause: bool = False,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """启动单个任务"""
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    if not task.enabled:
        raise HTTPException(status_code=400, detail="任务已被禁用，无法启动")
    if task.is_running:
        raise HTTPException(status_code=400, detail="任务已在运行中")
    if force_unpause:
        all_tasks = await task_service.get_all_tasks()
        _ensure_no_duplicate_task_name_for_unpause(all_tasks, task)

    start_manual_fn = getattr(process_service, "start_task_manual", None)
    if callable(start_manual_fn):
        result = await start_manual_fn(task, force_unpause=force_unpause)
        if result.status == "paused":
            reason = result.reason or "未知错误"
            paused_until = result.paused_until or "未知时间"
            raise HTTPException(
                status_code=409,
                detail=(
                    f"任务处于熔断暂停状态（原因：{reason}，恢复时间：{paused_until}），"
                    "请先解除熔断或确认解除后启动"
                ),
            )
        if result.status == "busy":
            raise HTTPException(status_code=423, detail="任务正在启动或修改，请稍后重试")
        if result.status == "stale":
            raise HTTPException(status_code=400, detail="任务已更改，请刷新后重试")
        if result.status == "already_running":
            raise HTTPException(status_code=400, detail="任务已在运行中")
        if result.status != "started":
            raise HTTPException(status_code=500, detail="启动任务失败")
    else:
        success = await process_service.start_task(
            task_id,
            task.task_name,
            force_unpause=force_unpause,
        )
        if not success:
            raise HTTPException(status_code=500, detail="启动任务失败")
    return {"message": f"任务 '{task.task_name}' 已启动"}
@router.post("/stop/{task_id}", response_model=dict)
async def stop_task(
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """停止单个任务"""
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    await process_service.stop_task(task_id)
    return {"message": f"任务ID {task_id} 已发送停止信号"}
