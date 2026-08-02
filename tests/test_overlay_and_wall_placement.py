"""2026-08-02 實測抓到的兩個擺放缺口。

兩個都是 Phase 1 把型別名單從「2 種地毯 + 1 種壁掛」擴大到型錄宣告的
「7 種 + 4 種」之後才浮現的——舊名單太小,漏洞被蓋住了。
"""
from backend.server.scene_service import floorplan_from_editor_payload, generate_layout

W, H = 500.0, 400.0

EDITOR = {
    "coordinate_unit": "cm",
    "width_cm": W,
    "depth_cm": H,
    "room_height_cm": 270,
    "structures": {
        "walls": [
            {"start": {"x": 0, "y": 0}, "end": {"x": W, "y": 0}},
            {"start": {"x": W, "y": 0}, "end": {"x": W, "y": H}},
            {"start": {"x": W, "y": H}, "end": {"x": 0, "y": H}},
            {"start": {"x": 0, "y": H}, "end": {"x": 0, "y": 0}},
        ],
        "doors": [],
        "windows": [],
        "beams": [],
        "columns": [],
    },
}


def _item(fid: str, item_type: str, name: str, w: float, d: float, h: float) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": item_type,
        "name_zh_raw": name,
        "size_cm": {"width": w, "depth": d, "height": h},
    }


def _layout(items: list[dict]) -> dict[str, dict]:
    floorplan, room = floorplan_from_editor_payload(EDITOR)
    placed = generate_layout(
        room.width,
        room.depth,
        items,
        room=room,
        place_boundary=None,
        floorplan=floorplan,
    )
    return {obj["furniture_id"]: obj for obj in placed}


def _footprint(obj: dict) -> tuple[float, float, float, float]:
    pos, size = obj["position_cm"], obj["size_cm"]
    rotated = round(obj.get("rotation_y_deg") or 0) % 180 == 90
    width = size["depth"] if rotated else size["width"]
    depth = size["width"] if rotated else size["depth"]
    return (
        pos["x"] - width / 2,
        pos["z"] - depth / 2,
        pos["x"] + width / 2,
        pos["z"] + depth / 2,
    )


def _overlaps(a: dict, b: dict) -> bool:
    ax0, az0, ax1, az1 = _footprint(a)
    bx0, bz0, bx1, bz1 = _footprint(b)
    return ax0 < bx1 and bx0 < ax1 and az0 < bz1 and bz0 < az1


def test_rug_that_cannot_fit_under_the_sofa_falls_back_to_free_placement() -> None:
    """沙發貼牆時大地毯鋪不進沙發下,但不該因此被修復層一路換小到移除。

    原本 overlay 分支只有「找不到目標家具」才退回自由擺放;找得到目標
    但鋪不下就直接判失敗,使用者看到的是「沒有地毯」。
    """
    result = _layout(
        [
            _item("sofa-1", "sofa", "三人座沙發", 200, 90, 80),
            _item("rug-1", "round-rug", "圓形地毯", 180, 180, 2),
        ]
    )

    assert "rug-1" in result
    rug = result["rug-1"]
    assert rug["placement_failed"] is False, rug.get("placement_reason")

    x0, z0, x1, z1 = _footprint(rug)
    assert -W / 2 <= x0 and x1 <= W / 2, "地毯必須完整落在房間內"
    assert -H / 2 <= z0 and z1 <= H / 2


def test_wall_mounted_items_do_not_stack_on_the_same_corner() -> None:
    """壁掛原本吃固定角落座標,不走引擎——第二件就會疊在第一件上面。"""
    result = _layout(
        [
            _item("shelf-1", "wall-shelf", "壁掛層架", 80, 25, 30),
            _item("mirror-1", "large-mirror", "掛鏡", 60, 5, 160),
        ]
    )

    shelf, mirror = result["shelf-1"], result["mirror-1"]
    assert shelf["placement_failed"] is False
    assert mirror["placement_failed"] is False
    assert not _overlaps(shelf, mirror), (
        f"壁掛互疊:層架 {_footprint(shelf)} 掛鏡 {_footprint(mirror)}"
    )


def test_wall_shelf_avoids_a_tall_wardrobe_but_not_a_low_sideboard() -> None:
    """垂直佔用帶要在自動配置這條路上也生效,不只在拖曳驗證。"""
    with_wardrobe = _layout(
        [
            _item("wardrobe-1", "wardrobe", "衣櫃", 120, 60, 200),
            _item("shelf-1", "wall-shelf", "壁掛層架", 80, 25, 30),
        ]
    )
    assert not _overlaps(with_wardrobe["wardrobe-1"], with_wardrobe["shelf-1"])

    # 矮邊櫃 0–80 與層架 120–150 垂直不重疊,允許共用平面位置。
    from backend.catalog.style_db import catalog_item_from_scene_object
    from backend.engine.geometry import vertical_overlap
    from backend.engine.models import PlacedFurniture

    shelf = PlacedFurniture(
        id="s", catalog=catalog_item_from_scene_object("wall-shelf", "層架", 80, 25, 30)
    )
    sideboard = PlacedFurniture(
        id="b", catalog=catalog_item_from_scene_object("sideboard", "邊櫃", 120, 40, 80)
    )
    assert vertical_overlap(shelf, sideboard) is False
