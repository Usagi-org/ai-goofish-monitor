import copy
import pytest

from src.services.item_detail_parser import (
    ItemDetailSnapshot,
    apply_detail_to_item_data,
    classify_item_do_status,
    extract_item_detail_fields,
)


@pytest.mark.parametrize(
    "item_do,expected_raw",
    [
        ({"itemStatus": 0}, 0),
        ({"itemStatus": "0"}, "0"),
        ({"itemStatusStr": "在售"}, None),
        ({"statusDesc": "商品出售中"}, None),
    ],
)
def test_classify_item_do_status_active_variants(item_do, expected_raw):
    mapped, label, raw = classify_item_do_status(item_do)
    assert mapped == "active"
    assert label == "在售"
    assert raw == expected_raw


@pytest.mark.parametrize(
    "item_do,expected_raw",
    [
        ({"itemStatus": 1}, 1),
        ({"itemStatus": "1"}, "1"),
        ({"sold": True}, None),
        ({"isSold": True}, None),
        ({"gmtSold": "2026-01-01 12:00:00"}, None),
        ({"itemStatusStr": "已卖出"}, None),
        ({"statusDesc": "宝贝已售"}, None),
        ({"soldOutText": "卖掉了"}, None),
        ({"statusText": "已拍下"}, None),
        ({"bizStatusStr": "已成交"}, None),
        ({"tradeStatusStr": "已售罄"}, None),
        ({"quantity": 0, "soldPrice": "3999"}, None),
        ({"quantity": "0", "itemStatus": 9}, 9),
    ],
)
def test_classify_item_do_status_sold_variants(item_do, expected_raw):
    mapped, label, raw = classify_item_do_status(item_do)
    assert mapped == "sold"
    assert label == "已售出"
    assert raw == expected_raw


@pytest.mark.parametrize(
    "item_do,expected_raw",
    [
        ({"itemStatus": 2}, 2),
        ({"itemStatus": 3}, 3),
        ({"itemStatus": -1}, -1),
        ({"itemStatus": "2"}, "2"),
        ({"itemStatus": "-1"}, "-1"),
        ({"statusDesc": "商品已下架"}, None),
        ({"itemStatusStr": "链接已失效"}, None),
        ({"statusText": "宝贝不存在"}, None),
        ({"bizStatusStr": "已删除"}, None),
        ({"tradeStatusStr": "交易已关闭"}, None),
        ({"quantity": 0, "itemStatus": 2}, 2),
        ({"quantity": "0", "itemStatus": "3"}, "3"),
    ],
)
def test_classify_item_do_status_expired_variants(item_do, expected_raw):
    mapped, label, raw = classify_item_do_status(item_do)
    assert mapped == "expired"
    assert label == "已下架"
    assert raw == expected_raw


def test_classify_item_do_status_guards_bool_against_int_matching():
    assert classify_item_do_status({"itemStatus": True}) == ("unknown", None, None)
    assert classify_item_do_status({"itemStatus": False}) == ("unknown", None, None)
    assert classify_item_do_status({"quantity": False, "soldPrice": "1200"}) == (
        "unknown",
        None,
        None,
    )


def test_classify_item_do_status_unknown_preserves_first_status_text():
    mapped, label, raw = classify_item_do_status(
        {
            "itemStatus": 99,
            "itemStatusStr": "   ",
            "statusDesc": "待确认",
            "statusText": "其他状态",
        }
    )
    assert mapped == "unknown"
    assert label == "待确认"
    assert raw == 99


def test_extract_item_detail_fields_risk_control():
    snapshot = extract_item_detail_fields(
        {
            "ret": ["FAIL_SYS_USER_VALIDATE::哎哟喂,被挤爆啦,请稍后重试"],
            "data": {},
        }
    )
    assert snapshot.risk_control is True
    assert snapshot.login_required is False
    assert snapshot.mapped_status == "unknown"
    assert snapshot.error_reason == "FAIL_SYS_USER_VALIDATE"

    rgv_snapshot = extract_item_detail_fields(
        {
            "ret": ["RGV587_ERROR::SM::哎哟喂,被挤爆啦"],
            "data": {},
        }
    )
    assert rgv_snapshot.risk_control is True
    assert rgv_snapshot.error_reason == "RGV587_ERROR"

    session_snapshot = extract_item_detail_fields(
        {
            "ret": ["FAIL_SYS_SESSION_EXPIRED::Session过期"],
            "data": {},
        }
    )
    assert session_snapshot.risk_control is False
    assert session_snapshot.login_required is True
    assert session_snapshot.error_reason == "FAIL_SYS_SESSION_EXPIRED"


def test_classify_item_do_status_explicit_status_overrides_zero_quantity_and_zero_gmt_sold():
    assert classify_item_do_status(
        {"itemStatus": 0, "itemStatusStr": "在售", "quantity": 0, "soldPrice": "3999"}
    ) == ("active", "在售", 0)
    assert classify_item_do_status(
        {"itemStatus": 2, "quantity": 0, "soldPrice": "3999"}
    ) == ("expired", "已下架", 2)
    assert classify_item_do_status(
        {"itemStatus": 0, "gmtSold": "0"}
    ) == ("active", "在售", 0)
    assert classify_item_do_status(
        {"itemStatus": 0, "gmtSold": 0}
    ) == ("active", "在售", 0)


