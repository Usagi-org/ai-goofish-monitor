from src.config import (
    GEMINI_DEFAULT_MODEL_NAME,
    GEMINI_OPENAI_COMPAT_BASE_URL,
    resolve_ai_runtime_config,
)


def test_resolve_ai_runtime_prefers_openai_key_when_present():
    runtime = resolve_ai_runtime_config(
        {
            "OPENAI_API_KEY": "openai-key",
            "GEMINI_API_KEY": "gemini-key",
            "OPENAI_BASE_URL": "https://example.com/v1/",
            "OPENAI_MODEL_NAME": "custom-model",
        }
    )

    assert runtime["api_key"] == "openai-key"
    assert runtime["base_url"] == "https://example.com/v1/"
    assert runtime["model_name"] == "custom-model"
    assert runtime["is_gemini_openai_compat"] is False


def test_resolve_ai_runtime_uses_gemini_defaults_with_only_gemini_key():
    runtime = resolve_ai_runtime_config(
        {
            "GEMINI_API_KEY": "gemini-key",
            "OPENAI_BASE_URL": "",
            "OPENAI_MODEL_NAME": "",
        }
    )

    assert runtime["api_key"] == "gemini-key"
    assert runtime["base_url"] == GEMINI_OPENAI_COMPAT_BASE_URL
    assert runtime["model_name"] == GEMINI_DEFAULT_MODEL_NAME
    assert runtime["is_gemini_openai_compat"] is True


def test_resolve_ai_runtime_keeps_custom_base_and_model_for_gemini_key():
    runtime = resolve_ai_runtime_config(
        {
            "GEMINI_API_KEY": "gemini-key",
            "OPENAI_BASE_URL": "https://gateway.example/v1/",
            "OPENAI_MODEL_NAME": "gemini-2.5-flash",
        }
    )

    assert runtime["api_key"] == "gemini-key"
    assert runtime["base_url"] == "https://gateway.example/v1/"
    assert runtime["model_name"] == "gemini-2.5-flash"
    assert runtime["is_gemini_openai_compat"] is True


def test_resolve_ai_runtime_prefers_gemini_key_for_gemini_endpoint():
    runtime = resolve_ai_runtime_config(
        {
            "OPENAI_API_KEY": "openai-key",
            "GEMINI_API_KEY": "gemini-key",
            "OPENAI_BASE_URL": GEMINI_OPENAI_COMPAT_BASE_URL,
            "OPENAI_MODEL_NAME": "gemini-2.5-flash",
        }
    )

    assert runtime["api_key"] == "gemini-key"
    assert runtime["is_gemini_openai_compat"] is True
