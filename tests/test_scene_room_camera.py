"""逐房鏡頭必須是世界座標（QA 2026-08-01 BLOCKER #1）。

scene_json 的 polygon_cm 走場景座標，viewer 的世界 z 與場景 z 反向。舊版把
場景 z 原樣交給 setCameraState，每間房的鏡頭都落在 x 軸鏡像的位置——廚房視角
照到床、臥室視角照到餐桌，第 8 步逐房生圖的輸入也整批是錯的。
"""

from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


CAMERA_MODULE = STATIC_DIR / "scene_camera.js"


def _suggestion(room: dict, floorplan: dict) -> dict:
    module_uri = CAMERA_MODULE.as_uri()
    return run_workflow_script(
        f"""
        import {{ roomCameraSuggestion, sceneToWorldZCm }} from {json.dumps(module_uri)};
        const suggestion = roomCameraSuggestion({json.dumps(room)}, {json.dumps(floorplan)});
        console.log(JSON.stringify({{
          suggestion,
          worldZOfSceneZ100: sceneToWorldZCm(100),
        }}));
        """
    )


def test_room_camera_target_is_the_world_space_room_centre() -> None:
    # 房間中心在場景座標 (150, 300)；平面 400x400 → 場景中心相對值 (-50, +100)。
    floorplan = {"width_cm": 400, "depth_cm": 400}
    room = {
        "polygon_cm": [
            {"x": 100, "y": 250},
            {"x": 200, "y": 250},
            {"x": 200, "y": 350},
            {"x": 100, "y": 350},
        ]
    }

    result = _suggestion(room, floorplan)
    target_x, target_y, target_z = result["suggestion"]["target_cm"]

    assert target_x == -50
    assert target_y == 82
    # 場景 z = +100 → 世界 z = -100。翻面沒做的話這裡會是 +100。
    assert target_z == -100
    assert result["worldZOfSceneZ100"] == -100


def test_two_rooms_keep_their_relative_order_along_z() -> None:
    """北側房間的世界 z 必須小於南側，否則鏡頭會整組對調。"""
    floorplan = {"width_cm": 400, "depth_cm": 400}
    north = {"polygon_cm": [
        {"x": 0, "y": 0}, {"x": 200, "y": 0}, {"x": 200, "y": 100}, {"x": 0, "y": 100},
    ]}
    south = {"polygon_cm": [
        {"x": 0, "y": 300}, {"x": 200, "y": 300}, {"x": 200, "y": 400}, {"x": 0, "y": 400},
    ]}

    north_z = _suggestion(north, floorplan)["suggestion"]["target_cm"][2]
    south_z = _suggestion(south, floorplan)["suggestion"]["target_cm"][2]

    assert north_z > south_z


def test_missing_polygon_falls_back_without_throwing() -> None:
    result = _suggestion({}, {})
    suggestion = result["suggestion"]

    assert suggestion["camera_type"] == "perspective"
    assert suggestion["preset"] == "room"
    assert len(suggestion["position_cm"]) == 3
    assert all(isinstance(value, (int, float)) for value in suggestion["target_cm"])


def test_narrow_room_candidates_are_clamped_into_lockable_space() -> None:
    """陽台級窄房間（80×300）：外接框比例推的候選鏡頭貼牆或出牆，
    三個候選一起死在 validateRoomCamera，第 7 步逐房視角卡死（floor04 實測）。
    clampRoomCamera 必須把它們夾回房內合法區。"""
    module_uri = CAMERA_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{
          clampRoomCamera, roomCameraSuggestion, validateRoomCamera,
        }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 400, depth_cm: 400 }};
        const room = {{ polygon_cm: [
          {{ x: 100, y: 50 }}, {{ x: 180, y: 50 }},
          {{ x: 180, y: 350 }}, {{ x: 100, y: 350 }},
        ] }};
        const base = roomCameraSuggestion(room, floorplan);
        const [x, y, z] = base.position_cm;
        const [tx, ty, tz] = base.target_cm;
        // scene_v2 的「活動視角」公式：把水平偏移旋轉 90 度。80cm 寬的房間會
        // 直接把鏡頭轉出牆外。
        const rotated = {{ ...base, position_cm: [tx + (z - tz), y, tz - (x - tx)] }};
        console.log(JSON.stringify({{
          rotated_raw: validateRoomCamera(rotated, room, floorplan),
          rotated_clamped: validateRoomCamera(
            clampRoomCamera(rotated, room, floorplan), room, floorplan),
          base_clamped: validateRoomCamera(
            clampRoomCamera(base, room, floorplan), room, floorplan),
        }}));
        """
    )

    assert result["rotated_raw"]["valid"] is False, "夾回前必須真的是壞鏡頭，測試才有意義"
    assert result["rotated_clamped"]["valid"] is True
    assert result["base_clamped"]["valid"] is True


def test_clamp_keeps_already_valid_cameras_untouched() -> None:
    module_uri = CAMERA_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ clampRoomCamera, roomCameraSuggestion }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 400, depth_cm: 400 }};
        const room = {{ polygon_cm: [
          {{ x: 100, y: 100 }}, {{ x: 300, y: 100 }},
          {{ x: 300, y: 300 }}, {{ x: 100, y: 300 }},
        ] }};
        const base = roomCameraSuggestion(room, floorplan);
        const clamped = clampRoomCamera(base, room, floorplan);
        console.log(JSON.stringify({{
          position_same: clamped.position_cm.every(
            (value, index) => Math.abs(value - base.position_cm[index]) < 1e-6),
          target_same: clamped.target_cm.every(
            (value, index) => Math.abs(value - base.target_cm[index]) < 1e-6),
        }}));
        """
    )

    assert result == {"position_same": True, "target_same": True}


