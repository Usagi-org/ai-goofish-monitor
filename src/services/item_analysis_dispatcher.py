"""
商品分析分发器
将卖家资料采集、图片下载、AI 分析和结果保存移出主抓取链路。
"""
import asyncio
import copy
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from src.keyword_rule_engine import build_search_text, evaluate_keyword_rules
from src.services.auto_order_service import AutoOrderService
from src.services.seller_active_service import (
    format_active_time,
    get_active_level,
)


SellerLoader = Callable[[str], Awaitable[dict]]
ImageDownloader = Callable[[str, list[str], str], Awaitable[list[str]]]
AIAnalyzer = Callable[[dict, list[str], str], Awaitable[Optional[dict]]]
Notifier = Callable[[dict, str], Awaitable[None]]
Saver = Callable[[dict, str], Awaitable[bool]]


@dataclass(frozen=True)
class ItemAnalysisJob:
    keyword: str
    task_name: str
    decision_mode: str
    analyze_images: bool
    prompt_text: str
    keyword_rules: tuple[str, ...]
    final_record: dict
    seller_id: Optional[str]
    zhima_credit_text: Optional[str]
    registration_duration_text: str
    seller_last_active_time: Optional[str] = None
    seller_online_status: Optional[str] = None


class ItemAnalysisDispatcher:
    """用受控并发处理商品分析和落盘。"""

    def __init__(
        self,
        *,
        concurrency: int,
        skip_ai_analysis: bool,
        seller_loader: SellerLoader,
        image_downloader: ImageDownloader,
        ai_analyzer: AIAnalyzer,
        notifier: Notifier,
        saver: Saver,
        auto_order_service: Optional[AutoOrderService] = None,
        task_config: Optional[dict] = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._skip_ai_analysis = skip_ai_analysis
        self._seller_loader = seller_loader
        self._image_downloader = image_downloader
        self._ai_analyzer = ai_analyzer
        self._notifier = notifier
        self._saver = saver
        self._auto_order_service = auto_order_service
        self._task_config = task_config or {}
        self._tasks: set[asyncio.Task] = set()
        self.completed_count = 0

    def submit(self, job: ItemAnalysisJob) -> None:
        task = asyncio.create_task(self._process_with_limit(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def join(self) -> None:
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks))

    async def _process_with_limit(self, job: ItemAnalysisJob) -> None:
        async with self._semaphore:
            await self._process_job(job)

    async def _process_job(self, job: ItemAnalysisJob) -> None:
        record = copy.deepcopy(job.final_record)
        item_data = record.get("商品信息", {}) or {}
        record["卖家信息"] = await self._load_seller_info(job)
        record["ai_analysis"] = await self._build_analysis_result(job, record)
        if await self._saver(record, job.keyword):
            self.completed_count += 1
        
        # 检查自动下单逻辑
        auto_order_result = None
        if self._auto_order_service:
            auto_order_result = await self._auto_order_service.process_auto_order(
                item_data=item_data,
                task_config=self._task_config,
            )
        
        await self._notify_with_auto_order(item_data, record["ai_analysis"], auto_order_result)

    async def _load_seller_info(self, job: ItemAnalysisJob) -> dict:
        seller_info = {}
        if job.seller_id:
            try:
                seller_info = await self._seller_loader(job.seller_id)
            except Exception as exc:
                print(f"   [卖家] 采集卖家 {job.seller_id} 信息失败：{exc}")
        
        merged = copy.deepcopy(seller_info or {})
        merged["卖家芝麻信用"] = job.zhima_credit_text
        merged["卖家注册时长"] = job.registration_duration_text
        
        # 添加活跃时间信息
        if job.seller_last_active_time:
            merged["卖家最后活跃时间"] = job.seller_last_active_time
            merged["卖家活跃时间格式化"] = format_active_time(job.seller_last_active_time)
            merged["卖家活跃等级"] = get_active_level(job.seller_last_active_time)
        if job.seller_online_status:
            merged["卖家在线状态"] = job.seller_online_status
        
        return merged

    async def _build_analysis_result(self, job: ItemAnalysisJob, record: dict) -> dict:
        if job.decision_mode == "keyword":
            return self._build_keyword_result(job, record)
        if self._skip_ai_analysis:
            return self._build_skip_ai_result()
        return await self._run_ai_analysis(job, record)

    def _build_keyword_result(self, job: ItemAnalysisJob, record: dict) -> dict:
        search_text = build_search_text(record)
        return evaluate_keyword_rules(list(job.keyword_rules), search_text)

    def _build_skip_ai_result(self) -> dict:
        return {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "商品已跳过 AI 分析，直接通知",
            "keyword_hit_count": 0,
        }

    def _build_ai_error_result(self, reason: str, *, error: str = "") -> dict:
        payload = {
            "analysis_source": "ai",
            "is_recommended": False,
            "reason": reason,
            "keyword_hit_count": 0,
        }
        if error:
            payload["error"] = error
        return payload

    async def _run_ai_analysis(self, job: ItemAnalysisJob, record: dict) -> dict:
        image_paths: list[str] = []
        try:
            image_paths = await self._download_images(job, record)
            if not job.prompt_text:
                return self._build_ai_error_result("任务未配置 AI prompt，跳过分析。")
            ai_result = await self._ai_analyzer(record, image_paths, job.prompt_text)
            if not ai_result:
                return self._build_ai_error_result(
                    "AI analysis returned None after retries.",
                    error="AI analysis returned None after retries.",
                )
            ai_result.setdefault("analysis_source", "ai")
            ai_result.setdefault("keyword_hit_count", 0)
            return ai_result
        except Exception as exc:
            return self._build_ai_error_result(
                f"AI 分析异常：{exc}",
                error=str(exc),
            )
        finally:
            self._cleanup_images(image_paths)

    async def _download_images(self, job: ItemAnalysisJob, record: dict) -> list[str]:
        if not job.analyze_images:
            return []
        item_data = record.get("商品信息", {}) or {}
        image_urls = item_data.get("商品图片列表", [])
        if not image_urls:
            return []
        return await self._image_downloader(
            item_data["商品 ID"],
            image_urls,
            job.task_name,
        )

    def _cleanup_images(self, image_paths: list[str]) -> None:
        for img_path in image_paths:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except Exception as exc:
                print(f"   [图片] 删除图片文件时出错：{exc}")

    async def _notify_with_auto_order(
        self,
        item_data: dict,
        analysis_result: dict,
        auto_order_result: Optional[dict] = None,
    ) -> None:
        """
        发送通知（支持自动下单）
        
        Args:
            item_data: 商品数据
            analysis_result: AI 分析结果
            auto_order_result: 自动下单结果（如果有）
        """
        # 如果不推荐，直接跳过
        if not analysis_result.get("is_recommended"):
            return
        
        # 准备通知数据
        notification_data = dict(item_data)
        reason = analysis_result.get("reason", "无")
        
        # 如果有自动下单结果，附加相关信息
        if auto_order_result:
            if auto_order_result.get("should_notify"):
                # 附加下单链接
                if auto_order_result.get("order_link"):
                    notification_data["下单链接 (PC)"] = auto_order_result["order_link"]
                if auto_order_result.get("mobile_order_link"):
                    notification_data["下单链接 (手机)"] = auto_order_result["mobile_order_link"]
                
                # 更新原因
                action_taken = auto_order_result.get("action_taken", "none")
                if action_taken == "link_generated":
                    reason = f"{reason}\n\n[自动下单] 价格匹配，已生成下单链接，请点击链接购买。"
                elif action_taken == "auto_buy_pending":
                    reason = f"{reason}\n\n[自动下单] 价格匹配，自动购买功能暂未完全实现，请手动点击链接购买。"
                elif action_taken == "notify_only":
                    reason = f"{reason}\n\n[自动下单] 价格匹配（仅通知模式）。"
                
                # 发送通知
                try:
                    await self._notifier(notification_data, reason)
                except Exception as exc:
                    print(f"   [通知] 发送推荐通知失败：{exc}")
            else:
                # 价格不匹配，不发送通知
                print(f"   [自动下单] 价格不匹配，跳过通知：{auto_order_result.get('reason', '')}")
        else:
            # 没有自动下单服务，直接发送通知
            try:
                await self._notifier(notification_data, reason)
            except Exception as exc:
                print(f"   [通知] 发送推荐通知失败：{exc}")
