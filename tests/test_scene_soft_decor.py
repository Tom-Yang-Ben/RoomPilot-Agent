from fastapi.testclient import TestClient

from backend.catalog.style_db import catalog_item_from_scene_object
from backend.engine.models import PlacedFurniture, Room
from backend.engine.placement import place_overlay_on_furniture
from backend.server.main import app
from backend.server.scene_service import floorplan_from_editor_payload, generate_layout


client = TestClient(app)


def _floorplan_editor() -> dict:
    return {
        "width_cm": 700,
        "depth_cm": 500,
        "rooms": [
            {
                "id": "living-1",
                "type": "living_room",
                "polygon_m": [
                    {"x": 0, "y": 0},
                    {"x": 7, "y": 0},
                    {"x": 7, "y": 5},
                    {"x": 0, "y": 5},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 7, "y": 0}},
                {"start": {"x": 7, "y": 0}, "end": {"x": 7, "y": 5}},
                {"start": {"x": 7, "y": 5}, "end": {"x": 0, "y": 5}},
                {"start": {"x": 0, "y": 5}, "end": {"x": 0, "y": 0}},
            ],
            "windows": [
                {"start": {"x": 1.5, "y": 0}, "end": {"x": 4.5, "y": 0}},
            ],
        },
    }


def test_legacy_demolition_candidate_is_cleared_without_removing_engine_wall() -> None:
    floorplan, room = floorplan_from_editor_payload(
        {
            "coordinate_unit": "cm",
            "width_cm": 700,
            "depth_cm": 500,
            "structures": {
                "walls": [
                    {
                        "id": "interior-wall",
                        "start": {"x": 350, "y": 0},
                        "end": {"x": 350, "y": 500},
                        "thickness_cm": 12,
                        "demolition_candidate": True,
                    }
                ]
            },
        }
    )

    assert floorplan["wall_segments"][0]["demolition_candidate"] is False
    assert floorplan["wall_count"] == 1
    assert len(room.walls) >= 1


def test_editor_door_swing_endpoint_uses_the_same_scene_coordinates_as_its_leaf() -> None:
    floorplan, _room = floorplan_from_editor_payload(
        {
            "coordinate_unit": "cm",
            "width_cm": 1000,
            "depth_cm": 800,
            "structures": {
                "doors": [
                    {
                        "id": "door-1",
                        "start": {"x": 500, "y": 100},
                        "end": {"x": 620, "y": 100},
                        "swing_end": {"x": 500, "y": 220},
                    }
                ]
            },
        }
    )

    door = floorplan["door_segments"][0]
    assert door["start"] == {"x": 0.0, "z": -300.0}
    assert door["end"] == {"x": 120.0, "z": -300.0}
    assert door["swing_end"] == {"x": 0.0, "z": -180.0}


def test_editor_preserves_confirmed_doorway_in_the_same_scene_coordinates() -> None:
    floorplan, _room = floorplan_from_editor_payload(
        {
            "coordinate_unit": "cm",
            "width_cm": 1000,
            "depth_cm": 800,
            "structures": {
                "doors": [
                    {
                        "id": "door-1",
                        "start": {"x": 500, "y": 100},
                        "end": {"x": 620, "y": 100},
                        "swing_end": {"x": 500, "y": 220},
                        "confirmed_wall_opening": {
                            "start": {"x": 500, "y": 220},
                            "end": {"x": 620, "y": 220},
                        },
                    }
                ]
            },
        }
    )

    doorway = floorplan["door_segments"][0]["confirmed_wall_opening"]
    assert doorway == {
        "start": {"x": 0.0, "z": -180.0},
        "end": {"x": 120.0, "z": -180.0},
    }


def test_editor_assigns_stable_architecture_ids_when_loading_older_projects() -> None:
    floorplan, _room = floorplan_from_editor_payload(
        {
            "coordinate_unit": "cm",
            "width_cm": 400,
            "depth_cm": 300,
            "structures": {
                "walls": [{"start": {"x": 0, "y": 0}, "end": {"x": 400, "y": 0}}],
                "doors": [{"start": {"x": 100, "y": 0}, "end": {"x": 190, "y": 0}}],
            },
        }
    )

    assert floorplan["wall_segments"][0]["id"] == "wall-1"
    assert floorplan["door_segments"][0]["id"] == "door-1"


