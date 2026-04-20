"""
AI 功能开关服务
负责 AI 功能的启用/禁用状态管理
"""
from datetime import datetime
from typing import Optional
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


# 全局缓存的 AI 开关状态
_ai_enabled_cache: Optional[bool] = None


class AiToggleService:
    """AI 功能开关服务"""

    def get_ai_enabled(self) -> bool:
        """获取 AI 功能开关状态"""
        global _ai_enabled_cache

        # 如果缓存中有值，直接返回
        if _ai_enabled_cache is not None:
            return _ai_enabled_cache

        # 从数据库读取
        with sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'ai_enabled'",
            )
            row = cursor.fetchone()

            if row is None:
                # 如果数据库中没有记录，返回默认值 True
                return True

            # 解析数据库值
            value = row[0]
            _ai_enabled_cache = str(value).lower() in ("true", "1", "yes", "y", "on")
            return _ai_enabled_cache

    def set_ai_enabled(self, enabled: bool) -> None:
        """设置 AI 功能开关状态"""
        global _ai_enabled_cache

        with sqlite_connection() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES ('ai_enabled', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                ("true" if enabled else "false", datetime.now().isoformat()),
            )
            conn.commit()

        # 更新缓存
        _ai_enabled_cache = enabled

    def refresh_cache(self) -> bool:
        """刷新缓存（从数据库重新读取）"""
        global _ai_enabled_cache
        _ai_enabled_cache = None
        return self.get_ai_enabled()


# 全局服务实例
_ai_toggle_service: Optional[AiToggleService] = None


def get_ai_toggle_service() -> AiToggleService:
    """获取 AI 开关服务实例"""
    global _ai_toggle_service
    if _ai_toggle_service is None:
        _ai_toggle_service = AiToggleService()
    return _ai_toggle_service


def is_ai_enabled() -> bool:
    """便捷函数：检查 AI 功能是否启用"""
    return get_ai_toggle_service().get_ai_enabled()
