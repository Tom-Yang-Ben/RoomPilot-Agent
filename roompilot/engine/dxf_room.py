"""dxf_room.py — 把 app/backend/dxf_parser 產生的樓面 JSON 轉成 furniture_engine 的 Room。

這是 SSOT 文件 F2「upgrade_to_3d:DXF→Room」的介面接點:
辨識/升維(柏彥,app/backend/dxf_parser.py)輸出 wall_polys,配置引擎(承安)吃
Room(width, depth, walls)。本模組只做「純資料轉換」,不依賴 ezdxf/shapely
(shapely 只有 geometry.py 在用),所以能獨立匯入與測試。

── 為什麼需要轉換:兩邊座標系、單位與牆體表示不同 ──────────────────────
  dxf_parser 輸出:
    - 原點在「平面中心」(座標可負),鍵是 x / z,單位公尺。
    - 牆體只給 `wall_polys`(緩衝後的實心多邊形,exterior=外框、holes=房間內部),
      **沒有牆中線線段** —— 所以 Room.walls 必須從環(ring)的邊還原。
  Room 引擎需要:
    - 原點在「角落」,房間 = box(0, 0, width, depth),座標全為正、家具限制其中。
    - 單位一律公分——本模組是「公尺→公分」的唯一邊界,上游 dxf_parser
      的公尺輸出在這裡 ×100 進引擎。
    - 牆是「有厚度的線段」Wall(x1,y1,x2,y2,thickness),hits_wall 會把它變旋轉矩形。

  因此本模組:① 公尺 ×100 轉公分;② 平移到角落原點;③ 從 wall_polys 的環邊還原成
             Wall 線段;④ width/depth 取自選定範圍;⑤ z 軸直接對應引擎的 y 軸(同為平面第二軸)。

── mode ────────────────────────────────────────────────────────────
  "largest"(預設,demo 友善):取面積最大的 hole(=最大房間)當 Room,家具擺進
      真正的房間裡;找不到任何 hole(牆體未閉合,如 simplehouseplandwg)時,
      自動退回 "plan"。
  "plan"(完整平面):用整張圖 bbox 當 Room,所有環邊都當牆。座標與 3D 全景一致,
      但 place_furniture 從平面中心起放,多房型時中心可能落在牆上而放不下。
"""
from __future__ import annotations
from dataclasses import dataclass

from roompilot.engine.models import Room, Wall

# 環邊當「薄牆」的厚度(cm)。環本身已是實心牆的內牆面,取薄值只是讓家具與牆面留一點
# 縫、不要正貼;取太厚會把可用空間吃掉。
DEFAULT_WALL_SEG_THICKNESS = 6.0

_M_TO_CM = 100.0


def _scale_ring(ring: list) -> list:
    """dxf_parser 的公尺環轉為公分環。"""
    return [[p[0] * _M_TO_CM, p[1] * _M_TO_CM] for p in ring]


def _ring_area(ring: list) -> float:
    """多邊形面積(shoelace,絕對值,cm²)。ring 為 [[x,z],...],首尾是否重複皆可。"""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _ring_bbox(ring: list) -> tuple:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _walls_from_ring(ring: list, ox: float, oz: float, thickness: float) -> list:
    """把一個環(閉合折線)的每條邊變成一段 Wall,並平移 (ox,oz) 到角落原點。"""
    walls = []
    n = len(ring)
    for i in range(n):
        x1, z1 = ring[i]
        x2, z2 = ring[(i + 1) % n]
        if abs(x1 - x2) < 1e-7 and abs(z1 - z2) < 1e-7:
            continue  # 跳過首尾重複點造成的零長度邊
        walls.append(Wall(x1 - ox, z1 - oz, x2 - ox, z2 - oz, thickness))
    return walls


@dataclass
class DxfRoomBuild:
    """轉換結果。room 與 offset 都使用公分。"""
    room: Room
    offset: tuple      # (ox, oz):選定範圍在平面座標中的最小角(公分)
    mode: str          # 實際採用的模式:"largest" / "plan" / "plan(fallback)"
    source_area: float  # 選定範圍面積(cm²)


def build_room_from_dxf(
    parsed: dict,
    mode: str = "largest",
    wall_seg_thickness: float = DEFAULT_WALL_SEG_THICKNESS,
) -> DxfRoomBuild:
    """dxf_parser 的公尺輸出轉為公分 DxfRoomBuild。"""
    polys = parsed.get("wall_polys") or []
    holes = [_scale_ring(h) for p in polys for h in (p.get("holes") or []) if len(h) >= 3]

    if mode == "largest" and holes:
        ring = max(holes, key=_ring_area)
        minx, minz, maxx, maxz = _ring_bbox(ring)
        room = Room(
            width=round(maxx - minx, 1),
            depth=round(maxz - minz, 1),
            walls=_walls_from_ring(ring, minx, minz, wall_seg_thickness),
        )
        return DxfRoomBuild(room, (minx, minz), "largest", _ring_area(ring))

    # plan 模式,或 largest 找不到封閉房間時退回這裡:整張圖 bbox + 所有環邊當牆
    bb = parsed["bbox"]
    ox, oz = bb["minx"] * _M_TO_CM, bb["minz"] * _M_TO_CM
    walls = []
    for p in polys:
        ext = p.get("exterior") or []
        if len(ext) >= 3:
            walls += _walls_from_ring(_scale_ring(ext), ox, oz, wall_seg_thickness)
        for h in (p.get("holes") or []):
            if len(h) >= 3:
                walls += _walls_from_ring(_scale_ring(h), ox, oz, wall_seg_thickness)
    room = Room(
        width=round(bb["maxx"] * _M_TO_CM - ox, 1),
        depth=round(bb["maxz"] * _M_TO_CM - oz, 1),
        walls=walls,
    )
    used = "plan" if (mode == "plan" or not polys) else "plan(fallback:無封閉房間)"
    return DxfRoomBuild(room, (ox, oz), used, room.width * room.depth)


def room_from_dxf(parsed: dict, mode: str = "largest", **kw) -> Room:
    """便捷版:只回 Room(demo_app / 引擎直接用)。需要座標映射時改用 build_room_from_dxf。"""
    return build_room_from_dxf(parsed, mode, **kw).room

