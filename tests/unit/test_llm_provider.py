"""Tests for LLM provider detection, settings resolution, and MiniMax integration."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.infrastructure.config.settings import (
    AISettings,
    LLMProvider,
    _PROVIDER_PRESETS,
)
from src.infrastructure.external.ai_client import AIClient


# Helper to clear all AI-related env vars so pydantic doesn't read stale values
_AI_ENV_KEYS = (
    "LLM_PROVIDER",
    "OPENAI_API_KEY",
    "MINIMAX_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL_NAME",
    "PROXY_URL",
    "AI_DEBUG_MODE",
    "ENABLE_RESPONSE_FORMAT",
    "ENABLE_THINKING",
    "SKIP_AI_ANALYSIS",
)


@pytest.fixture(autouse=True)
def _clean_ai_env(monkeypatch):
    """Remove all AI-related env vars before each test."""
    for key in _AI_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# AISettings.resolve_provider
# ---------------------------------------------------------------------------


class TestResolveProvider:
    """Tests for LLM provider auto-detection logic."""

    def test_defaults_to_openai_when_no_env(self):
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.OPENAI

    def test_explicit_minimax_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX

    def test_explicit_openai_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.OPENAI

    def test_auto_detect_minimax_from_api_key(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX

    def test_openai_takes_precedence_when_both_keys_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-key")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.OPENAI

    def test_invalid_provider_falls_back_to_auto_detect(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX

    def test_case_insensitive_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "MiniMax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX


# ---------------------------------------------------------------------------
# AISettings.resolved_api_key
# ---------------------------------------------------------------------------


class TestResolvedApiKey:
    """Tests for API key resolution per provider."""

    def test_openai_returns_openai_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolved_api_key() == "sk-openai"

    def test_minimax_returns_minimax_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolved_api_key() == "mm-key"

    def test_minimax_falls_back_to_openai_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-shared")
        settings = AISettings()
        assert settings.resolved_api_key() == "sk-shared"


# ---------------------------------------------------------------------------
# AISettings.resolved_base_url / resolved_model_name
# ---------------------------------------------------------------------------


class TestResolvedDefaults:
    """Tests for base URL and model name resolution with provider presets."""

    def test_minimax_defaults_when_no_explicit_url(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.resolved_base_url() == "https://api.minimax.io/v1"
        assert settings.resolved_model_name() == "MiniMax-M2.7"

    def test_explicit_url_overrides_minimax_default(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.minimax.io/v1")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "MiniMax-M2.5")
        settings = AISettings()
        assert settings.resolved_base_url() == "https://custom.minimax.io/v1"
        assert settings.resolved_model_name() == "MiniMax-M2.5"

    def test_openai_no_defaults(self):
        settings = AISettings()
        assert settings.resolved_base_url() == ""
        assert settings.resolved_model_name() == ""

    def test_openai_uses_explicit_values(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")
        settings = AISettings()
        assert settings.resolved_base_url() == "https://api.openai.com/v1"
        assert settings.resolved_model_name() == "gpt-4o"


# ---------------------------------------------------------------------------
# AISettings.is_configured
# ---------------------------------------------------------------------------


class TestIsConfigured:
    """Tests for is_configured with provider presets."""

    def test_minimax_configured_with_only_api_key(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-key")
        settings = AISettings()
        assert settings.is_configured() is True

    def test_openai_not_configured_without_url(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-key")
        settings = AISettings()
        assert settings.is_configured() is False

    def test_openai_configured_with_url_and_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")
        settings = AISettings()
        assert settings.is_configured() is True


# ---------------------------------------------------------------------------
# Provider presets registry
# ---------------------------------------------------------------------------


class TestProviderPresets:
    """Tests for provider preset values."""

    def test_minimax_preset_exists(self):
        assert LLMProvider.MINIMAX in _PROVIDER_PRESETS

    def test_minimax_preset_has_required_keys(self):
        preset = _PROVIDER_PRESETS[LLMProvider.MINIMAX]
        assert "base_url" in preset
        assert "model_name" in preset

    def test_minimax_base_url_value(self):
        assert _PROVIDER_PRESETS[LLMProvider.MINIMAX]["base_url"] == "https://api.minimax.io/v1"

    def test_minimax_default_model(self):
        assert _PROVIDER_PRESETS[LLMProvider.MINIMAX]["model_name"] == "MiniMax-M2.7"


# ---------------------------------------------------------------------------
# AIClient initialization with MiniMax
# ---------------------------------------------------------------------------


class TestAIClientMiniMax:
    """Tests for AIClient behavior with MiniMax provider."""

    def test_client_initializes_with_minimax_settings(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-test-key")
        client = AIClient()
        assert client.is_available()
        assert client.settings.resolve_provider() == LLMProvider.MINIMAX

    def test_client_uses_resolved_model_in_call(self):
        client = AIClient.__new__(AIClient)
        client.settings = SimpleNamespace(
            model_name="",
            enable_response_format=True,
            enable_thinking=False,
            resolve_provider=lambda: LLMProvider.MINIMAX,
            resolved_model_name=lambda: "MiniMax-M2.7",
        )
        request_history = []

        async def fake_create(**kwargs):
            request_history.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"ok":true}')
                    )
                ]
            )

        responses = SimpleNamespace(create=fake_create)
        chat = SimpleNamespace(completions=SimpleNamespace(create=fake_create))
        client.client = SimpleNamespace(responses=responses, chat=chat)

        response = asyncio.run(client._call_ai([{"role": "user", "content": "test"}]))
        assert response == '{"ok":true}'
        assert request_history[0]["model"] == "MiniMax-M2.7"

    def test_explicit_minimax_provider_with_custom_model(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-test-key")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "MiniMax-M2.5-highspeed")
        client = AIClient()
        assert client.is_available()
        assert client.settings.resolved_model_name() == "MiniMax-M2.5-highspeed"
        assert client.settings.resolved_base_url() == "https://api.minimax.io/v1"


# ---------------------------------------------------------------------------
# LLMProvider enum
# ---------------------------------------------------------------------------


class TestLLMProviderEnum:
    """Tests for LLMProvider enum values."""

    def test_openai_value(self):
        assert LLMProvider.OPENAI.value == "openai"

    def test_minimax_value(self):
        assert LLMProvider.MINIMAX.value == "minimax"

    def test_from_string(self):
        assert LLMProvider("minimax") == LLMProvider.MINIMAX
        assert LLMProvider("openai") == LLMProvider.OPENAI