def test_auto_decor_uses_verified_floor_lamp_catalog_items() -> None:
    sofa = {
        "furniture_id": "sofa-existing",
        "normalized_type": "sofa",
        "name_zh_raw": "既有沙發",
        "size_cm": {"width": 210, "depth": 90, "height": 82},
        "position_cm": {"x": 0, "z": 120},
        "rotation_y_deg": 180,
        "position_locked": True,
    }

    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan_editor": _floorplan_editor(),
            "placement_room_id": "living-1",
            "scene_objects": [sofa],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    generated = [item for item in payload["scene_objects"] if item.get("auto_decor_role")]
    assert {item["auto_decor_role"] for item in generated} == {"curtain", "rug", "plant", "light"}
    assert payload["decor_summary"]["unavailable"] == []
    assert all(item["model_url"] for item in generated)
    assert all(item["placement_engine"] == "furniture_engine" for item in generated)
    assert all(item["placement_failed"] is False for item in generated)
    light = next(item for item in generated if item["auto_decor_role"] == "light")
    assert light["normalized_type"] == "floor-lamp"

    rug = next(item for item in generated if item["auto_decor_role"] == "rug")
    assert rug["position_cm"] == sofa["position_cm"]

    curtain = next(item for item in generated if item["auto_decor_role"] == "curtain")
    assert curtain["size_cm"]["width"] == 330
    assert curtain["position_cm"]["z"] < -200
    assert curtain["rotation_y_deg"] == 0


def test_rug_relation_is_validated_by_the_engine() -> None:
    room = Room(width=700, depth=500, walls=[])
    sofa_catalog = catalog_item_from_scene_object("sofa", "沙發", 210, 90, 82)
    rug_catalog = catalog_item_from_scene_object("large-medium-rug", "地毯", 180, 120, 1)
    sofa = PlacedFurniture(
        id="sofa",
        catalog=sofa_catalog,
        pos_x=350,
        pos_y=350,
        rotation=180,
    )

    result = place_overlay_on_furniture(room, rug_catalog, "rug", sofa)

    assert result["success"] is True
    assert result["reason"] is None
    assert result["placed"].pos_x == sofa.pos_x
    assert result["placed"].pos_y == sofa.pos_y


def test_empty_room_does_not_receive_scattered_decor() -> None:
    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan_editor": _floorplan_editor(),
            "placement_room_id": "living-1",
            "scene_objects": [],
        },
    )

    assert response.status_code == 200
    generated = [
        item
        for item in response.json()["scene_objects"]
        if item.get("auto_decor_role")
    ]
    assert {item["auto_decor_role"] for item in generated} == {"curtain"}


def test_confirmed_bedroom_type_allows_rug_and_verified_floor_lamp_only() -> None:
    bed = {
        "furniture_id": "bed-existing",
        "normalized_type": "bed-frame",
        "name_zh_raw": "雙人床",
        "size_cm": {"width": 160, "depth": 200, "height": 40},
        "position_cm": {"x": 0, "z": 0},
        "position_locked": True,
    }
    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan": {
                "width_cm": 700,
                "depth_cm": 500,
                "room_regions": [
                    {
                        "exterior": [[-3.5, -2.5], [3.5, -2.5], [3.5, 2.5], [-3.5, 2.5]],
                        "holes": [],
                    }
                ],
            },
            "room": {"id": "bedroom-1", "type": "bedroom"},
            "placement_room_id": "bedroom-1",
            "scene_objects": [bed],
        },
    )

    assert response.status_code == 200
    roles = {
        item["auto_decor_role"]
        for item in response.json()["scene_objects"]
        if item.get("auto_decor_role")
    }
    assert roles == {"rug", "light"}


def test_decor_does_not_use_furniture_assigned_to_another_room() -> None:
    bedroom_bed = {
        "furniture_id": "bedroom-bed",
        "normalized_type": "bed-frame",
        "name_zh_raw": "臥室雙人床",
        "size_cm": {"width": 160, "depth": 200, "height": 40},
        "position_cm": {"x": 0, "z": 0},
        "position_locked": True,
        "placement_room_id": "bedroom-1",
    }
    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan": {
                "width_cm": 700,
                "depth_cm": 500,
                "room_regions": [
                    {
                        "exterior": [[-3.5, -2.5], [3.5, -2.5], [3.5, 2.5], [-3.5, 2.5]],
                        "holes": [],
                    }
                ],
            },
            "room": {"id": "balcony-1", "type": "balcony"},
            "placement_room_id": "balcony-1",
            "scene_objects": [bedroom_bed],
        },
    )

    assert response.status_code == 200
    roles = {
        item["auto_decor_role"]
        for item in response.json()["scene_objects"]
        if item.get("auto_decor_role")
    }
    assert roles == {"plant"}


