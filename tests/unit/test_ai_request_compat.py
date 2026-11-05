from src.services.ai_request_compat import (
    is_chat_completions_api_unsupported_error,
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


def test_chat_completions_unsupported_detected_via_protocol_not_supported_code():
    """PackyCode's codex group rejects /v1/chat/completions with 400 protocol_not_supported."""

    class _Err(Exception):
        status_code = 400
        body = {
            "message": "模型 gpt-6.1-sol 不支持 chat completions 协议",
            "code": "protocol_not_supported",
        }

    assert is_chat_completions_api_unsupported_error(_Err()) is True


def test_chat_completions_unsupported_detected_via_localized_message():
    err = Exception(
        "Error code: 400 - 模型 gpt-6.1-sol 不支持 chat completions 协议 "
        "(request id: 01M6JB52BYNMXS4J6JHVY1DC2Z)"
    )
    assert is_chat_completions_api_unsupported_error(err) is True


def test_chat_completions_unsupported_not_triggered_by_unrelated_400():
    class _Err(Exception):
        status_code = 400
        body = {"message": "Invalid input", "code": "invalid_request_error"}

        def __str__(self):
            return "Error code: 400 - Invalid input"

    assert is_chat_completions_api_unsupported_error(_Err()) is False


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
