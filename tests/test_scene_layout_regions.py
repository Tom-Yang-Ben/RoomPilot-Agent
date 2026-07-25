from pathlib import Path

from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_layout_variant_b_uses_a_different_engine_validated_candidate() -> None:
    payload = {
        "floorplan_editor": {
            "coordinate_unit": "cm",
            "width_cm": 600,
            "depth_cm": 500,
            "room_height_cm": 270,
            "rooms": [{
                "id": "bedroom-1",
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 600, "y": 0},
                    {"x": 600, "y": 500},
                    {"x": 0, "y": 500},
                ],
            }],
            "structures": {"walls": [], "doors": [], "windows": [], "beams": [], "columns": []},
        },
        "placement_room_id": "bedroom-1",
        "scene_objects": [{
            "furniture_id": "wardrobe-1",
            "name_zh_raw": "衣櫃",
            "normalized_type": "wardrobe",
            "size_cm": {"width": 120, "depth": 60, "height": 200},
        }],
    }
    scheme_a = client.post("/api/scene/layout", json={**payload, "placement_variant": "A"})
    scheme_b = client.post("/api/scene/layout", json={**payload, "placement_variant": "B"})

    assert scheme_a.status_code == 200
    assert scheme_b.status_code == 200
    item_a = scheme_a.json()["scene_objects"][0]
    item_b = scheme_b.json()["scene_objects"][0]
    assert item_a.get("placement_failed") is not True
    assert item_b.get("placement_failed") is not True
    assert (
        item_a["position_cm"] != item_b["position_cm"]
        or item_a["rotation_y_deg"] != item_b["rotation_y_deg"]
    )


def test_layout_places_furniture_in_requested_room_region() -> None:
    floorplan = {
        "width_cm": 1000,
        "depth_cm": 600,
        "room_regions": [
            {
                "room_id": "living-room",
                "exterior": [[-5, -3], [1, -3], [1, 3], [-5, 3]],
                "holes": [],
            },
            {
                "room_id": "bedroom-1",
                "exterior": [[2, -2], [5, -2], [5, 2], [2, 2]],
                "holes": [],
            },
        ],
    }
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan": floorplan,
            "placement_room_id": "bedroom-1",
            "scene_objects": [
                {
                    "furniture_id": "bed-1",
                    "name_zh_raw": "床",
                    "normalized_type": "bed",
                    "size_cm": {"width": 160, "depth": 200, "height": 82},
                    "position_cm": {"x": 0, "z": 0},
                    "rotation_y_deg": 0,
                }
            ],
        },
    )

    assert response.status_code == 200
    item = response.json()["scene_objects"][0]
    assert item.get("placement_failed") is not True
    # bedroom-1 的中心原點 x 範圍是 2..5m；家具中心應落在該房間，而非較大的客廳。
    assert 200 <= item["position_cm"]["x"] <= 500


def test_wall_furniture_anchors_to_the_requested_room_boundary() -> None:
    floorplan = {
        "width_cm": 949.8,
        "depth_cm": 1044.43,
        "room_regions": [
            {
                "room_id": "storage-1",
                "room_type": "storage",
                "exterior": [
                    [-4.504, -3.1492],
                    [-0.131, -3.1492],
                    [-0.131, 0.7178],
                    [-4.504, 0.7178],
                ],
                "holes": [],
            },
        ],
    }
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan": floorplan,
            "placement_room_id": "storage-1",
            "scene_objects": [
                {
                    "furniture_id": "storage-cabinet-1",
                    "name_zh_raw": "storage cabinet",
                    "normalized_type": "storage-cabinet",
                    "size_cm": {"width": 120, "depth": 45, "height": 75},
                    "position_locked": False,
                }
            ],
        },
    )

    assert response.status_code == 200
    item = response.json()["scene_objects"][0]
    assert item["placement_failed"] is False
    x_cm = item["position_cm"]["x"]
    z_cm = item["position_cm"]["z"]
    footprint = item["footprint_cm"]
    wall_gap_cm = min(
        x_cm - (-450.4) - footprint["width"] / 2,
        -13.1 - x_cm - footprint["width"] / 2,
        z_cm - (-314.92) - footprint["depth"] / 2,
        71.78 - z_cm - footprint["depth"] / 2,
    )
    assert -1 <= wall_gap_cm <= 12


def test_manual_wall_snap_is_resolved_by_the_backend_layout_engine() -> None:
    floorplan = {
        "width_cm": 949.8,
        "depth_cm": 1044.43,
        "room_regions": [
            {
                "room_id": "storage-1",
                "room_type": "storage",
                "exterior": [
                    [-4.504, -3.1492],
                    [-0.131, -3.1492],
                    [-0.131, 0.7178],
                    [-4.504, 0.7178],
                ],
                "holes": [],
            },
        ],
    }
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan": floorplan,
            "placement_room_id": "storage-1",
            "scene_objects": [
                {
                    "furniture_id": "storage-cabinet-1",
                    "name_zh_raw": "storage cabinet",
                    "normalized_type": "storage-cabinet",
                    "size_cm": {"width": 120, "depth": 45, "height": 75},
                    "position_locked": False,
                    "placement_hint_cm": {"x": -40, "z": -100},
                }
            ],
        },
    )
    assert response.status_code == 200
    item = response.json()["scene_objects"][0]
    assert item["placement_failed"] is False
    assert -60 <= item["position_cm"]["x"] <= -20
    assert item["rotation_y_deg"] == 90


def test_step6_drag_commits_backend_wall_snap_inside_original_room() -> None:
    source = (
        ROOT / "backend" / "server" / "static" / "scene_v2.js"
    ).read_text(encoding="utf-8")
    finish_drag = source.split("async function finishFurnitureDrag", 1)[1].split(
        "function addFurnitureFromLibrary", 1
    )[0]

    assert "resolveFurniturePosition" in finish_drag
    assert "resolved.position_cm" in finish_drag
    assert "resolved.rotation_y_deg" in finish_drag
    resolve_position = source.split("async function resolveFurniturePosition", 1)[1].split(
        "async function finishFurnitureDrag", 1
    )[0]
    assert "placement_room_id: item.roomId" in resolve_position
    assert "placement_hint_cm" in resolve_position
    assert "position_locked: true" in resolve_position