def test_redecorating_replaces_legacy_duplicates_and_uses_unique_models() -> None:
    sofa = {
        "furniture_id": "sofa-existing",
        "normalized_type": "sofa",
        "name_zh_raw": "既有沙發",
        "size_cm": {"width": 210, "depth": 90, "height": 82},
        "position_cm": {"x": 0, "z": 120},
        "rotation_y_deg": 180,
        "position_locked": True,
    }
    duplicated_legacy = {
        "furniture_id": "duplicated-decor-model",
        "normalized_type": "floor-lamp",
        "name_zh_raw": "舊自動燈具",
        "size_cm": {"width": 35, "depth": 35, "height": 150},
        "position_cm": {"x": 0, "z": 0},
        "auto_decor_role": "light",
    }

    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan_editor": _floorplan_editor(),
            "placement_room_id": "living-1",
            "scene_objects": [sofa, duplicated_legacy, dict(duplicated_legacy)],
        },
    )

    assert response.status_code == 200
    generated = [
        item
        for item in response.json()["scene_objects"]
        if item.get("auto_decor_role")
    ]
    roles = [item["auto_decor_role"] for item in generated]
    assert len(roles) == len(set(roles))
    catalog_ids = [
        item["furniture_id"]
        for item in generated
        if item["auto_decor_role"] != "curtain"
    ]
    assert len(catalog_ids) == len(set(catalog_ids))
    assert "duplicated-decor-model" not in catalog_ids


def test_large_furniture_uses_a_wall_anchor() -> None:
    items = [
        {
            "furniture_id": "wardrobe-1",
            "normalized_type": "wardrobe",
            "name_zh_raw": "大型衣櫃",
            "size_cm": {"width": 180, "depth": 60, "height": 220},
        }
    ]

    [placed] = generate_layout(700, 500, items)

    half_room_width = 350
    half_room_depth = 250
    half_width = placed["footprint_cm"]["width"] / 2
    half_depth = placed["footprint_cm"]["depth"] / 2
    wall_gap = min(
        half_room_width - abs(placed["position_cm"]["x"]) - half_width,
        half_room_depth - abs(placed["position_cm"]["z"]) - half_depth,
    )
    assert placed["placement_failed"] is False
    assert wall_gap <= 12


def test_scene_contract_preserves_2d_room_assignment() -> None:
    item = {
        "furniture_id": "bedroom-1-bed",
        "normalized_type": "bed",
        "name_zh_raw": "雙人床",
        "size_cm": {"width": 152, "depth": 200, "height": 55},
        "position_cm": {"x": -150, "z": 100},
        "position_locked": True,
        "placement_room_id": "bedroom-1",
    }

    [placed] = generate_layout(700, 500, [item])

    assert placed["placement_room_id"] == "bedroom-1"


def test_kitchen_gets_rug_but_no_floor_lamp() -> None:
    """落地燈屬起居/閱讀情境:餐廚(餐桌)不配落地燈,照明交天花吊燈方案;
    餐桌下的地毯照舊。"""
    table = {
        "furniture_id": "table-existing",
        "normalized_type": "dining-table",
        "name_zh_raw": "既有餐桌",
        "size_cm": {"width": 160, "depth": 90, "height": 75},
        "position_cm": {"x": 0, "z": 0},
        "rotation_y_deg": 0,
        "position_locked": True,
        "placement_room_id": "kitchen-1",
    }

    response = client.post(
        "/api/scene/decorate",
        json={
            "style": "scandinavian",
            "floorplan": {
                "coordinate_unit": "cm",
                "width_cm": 700,
                "depth_cm": 500,
                "room_regions": [
                    {
                        "room_id": "kitchen-1",
                        "room_type": "kitchen",
                        "exterior": [[-350, -250], [350, -250], [350, 250], [-350, 250]],
                        "holes": [],
                    }
                ],
            },
            "room": {"id": "kitchen-1", "type": "kitchen"},
            "placement_room_id": "kitchen-1",
            "scene_objects": [table],
        },
    )

    assert response.status_code == 200
    roles = {
        item["auto_decor_role"]
        for item in response.json()["scene_objects"]
        if item.get("auto_decor_role")
    }
    assert "light" not in roles
    assert "rug" in roles
