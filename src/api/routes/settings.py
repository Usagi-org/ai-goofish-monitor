"""
设置管理路由
"""
import os
from typing import Optional, Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_process_service
from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import (
    AISettings,
    reload_settings,
    scraper_settings,
)
from src.services.ai_request_compat import (
    CHAT_COMPLETIONS_API_MODE,
    RESPONSES_API_MODE,
    build_ai_request_params,
    create_ai_response_sync,
    is_chat_completions_api_unsupported_error,
    is_responses_api_unsupported_error,
    is_json_output_unsupported_error,
    next_output_format,
)
from src.services.ai_response_parser import extract_ai_response_content, parse_ai_response_json
from src.services.ai_model_service import ModelListError, list_provider_models
from src.services.notification_config_service import (
    NotificationSettingsValidationError,
    build_configured_channels,
    build_notification_settings_response,
    build_notification_status_flags,
    load_notification_settings,
    model_dump,
    prepare_notification_test_settings,
    prepare_notification_settings_update,
)
from src.services.notification_service import build_notification_service
from src.services.process_service import ProcessService


router = APIRouter(prefix="/api/settings", tags=["settings"])
AI_TEST_PROMPT = 'Return only this JSON object: {"ok": true}. Do not include explanations.'
AI_TEST_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean", "enum": [True]}}, "required": ["ok"], "additionalProperties": False}


def _reload_env() -> None:
    load_dotenv(dotenv_path=env_manager.env_file, override=True)
    reload_settings()