@pytest.mark.parametrize(
    "ret_value",
    [
        ["FAIL_BIZ_ITEM_NOT_EXIST::商品不存在"],
        ["ITEM_NOT_FOUND::宝贝不存在"],
        "商品已下架或已删除",
    ],
)
def test_extract_item_detail_fields_not_found_ret_maps_to_expired(ret_value):
    snapshot = extract_item_detail_fields({"ret": ret_value, "data": {"itemDO": {}}})
    assert snapshot.risk_control is False
    assert snapshot.mapped_status == "expired"
    assert snapshot.status_label == "已下架"


def test_extract_item_detail_fields_extracts_desc_images_title_and_seller():
    detail_json = {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "itemDO": {
                "title": "  MacBook Air M1 16+512 自用成色极佳  ",
                "desc": "  无拆无修，电池健康92%，原装充电器齐全  ",
                "imageInfos": [
                    {"url": "https://img.example.com/1.jpg"},
                    {"url": ""},
                    "invalid",
                    {"url": "https://img.example.com/2.jpg"},
                ],
                "wantCnt": 18,
                "browseCnt": 320,
                "itemStatus": 0,
            },
            "sellerDO": {
                "sellerId": 987654,
                "zhimaLevelInfo": {"levelName": "信用极好"},
                "userRegDay": "730",
            },
        },
    }

    snapshot = extract_item_detail_fields(detail_json)
    assert snapshot == ItemDetailSnapshot(
        title="MacBook Air M1 16+512 自用成色极佳",
        description="无拆无修，电池健康92%，原装充电器齐全",
        image_urls=[
            "https://img.example.com/1.jpg",
            "https://img.example.com/2.jpg",
        ],
        want_count=18,
        browse_count=320,
        item_status_raw=0,
        mapped_status="active",
        status_label="在售",
        seller_id="987654",
        zhima_credit_text="信用极好",
        registration_days=730,
        risk_control=False,
        error_reason=None,
    )


def test_extract_item_detail_fields_desc_fallbacks_and_safe_reg_days():
    snapshot = extract_item_detail_fields(
        {
            "ret": ["SUCCESS::调用成功"],
            "data": {
                "itemDO": {
                    "desc": "   ",
                    "descText": "备用描述字段",
                    "itemStatus": 1,
                },
                "sellerDO": {
                    "userRegDay": True,
                },
            },
        }
    )
    assert snapshot.description == "备用描述字段"
    assert snapshot.registration_days == 0
    assert snapshot.mapped_status == "sold"


def test_apply_detail_to_item_data_is_immutable_updates_fuller_title_and_is_idempotent():
    original = {
        "商品ID": "1001",
        "商品标题": "未知标题",
        "当前售价": "¥3800",
    }
    original_copy = copy.deepcopy(original)

    snapshot = ItemDetailSnapshot(
        title="MacBook Air M1 16+512 深空灰",
        description="个人一手自用，箱说全。",
        image_urls=[
            "https://img.example.com/a.jpg",
            "https://img.example.com/b.jpg",
        ],
        want_count=12,
        browse_count=200,
        item_status_raw=0,
        mapped_status="active",
        status_label="在售",
        seller_id="123",
        zhima_credit_text="信用极好",
        registration_days=400,
    )

    updated, changed = apply_detail_to_item_data(
        original,
        snapshot,
        checked_at="2026-01-05T10:00:00",
    )
    assert original == original_copy
    assert changed is True
    assert updated["商品标题"] == "MacBook Air M1 16+512 深空灰"
    assert updated["商品描述"] == "个人一手自用，箱说全。"
    assert updated["商品图片列表"] == [
        "https://img.example.com/a.jpg",
        "https://img.example.com/b.jpg",
    ]
    assert updated["商品主图链接"] == "https://img.example.com/a.jpg"
    assert updated["“想要”人数"] == 12
    assert updated["浏览量"] == 200
    assert updated["商品状态"] == "在售"
    assert updated["商品状态码"] == 0
    assert updated["状态检查时间"] == "2026-01-05T10:00:00"

    repeated, repeated_changed = apply_detail_to_item_data(
        updated,
        snapshot,
        checked_at="2026-01-05T10:00:00",
    )
    assert repeated == updated
    assert repeated_changed is False

    shorter_snapshot = ItemDetailSnapshot(
        title="MacBook Air",
        description="个人一手自用，箱说全。",
        image_urls=[
            "https://img.example.com/a.jpg",
            "https://img.example.com/b.jpg",
        ],
        want_count=12,
        browse_count=200,
        item_status_raw=0,
        mapped_status="active",
        status_label="在售",
        seller_id="123",
        zhima_credit_text="信用极好",
        registration_days=400,
    )
    after_shorter, shorter_changed = apply_detail_to_item_data(
        updated,
        shorter_snapshot,
        checked_at="2026-01-05T10:00:00",
    )
    assert after_shorter["商品标题"] == "MacBook Air M1 16+512 深空灰"
    assert shorter_changed is False
