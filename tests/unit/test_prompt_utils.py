import json
import asyncio

import pytest

import src.prompt_utils as prompt_utils
from src.services.ai_response_parser import EmptyAIResponseError


def test_generate_criteria_closes_ai_client_after_success(monkeypatch, tmp_path):
    close_state = {"closed": False}
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            return json.dumps({"criteria": "第一部分：核心分析原则\n必须为CMR硬盘。\n第二部分：详细分析指南\n核对型号、SMART与价格。"}, ensure_ascii=False)

        async def close(self):
            close_state["closed"] = True

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    result = asyncio.run(
        prompt_utils.generate_criteria("need a gpu", str(reference_file))
    )

    assert result.startswith("第一部分：核心分析原则")
    assert close_state["closed"] is True


def test_generate_criteria_drops_think_blocks_and_raises_output_limit(monkeypatch, tmp_path):
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")
    captured = {}

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **kwargs):
            captured.update(kwargs)
            return json.dumps({"criteria": "<think>先分析需求</think>\n第一部分：核心分析原则\n电池健康度不足需核实。\n第二部分：详细分析指南\n检查状态。"}, ensure_ascii=False)

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    result = asyncio.run(
        prompt_utils.generate_criteria("need a watch", str(reference_file))
    )

    assert result.startswith("第一部分") and "<think>" not in result
    assert captured["max_output_tokens"] == prompt_utils.CRITERIA_MAX_OUTPUT_TOKENS
    assert captured["max_output_tokens"] > 800


def test_generate_criteria_rejects_truncated_think_block(monkeypatch, tmp_path):
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            return json.dumps({"criteria": "<think>输出到这里被截断"})

        async def close(self):
            return None

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    with pytest.raises(RuntimeError, match="思考过程占满了输出长度"):
        asyncio.run(prompt_utils.generate_criteria("need a watch", str(reference_file)))


def test_generate_criteria_closes_ai_client_after_ai_failure(monkeypatch, tmp_path):
    close_state = {"closed": False}
    reference_file = tmp_path / "reference.txt"
    reference_file.write_text("reference", encoding="utf-8")

    class FakeAIClient:
        def is_available(self):
            return True

        def refresh(self):
            raise AssertionError("refresh should not be called")

        async def _call_ai(self, *_args, **_kwargs):
            raise EmptyAIResponseError("AI响应内容为空。")

        async def close(self):
            close_state["closed"] = True

    monkeypatch.setattr(prompt_utils, "AIClient", FakeAIClient)

    with pytest.raises(EmptyAIResponseError, match="AI响应内容为空"):
        asyncio.run(prompt_utils.generate_criteria("need a gpu", str(reference_file)))

    assert close_state["closed"] is True



def test_generation_rejects_reasoning_saved_inside_criteria(monkeypatch):
    class FakeAIClient:
        async def _call_ai(self, *_args, **kwargs):
            return json.dumps({"criteria":"我们需要回答中文，考虑是否包含第一部分和第二部分，可能"})
    with pytest.raises(ValueError, match="分析标准"):
        asyncio.run(prompt_utils._request_generated_text(FakeAIClient(), "generate"))



def test_failed_generation_preserves_existing_criteria(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import src.services.task_generation_runner as runner
    monkeypatch.chdir(tmp_path)
    (tmp_path / "prompts").mkdir()
    existing = tmp_path / "prompts/disk_criteria.txt"
    existing.write_text("previous valid criteria")
    async def broken(**kwargs):
        raise ValueError("AI回答未完成")
    monkeypatch.setattr(runner, "generate_criteria", broken)
    class Jobs:
        async def advance(self, *args): pass
        async def fail(self, *args): pass
    asyncio.run(runner.run_ai_generation_job(job_id="test", req=SimpleNamespace(keyword="disk", description="disk"),
        task_service=None, scheduler_service=None, generation_service=Jobs()))
    assert existing.read_text() == "previous valid criteria"


def test_builtin_macbook_criteria_matches_section_and_schema_keys():
    import re
    from pathlib import Path
    from src.services.ai_output_schema import CriteriaAnalysis

    criteria_path = Path(__file__).resolve().parents[2] / "prompts" / "macbook_criteria.txt"
    text = criteria_path.read_text(encoding="utf-8")

    assert re.match(r"^(?:#{1,6}\s*)?(?:\*\*)?第一部分[：:]", text)
    assert re.search(r"(?m)^(?:#{1,6}\s*)?(?:\*\*)?第二部分[：:]", text)
    for field_name in CriteriaAnalysis.model_fields:
        assert f"`{field_name}`" in text
    for legacy_key in ("model_chip", "battery_health", "seller_credit", "shipping"):
        assert legacy_key not in text
