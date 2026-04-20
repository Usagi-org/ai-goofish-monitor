"""
卖家活跃时间服务
解析和格式化卖家的活跃时间信息
"""
from datetime import datetime
from typing import Optional


def format_active_time(last_active_time: Optional[str]) -> str:
    """
    格式化卖家最后活跃时间
    
    Args:
        last_active_time: ISO 格式的时间字符串或其他格式
        
    Returns:
        格式化后的活跃时间文本
    """
    if not last_active_time:
        return "未知"
    
    try:
        # 尝试解析 ISO 格式时间
        if "T" in last_active_time:
            active_dt = datetime.fromisoformat(last_active_time.replace("Z", "+00:00"))
        else:
            # 尝试解析其他常见格式
            active_dt = datetime.strptime(last_active_time, "%Y-%m-%d %H:%M:%S")
        
        # 计算与当前时间的差值
        now = datetime.now(active_dt.tzinfo) if active_dt.tzinfo else datetime.now()
        diff = now - active_dt
        
        # 格式化时间差
        if diff.total_seconds() < 60:
            return "刚刚在线"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}分钟前"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}小时前"
        elif diff.days < 7:
            return f"{diff.days}天前"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks}周前"
        else:
            # 超过一个月，返回具体日期
            return active_dt.strftime("%Y-%m-%d")
    
    except (ValueError, TypeError, AttributeError):
        # 解析失败，返回原始值或"未知"
        return last_active_time if last_active_time else "未知"


def is_seller_recently_active(
    last_active_time: Optional[str],
    within_hours: int = 24
) -> bool:
    """
    判断卖家是否在指定时间内活跃
    
    Args:
        last_active_time: 最后活跃时间
        within_hours: 多少小时内算活跃
        
    Returns:
        是否活跃
    """
    if not last_active_time:
        return False
    
    try:
        # 尝试解析 ISO 格式时间
        if "T" in last_active_time:
            active_dt = datetime.fromisoformat(last_active_time.replace("Z", "+00:00"))
        else:
            active_dt = datetime.strptime(last_active_time, "%Y-%m-%d %H:%M:%S")
        
        now = datetime.now(active_dt.tzinfo) if active_dt.tzinfo else datetime.now()
        diff = now - active_dt
        
        return diff.total_seconds() < (within_hours * 3600)
    
    except (ValueError, TypeError, AttributeError):
        return False


def get_active_level(last_active_time: Optional[str]) -> str:
    """
    根据活跃时间判断卖家活跃等级
    
    Args:
        last_active_time: 最后活跃时间
        
    Returns:
        活跃等级：非常活跃/活跃/一般/不活跃/未知
    """
    if not last_active_time:
        return "未知"
    
    try:
        if is_seller_recently_active(last_active_time, within_hours=1):
            return "非常活跃"
        elif is_seller_recently_active(last_active_time, within_hours=24):
            return "活跃"
        elif is_seller_recently_active(last_active_time, within_hours=72):
            return "一般"
        else:
            return "不活跃"
    except Exception:
        return "未知"
