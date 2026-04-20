"""
通知配置读写与校验服务
只保留飞书通知渠道
"""
import json
from urllib.parse import urlparse

from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import NotificationSettings


NOTIFICATION_FIELD_MAP = {
    "FEISHU_WEBHOOK_URL": "feishu_webhook_url",
    "PCURL_TO_MOBILE": "pcurl_to_mobile",
}

CHANNEL_NOTIFICATION_FIELDS = {
    "feishu": {"FEISHU_WEBHOOK_URL"},
}

SECRET_NOTIFICATION_FIELDS = {
    "FEISHU_WEBHOOK_URL",
}

JSON_NOTIFICATION_FIELDS = {}

URL_FIELDS = {
    "FEISHU_WEBHOOK_URL",
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
        "FEISHU_WEBHOOK_URL": "",
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
        "feishu_webhook_url_set": bool(notification_settings.feishu_webhook_url),
    }


def build_configured_channels(
    settings: NotificationSettings | None = None,
) -> list[str]:
    notification_settings = settings or load_notification_settings()
    channels = []
    if notification_settings.feishu_webhook_url:
        channels.append("feishu")
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


def prepare_notification_test_settings(
    patch_payload: dict,
    existing_settings: NotificationSettings | None = None,
    *,
    channel: str | None = None,
) -> NotificationSettings:
    if channel is None:
        _, _, merged_settings = prepare_notification_settings_update(
            patch_payload,
            existing_settings,
        )
        return merged_settings

    if channel not in CHANNEL_NOTIFICATION_FIELDS:
        raise NotificationSettingsValidationError(f"不支持的通知渠道：{channel}")

    current_settings = existing_settings or load_notification_settings()
    included_env_fields = set(CHANNEL_NOTIFICATION_FIELDS[channel])
    included_env_fields.add("PCURL_TO_MOBILE")
    merged_values = _build_channel_test_values(current_settings, included_env_fields)

    for env_name, raw_value in patch_payload.items():
        if env_name not in included_env_fields:
            continue
        attr_name = NOTIFICATION_FIELD_MAP[env_name]
        merged_values[attr_name] = _normalize_patch_value(env_name, raw_value)

    normalized_values = _normalize_notification_values(merged_values)
    candidate_settings = _build_notification_settings_model(normalized_values)
    _validate_notification_settings(candidate_settings)
    return candidate_settings


def _notification_settings_to_values(settings: NotificationSettings) -> dict:
    return {
        attr_name: getattr(settings, attr_name)
        for attr_name in NOTIFICATION_FIELD_MAP.values()
    }


def _build_channel_test_values(
    settings: NotificationSettings,
    included_env_fields: set[str],
) -> dict:
    values = {
        attr_name: None
        for attr_name in NOTIFICATION_FIELD_MAP.values()
    }
    values["pcurl_to_mobile"] = True

    for env_name in included_env_fields:
        attr_name = NOTIFICATION_FIELD_MAP[env_name]
        values[attr_name] = getattr(settings, attr_name)

    return values


def load_notification_settings() -> NotificationSettings:
    return _build_notification_settings_model(
        {
            "feishu_webhook_url": _normalize_existing_text(env_manager.get_value("FEISHU_WEBHOOK_URL")),
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
    return values


def _validate_notification_settings(settings: NotificationSettings) -> None:
    if settings.feishu_webhook_url is not None:
        _validate_http_url("FEISHU_WEBHOOK_URL", settings.feishu_webhook_url)


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
