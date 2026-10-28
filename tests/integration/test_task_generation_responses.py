import asyncio
from types import SimpleNamespace

import pytest

from src.domain.models.task import TaskGenerateRequest
from src.infrastructure.external.ai_client import AIClient
from src.services.task_generation_runner import build_criteria_filename, run_ai_generation_job


@pytest.mark.parametrize("response_kind, expected_error, expected_calls", [
    ("truncated_chat", "length", 1),
    ("truncated_reasoning", "length", 1),
    ("incomplete_responses", "incomplete", 2),
    ("completed", None, 1),
    ("completed_reasoning", None, 1),
])
def test_task_generation_only_saves_completed_content(
    response_kind, expected_error, expected_calls, api_context, monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_MODEL_NAME", "test-model")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "macbook_criteria.txt").write_text("reference", encoding="utf-8")
    criteria_file = tmp_path / build_criteria_filename("test tv")
    criteria_file.write_text("existing criteria", encoding="utf-8")
    calls = []
    closed = []

    async def create(**kwargs):
        calls.append(kwargs)
        if response_kind == "incomplete_responses":
            if "messages" in kwargs:
                raise Exception("404 page not found")
            return SimpleNamespace(status="incomplete", output_text="unfinished criteria")
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="length" if response_kind.startswith("truncated") else "stop",
            message=SimpleNamespace(
                content=None if response_kind.endswith("reasoning") else "final criteria",
                reasoning_content="final criteria" if response_kind == "completed_reasoning" else "unfinished reasoning",
            ),
        )])

    async def close():
        closed.append(True)

    endpoint = SimpleNamespace(create=create)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=endpoint), responses=endpoint, close=close,
    )
    monkeypatch.setattr(AIClient, "_initialize_client", lambda self: client)
    generation_service = api_context["task_generation_service"]
    task_service = api_context["task_service"]
    scheduler = api_context["scheduler_service"]
    req = TaskGenerateRequest(
        task_name="Test TV", keyword="test tv", description="85 inch TV", decision_mode="ai",
    )

    async def run():
        job = await generation_service.create_job(req.task_name)
        await run_ai_generation_job(
            job_id=job.job_id, req=req, task_service=task_service,
            scheduler_service=scheduler, generation_service=generation_service,
        )
        return await generation_service.get_job(job.job_id), await task_service.get_all_tasks()

    job, tasks = asyncio.run(run())

    assert closed == [True]
    assert len(calls) == expected_calls
    if expected_error is None:
        assert job.status == "completed"
        assert criteria_file.read_text(encoding="utf-8") == "final criteria"
        assert len(tasks) == 1
        assert scheduler.reload_calls == 1
    else:
        assert job.status == "failed"
        assert job.current_step == "llm"
        assert expected_error in job.error
        assert tasks == []
        assert scheduler.reload_calls == 0
        assert criteria_file.read_text(encoding="utf-8") == "existing criteria"
