
from fastapi.testclient import TestClient

from backend.paths import STATIC_DIR
from backend.server.main import app
from backend.server.scene_service import (
    orient_layout_toward_targets,
    validate_single_placement,
)


client = TestClient(app)


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
    assert "落地窗" in result["reason"]


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


def test_viewer_keeps_boundary_walls_exterior_and_door_inside_snapped_assembly() -> None:
    source = (
        STATIC_DIR / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    resolver = source.split("function wallMaterialResolver", 1)[1].split(
        "function createFloorMaterial", 1
    )[0]
    opening = source.split("function buildOpeningAssembly", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]

    assert "isExteriorWallSegment(segment, sceneData.floorplan)" in resolver
    assert "segment.boundary_side" in resolver
    assert 'roompilotWallSurfaceRole = "exterior"' in resolver
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


def _multi_item_bedroom_payload() -> dict:
    """一間放滿貼牆家具的臥室——逐房 A/B 比較實際會送的形狀。"""
    return {
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
        "scene_objects": [
            {
                "furniture_id": "bed-1",
                "name_zh_raw": "雙人床",
                "normalized_type": "bed",
                "size_cm": {"width": 150, "depth": 200, "height": 45},
            },
            {
                "furniture_id": "wardrobe-1",
                "name_zh_raw": "雙門衣櫃",
                "normalized_type": "wardrobe",
                "size_cm": {"width": 120, "depth": 60, "height": 200},
            },
            {
                "furniture_id": "bookcase-1",
                "name_zh_raw": "書櫃",
                "normalized_type": "bookcase",
                "size_cm": {"width": 160, "depth": 40, "height": 202},
            },
            {
                "furniture_id": "cabinet-1",
                "name_zh_raw": "收納櫃",
                "normalized_type": "cabinet",
                "size_cm": {"width": 80, "depth": 42, "height": 64},
            },
        ],
    }


def _layout_items(payload: dict, variant: str) -> dict:
    response = client.post("/api/scene/layout", json={**payload, "placement_variant": variant})
    assert response.status_code == 200
    return {item["furniture_id"]: item for item in response.json()["scene_objects"]}


def test_layout_variant_b_does_not_collapse_every_item_to_one_orientation() -> None:
    """方案 B 必須仍是「排過的房間」,不是整房 0° 排排站。

    候選清單尾巴是一組 0° 網格保底位置。B 若用「整份候選反轉」產生,網格會
    排到最前面,貼牆家具全部改拿 0° 網格點——使用者選了 B 就得到一個比 A 難看
    的版面(實測:臥室八件全部 rotation 0,座標落在規則格子上)。
    """
    payload = _multi_item_bedroom_payload()
    items_a = _layout_items(payload, "A")
    items_b = _layout_items(payload, "B")

    for items in (items_a, items_b):
        for item in items.values():
            assert item.get("placement_failed") is not True

    rotations_b = {item["rotation_y_deg"] for item in items_b.values()}
    assert len(rotations_b) > 1, (
        f"方案 B 的家具朝向全部塌成同一個角度 {rotations_b},是候選網格搶先的排排站版面"
    )

    differences = [
        furniture_id
        for furniture_id, item_a in items_a.items()
        if item_a["position_cm"] != items_b[furniture_id]["position_cm"]
        or item_a["rotation_y_deg"] != items_b[furniture_id]["rotation_y_deg"]
    ]
    assert differences, "方案 B 與方案 A 完全相同,逐房 A/B 選擇會變成沒有作用"


def test_layout_variant_b_keeps_wall_anchored_furniture_against_a_wall() -> None:
    """B 是「換一面主牆」,不是「丟到房間中央」:貼牆家具仍要貼著某一面牆。"""
    payload = _multi_item_bedroom_payload()
    items_b = _layout_items(payload, "B")

    for furniture_id in ("wardrobe-1", "bookcase-1"):
        item = items_b[furniture_id]
        footprint = item["footprint_cm"]
        x_cm, z_cm = item["position_cm"]["x"], item["position_cm"]["z"]
        wall_gap_cm = min(
            x_cm + 300 - footprint["width"] / 2,
            300 - x_cm - footprint["width"] / 2,
            z_cm + 250 - footprint["depth"] / 2,
            250 - z_cm - footprint["depth"] / 2,
        )
        assert wall_gap_cm <= 15, f"{furniture_id} 離最近的牆 {wall_gap_cm:.1f}cm,不再是貼牆擺放"


def test_layout_variant_a_is_unaffected_by_the_variant_b_anchors() -> None:
    """方案 A 不因 B 的鏡射錨點而漂移:同輸入必得同輸出,且與未指定 variant 相同。"""
    payload = _multi_item_bedroom_payload()
    explicit = client.post("/api/scene/layout", json={**payload, "placement_variant": "A"})
    default = client.post("/api/scene/layout", json={**payload})

    assert explicit.status_code == 200
    assert default.status_code == 200
    assert explicit.json()["scene_objects"] == default.json()["scene_objects"]


def _room_payload(scene_objects: list[dict], room_id: str = "room-a") -> dict:
    return {
        "floorplan_editor": {
            "coordinate_unit": "cm",
            "width_cm": 600,
            "depth_cm": 500,
            "room_height_cm": 270,
            "rooms": [{
                "id": room_id,
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 600, "y": 0},
                    {"x": 600, "y": 500},
                    {"x": 0, "y": 500},
                ],
            }],
            "structures": {"walls": [], "doors": [], "windows": [], "beams": [], "columns": []},
        },
        "placement_room_id": room_id,
        "scene_objects": scene_objects,
    }


