"""TV-first 客廳成組＋避窗擺位（2026-08-02 拍板）。

規格：電視櫃當客廳錨點、選「無門無窗最長牆段」（avoid_windows：不論家具
高度，窗段一律視為阻擋——電視 50cm 高本可鑽一般窗下，拍板不准＝逆光）；
沙發擺電視正前方、面向電視，觀影距離＝房深 × 0.45 夾 250–700cm
（place_in_front_of 內建 ×0.75／×0.5 縮距階梯）；茶几居中其間。
「opposite 對面放不下退任意牆」的 fallback 廢除——那是電視沙發同牆怪局
（live 專案 b2b2c83f）的根因，放不下改為誠實失敗。
床同吃 avoid_windows（床頭不靠窗）。
"""

import pytest

from backend.engine.clearance_defaults import catalog_with_default_clearance
from backend.engine.layout_strategy import (
    ROOM_RULES,
    PlacementRule,
    place_against_wall,
    place_in_front_of,
    place_room,
)
from backend.engine.models import FurnitureCatalogItem, Opening, PlacedFurniture, Room


def item(type_, name, width, depth, height=80.0) -> FurnitureCatalogItem:
    return catalog_with_default_clearance(
        FurnitureCatalogItem(type=type_, name=name, width=width, depth=depth, height=height)
    )


def window(x1, y1, x2, y2, window_type="standard") -> Opening:
    return Opening(kind="window", x1=x1, y1=y1, x2=x2, y2=y2, window_type=window_type)


def door(x1, y1, x2, y2) -> Opening:
    return Opening(kind="door", x1=x1, y1=y1, x2=x2, y2=y2)


TV = item("tv-bench", "電視櫃", 154, 40, height=50)
SOFA = item("sofa", "沙發", 182, 80, height=90)
COFFEE = item("coffee-table", "茶几", 90, 55, height=45)


def _bounds(placed: PlacedFurniture) -> tuple[float, float, float, float]:
    if placed.rotation in (90, 270):
        w, d = placed.catalog.depth, placed.catalog.width
    else:
        w, d = placed.catalog.width, placed.catalog.depth
    return (
        placed.pos_x - w / 2,
        placed.pos_y - d / 2,
        placed.pos_x + w / 2,
        placed.pos_y + d / 2,
    )


def living_room(depth: float = 600.0) -> Room:
    # 北牆一般窗（窗台 90）幾乎滿佈；南牆乾淨。
    return Room(width=700.0, depth=depth, openings=[window(50, depth, 650, depth)])


def _run_living(depth: float):
    room = living_room(depth)
    result = place_room(room, "living_room", [(TV, "tv"), (SOFA, "sofa"), (COFFEE, "ct")])
    assert not result["failed"], result["failed"]
    by_id = {p.id: p for p in result["placed"]}
    return room, by_id["tv"], by_id["sofa"], by_id["ct"]


def test_avoid_windows_rejects_low_furniture_sneaking_under_the_window():
    room = Room(
        width=700.0,
        depth=600.0,
        openings=[window(50, 600, 650, 600), door(250, 0, 340, 0)],
    )
    # 舊行為：電視 50 高低於窗台 → 北牆整段可用（700 > 南牆最長 360）→ 貼窗下。
    loose = place_against_wall(room, TV, "tv", [], treat_windows_as_blocking=False)
    assert loose["success"] and loose["side"] == "north"
    # 拍板行為：窗段一律阻擋 → 北牆兩小段放不下 154 → 換無窗牆（此房是最長的西牆）。
    strict = place_against_wall(room, TV, "tv", [], treat_windows_as_blocking=True)
    assert strict["success"] and strict["side"] != "north"


