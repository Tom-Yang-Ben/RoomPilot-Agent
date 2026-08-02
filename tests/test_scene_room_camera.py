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