def _wall_gap_cm(item: dict, half_width_cm: float = 300.0, half_depth_cm: float = 250.0) -> float:
    """家具外框離最近一面房間牆的距離(房間為以原點為中心的矩形)。"""
    footprint = item["footprint_cm"]
    x_cm, z_cm = item["position_cm"]["x"], item["position_cm"]["z"]
    return min(
        x_cm + half_width_cm - footprint["width"] / 2,
        half_width_cm - x_cm - footprint["width"] / 2,
        z_cm + half_depth_cm - footprint["depth"] / 2,
        half_depth_cm - z_cm - footprint["depth"] / 2,
    )


def test_catalog_subdivided_types_reach_the_same_anchors_as_their_family() -> None:
    """型錄用細分名(cabinet-cupboard / fabric-sofa),擺放錨點用粗分名。

    沒有對照的話這些型別一條 elif 都比對不到,只拿得到「房間正中心」加 3×3 網格,
    於是站在房間中央不貼牆——型錄裡這樣的落地家具有 3,373 件。
    """
    payload = _room_payload([
        {
            "furniture_id": "cabinet-1",
            "name_zh_raw": "收納櫃",
            "normalized_type": "cabinet-cupboard",
            "size_cm": {"width": 120, "depth": 42, "height": 200},
        },
        {
            "furniture_id": "sofa-1",
            "name_zh_raw": "布沙發",
            "normalized_type": "fabric-sofa",
            "size_cm": {"width": 210, "depth": 90, "height": 85},
        },
    ])
    items = {item["furniture_id"]: item for item in
             client.post("/api/scene/layout", json=payload).json()["scene_objects"]}

    for furniture_id in ("cabinet-1", "sofa-1"):
        item = items[furniture_id]
        assert item.get("placement_failed") is not True
        gap = _wall_gap_cm(item)
        assert gap <= 15, f"{furniture_id} 離最近的牆 {gap:.1f}cm,沒有拿到族系錨點"


def test_extra_cabinets_slide_along_the_wall_instead_of_parking_mid_room() -> None:
    """類型錨點只有 3 個離散貼牆點;第 4 個櫃體以前只能站在房間中央。"""
    payload = _room_payload([
        {
            "furniture_id": f"cabinet-{index}",
            "name_zh_raw": f"收納櫃{index}",
            "normalized_type": "cabinet-cupboard",
            "size_cm": {"width": 80, "depth": 42, "height": 200},
        }
        for index in range(1, 5)
    ])
    items = client.post("/api/scene/layout", json=payload).json()["scene_objects"]

    assert len(items) == 4
    for item in items:
        assert item.get("placement_failed") is not True
        gap = _wall_gap_cm(item)
        assert gap <= 15, f'{item["furniture_id"]} 離最近的牆 {gap:.1f}cm,停在房間中央'


