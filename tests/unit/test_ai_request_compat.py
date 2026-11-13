from src.services.ai_request_compat import (
    is_json_output_unsupported_error,
    is_responses_api_unsupported_error,
    is_temperature_unsupported_error,
    remove_temperature_param,
)


def test_is_temperature_unsupported_error_detects_unsupported_message():
    err = Exception("temperature is not supported by this gateway")
    assert is_temperature_unsupported_error(err) is True


def test_remove_temperature_param_removes_only_temperature():
    params = {"model": "x", "temperature": 0.5, "max_output_tokens": 128}
    result = remove_temperature_param(params)

    assert "temperature" not in result
    assert result["model"] == "x"
    assert result["max_output_tokens"] == 128


def test_is_responses_api_unsupported_error_detects_gemini_plain_404():
    class _Resp:
        text = ""

    class _Err(Exception):
        status_code = 404
        body = ""
        response = _Resp()

        def __str__(self):
            return "Error code: 404"

    assert is_responses_api_unsupported_error(_Err()) is True


# -- is_json_output_unsupported_error tests --


def test_json_output_error_detected_via_body_param_response_format():
    """Vercel AI Gateway returns 400 with param='response_format'."""

    class _Err(Exception):
        body = {
            "message": "Invalid input",
            "type": "invalid_request_error",
            "param": "response_format",
            "code": "invalid_request_error",
        }

    assert is_json_output_unsupported_error(_Err()) is True


def test_json_output_error_detected_via_body_param_response_format_type():
    class _Err(Exception):
        body = {
            "message": "Invalid input",
            "param": "response_format.type",
        }

    assert is_json_output_unsupported_error(_Err()) is True


def test_json_output_error_detected_via_legacy_string_matching():
    err = Exception(
        "response_format.type is not supported by this model"
    )
    assert is_json_output_unsupported_error(err) is True


def test_json_output_error_not_triggered_by_unrelated_400():
    class _Err(Exception):
        body = {
            "message": "Invalid input",
            "param": "messages",
        }

    assert is_json_output_unsupported_error(_Err()) is False


def test_json_output_error_not_triggered_without_body():
    err = Exception("some random 400 error")
    assert is_json_output_unsupported_error(err) is False


import pytest
from src.services.ai_request_compat import build_ai_request_params

@pytest.mark.parametrize("api_mode", ["chat_completions", "responses"])
@pytest.mark.parametrize("output_format", ["json_object", "json_schema", "none"])
def test_output_formats_use_correct_api_envelope(api_mode, output_format):
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"], "additionalProperties": False}
    result = build_ai_request_params(api_mode, model="test", messages=[],
        enable_json_output=True, output_format=output_format, json_schema=schema,
        schema_name="test_result")
    actual = result.get("response_format") if api_mode == "chat_completions" else result.get("text", {}).get("format")
    if output_format == "none":
        assert actual is None
    else:
        assert actual["type"] == output_format
        if output_format == "json_schema":
            envelope = actual["json_schema"] if api_mode == "chat_completions" else actual
            assert envelope["strict"] is True and envelope["schema"] == schema
            assert envelope["name"] == "test_result"