def test_tv_first_group_sofa_backs_on_opposite_wall():
    """2026-08-02 拍板：沙發＝貼電視對面牆、背有靠、面向電視——觀影距離是
    「兩牆間距」的純幾何結果（比例語意，零絕對公分），巨人屋（未重定標
    平面）下規則不失真。使用者實測：比例 0.45 版沙發漂房中背後懸空、
    絕對夾限在巨人屋下語意錯亂，都棄用。"""
    room, tv, sofa, ct = _run_living(600.0)
    assert tv.pos_y == pytest.approx(20.0)  # 貼南牆（北牆有窗，avoid_windows）
    assert tv.rotation == 0  # 正面朝房內
    assert sofa.rotation == 180  # 面向電視
    assert sofa.pos_x == pytest.approx(tv.pos_x)  # 三件套對齊中線
    assert _bounds(sofa)[3] == pytest.approx(600.0)  # 背貼北牆（電視對面）
    assert _bounds(tv)[3] < ct.pos_y < _bounds(sofa)[1]  # 茶几在電視與沙發之間
    assert ct.pos_x == pytest.approx(sofa.pos_x)


def test_sofa_scales_with_room_no_absolute_distance():
    # 任何房深下沙發都貼對面牆：距離＝房深−兩件深，純比例、無絕對夾限。
    for depth in (500.0, 1700.0):
        room = Room(width=1800.0, depth=depth, openings=[window(50, depth, 650, depth)])
        result = place_room(room, "living_room", [(TV, "tv"), (SOFA, "sofa"), (COFFEE, "ct")])
        assert not result["failed"], (depth, result["failed"])
        by_id = {p.id: p for p in result["placed"]}
        assert _bounds(by_id["sofa"])[3] == pytest.approx(depth)
        gap = _bounds(by_id["sofa"])[1] - _bounds(by_id["tv"])[3]
        assert gap == pytest.approx(depth - 40.0 - 80.0)


def test_front_attach_steps_down_when_ideal_distance_is_blocked():
    room = Room(width=700.0, depth=600.0)
    tv = PlacedFurniture(id="tv", catalog=TV, pos_x=350.0, pos_y=20.0, rotation=0)
    blocker = PlacedFurniture(
        id="p",
        catalog=item("flower-pots-planter", "植栽", 60, 60, height=120),
        pos_x=350.0,
        pos_y=365.0,
        rotation=0,
    )
    result = place_in_front_of(
        room, SOFA, "sofa", tv, [tv, blocker], gap=270.0, face="target"
    )
    assert result["success"], result["reason"]
    gap = _bounds(result["placed"])[1] - _bounds(tv)[3]
    assert gap == pytest.approx(270.0 * 0.75)


def test_opposite_no_longer_falls_back_to_any_wall(monkeypatch):
    monkeypatch.setitem(
        ROOM_RULES,
        "_tv_first_test",
        {
            "sofa": PlacementRule(anchor=True, order=0),
            "tv-bench": PlacementRule(attach="opposite", attach_to=("sofa",), order=20),
        },
    )
    # 沙發貼南牆；對面（北）整面落地窗放不下。舊行為會退回任意牆跟沙發擠同側。
    room = Room(
        width=500.0,
        depth=400.0,
        openings=[window(10, 400, 490, 400, window_type="floor_to_ceiling")],
    )
    result = place_room(room, "_tv_first_test", [(SOFA, "sofa"), (TV, "tv")])
    assert [p.id for p in result["placed"]] == ["sofa"]
    assert [f["id"] for f in result["failed"]] == ["tv"]


