import os
import sys
from typing import Mapping, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

# --- AI & Notification Configuration ---
load_dotenv()

# --- File Paths & Directories ---
STATE_FILE = "xianyu_state.json"
IMAGE_SAVE_DIR = "images"
CONFIG_FILE = "config.json"
os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

# 任务隔离的临时图片目录前缀
TASK_IMAGE_DIR_PREFIX = "task_images_"

# --- API URL Patterns ---
API_URL_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search"
DETAIL_API_URL_PATTERN = "h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail"

# --- Environment Variables ---
GEMINI_OPENAI_COMPAT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT_MODEL_NAME = "gemini-2.0-flash"


def resolve_ai_runtime_config(env: Optional[Mapping[str, str]] = None) -> dict:
    source = env or os.environ

    openai_api_key = source.get("OPENAI_API_KEY")
    gemini_api_key = source.get("GEMINI_API_KEY")
    base_url = source.get("OPENAI_BASE_URL") or ""
    model_name = source.get("OPENAI_MODEL_NAME") or ""

    use_gemini_defaults = bool(gemini_api_key and not openai_api_key)
    resolved_base_url = base_url or (GEMINI_OPENAI_COMPAT_BASE_URL if use_gemini_defaults else "")
    resolved_model_name = model_name or (GEMINI_DEFAULT_MODEL_NAME if use_gemini_defaults else "")

    return {
        "api_key": openai_api_key or gemini_api_key,
        "base_url": resolved_base_url,
        "model_name": resolved_model_name,
        "is_gemini_openai_compat": use_gemini_defaults,
    }


_ai_runtime = resolve_ai_runtime_config()

API_KEY = _ai_runtime["api_key"]
BASE_URL = _ai_runtime["base_url"]
MODEL_NAME = _ai_runtime["model_name"]
PROXY_URL = os.getenv("PROXY_URL")
NTFY_TOPIC_URL = os.getenv("NTFY_TOPIC_URL")
GOTIFY_URL = os.getenv("GOTIFY_URL")
GOTIFY_TOKEN = os.getenv("GOTIFY_TOKEN")
BARK_URL = os.getenv("BARK_URL")
WX_BOT_URL = os.getenv("WX_BOT_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_METHOD = os.getenv("WEBHOOK_METHOD", "POST").upper()
WEBHOOK_HEADERS = os.getenv("WEBHOOK_HEADERS")
WEBHOOK_CONTENT_TYPE = os.getenv("WEBHOOK_CONTENT_TYPE", "JSON").upper()
WEBHOOK_QUERY_PARAMETERS = os.getenv("WEBHOOK_QUERY_PARAMETERS")
WEBHOOK_BODY = os.getenv("WEBHOOK_BODY")
PCURL_TO_MOBILE = os.getenv("PCURL_TO_MOBILE", "false").lower() == "true"
RUN_HEADLESS = os.getenv("RUN_HEADLESS", "true").lower() != "false"
LOGIN_IS_EDGE = os.getenv("LOGIN_IS_EDGE", "false").lower() == "true"
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"
AI_DEBUG_MODE = os.getenv("AI_DEBUG_MODE", "false").lower() == "true"
SKIP_AI_ANALYSIS = os.getenv("SKIP_AI_ANALYSIS", "false").lower() == "true"
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
ENABLE_RESPONSE_FORMAT = os.getenv("ENABLE_RESPONSE_FORMAT", "true").lower() == "true"

# Allow running without any saved login state cookies.
# This will likely be more fragile and may trigger risk-control pages more often.
ALLOW_GUEST_MODE = os.getenv("ALLOW_GUEST_MODE", "false").lower() == "true"

# --- Headers ---
IMAGE_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# --- Client Initialization ---
# 检查配置是否齐全
if not all([BASE_URL, MODEL_NAME]):
    print(
        "警告：未在 .env 文件中完整设置 OPENAI_BASE_URL 和 OPENAI_MODEL_NAME。AI相关功能可能无法使用。"
    )
    client = None
else:
    try:
        if _ai_runtime["is_gemini_openai_compat"]:
            print("检测到 GEMINI_API_KEY，已自动启用 Gemini OpenAI 兼容端点。")

        if PROXY_URL:
            print(f"正在为AI请求使用HTTP/S代理: {PROXY_URL}")
            # httpx 会自动从环境变量中读取代理设置
            os.environ["HTTP_PROXY"] = PROXY_URL
            os.environ["HTTPS_PROXY"] = PROXY_URL

        # openai 客户端内部的 httpx 会自动从环境变量中获取代理配置
        client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    except Exception as e:
        print(f"初始化 OpenAI 客户端时出错: {e}")
        client = None

# 检查AI客户端是否成功初始化
if not client:
    # 在 prompt_generator.py 中，如果 client 为 None，会直接报错退出
    # 在 spider_v2.py 中，AI分析会跳过
    # 为了保持一致性，这里只打印警告，具体逻辑由调用方处理
    pass

# 检查关键配置
if not all([BASE_URL, MODEL_NAME]) and "prompt_generator.py" in sys.argv[0]:
    sys.exit(
        "错误：请确保在 .env 文件中完整设置了 OPENAI_BASE_URL 和 OPENAI_MODEL_NAME。"
        "如果使用 Gemini API Key，可仅设置 GEMINI_API_KEY 并让系统自动填充兼容端点。"
    )


def get_ai_request_params(**kwargs):
    """
    构建AI请求参数，根据ENABLE_THINKING和ENABLE_RESPONSE_FORMAT环境变量决定是否添加相应参数
    """
    if ENABLE_THINKING:
        kwargs["extra_body"] = {"enable_thinking": False}

    # 如果禁用response_format，则移除该参数
    if not ENABLE_RESPONSE_FORMAT and "response_format" in kwargs:
        del kwargs["response_format"]

    return kwargs
