from src.xianyu.guards import (
    build_login_required_message,
    format_risk_sleep_message,
    is_risk_control_ret,
)


def test_build_login_required_message_preserves_existing_text() -> None:
    url = "https://passport.goofish.com/mini_login.htm"

    assert (
        build_login_required_message(url)
        == "Login required: redirected to https://passport.goofish.com/mini_login.htm (cookies/state likely expired)"
    )


def test_is_risk_control_ret_matches_stringified_ret_value() -> None:
    assert is_risk_control_ret(["FAIL_SYS_USER_VALIDATE::需要验证"]) is True
    assert is_risk_control_ret("FAIL_SYS_USER_VALIDATE") is True
    assert is_risk_control_ret(["SUCCESS::调用成功"]) is False
    assert is_risk_control_ret(None) is False


def test_format_risk_sleep_message_preserves_existing_text() -> None:
    assert (
        format_risk_sleep_message(30)
        == "为避免账户风险，将执行一次长时间休眠 (30 秒) 后再退出..."
    )