def test_generate_layout_adapter_honours_tv_first():
    """server 側 `_strategy_placement` 是策略層的整合端複製品（總帳 §5.4），
    gap_ratio_depth／face／avoid_windows 必須跟引擎同步，否則 API 路徑
    仍是同牆怪局（本案第一次修完引擎、API 重演即現形）。"""
    from backend.server.scene_service import floorplan_from_editor_payload, generate_layout

    editor = {
        "coordinate_unit": "cm",
        "width_cm": 700,
        "depth_cm": 600,
        "room_height_cm": 270,
        "rooms": [
            {
                "id": "lr",
                "type": "living_room",
                "label": "客廳",
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 700, "y": 0},
                    {"x": 700, "y": 600},
                    {"x": 0, "y": 600},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 700, "y": 0}},
                {"start": {"x": 700, "y": 0}, "end": {"x": 700, "y": 600}},
                {"start": {"x": 700, "y": 600}, "end": {"x": 0, "y": 600}},
                {"start": {"x": 0, "y": 600}, "end": {"x": 0, "y": 0}},
            ],
            "doors": [],
            "windows": [{"start": {"x": 50, "y": 600}, "end": {"x": 650, "y": 600}}],
            "beams": [],
            "columns": [],
        },
    }
    floorplan, room = floorplan_from_editor_payload(editor)

    def obj(fid, type_, w, d, h):
        return {
            "furniture_id": fid,
            "normalized_type": type_,
            "name_zh_raw": fid,
            "size_cm": {"width": w, "depth": d, "height": h},
            "position_cm": {"x": 0, "z": 0},
            "rotation_y_deg": 0,
            "position_locked": False,
        }

    out = generate_layout(
        room.width,
        room.depth,
        [obj("tv", "tv-bench", 154, 40, 50), obj("sofa", "sofa", 182, 80, 90),
         obj("ct", "coffee-table", 90, 55, 45)],
        room=room,
        floorplan=floorplan,
        placement_variant="A",
        room_type="living_room",
    )
    by_id = {str(o["furniture_id"]): o for o in out}
    tv, sofa, ct = by_id["tv"], by_id["sofa"], by_id["ct"]
    assert not tv.get("placement_failed") and not sofa.get("placement_failed")
    # 沙發貼電視對面牆（opposite）：中心距＝房深−半深和（600−60），
    # 容差涵蓋兩側 8cm 貼牆內縮。
    assert abs((tv["rotation_y_deg"] - sofa["rotation_y_deg"]) % 360) == 180
    assert tv["position_cm"]["x"] == pytest.approx(sofa["position_cm"]["x"], abs=1.0)
    center_gap = abs(sofa["position_cm"]["z"] - tv["position_cm"]["z"])
    assert center_gap == pytest.approx(600.0 - 60.0, abs=20.0)
    assert not ct.get("placement_failed")


def test_generate_layout_passes_model_orientation_through():
    """GLB 出廠朝向修正（model_orientation_deg）必須穿過 server 的輸出白名單
    ——第一版漏了這層：2D 存 180、sceneData 拿到 None，桌椅照樣反向
    （使用者二度回報實錘）。三層傳遞鏈每層都要有守門。"""
    from backend.server.scene_service import floorplan_from_editor_payload, generate_layout

    editor = {
        "coordinate_unit": "cm",
        "width_cm": 500,
        "depth_cm": 400,
        "room_height_cm": 270,
        "rooms": [
            {
                "id": "r",
                "type": "bedroom",
                "label": "臥室",
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 500, "y": 0},
                    {"x": 500, "y": 400},
                    {"x": 0, "y": 400},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 500, "y": 0}},
                {"start": {"x": 500, "y": 0}, "end": {"x": 500, "y": 400}},
                {"start": {"x": 500, "y": 400}, "end": {"x": 0, "y": 400}},
                {"start": {"x": 0, "y": 400}, "end": {"x": 0, "y": 0}},
            ],
            "doors": [], "windows": [], "beams": [], "columns": [],
        },
    }
    floorplan, room = floorplan_from_editor_payload(editor)
    out = generate_layout(
        room.width, room.depth,
        [{
            "furniture_id": "dk", "normalized_type": "desk", "name_zh_raw": "桌",
            "size_cm": {"width": 120, "depth": 60, "height": 75},
            "position_cm": {"x": 0, "z": -100}, "rotation_y_deg": 0,
            "position_locked": True, "model_orientation_deg": 180,
        }],
        room=room, floorplan=floorplan, placement_variant="A", room_type="bedroom",
    )
    assert out[0]["model_orientation_deg"] == 180


def test_living_room_desk_set_chair_faces_desk():
    """配套池的桌椅組（電競角）進客廳也要成組：椅貼桌前 8cm、面向桌。
    （隨機配套拍板：desk-set 可出現在臥室或客廳。）"""
    import math

    desk = item("desk", "電競桌", 118, 60, height=75)
    chair = item("office-chair", "電競椅", 67, 65, height=90)
    room = Room(width=700.0, depth=600.0, openings=[window(50, 600, 650, 600)])
    result = place_room(
        room, "living_room", [(TV, "tv"), (SOFA, "sofa"), (desk, "dk"), (chair, "ch")]
    )
    assert not result["failed"], result["failed"]
    by_id = {p.id: p for p in result["placed"]}
    dk, ch = by_id["dk"], by_id["ch"]
    assert abs((dk.rotation - ch.rotation) % 360) == 180
    dist = math.hypot(ch.pos_x - dk.pos_x, ch.pos_y - dk.pos_y)
    assert dist == pytest.approx(60 / 2 + 8 + 65 / 2, abs=1.0)


