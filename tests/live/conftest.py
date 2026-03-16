from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.live._support import (
    LiveServer,
    build_server_env,
    find_free_port,
    load_live_settings,
    prepare_workspace,
    terminate_process,
    wait_for_server_ready,
)


LIVE_SKIP_REASON = "真实流量 live smoke 默认关闭；请显式设置 RUN_LIVE_TESTS=1。"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip_marker = pytest.mark.skip(reason=LIVE_SKIP_REASON)
    for item in items:
        if "live" not in item.keywords and "live_slow" not in item.keywords:
            continue
        item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def live_settings():
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        pytest.skip(LIVE_SKIP_REASON)
    repo_root = Path(__file__).resolve().parents[2]
    settings = load_live_settings(repo_root)
    if not settings.account_source_path.exists():
        pytest.fail(f"live 登录态文件不存在: {settings.account_source_path}")
    if not settings.ai_test_payload.get("OPENAI_BASE_URL") or not settings.ai_test_payload.get(
        "OPENAI_MODEL_NAME"
    ):
        pytest.fail("live 测试需要 OPENAI_BASE_URL 与 OPENAI_MODEL_NAME。")
    return settings


@pytest.fixture(scope="session")
def live_server(live_settings, request, tmp_path_factory):
    workspace = tmp_path_factory.mktemp("live-smoke")
    account_state_file = prepare_workspace(workspace, live_settings)
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_path = workspace / "live-app.log"
    env = build_server_env(workspace, live_settings.repo_root, port)
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=workspace,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_server_ready(base_url, process, log_path)
    except Exception:
        terminate_process(process)
        log_handle.close()
        raise

    server = LiveServer(
        base_url=base_url,
        workspace=workspace,
        server_log_path=log_path,
        account_state_file=account_state_file,
        settings=live_settings,
    )
    try:
        yield server
    finally:
        terminate_process(process)
        log_handle.close()
        if request.session.testsfailed:
            print(f"live smoke 失败，保留工作目录供排查: {workspace}")
            return
        shutil.rmtree(workspace, ignore_errors=True)