def _env_bool(key: str, default: bool = False) -> bool:
    value = env_manager.get_value(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    value = env_manager.get_value(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_bool_value(value: bool) -> str:
    return "true" if value else "false"


class NotificationSettingsModel(BaseModel):
    """通知设置模型"""

    NTFY_TOPIC_URL: Optional[str] = None
    PUSHPLUS_TOKEN: Optional[str] = None
    PUSHPLUS_TOPIC: Optional[str] = None
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    BARK_URL: Optional[str] = None
    WX_BOT_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_API_BASE_URL: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_METHOD: Optional[str] = None
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = None
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    PCURL_TO_MOBILE: Optional[bool] = None


class NotificationTestRequest(BaseModel):
    """通知测试请求"""

    channel: Optional[str] = None
    settings: NotificationSettingsModel = Field(default_factory=NotificationSettingsModel)


class AISettingsModel(BaseModel):
    """AI设置模型"""

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL_NAME: Optional[str] = None
    SKIP_AI_ANALYSIS: Optional[bool] = None
    AI_OUTPUT_FORMAT: Optional[Literal["none", "json_object", "json_schema"]] = None
    AI_MAX_OUTPUT_TOKENS: Optional[int] = Field(default=None, ge=512, le=65536)
    PROXY_URL: Optional[str] = None


class RotationSettingsModel(BaseModel):
    ACCOUNT_ROTATION_ENABLED: Optional[bool] = None
    ACCOUNT_ROTATION_MODE: Optional[str] = None
    ACCOUNT_ROTATION_RETRY_LIMIT: Optional[int] = None
    ACCOUNT_BLACKLIST_TTL: Optional[int] = None
    ACCOUNT_STATE_DIR: Optional[str] = None
    PROXY_ROTATION_ENABLED: Optional[bool] = None
    PROXY_ROTATION_MODE: Optional[str] = None
    PROXY_POOL: Optional[str] = None
    PROXY_ROTATION_RETRY_LIMIT: Optional[int] = None
    PROXY_BLACKLIST_TTL: Optional[int] = None


class AIModelsRequest(BaseModel):
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    PROXY_URL: Optional[str] = None


def _url_origin(raw_url: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(raw_url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return (parsed.scheme.lower(), parsed.hostname.lower(), port)


def _can_reuse_saved_api_key(submitted_base_url: Optional[str], saved_base_url: str) -> bool:
    if submitted_base_url is None or not submitted_base_url.strip():
        return True
    submitted_origin = _url_origin(submitted_base_url)
    return submitted_origin is not None and submitted_origin == _url_origin(saved_base_url)


@router.post('/ai/models')
def get_ai_models(payload: AIModelsRequest):
    """Read models using draft credentials; never persist them or change the model."""
    saved_base_url = env_manager.get_value('OPENAI_BASE_URL', '')
    saved_api_key = env_manager.get_value('OPENAI_API_KEY', '')
    base_url = payload.OPENAI_BASE_URL if payload.OPENAI_BASE_URL is not None else saved_base_url
    submitted_key = (payload.OPENAI_API_KEY or '').strip()
    can_reuse = (payload.OPENAI_BASE_URL is None) or (
        _url_origin(base_url) is not None and _url_origin(base_url) == _url_origin(saved_base_url)
    )
    api_key = submitted_key or (saved_api_key if can_reuse else '')
    proxy_url = payload.PROXY_URL if payload.PROXY_URL is not None else env_manager.get_value('PROXY_URL', '')
    try:
        models = list_provider_models(base_url, api_key, proxy_url)
        return {'success': True, 'models': models}
    except ValueError as error:
        # A provider's 401 is not an expired application login session.
        message = str(error) if isinstance(error, ModelListError) else '接口地址无效，请检查 API Base URL。'
        return {'success': False, 'models': [], 'message': message}


@router.get("/notifications")
async def get_notification_settings():
    return build_notification_settings_response(load_notification_settings())


@router.put("/notifications")
async def update_notification_settings(settings: NotificationSettingsModel):
    try:
        updates, deletions, merged_settings = prepare_notification_settings_update(
            model_dump(settings, exclude_unset=True),
            load_notification_settings(),
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    success = env_manager.apply_changes(updates=updates, deletions=deletions)
    if not success:
        raise HTTPException(status_code=500, detail="更新通知设置失败")

    _reload_env()
    return {
        "message": "通知设置已成功更新",
        "configured_channels": build_configured_channels(merged_settings),
    }


@router.post("/notifications/test")
async def test_notification_settings(payload: NotificationTestRequest):
    try:
        merged_settings = prepare_notification_test_settings(
            model_dump(payload.settings, exclude_unset=True),
            load_notification_settings(),
            channel=payload.channel,
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    service = build_notification_service(merged_settings)
    if not service.clients:
        if payload.channel:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        raise HTTPException(status_code=422, detail="请至少配置一个可用的通知渠道")

    results = await service.send_test_notification()
    if payload.channel:
        if payload.channel not in results:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        results = {payload.channel: results[payload.channel]}

    return {
        "message": "测试通知已执行",
        "results": results,
    }


@router.get("/rotation")
async def get_rotation_settings():
    return {
        "ACCOUNT_ROTATION_ENABLED": _env_bool("ACCOUNT_ROTATION_ENABLED", False),
        "ACCOUNT_ROTATION_MODE": env_manager.get_value("ACCOUNT_ROTATION_MODE", "per_task"),
        "ACCOUNT_ROTATION_RETRY_LIMIT": _env_int("ACCOUNT_ROTATION_RETRY_LIMIT", 2),
        "ACCOUNT_BLACKLIST_TTL": _env_int("ACCOUNT_BLACKLIST_TTL", 300),
        "ACCOUNT_STATE_DIR": env_manager.get_value("ACCOUNT_STATE_DIR", "state"),
        "PROXY_ROTATION_ENABLED": _env_bool("PROXY_ROTATION_ENABLED", False),
        "PROXY_ROTATION_MODE": env_manager.get_value("PROXY_ROTATION_MODE", "per_task"),
        "PROXY_POOL": env_manager.get_value("PROXY_POOL", ""),
        "PROXY_ROTATION_RETRY_LIMIT": _env_int("PROXY_ROTATION_RETRY_LIMIT", 2),
        "PROXY_BLACKLIST_TTL": _env_int("PROXY_BLACKLIST_TTL", 300),
    }


@router.put("/rotation")
async def update_rotation_settings(settings: RotationSettingsModel):
    updates = {}
    payload = model_dump(settings, exclude_unset=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新轮换设置失败")
    _reload_env()
    return {"message": "轮换设置已成功更新"}


@router.get("/status")
async def get_system_status(
    process_service: ProcessService = Depends(get_process_service),
):
    state_file = "xianyu_state.json"
    login_state_exists = os.path.exists(state_file)
    env_file_exists = os.path.exists(env_manager.env_file)
    openai_api_key = env_manager.get_value("OPENAI_API_KEY", "")
    openai_base_url = env_manager.get_value("OPENAI_BASE_URL", "")
    openai_model_name = env_manager.get_value("OPENAI_MODEL_NAME", "")
    ai_settings = AISettings()
    notification_settings = load_notification_settings()
    running_task_ids = [
        task_id
        for task_id, process in process_service.processes.items()
        if process and process.returncode is None
    ]

    return {
        "ai_configured": ai_settings.is_configured(),
        "notification_configured": notification_settings.has_any_notification_enabled(),
        "headless_mode": scraper_settings.run_headless,
        "running_in_docker": scraper_settings.running_in_docker,
        "scraper_running": len(running_task_ids) > 0,
        "running_task_ids": running_task_ids,
        "login_state_file": {
            "exists": login_state_exists,
            "path": state_file,
        },
        "env_file": {
            "exists": env_file_exists,
            "openai_api_key_set": bool(openai_api_key),
            "openai_base_url_set": bool(openai_base_url),
            "openai_model_name_set": bool(openai_model_name),
            **build_notification_status_flags(notification_settings),
        },
        "configured_notification_channels": build_configured_channels(notification_settings),
    }


@router.get("/ai")
async def get_ai_settings():
    return {
        "OPENAI_BASE_URL": env_manager.get_value("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": env_manager.get_value("OPENAI_MODEL_NAME", ""),
        "AI_OUTPUT_FORMAT": env_manager.get_value("AI_OUTPUT_FORMAT", "json_object") if _env_bool("ENABLE_RESPONSE_FORMAT", True) else "none",
        "AI_MAX_OUTPUT_TOKENS": _env_int("AI_MAX_OUTPUT_TOKENS", 16384),
        "SKIP_AI_ANALYSIS": env_manager.get_value("SKIP_AI_ANALYSIS", "false").lower() == "true",
        "PROXY_URL": env_manager.get_value("PROXY_URL", ""),
    }


@router.put("/ai")
async def update_ai_settings(settings: AISettingsModel):
    updates = {}
    if settings.OPENAI_API_KEY is not None:
        updates["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if settings.OPENAI_BASE_URL is not None:
        updates["OPENAI_BASE_URL"] = settings.OPENAI_BASE_URL
    if settings.OPENAI_MODEL_NAME is not None:
        updates["OPENAI_MODEL_NAME"] = settings.OPENAI_MODEL_NAME
    if settings.SKIP_AI_ANALYSIS is not None:
        updates["SKIP_AI_ANALYSIS"] = str(settings.SKIP_AI_ANALYSIS).lower()
    if settings.PROXY_URL is not None:
        updates["PROXY_URL"] = settings.PROXY_URL

    if settings.AI_OUTPUT_FORMAT is not None:
        updates["AI_OUTPUT_FORMAT"] = settings.AI_OUTPUT_FORMAT
        updates["ENABLE_RESPONSE_FORMAT"] = str(settings.AI_OUTPUT_FORMAT != "none").lower()
    if settings.AI_MAX_OUTPUT_TOKENS is not None:
        updates["AI_MAX_OUTPUT_TOKENS"] = str(settings.AI_MAX_OUTPUT_TOKENS)
    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新AI设置失败")
    _reload_env()
    return {"message": "AI设置已成功更新"}


@router.post("/ai/test")
def test_ai_settings(settings: dict):
    """测试所选输出格式；使用线程池，避免阻塞任务和 WebSocket。"""
    client = None
    try:
        from openai import OpenAI
        import httpx

        validated = AISettingsModel(**settings)
        saved_base_url = env_manager.get_value("OPENAI_BASE_URL", "")
        saved_api_key = env_manager.get_value("OPENAI_API_KEY", "")
        submitted_base_url = (validated.OPENAI_BASE_URL or "").strip()
        base_url = submitted_base_url or saved_base_url
        submitted_key = (validated.OPENAI_API_KEY or "").strip()
        can_reuse = _can_reuse_saved_api_key(submitted_base_url, saved_base_url)
        api_key = submitted_key or (saved_api_key if can_reuse else "")
        if not api_key:
            if submitted_base_url and not can_reuse and saved_api_key:
                raise ValueError("更换 API Base URL 后请填写对应的 API Key 再测试连接。")
            raise ValueError("请先配置 API Key。")
        client_params = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": httpx.Timeout(120.0),
            "max_retries": 0,
        }
        proxy_url = validated.PROXY_URL or env_manager.get_value("PROXY_URL", "")
        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)
        model_name = validated.OPENAI_MODEL_NAME or env_manager.get_value("OPENAI_MODEL_NAME", "")
        selected_format = validated.AI_OUTPUT_FORMAT or env_manager.get_value("AI_OUTPUT_FORMAT", "json_object")
        output_format = selected_format
        budget = validated.AI_MAX_OUTPUT_TOKENS or _env_int("AI_MAX_OUTPUT_TOKENS", 16384)
        client = OpenAI(**client_params)
        api_mode = CHAT_COMPLETIONS_API_MODE
        messages = [{"role": "user", "content": AI_TEST_PROMPT}]
        for attempt in range(4):
            try:
                params = build_ai_request_params(api_mode, model=model_name, messages=messages,
                    max_output_tokens=budget, enable_json_output=output_format != "none",
                    output_format=output_format, json_schema=AI_TEST_SCHEMA, schema_name="connection_test")
                response = create_ai_response_sync(client, api_mode, params)
                content = extract_ai_response_content(response)
                result = parse_ai_response_json(content)
                if result != {"ok": True} or result.get("ok") is not True:
                    raise ValueError("模型未按测试要求返回 JSON 对象。")
                suffix = "" if output_format == selected_format else f" 所选 {selected_format} 不受支持，实际回退为 {output_format}。"
                return {"success": True, "message": f"AI连接和 JSON 输出测试通过（{output_format}）。" + suffix,
                        "response": content, "output_format": output_format, "api_mode": api_mode}
            except Exception as exc:
                if attempt == 3:
                    raise
                if api_mode == CHAT_COMPLETIONS_API_MODE and is_chat_completions_api_unsupported_error(exc):
                    api_mode = RESPONSES_API_MODE
                elif output_format != "none" and is_json_output_unsupported_error(exc):
                    output_format = next_output_format(output_format)
                else:
                    raise
    except Exception as exc:
        return {"success": False, "message": f"AI模型连接测试失败: {exc}"}
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()