def test_bedside_table_lands_beside_the_bed_not_in_a_corner() -> None:
    """床頭櫃的既有錨點是房間角落;床在房間中段時它會離床一公尺遠。"""
    payload = _room_payload([
        {
            "furniture_id": "bed-1",
            "name_zh_raw": "雙人床",
            "normalized_type": "bed",
            "size_cm": {"width": 152, "depth": 200, "height": 45},
        },
        {
            "furniture_id": "nightstand-1",
            "name_zh_raw": "床頭櫃",
            "normalized_type": "bedside-table",
            "size_cm": {"width": 45, "depth": 40, "height": 50},
        },
    ])
    items = {item["furniture_id"]: item for item in
             client.post("/api/scene/layout", json=payload).json()["scene_objects"]}
    bed, nightstand = items["bed-1"], items["nightstand-1"]
    assert nightstand.get("placement_failed") is not True

    gap_x = (
        abs(nightstand["position_cm"]["x"] - bed["position_cm"]["x"])
        - (bed["footprint_cm"]["width"] + nightstand["footprint_cm"]["width"]) / 2
    )
    overlap_z = (
        (bed["footprint_cm"]["depth"] + nightstand["footprint_cm"]["depth"]) / 2
        - abs(nightstand["position_cm"]["z"] - bed["position_cm"]["z"])
    )
    assert gap_x <= 12, f"床頭櫃離床側邊 {gap_x:.1f}cm,不是床頭櫃是孤島"
    assert overlap_z > 0, "床頭櫃沒有落在床身的長度範圍內"


def test_bedside_table_without_a_bed_still_gets_placed() -> None:
    """房裡沒有床時,床頭櫃必須退回一般錨點,不能因為找不到床就擺放失敗。"""
    payload = _room_payload([{
        "furniture_id": "nightstand-1",
        "name_zh_raw": "床頭櫃",
        "normalized_type": "bedside-table",
        "size_cm": {"width": 45, "depth": 40, "height": 50},
    }])
    item = client.post("/api/scene/layout", json=payload).json()["scene_objects"][0]
    assert item.get("placement_failed") is not True


def test_wall_mounted_item_hangs_on_the_requested_room_wall() -> None:
    """壁掛沿的必須是該房間的牆,不是整張平面圖的外框。

    多房平面圖裡,整圖外框的四面牆對這個房間而言在別人家裡,一路撲空後會退到
    房間代表點——鏡櫃因此浮在浴室正中央。
    """
    payload = {
        "floorplan_editor": {
            "coordinate_unit": "cm",
            "width_cm": 1000,
            "depth_cm": 800,
            "room_height_cm": 270,
            "rooms": [
                {
                    "id": "bathroom-1",
                    "polygon_cm": [
                        {"x": 620, "y": 500},
                        {"x": 980, "y": 500},
                        {"x": 980, "y": 780},
                        {"x": 620, "y": 780},
                    ],
                },
                {
                    "id": "living-1",
                    "polygon_cm": [
                        {"x": 20, "y": 20},
                        {"x": 600, "y": 20},
                        {"x": 600, "y": 780},
                        {"x": 20, "y": 780},
                    ],
                },
            ],
            "structures": {"walls": [], "doors": [], "windows": [], "beams": [], "columns": []},
        },
        "placement_room_id": "bathroom-1",
        "scene_objects": [{
            "furniture_id": "mirror-1",
            "name_zh_raw": "鏡櫃",
            "normalized_type": "mirror-cabinet",
            "size_cm": {"width": 60, "depth": 15, "height": 70},
        }],
    }
    item = client.post("/api/scene/layout", json=payload).json()["scene_objects"][0]
    assert item.get("placement_failed") is not True

    # 浴室在場景座標(以整圖中心為原點)的範圍
    x_cm, z_cm = item["position_cm"]["x"], item["position_cm"]["z"]
    left, right, top, bottom = 620 - 500, 980 - 500, 500 - 400, 780 - 400
    assert left <= x_cm <= right and top <= z_cm <= bottom, "壁掛跑出了指定的房間"
    gap = min(x_cm - left, right - x_cm, z_cm - top, bottom - z_cm)
    assert gap <= 40, f"鏡櫃離浴室最近的牆 {gap:.1f}cm,浮在房間中央"


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
        STATIC_DIR / "scene_v2.js"
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
