from pathlib import Path

from fastapi.testclient import TestClient

from backend.server.main import app
from backend.server.scene_service import (
    orient_layout_toward_targets,
    validate_single_placement,
)


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_window_clearance_rejects_furniture_in_front_of_confirmed_window() -> None:
    floorplan = {
        "coordinate_unit": "cm",
        "width_cm": 600,
        "depth_cm": 500,
        "window_segments": [
            {
                "start": {"x": -100, "z": -250},
                "end": {"x": 100, "z": -250},
                "window_type": "floor-to-ceiling",
            }
        ],
    }
    result = validate_single_placement(
        floorplan,
        {
            "furniture_id": "chair-1",
            "normalized_type": "armchair",
            "size_cm": {"width": 80, "depth": 80, "height": 90},
            "position_cm": {"x": 0, "z": -170},
            "rotation_y_deg": 0,
        },
        [],
    )

    assert result["ok"] is False
    assert "窗戶" in result["reason"]


def test_automatic_chair_faces_the_nearest_desk() -> None:
    scene_objects = [
        {
            "furniture_id": "desk-1",
            "normalized_type": "desk",
            "position_cm": {"x": 0, "z": -120},
            "position_locked": True,
            "placement_failed": False,
        },
        {
            "furniture_id": "chair-1",
            "normalized_type": "office-chair",
            "position_cm": {"x": 0, "z": 20},
            "position_locked": False,
            "placement_failed": False,
            "rotation_y_deg": 0,
        },
    ]

    oriented = orient_layout_toward_targets(scene_objects)

    assert oriented[1]["rotation_y_deg"] == 180
    assert oriented[1]["facing_target_id"] == "desk-1"


def test_orientation_pass_keeps_wall_anchored_sofa_and_snaps_chairs_to_axis() -> None:
    """沙發朝向由所靠的牆決定,orientation pass 不得再把它轉向最近的茶几;
    自由座椅(扶手椅)轉向目標時角度貼齊 90°,不產生斜角足跡。"""
    scene_objects = [
        {
            "furniture_id": "sofa-1",
            "normalized_type": "sofa",
            "position_cm": {"x": 0, "z": 150},
            "rotation_y_deg": 180,
            "position_locked": False,
            "placement_failed": False,
        },
        {
            "furniture_id": "ct-1",
            "normalized_type": "coffee-table",
            "position_cm": {"x": 80, "z": 40},
            "rotation_y_deg": 0,
            "position_locked": False,
            "placement_failed": False,
        },
        {
            "furniture_id": "armchair-1",
            "normalized_type": "armchair",
            "position_cm": {"x": -30, "z": 40},
            "rotation_y_deg": 0,
            "position_locked": False,
            "placement_failed": False,
        },
    ]

    oriented = orient_layout_toward_targets(scene_objects)

    assert oriented[0]["rotation_y_deg"] == 180
    assert "facing_target_id" not in oriented[0]
    # 扶手椅最近目標是茶几(dx=110, dz=0),atan2 → 90°,貼齊後仍 90°
    assert oriented[2]["rotation_y_deg"] == 90
    assert oriented[2]["facing_target_id"] == "ct-1"


def test_viewer_keeps_boundary_walls_in_room_finish_and_door_inside_snapped_assembly() -> None:
    source = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    resolver = source.split("function wallMaterialResolver", 1)[1].split(
        "function createFloorMaterial", 1
    )[0]
    opening = source.split("function buildOpeningAssembly", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]

    assert "function roomOverrideForInteriorPoint" in resolver
    assert "return materialForOverride(roomOverrideForInteriorPoint(sample));" in resolver
    assert 'roompilotWallSurfaceRole = "exterior"' not in resolver
    assert "leaf.position.set(0, centerY, 0)" in opening
    assert "assembly.add(leaf)" in opening
    assert "roomGroupRef.add(hingeGroup)" not in opening


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
    # 貼右牆(x 較大側)背對牆、正面朝 -x(房內)= 270。
    # 舊值 90 是鏡像慣例的特徵化殘留:rot=0 正面朝 +z,90 會臉貼右牆。
    assert item["rotation_y_deg"] == 270


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
