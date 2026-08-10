"""有櫃家具正面 50cm 淨空規則:引擎淨空判定 + raster 正面長條幾何。"""
from __future__ import annotations

from backend.engine.clearance import (
    CABINET_FRONT_CLEARANCE_CM,
    check_placement_with_clearance,
    clearance_polygon,
    is_cabinet_type,
)
from backend.engine.constraints import BlockedMasks
from backend.engine.layout_model import RoomContext
from backend.engine.models import FurnitureCatalogItem, PlacedFurniture, Room
from backend.engine.raster import make_grid
from backend.server.scene_service import (
    _cabinet_front_strip,
    raster_commit,
    raster_free,
)


def _ctx():
    grid = make_grid([0, 0, 600, 500])
    return RoomContext(
        grid=grid,
        masks=BlockedMasks(low=grid.blank(), band=grid.blank()),
        edges=[],
        centroid=(300, 250),
    )


def _commit(ctx, kind, w, d, cx, cy, rot=0.0):
    raster_commit(ctx, kind, w, d, cx - w / 2, cy - d / 2, rot, w / 2, d / 2)


def _free(ctx, kind, w, d, cx, cy, rot=0.0):
    return raster_free(ctx, kind, w, d, 80.0, cx - w / 2, cy - d / 2, rot, w / 2, d / 2)


def _placed(type_, name, w, d, x, y, rot=0.0):
    return PlacedFurniture(
        id=name,
        catalog=FurnitureCatalogItem(type=type_, name=name, width=w, depth=d),
        pos_x=x,
        pos_y=y,
        rotation=rot,
    )


def test_is_cabinet_type_recognizes_storage_families():
    for t in ("wardrobe", "cabinets-cupboard", "storage-solution-system",
              "pax-wardrobe", "chests-of-drawer", "sideboard", "shelving-unit",
              "bookcase", "tv-bench", "shoe-cabinet"):
        assert is_cabinet_type(t), t
    # 床頭櫃是成組副件(該貼床),不吃 50cm 正面淨空；床/沙發/餐桌也不是有櫃件。
    for t in ("bedside-table", "bed", "sofa", "dining-table", None):
        assert not is_cabinet_type(t), t


def test_cabinet_gets_synthesized_front_clearance_polygon():
    assert clearance_polygon(_placed("wardrobe", "衣櫃", 120, 60, 300, 100)) is not None
    assert clearance_polygon(_placed("bed", "床", 150, 200, 300, 100)) is None


def test_cabinet_front_blocked_by_flush_neighbor_but_clear_when_far():
    room = Room(width=600, depth=500, walls=[])
    wardrobe = _placed("wardrobe", "衣櫃", 120, 60, 300, 100)  # 正面 +y,淨空 y[130,180]
    near = _placed("bed", "床", 100, 50, 300, 155)             # 本體 y[130,180] 壓進淨空
    far = _placed("bed", "床", 100, 50, 300, 400)              # 遠離,不壓淨空

    assert check_placement_with_clearance(wardrobe, room, [near]) is not None
    assert check_placement_with_clearance(wardrobe, room, [far]) is None


def test_cabinet_front_strip_geometry():
    # 非有櫃件不產生長條。
    assert _cabinet_front_strip("sofa", 180, 90, 0, 0, 0, 90, 45) is None
    # 衣櫃(rot=0,場景正面 −y):中心 (60,130),長條中心退到 (60,75)、深 50。
    strip = _cabinet_front_strip("wardrobe", 120, 60, 0, 100, 0, 60, 30)
    assert strip is not None
    assert abs(strip.cx - 60) < 1e-6
    assert abs(strip.cy - 75) < 1e-6           # 130 - (30 + 25)
    assert abs(strip.w - 120) < 1e-6
    assert abs(strip.d - CABINET_FRONT_CLEARANCE_CM) < 1e-6


# ── raster 路徑(step6 主要引擎)整合 ──────────────────────────────

def test_raster_rejects_cabinet_when_furniture_in_front():
    ctx = _ctx()
    _commit(ctx, "bed", 100, 50, 300, 245)          # 床在衣櫃正面(−y)45cm 內
    assert _free(ctx, "wardrobe", 120, 60, 300, 300) is False
    # 對照:同位置的非有櫃件只驗本體(未壓到床)→ 可放,證明是「正面淨空」擋的。
    assert _free(ctx, "sofa", 120, 60, 300, 300) is True


def test_raster_accepts_cabinet_when_front_clear():
    ctx = _ctx()
    _commit(ctx, "bed", 100, 50, 300, 450)          # 床在衣櫃背面(+y),不擋正面
    assert _free(ctx, "wardrobe", 120, 60, 300, 300) is True


def test_raster_commit_reserves_cabinet_front():
    ctx = _ctx()
    _commit(ctx, "wardrobe", 120, 60, 300, 300)     # 烙印本體 + 正面 50cm
    assert _free(ctx, "armchair", 60, 60, 300, 245) is False   # 擠進正面 → 拒
    assert _free(ctx, "armchair", 60, 60, 300, 460) is True    # 別處 → 可放
