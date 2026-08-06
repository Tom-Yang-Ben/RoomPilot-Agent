"""第 4 步確認的 floorplan 必須產出連續牆體 wall_polys（2026-08-03 QA）。

當天實走：wall_segments 19、wall_polys 0——第 6 步 3D 的牆是一根根不相連的
板片，門片站在沒有牆的空地上。editor 路徑要像 dxf_parser 一樣把牆中線
buffer 成實心牆團，並把門窗洞從牆身開槽（門用 hinge→swing_end 的關門線，
不是打開的門片），前端 wall-mass 路徑才能帶著開口直接擠出連續牆。
"""

from __future__ import annotations

from shapely.geometry import Point, Polygon

from backend.paths import STATIC_DIR
from backend.server.scene_service import floorplan_from_editor_payload

W, H = 500.0, 400.0
# 角落原點的編輯器座標轉成中心原點：x-250、y-200。
CX, CY = W / 2, H / 2


def _editor(doors: list | None = None, windows: list | None = None) -> dict:
    return {
        "coordinate_unit": "cm",
        "width_cm": W,
        "depth_cm": H,
        "room_height_cm": 270,
        "structures": {
            "walls": [
                {"id": "wall-1", "thickness_cm": 12, "start": {"x": 0, "y": 0}, "end": {"x": W, "y": 0}},
                {"id": "wall-2", "thickness_cm": 12, "start": {"x": W, "y": 0}, "end": {"x": W, "y": H}},
                {"id": "wall-3", "thickness_cm": 12, "start": {"x": W, "y": H}, "end": {"x": 0, "y": H}},
                {"id": "wall-4", "thickness_cm": 12, "start": {"x": 0, "y": H}, "end": {"x": 0, "y": 0}},
            ],
            "doors": doors or [],
            "windows": windows or [],
            "beams": [],
            "columns": [],
        },
    }


def _wall_polygons(floorplan: dict) -> list[Polygon]:
    polys = [
        Polygon(poly["exterior"], [hole for hole in poly["holes"] if len(hole) >= 3])
        for poly in floorplan["wall_polys"]
    ]
    return [poly if poly.is_valid else poly.buffer(0) for poly in polys]


def _covered(polys: list[Polygon], x: float, z: float) -> bool:
    return any(poly.covers(Point(x, z)) for poly in polys)


def test_walls_become_a_continuous_mass_with_solid_corners() -> None:
    floorplan, _ = floorplan_from_editor_payload(_editor())
    polys = _wall_polygons(floorplan)

    assert polys, "editor 路徑必須產出 wall_polys，不能再是 0"
    assert floorplan["wall_polys_openings_cut"] is True
    # 牆中線上、轉角上都是實牆；房間內部不是。
    assert _covered(polys, 0, -CY)
    assert _covered(polys, CX, 0)
    assert _covered(polys, -CX, -CY)
    assert not _covered(polys, 0, 0)


def test_swing_door_cuts_its_closed_span_out_of_the_wall() -> None:
    """牆洞是 hinge→swing_end 的關門線；打開的門片（start→end）伸進房間，
    拿它去開槽會把槽開錯方向。"""
    door = {
        "id": "door-1",
        "start": {"x": 150, "y": 0},
        "end": {"x": 150, "y": 90},
        "swing_end": {"x": 240, "y": 0},
    }
    floorplan, _ = floorplan_from_editor_payload(_editor(doors=[door]))
    polys = _wall_polygons(floorplan)

    # 關門線中點（編輯器 x=195 → 中心 -55）開了槽。
    assert not _covered(polys, -55, -CY)
    # 槽只在門的跨距內：跨距外同一面牆仍是實牆。
    assert _covered(polys, -110, -CY)
    assert _covered(polys, 100, -CY)


def test_straight_door_without_swing_uses_its_own_segment() -> None:
    door = {
        "id": "door-2",
        "start": {"x": 500, "y": 150},
        "end": {"x": 500, "y": 230},
    }
    floorplan, _ = floorplan_from_editor_payload(_editor(doors=[door]))
    polys = _wall_polygons(floorplan)

    assert not _covered(polys, CX, -10)
    assert _covered(polys, CX, -150)


def test_window_opening_is_cut_from_its_host_wall() -> None:
    window = {
        "id": "window-1",
        "start": {"x": 200, "y": 400},
        "end": {"x": 300, "y": 400},
    }
    floorplan, _ = floorplan_from_editor_payload(_editor(windows=[window]))
    polys = _wall_polygons(floorplan)

    assert not _covered(polys, 0, CY)
    assert _covered(polys, -150, CY)


def test_opening_cut_flag_key_matches_between_backend_and_viewer() -> None:
    from backend.server import scene_service

    source = open(scene_service.__file__, encoding="utf-8").read()
    assert '"wall_polys_openings_cut": bool(wall_polys)' in source
    # build_scene_payload 重組 floorplan 區塊時必須透傳，否則存檔再讀回就退化。
    assert 'bool(parsed_floorplan.get("wall_polys_openings_cut"))' in source

    # 消費端的鍵名不能和生產端漂開。牆體改走逐段路線後，viewer 不再讀這個
    # 旗標；剩下的消費端是 scene_v2 的舊存檔結構刷新（refreshRestoredFloorplanStructure）。
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    assert "wall_polys_openings_cut === true" in controller
