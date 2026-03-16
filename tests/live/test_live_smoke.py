from __future__ import annotations

import time
from pathlib import Path

import pytest
import requests

from src.infrastructure.persistence.storage_names import build_result_filename


pytestmark = pytest.mark.live

REQUEST_TIMEOUT_SECONDS = 60
TASK_POLL_INTERVAL_SECONDS = 2
FORBIDDEN_LOG_MARKERS = (
    "Login required",
    "passport.goofish.com",
    "FAIL_SYS_USER_VALIDATE",
    "AI客户端未初始化",
    "未找到可用的登录状态文件",
    "检测到登录失效/重定向",
)

def api_request(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)
    return session.request(method=method, url=url, **kwargs)

def fetch_task(session: requests.Session, base_url: str, task_id: int) -> dict:
    response = api_request(session, "get", f"{base_url}/api/tasks/{task_id}")
    assert response.status_code == 200, response.text
    return response.json()

def fetch_results_or_none(
    session: requests.Session,
    base_url: str,
    filename: str,
    *,
    limit: int = 5,
) -> dict | None:
    response = api_request(
        session,
        "get",
        f"{base_url}/api/results/{filename}",
        params={"page": 1, "limit": limit},
    )
    if response.status_code == 404:
        return None
    assert response.status_code == 200, response.text
    return response.json()

def find_task_log(workspace: Path, task_id: int) -> Path | None:
    log_dir = workspace / "logs"
    matches = sorted(log_dir.glob(f"*_{task_id}.log"))
    return matches[0] if matches else None

def read_task_log(workspace: Path, task_id: int) -> tuple[Path | None, str]:
    log_path = find_task_log(workspace, task_id)
    if log_path is None:
        return None, ""
    return log_path, log_path.read_text(encoding="utf-8", errors="ignore")

def assert_log_is_clean(log_text: str, log_path: Path | None) -> None:
    assert log_path is not None, "live 任务日志不存在。"
    for marker in FORBIDDEN_LOG_MARKERS:
        assert marker not in log_text, f"日志包含失败标记 {marker}，请检查 {log_path}"

