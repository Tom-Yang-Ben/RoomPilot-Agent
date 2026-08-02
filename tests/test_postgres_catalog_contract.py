from backend.catalog.postgres_repository import _VIEW
from backend.server.postgres_catalog import _payload_from_row


def test_fastapi_uses_the_active_postgres_catalog_view() -> None:
    assert _VIEW == "roompilot.furniture_catalog_api_current"


def test_kai_postgres_row_maps_to_the_scene_catalog_contract() -> None:
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

    assert payload["catalog_scope"] == "kai_postgresql"
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
