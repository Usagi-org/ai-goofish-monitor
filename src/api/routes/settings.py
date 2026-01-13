"""
设置管理路由
"""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import get_process_service
from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import (
    AISettings,
    notification_settings,
    reload_settings,
    scraper_settings,
)
from src.services.process_service import ProcessService


router = APIRouter(prefix="/api/settings", tags=["settings"])

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
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    BARK_URL: Optional[str] = None
    WX_BOT_URL: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_METHOD: Optional[str] = None
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = None
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    PCURL_TO_MOBILE: Optional[bool] = None


class AISettingsModel(BaseModel):
    """AI设置模型"""
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL_NAME: Optional[str] = None
    SKIP_AI_ANALYSIS: Optional[bool] = None
    PROXY_URL: Optional[str] = None


class RotationSettingsModel(BaseModel):
    PROXY_ROTATION_ENABLED: Optional[bool] = None
    PROXY_ROTATION_MODE: Optional[str] = None
    PROXY_POOL: Optional[str] = None
    PROXY_ROTATION_RETRY_LIMIT: Optional[int] = None
    PROXY_BLACKLIST_TTL: Optional[int] = None


@router.get("/notifications")
async def get_notification_settings():
    """获取通知设置"""
    return {
        "NTFY_TOPIC_URL": env_manager.get_value("NTFY_TOPIC_URL", ""),
        "GOTIFY_URL": env_manager.get_value("GOTIFY_URL", ""),
        "GOTIFY_TOKEN": env_manager.get_value("GOTIFY_TOKEN", ""),
        "BARK_URL": env_manager.get_value("BARK_URL", ""),
        "WX_BOT_URL": env_manager.get_value("WX_BOT_URL", ""),
        "TELEGRAM_BOT_TOKEN": env_manager.get_value("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": env_manager.get_value("TELEGRAM_CHAT_ID", ""),
        "WEBHOOK_URL": env_manager.get_value("WEBHOOK_URL", ""),
        "WEBHOOK_METHOD": env_manager.get_value("WEBHOOK_METHOD", "POST"),
        "WEBHOOK_HEADERS": env_manager.get_value("WEBHOOK_HEADERS", ""),
        "WEBHOOK_CONTENT_TYPE": env_manager.get_value("WEBHOOK_CONTENT_TYPE", "JSON"),
        "WEBHOOK_QUERY_PARAMETERS": env_manager.get_value("WEBHOOK_QUERY_PARAMETERS", ""),
        "WEBHOOK_BODY": env_manager.get_value("WEBHOOK_BODY", ""),
        "PCURL_TO_MOBILE": _env_bool("PCURL_TO_MOBILE", True),
    }


@router.put("/notifications")
async def update_notification_settings(
    settings: NotificationSettingsModel,
):
    """更新通知设置"""
    updates = {}
    payload = settings.dict(exclude_none=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if success:
        _reload_env()
        return {"message": "通知设置已成功更新"}
    return {"message": "更新通知设置失败"}

@router.get("/rotation")
async def get_rotation_settings():
    return {
        "PROXY_ROTATION_ENABLED": _env_bool("PROXY_ROTATION_ENABLED", False),
        "PROXY_ROTATION_MODE": env_manager.get_value("PROXY_ROTATION_MODE", "per_task"),
        "PROXY_POOL": env_manager.get_value("PROXY_POOL", ""),
        "PROXY_ROTATION_RETRY_LIMIT": _env_int("PROXY_ROTATION_RETRY_LIMIT", 2),
        "PROXY_BLACKLIST_TTL": _env_int("PROXY_BLACKLIST_TTL", 300),
    }


@router.put("/rotation")
async def update_rotation_settings(
    settings: RotationSettingsModel,
):
    updates = {}
    payload = settings.dict(exclude_none=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if success:
        _reload_env()
        return {"message": "轮换设置已成功更新"}
    return {"message": "更新轮换设置失败"}


@router.get("/status")
async def get_system_status(
    process_service: ProcessService = Depends(get_process_service),
):
    """获取系统状态"""
    state_file = "xianyu_state.json"
    login_state_exists = os.path.exists(state_file)

    # 检查 .env 文件
    env_file_exists = os.path.exists(".env")

    # 检查关键环境变量是否设置
    openai_api_key = env_manager.get_value("OPENAI_API_KEY", "")
    openai_base_url = env_manager.get_value("OPENAI_BASE_URL", "")
    openai_model_name = env_manager.get_value("OPENAI_MODEL_NAME", "")
    ntfy_topic_url = env_manager.get_value("NTFY_TOPIC_URL", "")

    ai_settings = AISettings()
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
            "path": state_file
        },
        "env_file": {
            "exists": env_file_exists,
            "openai_api_key_set": bool(openai_api_key),
            "openai_base_url_set": bool(openai_base_url),
            "openai_model_name_set": bool(openai_model_name),
            "ntfy_topic_url_set": bool(ntfy_topic_url)
        }
    }


class AISettingsModel(BaseModel):
    """AI设置模型"""
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL_NAME: Optional[str] = None
    SKIP_AI_ANALYSIS: Optional[bool] = None


@router.get("/ai")
async def get_ai_settings():
    """获取AI设置"""
    return {
        "OPENAI_BASE_URL": env_manager.get_value("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": env_manager.get_value("OPENAI_MODEL_NAME", ""),
        "SKIP_AI_ANALYSIS": env_manager.get_value("SKIP_AI_ANALYSIS", "false").lower() == "true"
    }


@router.put("/ai")
async def update_ai_settings(
    settings: AISettingsModel,
):
    """更新AI设置"""
    updates = {}
    if settings.OPENAI_API_KEY is not None:
        updates["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    if settings.OPENAI_BASE_URL is not None:
        updates["OPENAI_BASE_URL"] = settings.OPENAI_BASE_URL
    if settings.OPENAI_MODEL_NAME is not None:
        updates["OPENAI_MODEL_NAME"] = settings.OPENAI_MODEL_NAME
    if settings.SKIP_AI_ANALYSIS is not None:
        updates["SKIP_AI_ANALYSIS"] = str(settings.SKIP_AI_ANALYSIS).lower()

    success = env_manager.update_values(updates)
    if success:
        _reload_env()
        return {"message": "AI设置已成功更新"}
    return {"message": "更新AI设置失败"}


@router.post("/ai/test")
async def test_ai_settings(
    settings: dict,
):
    """测试AI模型设置是否有效"""
    try:
        from openai import OpenAI
        import httpx

        stored_api_key = env_manager.get_value("OPENAI_API_KEY", "")
        submitted_api_key = settings.get("OPENAI_API_KEY", "")
        api_key = submitted_api_key or stored_api_key

        # 创建OpenAI客户端
        client_params = {
            "api_key": api_key,
            "base_url": settings.get("OPENAI_BASE_URL", ""),
            "timeout": httpx.Timeout(30.0),
        }

        # 如果有代理设置
        proxy_url = settings.get("PROXY_URL", "")
        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)

        model_name = settings.get("OPENAI_MODEL_NAME", "")
        print(f"AI测试 - BASE_URL: {client_params['base_url']}, MODEL: {model_name}")

        client = OpenAI(**client_params)

        # 测试连接
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            max_tokens=10
        )

        return {
            "success": True,
            "message": "AI模型连接测试成功！",
            "response": response.choices[0].message.content if response.choices else "No response"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"AI模型连接测试失败: {str(e)}"
        }
