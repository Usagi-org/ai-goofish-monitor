"""
通知配置读写与校验服务
"""
import json
from urllib.parse import urlparse

from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import NotificationSettings


NOTIFICATION_FIELD_MAP = {
    "NTFY_TOPIC_URL": "ntfy_topic_url",
    "GOTIFY_URL": "gotify_url",
    "GOTIFY_TOKEN": "gotify_token",
    "BARK_URL": "bark_url",
    "WX_BOT_URL": "wx_bot_url",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "WEBHOOK_URL": "webhook_url",
    "WEBHOOK_METHOD": "webhook_method",
    "WEBHOOK_HEADERS": "webhook_headers",
    "WEBHOOK_CONTENT_TYPE": "webhook_content_type",
    "WEBHOOK_QUERY_PARAMETERS": "webhook_query_parameters",
    "WEBHOOK_BODY": "webhook_body",
    "PCURL_TO_MOBILE": "pcurl_to_mobile",
}

SECRET_NOTIFICATION_FIELDS = {
    "BARK_URL",
    "GOTIFY_TOKEN",
    "WX_BOT_URL",
    "TELEGRAM_BOT_TOKEN",
    "WEBHOOK_URL",
    "WEBHOOK_HEADERS",
}

JSON_NOTIFICATION_FIELDS = {
    "WEBHOOK_HEADERS": True,
    "WEBHOOK_QUERY_PARAMETERS": True,
    "WEBHOOK_BODY": False,
}

URL_FIELDS = {
    "NTFY_TOPIC_URL",
    "GOTIFY_URL",
    "BARK_URL",
    "WX_BOT_URL",
    "WEBHOOK_URL",
}

ALLOWED_WEBHOOK_METHODS = {"GET", "POST"}
ALLOWED_WEBHOOK_CONTENT_TYPES = {"JSON", "FORM"}


class NotificationSettingsValidationError(ValueError):
    """通知配置校验错误"""


def model_dump(model, *, exclude_unset: bool = False) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset)
    return model.dict(exclude_unset=exclude_unset)


def build_notification_settings_response(
    settings: NotificationSettings | None = None,
) -> dict:
    notification_settings = settings or load_notification_settings()
    response = {
        "NTFY_TOPIC_URL": notification_settings.ntfy_topic_url or "",
        "GOTIFY_URL": notification_settings.gotify_url or "",
        "GOTIFY_TOKEN": "",
        "BARK_URL": "",
        "WX_BOT_URL": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": notification_settings.telegram_chat_id or "",
        "WEBHOOK_URL": "",
        "WEBHOOK_METHOD": notification_settings.webhook_method,
        "WEBHOOK_HEADERS": "",
        "WEBHOOK_CONTENT_TYPE": notification_settings.webhook_content_type,
        "WEBHOOK_QUERY_PARAMETERS": notification_settings.webhook_query_parameters or "",
        "WEBHOOK_BODY": notification_settings.webhook_body or "",
        "PCURL_TO_MOBILE": notification_settings.pcurl_to_mobile,
    }
    for field in SECRET_NOTIFICATION_FIELDS:
        attr_name = NOTIFICATION_FIELD_MAP[field]
        response[f"{field}_SET"] = bool(getattr(notification_settings, attr_name))
    response["CONFIGURED_CHANNELS"] = build_configured_channels(notification_settings)
    return response


def build_notification_status_flags(
    settings: NotificationSettings | None = None,
) -> dict:
    notification_settings = settings or load_notification_settings()
    return {
        "ntfy_topic_url_set": bool(notification_settings.ntfy_topic_url),
        "gotify_url_set": bool(notification_settings.gotify_url),
        "gotify_token_set": bool(notification_settings.gotify_token),
        "bark_url_set": bool(notification_settings.bark_url),
        "wx_bot_url_set": bool(notification_settings.wx_bot_url),
        "telegram_bot_token_set": bool(notification_settings.telegram_bot_token),
        "telegram_chat_id_set": bool(notification_settings.telegram_chat_id),
        "webhook_url_set": bool(notification_settings.webhook_url),
        "webhook_headers_set": bool(notification_settings.webhook_headers),
    }


