"""
任务生成作业执行器
"""
import os

import aiofiles

from src.domain.models.task import TaskCreate, TaskGenerateRequest
from src.prompt_utils import generate_criteria
from src.services.scheduler_service import SchedulerService
from src.services.task_generation_service import TaskGenerationService
from src.services.task_service import TaskService

def build_criteria_filename(keyword: str) -> str:
    safe_keyword = "".join(
        char for char in keyword.lower().replace(" ", "_")
        if char.isalnum() or char in "_-"
    ).rstrip()
    return f"prompts/{safe_keyword}_criteria.txt"


def build_task_create(req: TaskGenerateRequest, criteria_file: str) -> TaskCreate:
    return TaskCreate(
        task_name=req.task_name,
        enabled=True,
        keyword=req.keyword,
        description=req.description or "",
        analyze_images=req.analyze_images,
        max_pages=req.max_pages,
        personal_only=req.personal_only,
        min_price=req.min_price,
        max_price=req.max_price,
        cron=req.cron,
        ai_prompt_base_file="prompts/base_prompt.txt",
        ai_prompt_criteria_file=criteria_file,
        account_state_file=req.account_state_file,
        account_strategy=req.account_strategy,
        free_shipping=req.free_shipping,
        new_publish_option=req.new_publish_option,
        region=req.region,
        decision_mode=req.decision_mode or "ai",
        keyword_rules=req.keyword_rules,
    )


async def save_generated_criteria(output_filename: str, generated_criteria: str) -> None:
    if not generated_criteria or not generated_criteria.strip():
        raise RuntimeError("AI 未能生成分析标准，返回内容为空。")

    os.makedirs("prompts", exist_ok=True)
    async with aiofiles.open(output_filename, "w", encoding="utf-8") as file:
        await file.write(generated_criteria)


async def reload_scheduler(
    task_service: TaskService,
    scheduler_service: SchedulerService,
) -> None:
    tasks = await task_service.get_all_tasks()
    await scheduler_service.reload_jobs(tasks)


async def advance_job(
    generation_service: TaskGenerationService,
    job_id: str,
    step_key: str,
    message: str,
) -> None:
    await generation_service.advance(job_id, step_key, message)


async def run_ai_generation_job(
    *,
    job_id: str,
    req: TaskGenerateRequest,
    task_service: TaskService,
    scheduler_service: SchedulerService,
    generation_service: TaskGenerationService,
) -> None:
    output_filename = build_criteria_filename(req.keyword)
    try:
        await advance_job(
            generation_service,
            job_id,
            "prepare",
            "已接收请求，开始准备分析标准。",
        )

        async def report_progress(step_key: str, message: str) -> None:
            await advance_job(generation_service, job_id, step_key, message)

        generated_criteria = await generate_criteria(
            user_description=req.description or "",
            reference_file_path="prompts/macbook_criteria.txt",
            progress_callback=report_progress,
        )

        await advance_job(
            generation_service,
            job_id,
            "persist",
            f"正在保存分析标准到 {output_filename}。",
        )
        await save_generated_criteria(output_filename, generated_criteria)

        await advance_job(
            generation_service,
            job_id,
            "task",
            "分析标准已生成，正在创建任务记录。",
        )
        task = await task_service.create_task(build_task_create(req, output_filename))
        await reload_scheduler(task_service, scheduler_service)
        await generation_service.complete(job_id, task, f"任务“{req.task_name}”创建完成。")
    except Exception as exc:
        if os.path.exists(output_filename):
            os.remove(output_filename)
        await generation_service.fail(job_id, f"AI 任务生成失败: {exc}")
