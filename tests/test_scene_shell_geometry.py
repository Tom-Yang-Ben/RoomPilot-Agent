"""房屋 3D 外殼純函式幾何層（scene_shell_geometry.js）單元測試。

對映 docs/3D房屋場景建置流程.md 的關鍵不變式：窗群聚 Union-Find、
windowPieces / openingInfill 雙路徑、estimateProfile 斷面推定、
floorBox 與 fitCameraPose、空輸入不崩潰。
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_MODULE = ROOT / "backend" / "server" / "static" / "scene_shell_geometry.js"


def run_shell_script(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def module_import(names: str) -> str:
    return f"import {{ {names} }} from {json.dumps(SHELL_MODULE.as_uri())};"


def test_window_symbol_lines_cluster_into_single_windows() -> None:
    result = run_shell_script(
        f"""
        {module_import('clusterOpeningSegments, DEFAULT_SCENE_CONFIG')}
        const reps = clusterOpeningSegments([
          {{ start: {{x: 0, z: 0}}, end: {{x: 120, z: 0}} }},
          {{ id: "w-1", start: {{x: -5, z: 8}}, end: {{x: 125, z: 8}} }},
          {{ start: {{x: 0, z: 16}}, end: {{x: 120, z: 16}} }},
          {{ id: "w-2", start: {{x: 300, z: 0}}, end: {{x: 420, z: 0}} }},
          {{ start: {{x: 500, z: 0}}, end: {{x: 520, z: 0}} }},
          {{ id: "w-c", confirmed: true, start: {{x: 600, z: 0}}, end: {{x: 625, z: 0}} }},
        ], DEFAULT_SCENE_CONFIG, "window");
        console.log(JSON.stringify(reps.map((rep) => rep.id || null)));
        """
    )
    # 辨識窗 w-1 與兩條無 ID 符號線 → 1 群取最長 w-1；短於 30cm 的無身份
    # 雜訊被丟棄；confirmed 短窗保留；依代表段中點 x 排序（60 < 360 < 612.5）。
    assert result == ["w-1", "w-2", "w-c"]


def test_distinct_ids_never_merge_and_symbol_lines_do() -> None:
    result = run_shell_script(
        f"""
        {module_import('clusterOpeningSegments, DEFAULT_SCENE_CONFIG')}
        const confirmedPair = clusterOpeningSegments([
          {{ id: "win-a", start: {{x: 0, z: 0}}, end: {{x: 90, z: 0}} }},
          {{ id: "win-b", start: {{x: 0, z: 10}}, end: {{x: 90, z: 10}} }},
        ], DEFAULT_SCENE_CONFIG, "window");
        const symbolPair = clusterOpeningSegments([
          {{ start: {{x: 0, z: 0}}, end: {{x: 90, z: 0}} }},
          {{ start: {{x: 0, z: 10}}, end: {{x: 90, z: 10}} }},
        ], DEFAULT_SCENE_CONFIG, "window");
        console.log(JSON.stringify({{
          confirmedCount: confirmedPair.length,
          symbolCount: symbolPair.length,
        }}));
        """
    )
    # 第 4 步擁有開口身份：不同非空 ID 永不合併；無 ID 符號線照文件合併。
    assert result == {"confirmedCount": 2, "symbolCount": 1}


def test_window_pieces_split_glass_and_infill() -> None:
    result = run_shell_script(
        f"""
        {module_import('windowPieces, shellConfig')}
        const cfg = shellConfig({{}});
        const window = {{
          id: "w-1",
          sill_height_cm: 90,
          height_cm: 120,
          start: {{x: 0, z: 0}},
          end: {{x: 200, z: 0}},
        }};
        const door = {{
          id: "d-1",
          height_cm: 210,
          start: {{x: 400, z: 0}},
          end: {{x: 490, z: 0}},
        }};
        console.log(JSON.stringify({{
          window: windowPieces(window, cfg, {{ kind: "window" }}),
          door: windowPieces(door, cfg, {{ kind: "door" }}),
        }}));
        """
    )
    window_pieces = result["window"]
    by_role = {piece["role"]: piece for piece in window_pieces}
    assert set(by_role) == {"window-glass", "window-sill-infill", "window-head-infill"}

    glass = by_role["window-glass"]
    assert glass["kind"] == "glass"
    assert glass["center"] == [100, 150, 0]
    assert glass["size"] == [200, 120, 2]

    sill = by_role["window-sill-infill"]
    assert sill["kind"] == "wall"
    assert sill["center"][1] == 44.7  # (90 - 0.6) / 2
    assert sill["size"] == [200, 89.4, 11.6]  # 厚 12 - 2·0.2

    head = by_role["window-head-infill"]
    assert head["size"][1] == 69.4  # 280 - 210 - 0.6
    assert head["center"][1] == 245.3

    door_pieces = result["door"]
    assert [piece["role"] for piece in door_pieces] == ["door-lintel"]
    lintel = door_pieces[0]
    assert lintel["kind"] == "wall"
    assert lintel["center"] == [445, 245, 0]  # (210+280)/2
    assert lintel["size"] == [90, 70, 11.6]


def test_estimate_profile_reads_wall_cross_section() -> None:
    result = run_shell_script(
        f"""
        {module_import('estimateProfile, DEFAULT_SCENE_CONFIG')}
        const opening = {{ start: {{x: 0, z: 0}}, end: {{x: 100, z: 0}} }};
        const polygons = [{{ exterior: [
          [-30, -18], [130, -18], [130, 6], [-30, 6],
          [400, -18], [-30, 100],
        ] }}];
        const flat = [{{ exterior: [[-10, 0], [110, 0], [110, 1], [-10, 1]] }}];
        console.log(JSON.stringify({{
          profile: estimateProfile(opening, polygons, DEFAULT_SCENE_CONFIG),
          fallback: estimateProfile(opening, flat, DEFAULT_SCENE_CONFIG),
        }}));
        """
    )
    profile = result["profile"]
    assert profile["thicknessCm"] == 24  # 法向 spread 6 - (-18)
    assert profile["offsetCm"] == -6
    assert profile["startU"] == -30
    assert profile["endU"] == 130
    assert profile["fallback"] is False

    fallback = result["fallback"]
    assert fallback["fallback"] is True
    assert fallback["thicknessCm"] == 12
    assert fallback["offsetCm"] == 0
    assert fallback["startU"] == 0
    assert fallback["endU"] == 100


def test_opening_infill_window_full_wall_door_lintel() -> None:
    result = run_shell_script(
        f"""
        {module_import('openingInfill, shellConfig')}
        const cfg = shellConfig({{}});
        const opening = {{
          sill_height_cm: 90,
          height_cm: 120,
          start: {{x: 0, z: 0}},
          end: {{x: 100, z: 0}},
        }};
        const profile = {{
          thicknessCm: 24, offsetCm: -6, startU: -30, endU: 130, fallback: false,
        }};
        console.log(JSON.stringify({{
          window: openingInfill(opening, profile, cfg, {{ kind: "window" }}),
          door: openingInfill(
            {{ height_cm: 210, start: {{x: 0, z: 0}}, end: {{x: 100, z: 0}} }},
            profile,
            cfg,
            {{ kind: "door" }},
          ),
        }}));
        """
    )
    window_boxes = result["window"]
    roles = [box["role"] for box in window_boxes]
    assert roles == ["opening-infill-wall", "window-glass"]

    infill = window_boxes[0]
    # 連續牆：全高、沿 startU..endU 搭接、中心線沿法向偏 offset。
    assert infill["center"] == [50, 140, -6]
    assert infill["size"] == [160, 280, 24]
    assert infill["kind"] == "wall"

    glass = window_boxes[1]
    assert glass["center"] == [50, 150, -6]
    assert glass["size"] == [100, 120, 24.4]  # 厚 profile + 2·epsilon
    assert glass["kind"] == "glass"

    door_boxes = result["door"]
    assert [box["role"] for box in door_boxes] == ["opening-infill-wall"]
    lintel = door_boxes[0]
    assert lintel["center"] == [50, 245, -6]  # 只補門楣 210..280
    assert lintel["size"] == [160, 70, 24]


def test_floor_box_and_camera_follow_structure_bbox() -> None:
    result = run_shell_script(
        f"""
        {module_import('floorBox, fitCameraPose, DEFAULT_SCENE_CONFIG')}
        const bbox = [-200, -150, 200, 150];
        console.log(JSON.stringify({{
          floor: floorBox(bbox, DEFAULT_SCENE_CONFIG),
          camera: fitCameraPose(bbox, DEFAULT_SCENE_CONFIG),
        }}));
        """
    )
    floor = result["floor"]
    assert floor["kind"] == "floor"
    assert floor["center"] == [0, -2.5, 0]
    assert floor["size"] == [500, 5, 400]  # 各向外擴 floorMarginCm 50、厚 5

    camera = result["camera"]
    # span = max(400, 300, 100) = 400；dist = 400 × 1.2 = 480。
    assert camera["target"] == [0, 0, 0]
    assert camera["position"] == [336, 432, 336]


def test_empty_plan_builds_empty_model() -> None:
    result = run_shell_script(
        f"""
        {module_import('buildSceneModel, DEFAULT_SCENE_CONFIG')}
        const model = buildSceneModel({{}}, DEFAULT_SCENE_CONFIG);
        console.log(JSON.stringify({{
          boxes: model.boxes.length,
          polygonWalls: model.polygonWalls.length,
          floor: model.floor,
          hasCamera: Boolean(model.cameraPose),
        }}));
        """
    )
    assert result == {"boxes": 0, "polygonWalls": 0, "floor": None, "hasCamera": True}


def test_build_scene_model_uses_infill_switch() -> None:
    result = run_shell_script(
        f"""
        {module_import('buildSceneModel, shellConfig')}
        const cfg = shellConfig({{}});
        const polygonPlan = {{
          wallPolygons: [{{ exterior: [[-200, -150], [200, -150], [200, 150], [-200, 150]] }}],
          windows: [{{ id: "w-1", start: {{x: -50, z: -150}}, end: {{x: 50, z: -150}} }}],
        }};
        const segmentPlan = {{
          walls: [{{ id: "wall-1", start: {{x: -200, z: 0}}, end: {{x: 200, z: 0}} }}],
          windows: [{{
            id: "w-1", host_wall_id: "wall-1", width_cm: 100,
            sill_height_cm: 90, height_cm: 120,
            start: {{x: -50, z: 0}}, end: {{x: 50, z: 0}},
          }}],
        }};
        const polygonModel = buildSceneModel(polygonPlan, cfg);
        const segmentModel = buildSceneModel(segmentPlan, cfg);
        console.log(JSON.stringify({{
          polygonRoles: polygonModel.boxes.map((box) => box.role),
          polygonWallCount: polygonModel.polygonWalls.length,
          segmentRoles: segmentModel.boxes.map((box) => box.role),
          segmentWindowCount: segmentModel.openings.windows.length,
          floorSize: segmentModel.floor.size,
        }}));
        """
    )
    # 路徑 B：多邊形牆存在 → 全部開口走 openingInfill。
    assert result["polygonWallCount"] == 1
    assert "opening-infill-wall" in result["polygonRoles"]
    assert "window-sill-infill" not in result["polygonRoles"]

    # 路徑 A：線段牆在 hosted 窗區間被切分成兩段 + 窗件三件 + 頂蓋。
    segment_roles = result["segmentRoles"]
    assert segment_roles.count("wall-section") == 2
    assert "window-sill-infill" in segment_roles
    assert "window-head-infill" in segment_roles
    assert "window-glass" in segment_roles
    assert "top-cap" in segment_roles
    assert result["segmentWindowCount"] == 1

    # 地板：結構 bbox（牆 400×窗同線 → 400×0…含窗 z=0 帶）外擴 50。
    assert result["floorSize"][0] == 500
