from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal, Optional


MappedItemStatus = Literal["active", "sold", "expired", "unknown"]

_STATUS_TEXT_FIELDS = (
    "itemStatusStr",
    "statusDesc",
    "soldOutText",
    "statusText",
    "bizStatusStr",
    "tradeStatusStr",
)

_SOLD_TEXT_MARKERS = ("已售", "已卖出", "卖掉了", "已拍下", "已成交", "售罄")
_EXPIRED_TEXT_MARKERS = ("下架", "失效", "不存在", "删除", "关闭")
_ACTIVE_TEXT_MARKERS = ("在售", "出售中")

_NOT_FOUND_RET_MARKERS = (
    "ITEM_NOT_FOUND",
    "宝贝不存在",
    "商品不存在",
    "已删除",
    "已下架",
    "FAIL_BIZ_ITEM_NOT_EXIST",
)
_RISK_CONTROL_RET_MARKERS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587_ERROR",
    "FAIL_SYS_ILLEGAL_ACCESS",
)
_LOGIN_REQUIRED_RET_MARKERS = (
    "FAIL_SYS_SESSION_EXPIRED",
    "FAIL_SYS_TOKEN_EXOIRED",
    "FAIL_SYS_TOKEN_EXPIRED",
    "FAIL_SYS_ILLEGAL_TOKEN",
)

_SOLD_STATUS_CODES = {1, "1"}
_EXPIRED_STATUS_CODES = {2, 3, -1, "2", "3", "-1"}
_ACTIVE_STATUS_CODES = {0, "0"}
_NON_SOLD_QUANTITY_EXCLUSION_CODES = _ACTIVE_STATUS_CODES | _EXPIRED_STATUS_CODES


@dataclass(frozen=True)
class ItemDetailSnapshot:
    title: Optional[str]
    description: Optional[str]
    image_urls: list[str]
    want_count: Optional[Any]
    browse_count: Optional[Any]
    item_status_raw: Optional[Any]
    mapped_status: MappedItemStatus
    status_label: Optional[str]
    seller_id: Optional[str]
    zhima_credit_text: Optional[str]
    registration_days: int
    risk_control: bool = False
    login_required: bool = False
    error_reason: Optional[str] = None


def _normalize_status_code(value: Any) -> Optional[Any]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def _matches_status_code(value: Any, codes: set[Any]) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value in codes
    if isinstance(value, str):
        return value.strip() in codes
    return False


def _is_truthy_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _has_sold_timestamp(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"0", "false", "null", "none"}:
            return False
        if cleaned.isdigit():
            return int(cleaned) > 0
        return True
    return False


