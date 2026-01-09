"""
FastAPI 依赖注入
提供服务实例的创建和管理
"""
from fastapi import Depends
from src.services.task_service import TaskService
from src.services.notification_service import NotificationService
from src.services.ai_service import AIAnalysisService
from src.services.process_service import ProcessService
from src.infrastructure.persistence.json_task_repository import JsonTaskRepository
from src.infrastructure.external.ai_client import AIClient
from src.infrastructure.external.notification_clients.ntfy_client import NtfyClient
from src.infrastructure.external.notification_clients.bark_client import BarkClient
from src.infrastructure.external.notification_clients.telegram_client import TelegramClient
from src.infrastructure.config.settings import notification_settings


# 全局 ProcessService 实例（将在 app.py 中设置）
_process_service_instance = None


def set_process_service(service: ProcessService):
    """设置全局 ProcessService 实例"""
    global _process_service_instance
    _process_service_instance = service


# 服务依赖注入
def get_task_service() -> TaskService:
    """获取任务管理服务实例"""
    repository = JsonTaskRepository()
    return TaskService(repository)


def get_notification_service() -> NotificationService:
    """获取通知服务实例"""
    clients = [
        NtfyClient(notification_settings.ntfy_topic_url),
        BarkClient(notification_settings.bark_url),
        TelegramClient(
            notification_settings.telegram_bot_token,
            notification_settings.telegram_chat_id
        )
    ]
    return NotificationService(clients)


def get_ai_service() -> AIAnalysisService:
    """获取AI分析服务实例"""
    ai_client = AIClient()
    return AIAnalysisService(ai_client)


def get_process_service() -> ProcessService:
    """获取进程管理服务实例"""
    if _process_service_instance is None:
        raise RuntimeError("ProcessService 未初始化")
    return _process_service_instance