def build_configured_channels(
    settings: NotificationSettings | None = None,
) -> list[str]:
    notification_settings = settings or load_notification_settings()
    channels = []
    if notification_settings.ntfy_topic_url:
        channels.append("ntfy")
    if notification_settings.bark_url:
        channels.append("bark")
    if notification_settings.gotify_url and notification_settings.gotify_token:
        channels.append("gotify")
    if notification_settings.wx_bot_url:
        channels.append("wecom")
    if notification_settings.telegram_bot_token and notification_settings.telegram_chat_id:
        channels.append("telegram")
    if notification_settings.webhook_url:
        channels.append("webhook")
    return channels


def prepare_notification_settings_update(
    patch_payload: dict,
    existing_settings: NotificationSettings | None = None,
) -> tuple[dict[str, str], list[str], NotificationSettings]:
    current_settings = existing_settings or load_notification_settings()
    merged_values = _notification_settings_to_values(current_settings)

    for env_name, raw_value in patch_payload.items():
        attr_name = NOTIFICATION_FIELD_MAP.get(env_name)
        if attr_name is None:
            continue
        merged_values[attr_name] = _normalize_patch_value(env_name, raw_value)

    normalized_values = _normalize_notification_values(merged_values)
    candidate_settings = _build_notification_settings_model(normalized_values)
    _validate_notification_settings(candidate_settings)

    updates = {}
    deletions = []
    for env_name, raw_value in patch_payload.items():
        attr_name = NOTIFICATION_FIELD_MAP.get(env_name)
        if attr_name is None:
            continue
        value = normalized_values[attr_name]
        if isinstance(value, bool):
            updates[env_name] = "true" if value else "false"
            continue
        if value is None:
            deletions.append(env_name)
            continue
        updates[env_name] = value
    return updates, deletions, candidate_settings


def _notification_settings_to_values(settings: NotificationSettings) -> dict:
    return {
        attr_name: getattr(settings, attr_name)
        for attr_name in NOTIFICATION_FIELD_MAP.values()
    }


def load_notification_settings() -> NotificationSettings:
    return _build_notification_settings_model(
        {
            "ntfy_topic_url": _normalize_existing_text(env_manager.get_value("NTFY_TOPIC_URL")),
            "gotify_url": _normalize_existing_text(env_manager.get_value("GOTIFY_URL")),
            "gotify_token": _normalize_existing_text(env_manager.get_value("GOTIFY_TOKEN")),
            "bark_url": _normalize_existing_text(env_manager.get_value("BARK_URL")),
            "wx_bot_url": _normalize_existing_text(env_manager.get_value("WX_BOT_URL")),
            "telegram_bot_token": _normalize_existing_text(env_manager.get_value("TELEGRAM_BOT_TOKEN")),
            "telegram_chat_id": _normalize_existing_text(env_manager.get_value("TELEGRAM_CHAT_ID")),
            "webhook_url": _normalize_existing_text(env_manager.get_value("WEBHOOK_URL")),
            "webhook_method": _normalize_existing_text(env_manager.get_value("WEBHOOK_METHOD")) or "POST",
            "webhook_headers": _normalize_existing_text(env_manager.get_value("WEBHOOK_HEADERS")),
            "webhook_content_type": _normalize_existing_text(env_manager.get_value("WEBHOOK_CONTENT_TYPE")) or "JSON",
            "webhook_query_parameters": _normalize_existing_text(env_manager.get_value("WEBHOOK_QUERY_PARAMETERS")),
            "webhook_body": _normalize_existing_text(env_manager.get_value("WEBHOOK_BODY")),
            "pcurl_to_mobile": _env_bool(env_manager.get_value("PCURL_TO_MOBILE"), True),
        }
    )