def test_locked_companion_pair_survives_confirm_revalidation():
    """「確認 2D」把引擎自擺座標鎖位重驗（confirmLayout2d 不帶 placement_room_id
    → room_type=None 的路徑）。companion（床頭櫃貼床 5cm）必須帶配套語意，
    否則被判「侵入床側淨空」——08-02 床頭櫃×2 實案：一只進待處理、一只被
    重排到廚房。"""
    from backend.server.scene_service import floorplan_from_editor_payload, generate_layout

    editor = {
        "coordinate_unit": "cm",
        "width_cm": 600,
        "depth_cm": 500,
        "room_height_cm": 270,
        "rooms": [
            {
                "id": "br",
                "type": "bedroom",
                "label": "臥室",
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 600, "y": 0},
                    {"x": 600, "y": 500},
                    {"x": 0, "y": 500},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 600, "y": 0}},
                {"start": {"x": 600, "y": 0}, "end": {"x": 600, "y": 500}},
                {"start": {"x": 600, "y": 500}, "end": {"x": 0, "y": 500}},
                {"start": {"x": 0, "y": 500}, "end": {"x": 0, "y": 0}},
            ],
            "doors": [],
            "windows": [],
            "beams": [],
            "columns": [],
        },
    }
    floorplan, room = floorplan_from_editor_payload(editor)

    def obj(fid, type_, w, d, h, pos=None, rot=0, locked=False):
        return {
            "furniture_id": fid,
            "normalized_type": type_,
            "name_zh_raw": fid,
            "size_cm": {"width": w, "depth": d, "height": h},
            "position_cm": pos or {"x": 0, "z": 0},
            "rotation_y_deg": rot,
            "position_locked": locked,
        }

    specs = [
        ("bed", "bed", 167, 205, 90),
        ("bt1", "bedside-table", 50, 37, 76),
        ("bt2", "bedside-table", 50, 37, 76),
    ]
    first = generate_layout(
        room.width, room.depth,
        [obj(f, t, w, d, h) for f, t, w, d, h in specs],
        room=room, floorplan=floorplan, placement_variant="A", room_type="bedroom",
    )
    fb = {o["furniture_id"]: o for o in first}
    assert all(not o.get("placement_failed") for o in first), first
    locked_items = [
        obj(f, t, w, d, h, pos=dict(fb[f]["position_cm"]),
            rot=fb[f]["rotation_y_deg"], locked=True)
        for f, t, w, d, h in specs
    ]
    second = generate_layout(
        room.width, room.depth, locked_items,
        room=room, floorplan=floorplan, placement_variant="A", room_type=None,
    )
    sb = {o["furniture_id"]: o for o in second}
    for fid, *_ in specs:
        assert not sb[fid].get("placement_failed"), (fid, sb[fid].get("placement_reason"))
        assert sb[fid]["position_cm"]["x"] == pytest.approx(fb[fid]["position_cm"]["x"], abs=0.5), fid
        assert sb[fid]["position_cm"]["z"] == pytest.approx(fb[fid]["position_cm"]["z"], abs=0.5), fid


def test_bed_head_never_leans_on_a_windowed_wall():
    low_bed = item("bed", "矮床", 167, 205, height=85)  # 低於窗台 90，舊規則會鑽窗牆
    room = Room(width=300.0, depth=600.0, openings=[window(0, 30, 0, 570)])  # 西牆滿窗
    result = place_room(room, "bedroom", [(low_bed, "bed")])
    assert not result["failed"], result["failed"]
    bed = result["placed"][0]
    assert _bounds(bed)[0] > 5.0  # 床頭沒貼上西牆（x=0）的窗牆