def test_room_camera_validation_rejects_views_behind_room_walls() -> None:
    module_uri = CAMERA_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ roomCameraSuggestion, validateRoomCamera }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 400, depth_cm: 400 }};
        const room = {{ polygon_cm: [
          {{ x: 100, y: 100 }}, {{ x: 300, y: 100 }},
          {{ x: 300, y: 300 }}, {{ x: 100, y: 300 }},
        ] }};
        const suggested = roomCameraSuggestion(room, floorplan);
        const outside = {{ ...suggested, position_cm: [260, 145, 260] }};
        console.log(JSON.stringify({{
          suggested: validateRoomCamera(suggested, room, floorplan),
          outside: validateRoomCamera(outside, room, floorplan),
        }}));
        """
    )

    assert result["suggested"]["valid"] is True
    assert result["outside"] == {
        "valid": False,
        "code": "camera_position_outside_room",
    }


def _validate_targets(targets: dict[str, list[float]]) -> dict:
    """固定房間與相機，只改 target_cm，回傳每個 target 的驗證結果。"""
    module_uri = CAMERA_MODULE.as_uri()
    return run_workflow_script(
        f"""
        import {{ validateRoomCamera }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 400, depth_cm: 400 }};
        const room = {{ polygon_cm: [
          {{ x: 100, y: 100 }}, {{ x: 300, y: 100 }},
          {{ x: 300, y: 300 }}, {{ x: 100, y: 300 }},
        ] }};
        const base = {{
          camera_type: "perspective", position_cm: [0, 145, 0],
          up: [0, 1, 0], fov_deg: 58, zoom: 1,
        }};
        const targets = {json.dumps(targets)};
        console.log(JSON.stringify(Object.fromEntries(
          Object.entries(targets).map(([name, target_cm]) => [
            name, validateRoomCamera({{ ...base, target_cm }}, room, floorplan),
          ]),
        )));
        """
    )


def test_target_exactly_on_a_wall_counts_as_inside_the_room() -> None:
    """`pointInPolygon` 的 `pointOnSegment` 分支：邊界算室內。

    scene_camera.js 的 pointInPolygon 與 scene_plan_geometry.js 的 pointInPolygonCm
    是兩份不同實作，差別就在這條分支——後者是標準 ray casting，邊界未定義。將來若
    要把兩者併成同一個函式，必須保留這個語意（例如帶 includeBoundary 選項），否則
    target 落在牆線上的逐房鏡頭會整批變成 camera_target_outside_room。

    容差是下在**外積**上的（scene_camera.js 的 pointOnSegment，tolerance 0.01），
    所以等效的垂距容差會隨邊長縮放：200cm 的牆約為 5e-5 cm。這裡只釘住「牆上算內、
    0.01cm 外算外」，不釘那個縮放行為——換成以垂距為準的實作也應該通過。

    平面座標換算：world x + 200 = plan x、200 - world z = plan y，房間是 plan
    (100,100)-(300,300)，所以 world x=100 正好落在 plan x=300 那面牆上。
    """
    result = _validate_targets(
        {
            "on_wall": [100, 82, 0],
            "on_corner": [100, 82, 100],
            "just_inside": [99.99, 82, 0],
            "just_outside": [100.01, 82, 0],
            "far_outside": [150, 82, 0],
        }
    )

    assert result["on_wall"]["valid"] is True, "target 落在牆線上必須算室內"
    assert result["on_corner"]["valid"] is True, "target 落在轉角必須算室內"
    assert result["just_inside"]["valid"] is True
    assert result["just_outside"] == {
        "valid": False,
        "code": "camera_target_outside_room",
    }
    assert result["far_outside"]["code"] == "camera_target_outside_room"


def test_position_on_a_wall_is_rejected_by_clearance_not_by_containment() -> None:
    """position 走不到邊界分支——8cm 淨空檢查會先擋下來。

    所以 pointInPolygon 的邊界語意只對 target 有實質影響。釘住這點是為了讓將來
    評估合併風險的人不必重推：position 那條線怎麼改都不會改變結果。
    """
    module_uri = CAMERA_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ validateRoomCamera }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 400, depth_cm: 400 }};
        const room = {{ polygon_cm: [
          {{ x: 100, y: 100 }}, {{ x: 300, y: 100 }},
          {{ x: 300, y: 300 }}, {{ x: 100, y: 300 }},
        ] }};
        console.log(JSON.stringify(validateRoomCamera({{
          camera_type: "perspective",
          position_cm: [100, 145, 0],
          target_cm: [0, 82, 0],
          up: [0, 1, 0], fov_deg: 58, zoom: 1,
        }}, room, floorplan)));
        """
    )

    assert result == {"valid": False, "code": "camera_too_close_to_wall"}
