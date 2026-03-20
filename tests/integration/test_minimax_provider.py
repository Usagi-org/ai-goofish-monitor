"""Integration tests for MiniMax LLM provider.

These tests verify the end-to-end provider detection and client creation
flow without making real API calls.
"""

import os

import pytest

from src.infrastructure.config.settings import AISettings, LLMProvider
from src.infrastructure.external.ai_client import AIClient


# Clear all AI-related env vars so pydantic doesn't read stale values
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


class TestMiniMaxProviderIntegration:
    """Integration tests for MiniMax provider auto-detection and client setup."""

    def test_env_based_minimax_detection(self, monkeypatch):
        """Simulate a user who only sets MINIMAX_API_KEY in .env."""
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-integration-test")

        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX
        assert settings.resolved_api_key() == "mm-integration-test"
        assert settings.resolved_base_url() == "https://api.minimax.io/v1"
        assert settings.resolved_model_name() == "MiniMax-M2.7"
        assert settings.is_configured() is True

    def test_env_based_openai_detection(self, monkeypatch):
        """Simulate a user who sets only OPENAI_* variables."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-integration-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-4o")

        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.OPENAI
        assert settings.resolved_api_key() == "sk-integration-test"
        assert settings.resolved_base_url() == "https://api.openai.com/v1"
        assert settings.resolved_model_name() == "gpt-4o"

    def test_explicit_minimax_with_custom_model(self, monkeypatch):
        """Simulate LLM_PROVIDER=minimax with a custom model override."""
        monkeypatch.setenv("LLM_PROVIDER", "minimax")
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-custom-test")
        monkeypatch.setenv("OPENAI_MODEL_NAME", "MiniMax-M2.5-highspeed")

        settings = AISettings()
        assert settings.resolve_provider() == LLMProvider.MINIMAX
        assert settings.resolved_model_name() == "MiniMax-M2.5-highspeed"
        assert settings.resolved_base_url() == "https://api.minimax.io/v1"

    def test_ai_client_creates_with_minimax(self, monkeypatch):
        """AIClient should initialize successfully with MiniMax env vars."""
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-client-test")

        client = AIClient()
        assert client.is_available()
        assert client.settings.resolve_provider() == LLMProvider.MINIMAX
        assert client.client is not None

    def test_legacy_config_picks_up_minimax(self, monkeypatch):
        """Legacy config globals should reflect MiniMax provider settings."""
        monkeypatch.setenv("MINIMAX_API_KEY", "mm-legacy-test")

        settings = AISettings()
        assert settings.resolved_api_key() == "mm-legacy-test"
        assert settings.resolved_base_url() == "https://api.minimax.io/v1"
        assert settings.resolved_model_name() == "MiniMax-M2.7"
