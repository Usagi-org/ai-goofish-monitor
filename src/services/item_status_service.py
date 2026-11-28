from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from src.config import DETAIL_API_URL_PATTERN, RUN_HEADLESS, STATE_FILE
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.infrastructure.persistence.storage_names import build_result_filename
from src.rotation import load_state_files
from src.services.account_strategy_service import resolve_account_runtime_plan
from src.services.item_detail_parser import extract_item_detail_fields
from src.services.result_storage_service import (
    load_items_for_status_check_async,
    update_item_detail_and_status_async,
)
from src.utils import random_sleep


DetailFetcher = Callable[[dict], Awaitable[dict]]


class StatusCheckInProgressError(RuntimeError):
    """已有状态检查任务正在运行。"""


class NoAvailableStateFileError(ValueError):
    """未找到可用的闲鱼登录状态文件。"""


_STATUS_CHECK_LOCK = asyncio.Lock()

_ANTI_DETECTION_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}};
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 5});
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({state: Notification.permission}) :
        originalQuery(parameters)
);
"""


def _find_matching_task_account_config(filename: str) -> tuple[Optional[str], Optional[str]]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        row = conn.execute(
            """
            SELECT t.account_strategy, t.account_state_file
            FROM result_items r
            JOIN tasks t ON r.task_name = t.task_name
            WHERE r.result_filename = ? AND r.task_name != ''
            ORDER BY r.crawl_time DESC, r.id DESC
            LIMIT 1
            """,
            (filename,),
        ).fetchone()
        if row is not None:
            return row["account_strategy"], row["account_state_file"]

        task_rows = conn.execute(
            """
            SELECT keyword, account_strategy, account_state_file
            FROM tasks
            ORDER BY id ASC
            """
        ).fetchall()
        for task_row in task_rows:
            if build_result_filename(str(task_row["keyword"] or "")) == filename:
                return task_row["account_strategy"], task_row["account_state_file"]
    return None, None


def resolve_status_check_state_file(
    filename: str,
    *,
    state_file: str | None = None,
) -> str:
    if state_file is not None:
        cleaned = str(state_file).strip()
        if cleaned and os.path.exists(cleaned):
            return cleaned
        raise NoAvailableStateFileError(
            "未找到可用的闲鱼登录状态文件，请先在账号管理中配置登录态。"
        )

    strategy, account_state_file = _find_matching_task_account_config(filename)
    available_account_files = [
        path for path in load_state_files("state") if os.path.exists(path)
    ]
    has_root_state = os.path.exists(STATE_FILE)
    plan = resolve_account_runtime_plan(
        strategy=strategy,
        account_state_file=account_state_file,
        has_root_state_file=has_root_state,
        available_account_files=available_account_files,
    )

    ordered_candidates: list[str] = []
    if plan["forced_account"]:
        ordered_candidates.append(plan["forced_account"])
    if plan["prefer_root_state"] and has_root_state:
        ordered_candidates.append(STATE_FILE)
    if plan["use_account_pool"]:
        ordered_candidates.extend(available_account_files)
    if has_root_state:
        ordered_candidates.append(STATE_FILE)
    ordered_candidates.extend(available_account_files)

    for candidate in ordered_candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    raise NoAvailableStateFileError(
        "未找到可用的闲鱼登录状态文件，请先在账号管理中配置登录态。"
    )


async def _check_page_risk_control(page, *, timeout_ms: int = 0) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from src.scraper import RiskControlError

    for selector, marker in (
        ("div.baxia-dialog-mask", "baxia-dialog"),
        ("div.J_MIDDLEWARE_FRAME_WIDGET", "J_MIDDLEWARE_FRAME_WIDGET"),
    ):
        locator = page.locator(selector)
        if timeout_ms > 0:
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                raise RiskControlError(marker)
            except PlaywrightTimeoutError:
                continue
        elif await locator.count() > 0 and await locator.first.is_visible():
            raise RiskControlError(marker)


@asynccontextmanager
async def _open_playwright_detail_fetcher(state_file: str):
    from playwright.async_api import (
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
    from src.scraper import (
        LoginRequiredError,
        _build_context_overrides,
        _build_extra_headers,
        _clean_kwargs,
        _default_context_options,
        _is_login_url,
        _resolve_browser_channel,
        prepare_chromium_launch_args,
    )

    snapshot_data = None
    try:
        with open(state_file, "r", encoding="utf-8") as handle:
            snapshot_data = json.load(handle)
    except Exception:
        snapshot_data = None

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=RUN_HEADLESS,
            args=prepare_chromium_launch_args(),
            channel=_resolve_browser_channel(),
        )
        try:
            context_kwargs = _default_context_options()
            storage_state_arg: Any = state_file
            if isinstance(snapshot_data, dict):
                if any(
                    key in snapshot_data
                    for key in ("env", "headers", "page", "storage")
                ):
                    storage_state_arg = {"cookies": snapshot_data.get("cookies", [])}
                    context_kwargs.update(_build_context_overrides(snapshot_data))
                    extra_headers = _build_extra_headers(snapshot_data.get("headers"))
                    if extra_headers:
                        context_kwargs["extra_http_headers"] = extra_headers
                else:
                    storage_state_arg = snapshot_data

            context = await browser.new_context(
                storage_state=storage_state_arg,
                **_clean_kwargs(context_kwargs),
            )
            await context.add_init_script(_ANTI_DETECTION_INIT_SCRIPT)
            request_count = 0

            async def _fetch_detail(item: dict) -> dict:
                nonlocal request_count
                link = str(item.get("link") or "").strip()
                if not link:
                    raise ValueError("商品缺少有效链接")

                if request_count > 0:
                    await random_sleep(2.0, 4.0)
                request_count += 1

                page = await context.new_page()
                try:
                    try:
                        async with page.expect_response(
                            lambda r: DETAIL_API_URL_PATTERN in r.url,
                            timeout=20000,
                        ) as detail_info:
                            await page.goto(
                                link,
                                wait_until="domcontentloaded",
                                timeout=20000,
                            )
                    except PlaywrightTimeoutError as exc:
                        if _is_login_url(page.url):
                            raise LoginRequiredError(
                                f"页面重定向至登录页: {page.url}"
                            ) from exc
                        await _check_page_risk_control(page, timeout_ms=1000)
                        raise TimeoutError("等待商品详情接口响应超时") from exc

                    if _is_login_url(page.url):
                        raise LoginRequiredError(f"页面重定向至登录页: {page.url}")
                    await _check_page_risk_control(page)

                    detail_response = await detail_info.value
                    if not detail_response.ok:
                        raise RuntimeError(
                            f"商品详情接口返回异常状态码: {detail_response.status}"
                        )
                    return await detail_response.json()
                finally:
                    await page.close()

            yield _fetch_detail
        finally:
            await browser.close()


def _empty_check_summary() -> dict:
    return {
        "checked": 0,
        "updated": 0,
        "sold_count": 0,
        "expired_count": 0,
        "active_count": 0,
        "unknown_count": 0,
        "failed_count": 0,
        "stopped_reason": None,
        "results": [],
    }


def _is_risk_control_exception(exc: Exception) -> bool:
    return any(cls.__name__ == "RiskControlError" for cls in type(exc).__mro__)


def _is_login_required_exception(exc: Exception) -> bool:
    return any(cls.__name__ == "LoginRequiredError" for cls in type(exc).__mro__)


async def check_result_items_status(
    filename: str,
    *,
    item_ids: list[str] | None = None,
    limit: int = 10,
    state_file: str | None = None,
    detail_fetcher: DetailFetcher | None = None,
) -> dict:
    if _STATUS_CHECK_LOCK.locked():
        raise StatusCheckInProgressError("已有状态检查任务正在运行，请稍后再试")

    async with _STATUS_CHECK_LOCK:
        clamped_limit = max(1, min(20, int(limit)))
        items = await load_items_for_status_check_async(
            filename,
            item_ids=item_ids,
            limit=clamped_limit,
        )
        if item_ids is not None and not items:
            raise LookupError("未找到指定商品")
        if not items:
            return _empty_check_summary()

        resolved_state_file: Optional[str] = None
        if detail_fetcher is None:
            resolved_state_file = await asyncio.to_thread(
                resolve_status_check_state_file,
                filename,
                state_file=state_file,
            )

        summary = _empty_check_summary()

        async def _run_batch(fetcher: DetailFetcher) -> None:
            for item in items:
                item_id = str(item.get("item_id") or "")
                previous_status = str(item.get("status") or "active")
                summary["checked"] += 1

                try:
                    detail_json = await fetcher(item)
                except Exception as exc:
                    summary["failed_count"] += 1
                    summary["results"].append(
                        {
                            "item_id": item_id,
                            "previous_status": previous_status,
                            "status": previous_status,
                            "status_label": None,
                            "description_updated": False,
                            "error": str(exc),
                        }
                    )
                    if _is_risk_control_exception(exc):
                        summary["stopped_reason"] = (
                            f"触发闲鱼风控验证（{exc}），已立即停止剩余检查，请稍后再试或更新登录态。"
                        )
                        break
                    if _is_login_required_exception(exc):
                        summary["stopped_reason"] = (
                            f"闲鱼登录态已失效（{exc}），已停止检查，请先在账号管理中更新登录态。"
                        )
                        break
                    continue

                snapshot = extract_item_detail_fields(detail_json)
                if snapshot.risk_control:
                    error_reason = snapshot.error_reason or "FAIL_SYS_USER_VALIDATE"
                    summary["failed_count"] += 1
                    summary["stopped_reason"] = (
                        f"触发闲鱼风控验证（{error_reason}），已立即停止剩余检查，请稍后再试或更新登录态。"
                    )
                    summary["results"].append(
                        {
                            "item_id": item_id,
                            "previous_status": previous_status,
                            "status": previous_status,
                            "mapped_status": "unknown",
                            "status_label": None,
                            "description_updated": False,
                            "error": error_reason,
                        }
                    )
                    break

                if snapshot.login_required:
                    error_reason = snapshot.error_reason or "FAIL_SYS_SESSION_EXPIRED"
                    summary["failed_count"] += 1
                    summary["stopped_reason"] = (
                        f"闲鱼登录态已失效（{error_reason}），已停止检查，请先在账号管理中更新登录态。"
                    )
                    summary["results"].append(
                        {
                            "item_id": item_id,
                            "previous_status": previous_status,
                            "status": previous_status,
                            "mapped_status": "unknown",
                            "status_label": None,
                            "description_updated": False,
                            "error": error_reason,
                        }
                    )
                    break

                checked_at = datetime.now().isoformat()
                next_status = (
                    snapshot.mapped_status
                    if snapshot.mapped_status in {"active", "sold", "expired"}
                    else None
                )
                persisted = await update_item_detail_and_status_async(
                    filename,
                    item_id,
                    status=next_status,
                    detail_snapshot=snapshot,
                    checked_at=checked_at,
                )

                if snapshot.mapped_status == "sold":
                    summary["sold_count"] += 1
                elif snapshot.mapped_status == "expired":
                    summary["expired_count"] += 1
                elif snapshot.mapped_status == "active":
                    summary["active_count"] += 1
                else:
                    summary["unknown_count"] += 1

                if persisted and persisted["changed"]:
                    summary["updated"] += 1

                persisted_info = (persisted or {}).get("item_info") or {}
                summary["results"].append(
                    {
                        "item_id": item_id,
                        "previous_status": (
                            persisted["previous_status"] if persisted else previous_status
                        ),
                        "status": persisted["status"] if persisted else previous_status,
                        "mapped_status": snapshot.mapped_status,
                        "status_label": snapshot.status_label,
                        "description_updated": bool(
                            persisted and persisted["description_updated"]
                        ),
                        "title": persisted_info.get("商品标题"),
                        "description": persisted_info.get("商品描述"),
                        "image_urls": persisted_info.get("商品图片列表"),
                        "checked_at": persisted_info.get("状态检查时间") or checked_at,
                        "error": None,
                    }
                )

        if detail_fetcher is not None:
            await _run_batch(detail_fetcher)
        else:
            assert resolved_state_file is not None
            async with _open_playwright_detail_fetcher(resolved_state_file) as fetcher:
                await _run_batch(fetcher)

        return summary
