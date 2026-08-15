from backend.agent.quote import build_quote
from backend.server.design_manual_service import _manual_rows
from backend.catalog.postgres_repository import _payload_from_row


def test_postgres_row_maps_to_the_scene_catalog_contract() -> None:
    payload = _payload_from_row(
        {
            "item_id": "chair-01",
            "name_en": "Chair",
            "name_zh": "椅子",
            "category_code": "dining-chair",
            "category_name_zh": "餐椅",
            "source_group": "IKEA",
            "kind": "furniture",
            "source_type": "seating",
            "primary_color": "黑色",
            "primary_material": "木材",
            "width_cm": 45,
            "depth_cm": 50,
            "height_cm": 80,
            "style_codes": ["modern", "minimalist"],
            "room_codes": ["dining_room"],
            "description": "適合餐桌使用。",
            "rag_text": ["黑色木製餐椅"],
            "object_type_zh": "餐椅",
            "glb_url": "https://cdn.example/chair.glb",
            "front_image_url": "https://cdn.example/chair-front.png",
            "side_image_url": "https://cdn.example/chair-side.png",
            "angle_45_image_url": "https://cdn.example/chair-angle.png",
        }
    )

    assert payload["catalog_scope"] == "developer_supplied"
    assert payload["model_url"] == "https://cdn.example/chair.glb"
    assert payload["preview_images"] == {
        "front": "https://cdn.example/chair-front.png",
        "side": "https://cdn.example/chair-side.png",
        "angle-45": "https://cdn.example/chair-angle.png",
    }
    assert payload["room_types"] == ["dining_room"]
    assert payload["style_candidates"] == [
        {"style_id": "modern_minimal", "score": 1.0},
        {"style_id": "modern_minimal", "score": 1.0},
    ]


def test_catalog_row_carries_the_price_into_the_quote() -> None:
    """型錄單價要一路帶到報價單，不能在型錄轉換這層掉。

    `roompilot.furniture_catalog_current` 可提供 `price_twd`，
    但 `_payload_from_row` 先前沒有輸出這一欄 → `scene_objects[].price_twd` 永遠
    是 None → 報價單每一列都印「待報價」。這裡把型錄列一路走到 QuoteLine，
    確保整條鏈不會再被某一層默默截斷。
    """
    payload = _payload_from_row(
        {
            "item_id": "sofa-01",
            "name_en": "Sofa",
            "name_zh": "三人布沙發",
            "category_code": "sofa",
            "kind": "furniture",
            "width_cm": 210,
            "depth_cm": 90,
            "height_cm": 85,
            "price_twd": 18800,
            "price_is_estimated": True,
        }
    )
    assert payload["price_twd"] == 18800.0
    assert payload["price_is_estimated"] is True

    # 型錄列 → scene_object（scene_service 以 {**catalog_item, **raw} 合併後輸出）
    scene_object = {
        "instance_id": "sofa-01#1",
        "name_zh_raw": payload["name_zh"],
        "normalized_type": payload["normalized_type"],
        "size_cm": payload["size_cm"],
        "price_twd": payload["price_twd"],
    }
    quote = build_quote([("客廳", _manual_rows([scene_object]))])
    line = quote.rooms[0].lines[0]
    assert line.unit_price == 18800.0
    assert line.subtotal == 18800.0
    assert quote.pending_count == 0
    assert "待報價" not in line.amount_text


def test_catalog_row_without_price_stays_pending() -> None:
    """型錄沒價就是沒價：標「待報價」，不猜、也不從總額裡藏起來。"""
    payload = _payload_from_row(
        {
            "item_id": "shelf-01",
            "name_zh": "層架",
            "category_code": "storage-cabinet",
            "kind": "furniture",
            "width_cm": 80,
            "depth_cm": 40,
            "height_cm": 180,
        }
    )
    assert payload["price_twd"] is None

    quote = build_quote(
        [
            (
                "書房",
                _manual_rows(
                    [
                        {
                            "instance_id": "shelf-01#1",
                            "name_zh_raw": payload["name_zh"],
                            "normalized_type": payload["normalized_type"],
                            "size_cm": payload["size_cm"],
                            "price_twd": payload["price_twd"],
                        }
                    ]
                ),
            )
        ]
    )
    line = quote.rooms[0].lines[0]
    assert line.unit_price is None and line.amount_text == "待報價"
    assert quote.total == 0.0 and quote.pending_count == 1
