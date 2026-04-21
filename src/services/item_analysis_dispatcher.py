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
from src.services.metrics_tracking_service import get_metrics_service


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
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._skip_ai_analysis = skip_ai_analysis
        self._seller_loader = seller_loader
        self._image_downloader = image_downloader
        self._ai_analyzer = ai_analyzer
        self._notifier = notifier
        self._saver = saver
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

        # 解析当前价格和想要数（用于比较和记录）
        item_id = str(item_data.get("商品 ID", ""))
        price_raw = item_data.get("当前售价")
        want_count_raw = item_data.get("想要人数")
        browse_count_raw = item_data.get("浏览量")

        # 解析价格为数值
        price_value = None
        if price_raw:
            try:
                price_value = float(str(price_raw).replace("¥", "").strip())
            except (ValueError, TypeError):
                price_value = None

        # 解析想要数为整数
        want_count_value = None
        browse_count_value = None
        if want_count_raw:
            try:
                want_count_value = int(str(want_count_raw).replace("想要", "").strip())
            except (ValueError, TypeError):
                pass
        if browse_count_raw:
            try:
                browse_count_value = int(str(browse_count_raw).replace("浏览", "").strip())
            except (ValueError, TypeError):
                pass

        # 先比较当前值和数据库最新记录（写入之前）
        if item_id:
            metrics_service = get_metrics_service()
            changes = metrics_service.compare_with_latest(
                item_id=item_id,
                current_price=price_value,
                current_price_display=str(price_raw) if price_raw else None,
                current_want_count=want_count_value,
            )
            # 设置或清除变化字段
            if changes and "price_change_display" in changes:
                item_data["price_change_display"] = changes["price_change_display"]
            else:
                item_data.pop("price_change_display", None)
            if changes and "want_count_change_display" in changes:
                item_data["want_count_change_display"] = changes["want_count_change_display"]
            else:
                item_data.pop("want_count_change_display", None)

        # 记录指标快照（价格、想要数）
        if item_id:
            try:
                metrics_service = get_metrics_service()
                metrics_service.record_metrics(
                    item_id=item_id,
                    title=item_data.get("商品标题", "")[:200],
                    price=price_value,
                    price_display=str(price_raw) if price_raw else None,
                    want_count=want_count_value,
                    browse_count=browse_count_value,
                    seller_id=item_data.get("卖家 ID"),
                    link=item_data.get("商品链接"),
                )
            except Exception as e:
                print(f"   [指标] 记录指标快照失败：{e}")

        await self._notify_if_recommended(item_data, record["ai_analysis"])

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

    async def _notify_if_recommended(self, item_data: dict, analysis_result: dict) -> None:
        if not analysis_result.get("is_recommended"):
            return
        try:
            await self._notifier(item_data, analysis_result.get("reason", "无"))
        except Exception as exc:
            print(f"   [通知] 发送推荐通知失败：{exc}")