def _is_zero_quantity(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value == 0
    if isinstance(value, str):
        return value.strip() == "0"
    return False


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stringify_ret(ret_raw: Any) -> str:
    if isinstance(ret_raw, list):
        return " ".join(str(part) for part in ret_raw if part is not None)
    if ret_raw is not None:
        return str(ret_raw)
    return ""


def _first_non_empty_text(mapping: dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def classify_item_do_status(
    item_do: dict,
) -> tuple[MappedItemStatus, Optional[str], Optional[Any]]:
    if not isinstance(item_do, dict):
        return ("unknown", None, None)

    status_texts: list[str] = []
    for field in _STATUS_TEXT_FIELDS:
        raw_text = item_do.get(field)
        if isinstance(raw_text, str):
            cleaned = raw_text.strip()
            if cleaned:
                status_texts.append(cleaned)
    first_status_text = status_texts[0] if status_texts else None

    item_status = _normalize_status_code(item_do.get("itemStatus"))

    has_sold_flag = (
        item_do.get("sold") is True
        or item_do.get("isSold") is True
        or _has_sold_timestamp(item_do.get("gmtSold"))
    )
    has_sold_code = _matches_status_code(item_status, _SOLD_STATUS_CODES)
    has_sold_text = any(
        marker in text
        for text in status_texts
        for marker in _SOLD_TEXT_MARKERS
    )
    if has_sold_flag or has_sold_code or has_sold_text:
        return ("sold", "已售出", item_status)

    has_expired_code = _matches_status_code(item_status, _EXPIRED_STATUS_CODES)
    has_expired_text = any(
        marker in text
        for text in status_texts
        for marker in _EXPIRED_TEXT_MARKERS
    )
    if has_expired_code or has_expired_text:
        return ("expired", "已下架", item_status)

    has_active_code = _matches_status_code(item_status, _ACTIVE_STATUS_CODES)
    has_active_text = any(
        marker in text
        for text in status_texts
        for marker in _ACTIVE_TEXT_MARKERS
    )
    if has_active_code or has_active_text:
        return ("active", "在售", item_status)

    has_zero_quantity_sold = _is_zero_quantity(item_do.get("quantity")) and (
        _is_truthy_value(item_do.get("soldPrice"))
        or (
            item_status is not None
            and not _matches_status_code(
                item_status, _NON_SOLD_QUANTITY_EXCLUSION_CODES
            )
        )
    )
    if has_zero_quantity_sold:
        return ("sold", "已售出", item_status)

    return ("unknown", first_status_text or None, item_status)


def extract_item_detail_fields(detail_json: dict) -> ItemDetailSnapshot:
    payload = detail_json if isinstance(detail_json, dict) else {}
    ret_text = _stringify_ret(payload.get("ret"))

    matched_risk_marker = next(
        (marker for marker in _RISK_CONTROL_RET_MARKERS if marker in ret_text),
        None,
    )
    if matched_risk_marker is not None:
        return ItemDetailSnapshot(
            title=None,
            description=None,
            image_urls=[],
            want_count=None,
            browse_count=None,
            item_status_raw=None,
            mapped_status="unknown",
            status_label=None,
            seller_id=None,
            zhima_credit_text=None,
            registration_days=0,
            risk_control=True,
            error_reason=matched_risk_marker,
        )

    matched_login_marker = next(
        (marker for marker in _LOGIN_REQUIRED_RET_MARKERS if marker in ret_text),
        None,
    )
    if matched_login_marker is not None:
        return ItemDetailSnapshot(
            title=None,
            description=None,
            image_urls=[],
            want_count=None,
            browse_count=None,
            item_status_raw=None,
            mapped_status="unknown",
            status_label=None,
            seller_id=None,
            zhima_credit_text=None,
            registration_days=0,
            login_required=True,
            error_reason=matched_login_marker,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}

    item_do = data.get("itemDO")
    if not isinstance(item_do, dict):
        item_do = {}

    seller_do = data.get("sellerDO")
    if not isinstance(seller_do, dict):
        seller_do = {}

    raw_seller_id = seller_do.get("sellerId")
    seller_id = (
        str(raw_seller_id)
        if raw_seller_id is not None and str(raw_seller_id).strip() != ""
        else None
    )
    zhima_level_info = seller_do.get("zhimaLevelInfo")
    zhima_credit_text = (
        zhima_level_info.get("levelName")
        if isinstance(zhima_level_info, dict)
        else None
    )
    registration_days = _safe_int(seller_do.get("userRegDay"), default=0)

    if not item_do and any(marker in ret_text for marker in _NOT_FOUND_RET_MARKERS):
        return ItemDetailSnapshot(
            title=None,
            description=None,
            image_urls=[],
            want_count=None,
            browse_count=None,
            item_status_raw=None,
            mapped_status="expired",
            status_label="已下架",
            seller_id=seller_id,
            zhima_credit_text=zhima_credit_text,
            registration_days=registration_days,
        )

    title = _first_non_empty_text(item_do, ("title",))
    description = _first_non_empty_text(item_do, ("desc", "descText", "description"))

    raw_image_infos = item_do.get("imageInfos")
    image_urls = [
        img["url"].strip()
        for img in (raw_image_infos if isinstance(raw_image_infos, list) else [])
        if isinstance(img, dict)
        and isinstance(img.get("url"), str)
        and img["url"].strip()
    ]

    want_count = item_do.get("wantCnt")
    browse_count = item_do.get("browseCnt")
    mapped_status, status_label, item_status_raw = classify_item_do_status(item_do)

    return ItemDetailSnapshot(
        title=title,
        description=description,
        image_urls=image_urls,
        want_count=want_count,
        browse_count=browse_count,
        item_status_raw=item_status_raw,
        mapped_status=mapped_status,
        status_label=status_label,
        seller_id=seller_id,
        zhima_credit_text=zhima_credit_text,
        registration_days=registration_days,
    )


def apply_detail_to_item_data(
    item_data: dict,
    snapshot: ItemDetailSnapshot,
    *,
    checked_at: Optional[str] = None,
) -> tuple[dict, bool]:
    updated = copy.deepcopy(item_data if isinstance(item_data, dict) else {})
    changed = False

    def _set_if_changed(key: str, value: Any) -> None:
        nonlocal changed
        if (
            key not in updated
            or type(updated[key]) is not type(value)
            or updated[key] != value
        ):
            updated[key] = value
            changed = True

    if snapshot.description:
        _set_if_changed("商品描述", snapshot.description)

    current_title = str(updated.get("商品标题") or "").strip()
    if snapshot.title and (
        not current_title
        or current_title == "未知标题"
        or len(snapshot.title) > len(current_title)
    ):
        _set_if_changed("商品标题", snapshot.title)

    if snapshot.image_urls:
        image_urls = list(snapshot.image_urls)
        _set_if_changed("商品图片列表", image_urls)
        _set_if_changed("商品主图链接", image_urls[0])

    if snapshot.want_count is not None:
        _set_if_changed("“想要”人数", snapshot.want_count)

    if snapshot.browse_count is not None:
        _set_if_changed("浏览量", snapshot.browse_count)

    if snapshot.status_label:
        _set_if_changed("商品状态", snapshot.status_label)

    if snapshot.item_status_raw is not None:
        _set_if_changed("商品状态码", snapshot.item_status_raw)

    if checked_at:
        _set_if_changed("状态检查时间", checked_at)

    return updated, changed
