from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import dotenv_values


DEFAULT_EXPECT_MIN_ITEMS = 1
DEFAULT_LIVE_DEBUG_LIMIT = 1
DEFAULT_LIVE_KEYWORD = "MacBook Pro M2"
DEFAULT_LIVE_TIMEOUT_SECONDS = 180
HEALTH_TIMEOUT_SECONDS = 60
NOTIFICATION_ENV_KEYS = (
    "NTFY_TOPIC_URL",
    "GOTIFY_URL",
    "GOTIFY_TOKEN",
    "BARK_URL",
    "WX_BOT_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "WEBHOOK_URL",
    "WEBHOOK_METHOD",
    "WEBHOOK_HEADERS",
    "WEBHOOK_CONTENT_TYPE",
    "WEBHOOK_QUERY_PARAMETERS",
    "WEBHOOK_BODY",
)


@dataclass(frozen=True)
class LiveTestSettings:
    repo_root: Path
    keyword: str
    task_name: str
    expect_min_items: int
    debug_limit: int
    timeout_seconds: int
    enable_task_generation: bool
    account_source_path: Path
    ai_test_payload: dict[str, str]


@dataclass(frozen=True)
class LiveServer:
    base_url: str
    workspace: Path
    server_log_path: Path
    account_state_file: Path
    settings: LiveTestSettings


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def load_runtime_env(repo_root: Path) -> dict[str, str]:
    runtime_env = os.environ.copy()
    env_file = repo_root / ".env"
    if not env_file.exists():
        return runtime_env
    file_values = {
        key: value
        for key, value in dotenv_values(env_file, encoding="utf-8").items()
        if key and value is not None
    }
    file_values.update(runtime_env)
    return file_values


def build_ai_test_payload(runtime_env: dict[str, str]) -> dict[str, str]:
    payload = {
        "OPENAI_BASE_URL": runtime_env.get("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": runtime_env.get("OPENAI_MODEL_NAME", ""),
    }
    api_key = runtime_env.get("OPENAI_API_KEY")
    if api_key:
        payload["OPENAI_API_KEY"] = api_key
    proxy_url = runtime_env.get("PROXY_URL")
    if proxy_url:
        payload["PROXY_URL"] = proxy_url
    return payload


def resolve_account_source(repo_root: Path) -> Path:
    configured = os.getenv("LIVE_TEST_ACCOUNT_STATE_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    state_dir = repo_root / "state"
    candidates = sorted(state_dir.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(
            "LIVE_TEST_ACCOUNT_STATE_FILE 未设置，且 state/ 下没有可用 JSON 登录态文件。"
        )
    return candidates[0]


def load_live_settings(repo_root: Path) -> LiveTestSettings:
    runtime_env = load_runtime_env(repo_root)
    return LiveTestSettings(
        repo_root=repo_root,
        keyword=os.getenv("LIVE_TEST_KEYWORD", DEFAULT_LIVE_KEYWORD).strip(),
        task_name=(os.getenv("LIVE_TEST_TASK_NAME", "Live Smoke Task").strip() or "Live Smoke Task"),
        expect_min_items=env_int("LIVE_EXPECT_MIN_ITEMS", DEFAULT_EXPECT_MIN_ITEMS),
        debug_limit=env_int("LIVE_TEST_DEBUG_LIMIT", DEFAULT_LIVE_DEBUG_LIMIT),
        timeout_seconds=env_int("LIVE_TIMEOUT_SECONDS", DEFAULT_LIVE_TIMEOUT_SECONDS),
        enable_task_generation=env_flag("LIVE_ENABLE_TASK_GENERATION"),
        account_source_path=resolve_account_source(repo_root),
        ai_test_payload=build_ai_test_payload(runtime_env),
    )


def mirror_path(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        return
    try:
        destination.symlink_to(source, target_is_directory=source.is_dir())
    except OSError:
        if source.is_dir():
            shutil.copytree(source, destination)
            return
        shutil.copy2(source, destination)


def prepare_workspace(workspace: Path, settings: LiveTestSettings) -> Path:
    for name in ("src", "spider_v2.py", "static", "dist"):
        mirror_path(settings.repo_root / name, workspace / name)
    shutil.copytree(settings.repo_root / "prompts", workspace / "prompts", dirs_exist_ok=True)
    state_dir = workspace / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    account_target = state_dir / settings.account_source_path.name
    shutil.copy2(settings.account_source_path, account_target)
    for name in ("logs", "images", "data"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    return account_target


def build_server_env(workspace: Path, repo_root: Path, port: int) -> dict[str, str]:
    env = load_runtime_env(repo_root)
    python_path_parts = [str(repo_root)]
    if env.get("PYTHONPATH"):
        python_path_parts.append(env["PYTHONPATH"])
    debug_limit = str(os.getenv("LIVE_TEST_DEBUG_LIMIT", DEFAULT_LIVE_DEBUG_LIMIT)).strip()
    env.update(
        {
            "APP_DATABASE_FILE": str(workspace / "data" / "live.sqlite3"),
            "ACCOUNT_STATE_DIR": str(workspace / "state"),
            "RUN_HEADLESS": "true",
            "SKIP_AI_ANALYSIS": "false",
            "AI_DEBUG_MODE": "true",
            "PYTHONUNBUFFERED": "1",
            "SERVER_PORT": str(port),
            "SPIDER_DEBUG_LIMIT": debug_limit,
            "PYTHONPATH": os.pathsep.join(python_path_parts),
        }
    )
    for key in NOTIFICATION_ENV_KEYS:
        env[key] = ""
    return env


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def wait_for_server_ready(base_url: str, process: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    last_error = "unknown"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                return
            last_error = f"health status={response.status_code} body={response.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(1)

    log_excerpt = ""
    if log_path.exists():
        log_excerpt = log_path.read_text(encoding="utf-8", errors="ignore")[-4000:]
    raise RuntimeError(
        "Live app 未在预期时间内启动。"
        f" last_error={last_error}\nserver_log={log_path}\n{log_excerpt}"
    )


def terminate_process(process: subprocess.Popen, timeout_seconds: int = 20) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
