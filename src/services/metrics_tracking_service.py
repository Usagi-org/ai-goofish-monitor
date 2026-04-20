"""
指标追踪服务
负责记录和追踪商品价格/想要数变化
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


class MetricsTrackingService:
    """指标追踪服务"""

    def record_metrics(
        self,
        item_id: str,
        title: str,
        price: Optional[float],
        price_display: Optional[str],
        want_count: Optional[int],
        browse_count: Optional[int],
        seller_id: Optional[str],
        link: Optional[str],
    ) -> bool:
        """
        记录商品指标快照（仅在价格或想要数变化时记录）
        Returns: True 表示实际创建了记录，False 表示跳过（数据无变化）
        """
        with sqlite_connection() as conn:
            snapshot_time = datetime.now().isoformat()

            # 检查最新一条记录，如果价格和想要数都相同，则跳过记录
            cursor = conn.execute(
                """
                SELECT price, want_count FROM item_metrics_history
                WHERE item_id = ?
                ORDER BY snapshot_time DESC LIMIT 1
                """,
                (item_id,),
            )
            last_record = cursor.fetchone()
            if last_record:
                last_price = last_record["price"]
                last_want_count = last_record["want_count"]

                # 如果价格和想要数都相同，跳过记录
                if price == last_price and want_count == last_want_count:
                    return False

            try:
                conn.execute(
                    """
                    INSERT INTO item_metrics_history (
                        item_id, title, snapshot_time, price, price_display,
                        want_count, browse_count, seller_id, link
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        title[:200],  # 限制标题长度
                        snapshot_time,
                        price,
                        price_display,
                        want_count,
                        browse_count,
                        seller_id,
                        link,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                # 忽略重复记录（UNIQUE 约束冲突）
                if "UNIQUE constraint failed" not in str(e):
                    print(f"记录指标历史失败：{e}")
                return False

    def get_price_history(
        self, item_id: str, days: int = 30
    ) -> List[Dict[str, Optional[float]]]:
        """获取价格历史"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT snapshot_time, price, price_display
                FROM item_metrics_history
                WHERE item_id = ?
                ORDER BY snapshot_time DESC
                LIMIT ?
                """,
                (item_id, days * 24 * 60),  # 假设最多每分钟一条记录
            )
            rows = cursor.fetchall()
            return [
                {
                    "time": row["snapshot_time"],
                    "price": row["price"],
                    "price_display": row["price_display"],
                }
                for row in rows
            ]

    def get_want_count_history(
        self, item_id: str, days: int = 30
    ) -> List[Dict[str, Optional[int]]]:
        """获取想要数历史"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT snapshot_time, want_count
                FROM item_metrics_history
                WHERE item_id = ?
                ORDER BY snapshot_time DESC
                LIMIT ?
                """,
                (item_id, days * 24 * 60),
            )
            rows = cursor.fetchall()
            return [
                {"time": row["snapshot_time"], "want_count": row["want_count"]}
                for row in rows
            ]

    def detect_price_change(
        self, item_id: str, threshold_percent: float = 0.0
    ) -> Optional[Dict]:
        """
        检测价格变化
        Args:
            item_id: 商品 ID
            threshold_percent: 价格变化百分比阈值（0 表示任意变化）
        Returns:
            价格变化信息，如果没有变化或未达到阈值则返回 None
        """
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT price, price_display, snapshot_time
                FROM item_metrics_history
                WHERE item_id = ? AND price IS NOT NULL
                ORDER BY snapshot_time DESC
                LIMIT 2
                """,
                (item_id,),
            )
            rows = cursor.fetchall()
            if len(rows) < 2:
                return None

            current = rows[0]
            previous = rows[1]

            current_price = current["price"]
            previous_price = previous["price"]

            if current_price == previous_price:
                return None

            change_amount = current_price - previous_price
            change_percent = (change_amount / previous_price) * 100 if previous_price else 0

            if abs(change_percent) < threshold_percent:
                return None

            return {
                "item_id": item_id,
                "current_price": current_price,
                "previous_price": previous_price,
                "change_amount": change_amount,
                "change_percent": change_percent,
                "is_price_drop": change_amount < 0,
                "current_price_display": current["price_display"],
            }

    def detect_want_count_change(
        self, item_id: str, threshold: int = 1
    ) -> Optional[Dict]:
        """
        检测想要数变化
        Args:
            item_id: 商品 ID
            threshold: 想要数变化阈值
        Returns:
            想要数变化信息，如果没有变化或未达到阈值则返回 None
        """
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT want_count, snapshot_time
                FROM item_metrics_history
                WHERE item_id = ? AND want_count IS NOT NULL
                ORDER BY snapshot_time DESC
                LIMIT 2
                """,
                (item_id,),
            )
            rows = cursor.fetchall()
            if len(rows) < 2:
                return None

            current = rows[0]
            previous = rows[1]

            current_want = current["want_count"]
            previous_want = previous["want_count"]

            change = current_want - previous_want

            if abs(change) < threshold:
                return None

            return {
                "item_id": item_id,
                "current_want_count": current_want,
                "previous_want_count": previous_want,
                "change_amount": change,
                "is_increasing": change > 0,
            }

    def get_last_snapshot(self, item_id: str) -> Optional[Dict]:
        """获取最新的指标快照"""
        with sqlite_connection() as conn:
            cursor = conn.execute(
                """
                SELECT price, price_display, want_count, browse_count, snapshot_time
                FROM item_metrics_history
                WHERE item_id = ?
                ORDER BY snapshot_time DESC
                LIMIT 1
                """,
                (item_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "price": row["price"],
                    "price_display": row["price_display"],
                    "want_count": row["want_count"],
                    "browse_count": row["browse_count"],
                    "snapshot_time": row["snapshot_time"],
                }
            return None

    def get_total_want_count_for_task(self, task_name: str) -> Optional[int]:
        """获取任务下所有商品的当前总想要数"""
        with sqlite_connection() as conn:
            # 首先获取所有相关的 item_id
            cursor = conn.execute(
                """
                SELECT DISTINCT item_id FROM (
                    SELECT item_id, MAX(snapshot_time) as latest_time
                    FROM item_metrics_history
                    WHERE item_id IN (
                        SELECT DISTINCT item_id FROM price_snapshots WHERE keyword = ?
                    )
                    GROUP BY item_id
                ) latest
                """,
                (task_name,),
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            item_ids = [row["item_id"] for row in rows]
            placeholders = ",".join("?" * len(item_ids))
            cursor = conn.execute(
                f"""
                SELECT SUM(want_count) as total
                FROM (
                    SELECT im.item_id, im.want_count
                    FROM item_metrics_history im
                    INNER JOIN (
                        SELECT item_id, MAX(snapshot_time) as max_time
                        FROM item_metrics_history
                        WHERE item_id IN ({placeholders})
                        GROUP BY item_id
                    ) latest ON im.item_id = latest.item_id AND im.snapshot_time = latest.max_time
                )
                """,
                tuple(item_ids),
            )
            row = cursor.fetchone()
            return row["total"] if row else None

    def get_price_diff_for_task(self, task_name: str, since: Optional[str] = None) -> Optional[float]:
        """获取任务下所有商品的价格变化（本次 - 上次，只在本次有新记录时返回）

        Args:
            task_name: 任务名称
            since: 可选，只计算此时间之后创建的记录（ISO 格式）
        """
        from datetime import datetime, timedelta

        with sqlite_connection() as conn:
            # 获取所有相关的 item_id
            cursor = conn.execute(
                """
                SELECT DISTINCT item_id FROM price_snapshots WHERE keyword = ?
                """,
                (task_name,),
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            item_ids = [row["item_id"] for row in rows]
            if not item_ids:
                return None

            # 计算 5 分钟前的时间（用于判断是否是本次爬取新创建的记录）
            now = datetime.now()
            five_minutes_ago = (now - timedelta(minutes=5)).isoformat()

            # 如果提供了 since 参数，使用它作为时间下限
            time_lower_bound = since if since else five_minutes_ago

            # 计算每个商品的最新和上次价格差异
            total_diff = 0.0
            has_new_record = False  # 标记本次爬取是否有新记录
            count = 0
            for item_id in item_ids:
                # 获取最新价格和时间
                cursor = conn.execute(
                    """
                    SELECT price, snapshot_time FROM item_metrics_history
                    WHERE item_id = ? AND price IS NOT NULL
                    ORDER BY snapshot_time DESC LIMIT 1
                    """,
                    (item_id,),
                )
                current_row = cursor.fetchone()
                if not current_row:
                    continue

                current_price = current_row["price"]
                current_time = current_row["snapshot_time"]

                # 如果最新记录不是在时间下限之后创建的，说明本次爬取没有新变化
                if current_time < time_lower_bound:
                    continue

                # 标记本次爬取有新记录
                has_new_record = True

                # 获取上次价格（直接取上一条记录）
                cursor = conn.execute(
                    """
                    SELECT price FROM item_metrics_history
                    WHERE item_id = ? AND price IS NOT NULL
                    ORDER BY snapshot_time DESC LIMIT 1 OFFSET 1
                    """,
                    (item_id,),
                )
                prev_row = cursor.fetchone()
                if not prev_row or prev_row["price"] is None:
                    # 没有上次价格，使用当前价格作为基准（避免首次记录时计算错误）
                    prev_price = current_price
                else:
                    prev_price = prev_row["price"]

                total_diff += (current_price - prev_price)
                count += 1

            # 只有当本次爬取实际产生了新记录时，才返回价格差异
            if has_new_record and count > 0:
                return round(total_diff / count, 2)
            return None

    def get_want_count_diff_for_task(self, task_name: str, since: Optional[str] = None) -> Optional[int]:
        """获取任务下所有商品的想要数变化（本次 - 上次，只在本次有新记录时返回）

        Args:
            task_name: 任务名称
            since: 可选，只计算此时间之后创建的记录（ISO 格式）
        """
        from datetime import datetime, timedelta

        with sqlite_connection() as conn:
            # 获取所有相关的 item_id
            cursor = conn.execute(
                """
                SELECT DISTINCT item_id FROM price_snapshots WHERE keyword = ?
                """,
                (task_name,),
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            item_ids = [row["item_id"] for row in rows]
            if not item_ids:
                return None

            # 计算 5 分钟前的时间（用于判断是否是本次爬取新创建的记录）
            now = datetime.now()
            five_minutes_ago = (now - timedelta(minutes=5)).isoformat()

            # 如果提供了 since 参数，使用它作为时间下限
            time_lower_bound = since if since else five_minutes_ago

            # 计算每个商品的最新和上次想要数差异
            total_diff = 0
            has_new_record = False  # 标记本次爬取是否有新记录
            count = 0
            for item_id in item_ids:
                # 获取最新想要数和时间
                cursor = conn.execute(
                    """
                    SELECT want_count, snapshot_time FROM item_metrics_history
                    WHERE item_id = ? AND want_count IS NOT NULL
                    ORDER BY snapshot_time DESC LIMIT 1
                    """,
                    (item_id,),
                )
                current_row = cursor.fetchone()
                if not current_row:
                    continue

                current_want = current_row["want_count"]
                current_time = current_row["snapshot_time"]

                # 如果最新记录不是在时间下限之后创建的，说明本次爬取没有新变化
                if current_time < time_lower_bound:
                    continue

                # 标记本次爬取有新记录
                has_new_record = True

                # 获取上次想要数（直接取上一条记录）
                cursor = conn.execute(
                    """
                    SELECT want_count FROM item_metrics_history
                    WHERE item_id = ? AND want_count IS NOT NULL
                    ORDER BY snapshot_time DESC LIMIT 1 OFFSET 1
                    """,
                    (item_id,),
                )
                prev_row = cursor.fetchone()
                if not prev_row or prev_row["want_count"] is None:
                    # 没有上次想要数，使用当前值作为基准（避免首次记录时计算错误）
                    prev_want = current_want
                else:
                    prev_want = prev_row["want_count"]

                total_diff += (current_want - prev_want)
                count += 1

            # 只有当本次爬取实际产生了新记录时，才返回想要数差异
            if has_new_record and count > 0:
                return total_diff
            return None


# 全局服务实例
_metrics_service: Optional[MetricsTrackingService] = None


def get_metrics_service() -> MetricsTrackingService:
    """获取指标追踪服务实例"""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsTrackingService()
    return _metrics_service
