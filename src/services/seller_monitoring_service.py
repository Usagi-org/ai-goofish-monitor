"""
卖家监控服务
负责卖家维度的监控、黑名单/白名单管理
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


class SellerMonitoringService:
    """卖家监控服务"""

    def save_seller_info(self, seller_info: Dict) -> None:
        """保存或更新卖家信息"""
        with sqlite_connection() as conn:
            seller_id = seller_info.get("seller_id")
            if not seller_id:
                return

            conn.execute(
                """
                INSERT OR REPLACE INTO seller_info (
                    seller_id, seller_nickname, seller_avatar, zhima_credit,
                    registration_days, good_rate, total_items, total_ratings,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seller_id,
                    seller_info.get("seller_nickname"),
                    seller_info.get("seller_avatar"),
                    seller_info.get("zhima_credit"),
                    seller_info.get("registration_days"),
                    seller_info.get("good_rate"),
                    seller_info.get("total_items"),
                    seller_info.get("total_ratings"),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def get_seller_info(self, seller_id: str) -> Optional[Dict]:
        """获取卖家信息"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT seller_id, seller_nickname, seller_avatar, zhima_credit,
                       registration_days, good_rate, total_items, total_ratings,
                       last_updated
                FROM seller_info
                WHERE seller_id = ?
                """,
                (seller_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def add_to_blacklist(
        self, seller_id: str, reason: str = "", expires_at: Optional[str] = None
    ) -> None:
        """将卖家添加到黑名单"""
        with sqlite_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO seller_list (
                    seller_id, list_type, reason, created_at, expires_at
                ) VALUES (?, 'blacklist', ?, ?, ?)
                """,
                (seller_id, reason, datetime.now().isoformat(), expires_at),
            )
            conn.commit()

    def add_to_whitelist(
        self, seller_id: str, reason: str = "", expires_at: Optional[str] = None
    ) -> None:
        """将卖家添加到白名单"""
        with sqlite_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO seller_list (
                    seller_id, list_type, reason, created_at, expires_at
                ) VALUES (?, 'whitelist', ?, ?, ?)
                """,
                (seller_id, reason, datetime.now().isoformat(), expires_at),
            )
            conn.commit()

    def remove_from_list(self, seller_id: str) -> None:
        """从黑名单/白名单中移除卖家"""
        with sqlite_connection() as conn:
            conn.execute(
                "DELETE FROM seller_list WHERE seller_id = ?", (seller_id,)
            )
            conn.commit()

    def is_blacklisted(self, seller_id: str) -> bool:
        """检查卖家是否在黑名单中"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT expires_at FROM seller_list
                WHERE seller_id = ? AND list_type = 'blacklist'
                """,
                (seller_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            expires_at = row["expires_at"]
            if expires_at:
                try:
                    expire_time = datetime.fromisoformat(expires_at)
                    if datetime.now() > expire_time:
                        # 已过期，自动移除
                        self.remove_from_list(seller_id)
                        return False
                except (ValueError, TypeError):
                    pass
            return True

    def is_whitelisted(self, seller_id: str) -> bool:
        """检查卖家是否在白名单中"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT expires_at FROM seller_list
                WHERE seller_id = ? AND list_type = 'whitelist'
                """,
                (seller_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            expires_at = row["expires_at"]
            if expires_at:
                try:
                    expire_time = datetime.fromisoformat(expires_at)
                    if datetime.now() > expire_time:
                        # 已过期，自动移除
                        self.remove_from_list(seller_id)
                        return False
                except (ValueError, TypeError):
                    pass
            return True

    def get_blacklist(self) -> List[Dict]:
        """获取黑名单列表"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT seller_id, reason, created_at, expires_at
                FROM seller_list
                WHERE list_type = 'blacklist'
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_whitelist(self) -> List[Dict]:
        """获取白名单列表"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT seller_id, reason, created_at, expires_at
                FROM seller_list
                WHERE list_type = 'whitelist'
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_search_history(
        self, search_value: str, result_json: Optional[Dict] = None
    ) -> None:
        """保存商品 ID 搜索历史"""
        with sqlite_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_history (
                    search_type, search_value, result_json, searched_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "item_id",
                    search_value,
                    json.dumps(result_json) if result_json else None,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def get_search_history(
        self, limit: int = 20
    ) -> List[Dict]:
        """获取搜索历史"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT search_type, search_value, result_json, searched_at
                FROM search_history
                WHERE search_type = 'item_id'
                ORDER BY searched_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                if item.get("result_json"):
                    try:
                        item["result"] = json.loads(item["result_json"])
                    except (json.JSONDecodeError, TypeError):
                        item["result"] = None
                else:
                    item["result"] = None
                del item["result_json"]
                result.append(item)
            return result


# 全局服务实例
_seller_service: Optional[SellerMonitoringService] = None


def get_seller_service() -> SellerMonitoringService:
    """获取卖家监控服务实例"""
    global _seller_service
    if _seller_service is None:
        _seller_service = SellerMonitoringService()
    return _seller_service