def wait_for_task_running(
    session: requests.Session,
    base_url: str,
    task_id: int,
    timeout_seconds: int,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_task = {}
    while time.monotonic() < deadline:
        last_task = fetch_task(session, base_url, task_id)
        if last_task.get("is_running"):
            return last_task
        time.sleep(TASK_POLL_INTERVAL_SECONDS)
    pytest.fail(f"任务 {task_id} 未在预期时间内进入运行态: {last_task}")

def wait_for_task_completion(
    session: requests.Session,
    base_url: str,
    task_id: int,
    filename: str,
    expect_min_items: int,
    timeout_seconds: int,
    workspace: Path,
) -> tuple[dict, dict | None]:
    deadline = time.monotonic() + timeout_seconds
    last_task = {}
    last_results = None
    stop_sent = False
    while time.monotonic() < deadline:
        last_task = fetch_task(session, base_url, task_id)
        last_results = fetch_results_or_none(session, base_url, filename)
        if (
            last_results
            and last_results.get("total_items", 0) >= expect_min_items
            and last_task.get("is_running")
            and not stop_sent
        ):
            stop_response = api_request(session, "post", f"{base_url}/api/tasks/stop/{task_id}")
            assert stop_response.status_code == 200, stop_response.text
            stop_sent = True
        if not last_task.get("is_running"):
            return last_task, last_results
        time.sleep(TASK_POLL_INTERVAL_SECONDS)

    log_path, log_text = read_task_log(workspace, task_id)
    pytest.fail(
        f"任务 {task_id} 在 {timeout_seconds}s 内未结束。log={log_path}\n{log_text[-4000:]}"
    )

def delete_task_safely(session: requests.Session, base_url: str, task_id: int) -> None:
    response = api_request(session, "delete", f"{base_url}/api/tasks/{task_id}")
    assert response.status_code in {200, 404}, response.text

def build_live_task_payload(account_state_file: Path, task_name: str, keyword: str) -> dict:
    return {
        "task_name": task_name,
        "enabled": True,
        "keyword": keyword,
        "description": "Live smoke task for real Goofish traffic and real AI response validation.",
        "analyze_images": False,
        "max_pages": 1,
        "personal_only": True,
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": "prompts/macbook_criteria.txt",
        "account_state_file": str(account_state_file),
        "account_strategy": "fixed",
        "decision_mode": "ai",
    }

def test_live_preflight_smoke(live_server):
    with requests.Session() as session:
        health_response = api_request(session, "get", f"{live_server.base_url}/health")
        assert health_response.status_code == 200, health_response.text
        assert health_response.json()["status"] == "healthy"

        ai_response = api_request(
            session,
            "post",
            f"{live_server.base_url}/api/settings/ai/test",
            json=live_server.settings.ai_test_payload,
        )
        assert ai_response.status_code == 200, ai_response.text
        ai_result = ai_response.json()
        assert ai_result["success"] is True, ai_result
        assert live_server.account_state_file.exists()

def test_live_real_traffic_task_smoke(live_server):
    task_name = live_server.settings.task_name
    keyword = live_server.settings.keyword
    filename = build_result_filename(keyword)
    payload = build_live_task_payload(live_server.account_state_file, task_name, keyword)

    with requests.Session() as session:
        create_response = api_request(
            session,
            "post",
            f"{live_server.base_url}/api/tasks/",
            json=payload,
        )
        assert create_response.status_code == 200, create_response.text
        created_task = create_response.json()["task"]
        task_id = created_task["id"]

        try:
            start_response = api_request(
                session,
                "post",
                f"{live_server.base_url}/api/tasks/start/{task_id}",
            )
            assert start_response.status_code == 200, start_response.text

            final_task, result_data = wait_for_task_completion(
                session,
                live_server.base_url,
                task_id,
                filename,
                live_server.settings.expect_min_items,
                live_server.settings.timeout_seconds,
                live_server.workspace,
            )
            assert final_task["is_running"] is False

            files_response = api_request(session, "get", f"{live_server.base_url}/api/results/files")
            assert files_response.status_code == 200, files_response.text
            assert filename in files_response.json()["files"]

            if result_data is None:
                result_data = fetch_results_or_none(session, live_server.base_url, filename)
            assert result_data is not None, f"结果文件 {filename} 未生成。"
            assert result_data["total_items"] >= live_server.settings.expect_min_items

            item = result_data["items"][0]
            product = item.get("商品信息", {})
            analysis = item.get("ai_analysis", {})
            assert product.get("商品标题"), item
            assert product.get("商品链接"), item
            assert product.get("当前售价"), item
            assert analysis, item
            assert analysis.get("analysis_source") == "ai", item

            log_path, log_text = read_task_log(live_server.workspace, task_id)
            assert_log_is_clean(log_text, log_path)
        finally:
            delete_task_safely(session, live_server.base_url, task_id)


@pytest.mark.live_slow
def test_live_ai_task_generation_job(live_server):
    if not live_server.settings.enable_task_generation:
        pytest.skip("未设置 LIVE_ENABLE_TASK_GENERATION=1，跳过真实 AI 任务生成测试。")

    payload = {
        "task_name": f"{live_server.settings.task_name} Generated",
        "keyword": live_server.settings.keyword,
        "description": "Generate a practical second-hand inspection criteria for live smoke validation.",
        "analyze_images": False,
        "max_pages": 1,
        "personal_only": True,
        "account_state_file": str(live_server.account_state_file),
        "account_strategy": "fixed",
        "decision_mode": "ai",
    }

    with requests.Session() as session:
        response = api_request(
            session,
            "post",
            f"{live_server.base_url}/api/tasks/generate",
            json=payload,
        )
        assert response.status_code == 202, response.text
        job = response.json()["job"]
        job_id = job["job_id"]

        deadline = time.monotonic() + live_server.settings.timeout_seconds
        latest_job = job
        while time.monotonic() < deadline:
            status_response = api_request(
                session,
                "get",
                f"{live_server.base_url}/api/tasks/generate-jobs/{job_id}",
            )
            assert status_response.status_code == 200, status_response.text
            latest_job = status_response.json()["job"]
            if latest_job["status"] == "completed":
                break
            if latest_job["status"] == "failed":
                pytest.fail(f"真实 AI 任务生成失败: {latest_job}")
            time.sleep(TASK_POLL_INTERVAL_SECONDS)
        else:
            pytest.fail(f"真实 AI 任务生成超时: {latest_job}")

        task = latest_job["task"]
        assert task["ai_prompt_criteria_file"]
        task_id = task["id"]

        try:
            start_response = api_request(
                session,
                "post",
                f"{live_server.base_url}/api/tasks/start/{task_id}",
            )
            assert start_response.status_code == 200, start_response.text
            wait_for_task_running(
                session,
                live_server.base_url,
                task_id,
                timeout_seconds=min(live_server.settings.timeout_seconds, 30),
            )
            stop_response = api_request(
                session,
                "post",
                f"{live_server.base_url}/api/tasks/stop/{task_id}",
            )
            assert stop_response.status_code == 200, stop_response.text
            final_task, _ = wait_for_task_completion(
                session,
                live_server.base_url,
                task_id,
                build_result_filename(live_server.settings.keyword),
                expect_min_items=0,
                timeout_seconds=min(live_server.settings.timeout_seconds, 60),
                workspace=live_server.workspace,
            )
            assert final_task["is_running"] is False
        finally:
            delete_task_safely(session, live_server.base_url, task_id)
