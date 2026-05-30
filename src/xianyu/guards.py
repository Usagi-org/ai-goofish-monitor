def build_login_required_message(url: str) -> str:
    return f"Login required: redirected to {url} (cookies/state likely expired)"


def is_risk_control_ret(ret_value) -> bool:
    return "FAIL_SYS_USER_VALIDATE" in str(ret_value)


def format_risk_sleep_message(seconds: int) -> str:
    return f"为避免账户风险，将执行一次长时间休眠 ({seconds} 秒) 后再退出..."
