import asyncio
import json
import math
import os
import random
import re
import glob
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from openai import APIStatusError
from requests.exceptions import HTTPError


def retry_on_failure(retries=3, delay=5):
    """
    一个通用的异步重试装饰器，增加了对HTTP错误的详细日志记录。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except (APIStatusError, HTTPError) as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败，发生HTTP错误。")
                    if hasattr(e, 'status_code'):
                        print(f"  - 状态码 (Status Code): {e.status_code}")
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        response_text = e.response.text
                        print(
                            f"  - 返回值 (Response): {response_text[:300]}{'...' if len(response_text) > 300 else ''}")
                except json.JSONDecodeError as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败: JSON解析错误 - {e}")
                except Exception as e:
                    print(f"函数 {func.__name__} 第 {i + 1}/{retries} 次尝试失败: {type(e).__name__} - {e}")

                if i < retries - 1:
                    print(f"将在 {delay} 秒后重试...")
                    await asyncio.sleep(delay)

            print(f"函数 {func.__name__} 在 {retries} 次尝试后彻底失败。")
            return None
        return wrapper
    return decorator


async def safe_get(data, *keys, default="暂无"):
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


async def random_sleep(min_seconds: float, max_seconds: float):
    """异步等待一个在指定范围内的随机时间。"""
    delay = random.uniform(min_seconds, max_seconds)
    print(f"   [延迟] 等待 {delay:.2f} 秒... (范围: {min_seconds}-{max_seconds}s)")
    await asyncio.sleep(delay)


def log_time(message: str, prefix: str = "") -> None:
    """在日志前加上 YY-MM-DD HH:MM:SS 时间戳的简单打印。"""
    try:
        ts = datetime.now().strftime(' %Y-%m-%d %H:%M:%S')
    except Exception:
        ts = "--:--:--"
    print(f"[{ts}] {prefix}{message}")


def sanitize_filename(value: str) -> str:
    """生成安全的文件名片段。"""
    if not value:
        return "task"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "task"


def build_task_log_path(task_id: int, task_name: str) -> str:
    """生成任务日志路径（包含任务名）。"""
    safe_name = sanitize_filename(task_name)
    filename = f"{safe_name}_{task_id}.log"
    return os.path.join("logs", filename)


def resolve_task_log_path(task_id: int, task_name: str) -> str:
    """优先使用任务名生成日志路径，不存在时回退为按 ID 匹配。"""
    primary_path = build_task_log_path(task_id, task_name)
    if os.path.exists(primary_path):
        return primary_path
    pattern = os.path.join("logs", f"*_{task_id}.log")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return primary_path


def convert_goofish_link(url: str) -> str:
    """
    将Goofish商品链接转换为只包含商品ID的手机端格式。
    """
    match_first_link = re.search(r'item\?id=(\d+)', url)
    if match_first_link:
        item_id = match_first_link.group(1)
        bfp_json = f'{{"id":{item_id}}}'
        return f"https://pages.goofish.com/sharexy?loadingVisible=false&bft=item&bfs=idlepc.item&spm=a21ybx.item.0.0&bfp={quote(bfp_json)}"
    return url


def get_link_unique_key(link: str) -> str:
    """截取链接中第一个"&"之前的内容作为唯一标识依据。"""
    return link.split('&', 1)[0]


async def save_to_jsonl(data_record: dict, keyword: str):
    """将一个包含商品和卖家信息的完整记录追加保存到 .jsonl 文件。"""
    output_dir = "jsonl"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{keyword.replace(' ', '_')}_full_data.jsonl")
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(data_record, ensure_ascii=False) + "\n")
        return True
    except IOError as e:
        print(f"写入文件 {filename} 出错: {e}")
        return False


def format_registration_days(total_days: int) -> str:
    """
    将总天数格式化为“X年Y个月”的字符串。
    """
    if not isinstance(total_days, int) or total_days <= 0:
        return '未知'

    DAYS_IN_YEAR = 365.25
    DAYS_IN_MONTH = DAYS_IN_YEAR / 12

    years = math.floor(total_days / DAYS_IN_YEAR)
    remaining_days = total_days - (years * DAYS_IN_YEAR)
    months = round(remaining_days / DAYS_IN_MONTH)

    if months == 12:
        years += 1
        months = 0

    if years > 0 and months > 0:
        return f"来闲鱼{years}年{months}个月"
    elif years > 0 and months == 0:
        return f"来闲鱼{years}年整"
    elif years == 0 and months > 0:
        return f"来闲鱼{months}个月"
    else:
        return "来闲鱼不足一个月"
