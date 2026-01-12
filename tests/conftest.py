import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Add repository root to the path so package imports work consistently
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.api import dependencies as deps
from src.api.routes import tasks
from src.infrastructure.persistence.json_task_repository import JsonTaskRepository
from src.services.task_service import TaskService


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def load_json_fixture(fixtures_dir):
    def _load(name: str):
        return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture()
def sample_task_payload():
    return {
        "task_name": "Sony A7M4",
        "enabled": True,
        "keyword": "sony a7m4",
        "description": "Good condition body with accessories",
        "max_pages": 2,
        "personal_only": True,
        "min_price": "8000",
        "max_price": "16000",
        "cron": "*/15 * * * *",
        "ai_prompt_base_file": "prompts/base_prompt.txt",
        "ai_prompt_criteria_file": "prompts/sony_a7m4_criteria.txt",
    }


class FakeProcessService:
    def __init__(self):
        self.started = []
        self.stopped = []

    async def start_task(self, task_id: int, task_name: str) -> bool:
        self.started.append((task_id, task_name))
        return True

    async def stop_task(self, task_id: int):
        self.stopped.append(task_id)


@pytest.fixture()
def api_context(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("[]", encoding="utf-8")

    repository = JsonTaskRepository(config_file=str(config_file))
    task_service = TaskService(repository)
    process_service = FakeProcessService()

    app = FastAPI()
    app.include_router(tasks.router)

    def override_get_task_service():
        return task_service

    def override_get_process_service():
        return process_service

    app.dependency_overrides[deps.get_task_service] = override_get_task_service
    app.dependency_overrides[deps.get_process_service] = override_get_process_service

    return {
        "app": app,
        "config_file": config_file,
        "process_service": process_service,
    }


@pytest.fixture()
def api_client(api_context):
    return TestClient(api_context["app"])
