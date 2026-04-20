"""
任务生成作业执行器
"""
import os

import aiofiles

from src.config import is_ai_enabled
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
    try:
        await advance_job(
            generation_service,
            job_id,
            "prepare",
            "已接收请求，开始处理任务。",
        )

        async def report_progress(step_key: str, message: str) -> None:
            await advance_job(generation_service, job_id, step_key, message)

        # 商品 ID 监控模式：跳过 AI 生成分析标准，直接创建任务
        if req.task_type == "item_id":
            await advance_job(
                generation_service,
                job_id,
                "task",
                "商品 ID 监控模式，直接创建任务记录。",
            )
            # 商品 ID 监控模式：直接访问商品详情页，不需要筛选条件
            task = await task_service.create_task(TaskCreate(
                task_name=req.task_name,
                task_type="item_id",
                enabled=True,
                keyword=None,
                item_id_list=req.item_id_list,
                description="",  # 商品 ID 模式不需要 AI 生成标准
                analyze_images=True,  # 默认开启图片分析
                max_pages=1,  # 商品 ID 每次只查 1 个
                personal_only=False,  # 详情页不需要卖家筛选
                min_price=None,  # 详情页不需要价格筛选
                max_price=None,
                cron=req.cron,
                ai_prompt_base_file="prompts/base_prompt.txt",
                ai_prompt_criteria_file="",  # 不需要 AI 生成的分析标准
                account_state_file=req.account_state_file,
                account_strategy=req.account_strategy,
                free_shipping=False,  # 详情页不需要运费筛选
                new_publish_option="",  # 详情页不需要发布时间筛选
                region=None,  # 详情页不需要地区筛选
                decision_mode="ai",  # 固定使用 AI 分析
                keyword_rules=[],  # 不需要关键词规则
            ))
            await reload_scheduler(task_service, scheduler_service)
            await generation_service.complete(job_id, task, f"任务'{req.task_name}'创建完成。")
            return

        # 检查 AI 功能开关状态
        if not is_ai_enabled():
            # AI 功能被禁用，使用默认 criteria 文件
            output_filename = build_criteria_filename(req.keyword or "")
            await advance_job(
                generation_service,
                job_id,
                "persist",
                f"AI 功能已禁用，使用默认分析标准。",
            )
            # 使用基础的 prompt 作为 criteria
            default_criteria = """基于用户需求，推荐值得购买的商品。
关注商品的质量、价格合理性、卖家信誉等关键因素。"""
            await save_generated_criteria(output_filename, default_criteria)
        else:
            # AI 功能启用，正常生成分析标准
            output_filename = build_criteria_filename(req.keyword or "")
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
        await generation_service.complete(job_id, task, f"任务'{req.task_name}'创建完成。")
    except Exception as exc:
        await generation_service.fail(job_id, f"AI 任务生成失败：{exc}")
