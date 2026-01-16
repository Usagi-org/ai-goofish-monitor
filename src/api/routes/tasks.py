"""
任务管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import os
import aiofiles
from src.api.dependencies import get_task_service, get_process_service, get_scheduler_service
from src.services.task_service import TaskService
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.domain.models.task import Task, TaskCreate, TaskUpdate, TaskGenerateRequest
from src.api.routes.websocket import broadcast_message
from src.prompt_utils import generate_criteria
from src.utils import resolve_task_log_path


router = APIRouter(prefix="/api/tasks", tags=["tasks"])

async def _reload_scheduler_if_needed(
    task_service: TaskService,
    scheduler_service: SchedulerService,
):
    tasks = await task_service.get_all_tasks()
    await scheduler_service.reload_jobs(tasks)


@router.get("", response_model=List[dict])
async def get_tasks(
    service: TaskService = Depends(get_task_service),
):
    """获取所有任务"""
    tasks = await service.get_all_tasks()
    return [task.dict() for task in tasks]


@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
):
    """获取单个任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    return task.dict()


@router.post("/", response_model=dict)
async def create_task(
    task_create: TaskCreate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """创建新任务"""
    task = await service.create_task(task_create)
    await _reload_scheduler_if_needed(service, scheduler_service)
    return {"message": "任务创建成功", "task": task.dict()}


@router.post("/generate", response_model=dict)
async def generate_task(
    req: TaskGenerateRequest,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """使用 AI 生成分析标准并创建新任务"""
    print(f"收到 AI 任务生成请求: {req.task_name}")

    try:
        # 1. 生成唯一的文件名
        safe_keyword = "".join(
            c for c in req.keyword.lower().replace(' ', '_')
            if c.isalnum() or c in "_-"
        ).rstrip()
        output_filename = f"prompts/{safe_keyword}_criteria.txt"
        print(f"生成的文件路径: {output_filename}")

        # 2. 调用 AI 生成分析标准
        print("开始调用AI生成分析标准...")
        generated_criteria = await generate_criteria(
            user_description=req.description,
            reference_file_path="prompts/macbook_criteria.txt"
        )

        print(f"AI生成的分析标准长度: {len(generated_criteria) if generated_criteria else 0}")
        if not generated_criteria or len(generated_criteria.strip()) == 0:
            print("AI返回的内容为空或只有空白字符")
            raise HTTPException(status_code=500, detail="AI未能生成分析标准，返回内容为空。")

        # 3. 保存生成的文本到新文件
        print(f"开始保存分析标准到文件: {output_filename}")
        try:
            os.makedirs("prompts", exist_ok=True)
            async with aiofiles.open(output_filename, 'w', encoding='utf-8') as f:
                await f.write(generated_criteria)
            print(f"新的分析标准已保存到: {output_filename}")
        except IOError as e:
            print(f"保存分析标准文件失败: {e}")
            raise HTTPException(status_code=500, detail=f"保存分析标准文件失败: {e}")

        # 4. 创建新任务对象
        print("开始创建新任务对象...")
        task_create = TaskCreate(
            task_name=req.task_name,
            enabled=True,
            keyword=req.keyword,
            description=req.description,
            max_pages=req.max_pages,
            personal_only=req.personal_only,
            min_price=req.min_price,
            max_price=req.max_price,
            cron=req.cron,
            ai_prompt_base_file="prompts/base_prompt.txt",
            ai_prompt_criteria_file=output_filename,
            account_state_file=req.account_state_file,
            free_shipping=req.free_shipping,
            new_publish_option=req.new_publish_option,
            region=req.region,
        )

        # 5. 使用 TaskService 创建任务
        print("开始通过 TaskService 创建任务...")
        task = await service.create_task(task_create)

        print(f"AI任务创建成功: {req.task_name}")
        await _reload_scheduler_if_needed(service, scheduler_service)
        return {"message": "AI 任务创建成功。", "task": task.dict()}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"AI任务生成API发生未知错误: {str(e)}"
        print(error_msg)
        import traceback
        print(traceback.format_exc())

        # 如果文件已创建但任务创建失败，清理文件
        if 'output_filename' in locals() and os.path.exists(output_filename):
            try:
                os.remove(output_filename)
                print(f"已删除失败的文件: {output_filename}")
            except Exception as cleanup_error:
                print(f"清理失败文件时出错: {cleanup_error}")

        raise HTTPException(status_code=500, detail=error_msg)


@router.patch("/{task_id}", response_model=dict)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """更新任务"""
    try:
        existing_task = await service.get_task(task_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="任务未找到")

        # 检查是否需要重新生成 criteria 文件
        if task_update.description is not None and task_update.description != existing_task.description:
            print(f"检测到任务 {task_id} 的 description 更新，开始重新生成 criteria 文件...")

            try:
                # 生成新的文件名
                safe_keyword = "".join(
                    c for c in existing_task.keyword.lower().replace(' ', '_')
                    if c.isalnum() or c in "_-"
                ).rstrip()
                output_filename = f"prompts/{safe_keyword}_criteria.txt"
                print(f"目标文件路径: {output_filename}")

                # 调用 AI 生成新的分析标准
                print("开始调用 AI 生成新的分析标准...")
                generated_criteria = await generate_criteria(
                    user_description=task_update.description,
                    reference_file_path="prompts/macbook_criteria.txt"
                )

                if not generated_criteria or len(generated_criteria.strip()) == 0:
                    print("AI 返回的内容为空")
                    raise HTTPException(status_code=500, detail="AI 未能生成分析标准，返回内容为空。")

                # 保存生成的文本到文件
                print(f"保存新的分析标准到: {output_filename}")
                os.makedirs("prompts", exist_ok=True)
                async with aiofiles.open(output_filename, 'w', encoding='utf-8') as f:
                    await f.write(generated_criteria)
                print(f"新的分析标准已保存")

                # 更新 task_update 中的 ai_prompt_criteria_file 字段
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

        # 执行任务更新
        task = await service.update_task(task_id, task_update)
        await _reload_scheduler_if_needed(service, scheduler_service)
        return {"message": "任务更新成功", "task": task.dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """删除任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务未找到")
        
    await _reload_scheduler_if_needed(service, scheduler_service)

    try:
        keyword = (task.keyword or "").strip()
        if keyword:
            filename = f"{keyword.replace(' ', '_')}_full_data.jsonl"
            file_path = os.path.join("jsonl", filename)
            if os.path.exists(file_path):
                os.remove(file_path)
    except Exception as e:
        print(f"删除任务结果文件时出错: {e}")

    try:
        log_file_path = resolve_task_log_path(task_id, task.task_name)
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
    except Exception as e:
        print(f"删除任务日志文件时出错: {e}")

    return {"message": "任务删除成功"}


@router.post("/start/{task_id}", response_model=dict)
async def start_task(
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """启动单个任务"""
    # 获取任务信息
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    # 检查任务是否已启用
    if not task.enabled:
        raise HTTPException(status_code=400, detail="任务已被禁用，无法启动")

    # 检查任务是否已在运行
    if task.is_running:
        raise HTTPException(status_code=400, detail="任务已在运行中")

    # 启动任务进程
    success = await process_service.start_task(task_id, task.task_name)
    if not success:
        raise HTTPException(status_code=500, detail="启动任务失败")

    # 更新任务状态
    await task_service.update_task_status(task_id, True)

    # 广播任务状态变更
    await broadcast_message("task_status_changed", {"id": task_id, "is_running": True})

    return {"message": f"任务 '{task.task_name}' 已启动"}


@router.post("/stop/{task_id}", response_model=dict)
async def stop_task(
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """停止单个任务"""
    # 获取任务信息
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    # 停止任务进程
    await process_service.stop_task(task_id)

    # 更新任务状态
    await task_service.update_task_status(task_id, False)

    # 广播任务状态变更
    await broadcast_message("task_status_changed", {"id": task_id, "is_running": False})

    return {"message": f"任务ID {task_id} 已发送停止信号"}
