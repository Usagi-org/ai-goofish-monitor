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


def test_json_output_error_detected_for_sglang_grammar_constrained_decoding_400():
    """Issue #532: SGLang DFLASH speculative decoding 400 with param=None."""

    class _SGLangErr(Exception):
        status_code = 400
        body = {
            "object": "error",
            "message": (
                "DFLASH speculative decoding does not support "
                "grammar-constrained decoding yet."
            ),
            "type": "BadRequestError",
            "param": None,
            "code": 400,
        }

    err = _SGLangErr(
        "Error code: 400 - {'object': 'error', 'message': "
        "'DFLASH speculative decoding does not support grammar-constrained decoding yet.', "
        "'type': 'BadRequestError', 'param': None, 'code': 400}"
    )
    assert is_json_output_unsupported_error(err) is True


def test_json_output_error_detected_for_guided_decoding_and_unsupported_variants():
    assert (
        is_json_output_unsupported_error(
            Exception("This model does not support grammar-constrained decoding.")
        )
        is True
    )
    assert (
        is_json_output_unsupported_error(
            Exception("guided decoding is unsupported")
        )
        is True
    )
    assert (
        is_json_output_unsupported_error(
            Exception("This gateway does not support response_format")
        )
        is True
    )


def test_json_output_error_detected_via_nested_error_and_text_format_param():
    class _NestedParamErr(Exception):
        body = {
            "error": {
                "message": "Invalid input",
                "param": "text.format.type",
            }
        }

    class _TopLevelTextFormatErr(Exception):
        body = {
            "message": "Invalid input",
            "param": "text.format",
        }

    assert is_json_output_unsupported_error(_NestedParamErr()) is True
    assert is_json_output_unsupported_error(_TopLevelTextFormatErr()) is True


def test_json_output_error_not_triggered_by_unrelated_does_not_support_400():
    class _ImageUnsupportedErr(Exception):
        status_code = 400
        body = {
            "object": "error",
            "message": "This model does not support images.",
            "type": "BadRequestError",
            "param": None,
            "code": 400,
        }

    class _ToolsUnsupportedErr(Exception):
        status_code = 400
        body = {
            "error": {
                "param": "tools",
                "message": "tools are not supported by this model",
            }
        }

    class _ExplicitUnrelatedParamErr(Exception):
        status_code = 400
        body = {
            "param": "temperature",
            "message": "temperature is unsupported when response_format is set",
        }

    class _ContextLengthExceededErr(Exception):
        status_code = 400
        body = {
            "error": {
                "message": (
                    "This model's maximum context length is 8192 tokens. "
                    "However, your messages resulted in 10240 tokens."
                ),
                "type": "invalid_request_error",
                "param": "messages",
                "code": "context_length_exceeded",
            }
        }

    err = _ImageUnsupportedErr(
        "Error code: 400 - {'object': 'error', 'message': "
        "'This model does not support images.', "
        "'type': 'BadRequestError', 'param': None, 'code': 400}"
    )
    tools_err = _ToolsUnsupportedErr(
        "Error code: 400 - {'error': {'param': 'tools', "
        "'message': 'tools are not supported by this model'}}"
    )
    assert is_json_output_unsupported_error(err) is False
    assert is_json_output_unsupported_error(tools_err) is False
    assert is_json_output_unsupported_error(_ExplicitUnrelatedParamErr()) is False
    assert (
        is_json_output_unsupported_error(
            Exception("IMAGE INPUT IS NOT SUPPORTED BY THIS MODEL")
        )
        is False
    )
    assert is_json_output_unsupported_error(_ContextLengthExceededErr()) is False
    assert (
        is_json_output_unsupported_error(
            Exception("Error code: 400 - maximum context length is 8192 tokens")
        )
        is False
    )
    assert (
        is_json_output_unsupported_error(
            Exception("Unsupported media type in request")
        )
        is False
    )