def _build_notification_settings_model(values: dict) -> NotificationSettings:
    if hasattr(NotificationSettings, "model_construct"):
        return NotificationSettings.model_construct(**values)
    return NotificationSettings.construct(**values)


def _normalize_patch_value(env_name: str, value):
    if env_name == "PCURL_TO_MOBILE":
        return bool(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_existing_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_notification_values(values: dict) -> dict:
    normalized = dict(values)
    normalized["webhook_method"] = (
        (normalized.get("webhook_method") or "POST").strip().upper()
    )
    normalized["webhook_content_type"] = (
        (normalized.get("webhook_content_type") or "JSON").strip().upper()
    )

    for env_name, expect_dict in JSON_NOTIFICATION_FIELDS.items():
        attr_name = NOTIFICATION_FIELD_MAP[env_name]
        raw_value = normalized.get(attr_name)
        if raw_value is None:
            continue
        parsed = _parse_json_field(env_name, raw_value, expect_dict=expect_dict)
        normalized[attr_name] = json.dumps(
            parsed,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return normalized


def _validate_notification_settings(settings: NotificationSettings) -> None:
    for field_name in URL_FIELDS:
        value = getattr(settings, NOTIFICATION_FIELD_MAP[field_name])
        if value is not None:
            _validate_http_url(field_name, value)

    _validate_pair(
        "GOTIFY_URL",
        settings.gotify_url,
        "GOTIFY_TOKEN",
        settings.gotify_token,
    )
    _validate_pair(
        "TELEGRAM_BOT_TOKEN",
        settings.telegram_bot_token,
        "TELEGRAM_CHAT_ID",
        settings.telegram_chat_id,
    )

    if settings.webhook_method not in ALLOWED_WEBHOOK_METHODS:
        allowed = ", ".join(sorted(ALLOWED_WEBHOOK_METHODS))
        raise NotificationSettingsValidationError(
            f"WEBHOOK_METHOD 仅支持: {allowed}"
        )
    if settings.webhook_content_type not in ALLOWED_WEBHOOK_CONTENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_WEBHOOK_CONTENT_TYPES))
        raise NotificationSettingsValidationError(
            f"WEBHOOK_CONTENT_TYPE 仅支持: {allowed}"
        )

    has_webhook_extras = any(
        [
            settings.webhook_headers,
            settings.webhook_query_parameters,
            settings.webhook_body,
        ]
    )
    if has_webhook_extras and not settings.webhook_url:
        raise NotificationSettingsValidationError(
            "配置 Webhook 高级参数前必须先填写 WEBHOOK_URL"
        )

    if settings.webhook_content_type == "FORM" and settings.webhook_body:
        parsed_body = json.loads(settings.webhook_body)
        if not isinstance(parsed_body, dict):
            raise NotificationSettingsValidationError(
                "WEBHOOK_BODY 在 FORM 模式下必须是 JSON 对象"
            )


def _validate_http_url(field_name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise NotificationSettingsValidationError(
            f"{field_name} 必须是合法的 HTTP/HTTPS URL"
        )


def _validate_pair(
    left_name: str,
    left_value: str | None,
    right_name: str,
    right_value: str | None,
) -> None:
    if bool(left_value) == bool(right_value):
        return
    raise NotificationSettingsValidationError(
        f"{left_name} 与 {right_name} 必须成对配置"
    )


def _parse_json_field(
    field_name: str,
    raw_value: str,
    expect_dict: bool,
):
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise NotificationSettingsValidationError(
            f"{field_name} 不是合法 JSON: {exc.msg}"
        ) from exc
    if expect_dict and not isinstance(parsed, dict):
        raise NotificationSettingsValidationError(
            f"{field_name} 必须是 JSON 对象"
        )
    return parsed
