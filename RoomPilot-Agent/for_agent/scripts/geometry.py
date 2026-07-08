"""共用幾何工具：把管線的座標約定集中在一處，讓驗證與 3D 組裝用同一套邏輯。

約定（與 SKILL.md / agent 提示一致）：
  - 單位 cm；X 向右、Y 向上，原點左下。
  - position 為物件中心；rotation 為逆時針角度（度），0 度時本地 +Y 為正面朝向。
  - dimensions: width 沿本地 X、depth 沿本地 Y、height 沿 Z。
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple

try:
    from shapely.geometry import Polygon, Point
    from shapely.affinity import rotate, translate
    from shapely.ops import unary_union
except ImportError:  # 讓 --help / 語法檢查在未裝 shapely 時仍可用
    Polygon = Point = None  # type: ignore


def footprint(cx: float, cy: float, width: float, depth: float, rot_deg: float) -> "Polygon":
    """回傳一件矩形物件在平面上的投影多邊形（已旋轉、已平移到中心）。"""
    hw, hd = width / 2.0, depth / 2.0
    base = Polygon([(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)])
    base = rotate(base, rot_deg, origin=(0, 0), use_radians=False)
    return translate(base, xoff=cx, yoff=cy)


def furniture_footprint(item: Dict) -> "Polygon":
    d = item["dimensions"]
    p = item["position"]
    return footprint(p["x"], p["y"], d["width"], d["depth"], item.get("rotation", 0.0))


def wall_footprint(wall: Dict) -> "Polygon":
    """牆的投影：長度沿本地 X（width），厚度沿本地 Y（thickness）。"""
    p = wall["position"]
    return footprint(p["x"], p["y"], wall["width"], wall.get("thickness", 10.0),
                     wall.get("rotation", 0.0))


def inward_normal(rot_deg: float) -> Tuple[float, float]:
    """rotation=0 時正面朝 +Y；回傳該朝向的單位向量。"""
    r = math.radians(rot_deg)
    # 本地 +Y 經逆時針旋轉 rot 後的世界向量
    return (-math.sin(r), math.cos(r))


def clearance_zone_polygon(item: Dict, zone: Dict) -> "Polygon":
    """把家具宣告的 clearance_zone（front/back/left/right + depth）轉成世界座標多邊形。"""
    d = item["dimensions"]
    rot = item.get("rotation", 0.0)
    anchor = zone["anchor"]
    depth = zone["depth"]
    # 該邊在本地座標的外緣與寬度
    if anchor == "front":
        edge, along = d["depth"] / 2.0, d["width"]
        local_center = (0.0, edge + depth / 2.0); w, dp = along, depth
    elif anchor == "back":
        edge, along = d["depth"] / 2.0, d["width"]
        local_center = (0.0, -(edge + depth / 2.0)); w, dp = along, depth
    elif anchor == "right":
        edge, along = d["width"] / 2.0, d["depth"]
        local_center = (edge + depth / 2.0, 0.0); w, dp = depth, along
    else:  # left
        edge, along = d["width"] / 2.0, d["depth"]
        local_center = (-(edge + depth / 2.0), 0.0); w, dp = depth, along
    zw = zone.get("width", along)
    # 用本地中心 + 尺寸建矩形，再旋轉平移到世界
    if anchor in ("front", "back"):
        w = zw
    else:
        dp = zw
    poly = footprint(local_center[0], local_center[1], w, dp, 0.0)
    poly = rotate(poly, rot, origin=(0, 0), use_radians=False)
    p = item["position"]
    return translate(poly, xoff=p["x"], yoff=p["y"])


def door_swing_polygon(door: Dict, segments: int = 12) -> "Polygon":
    """門開合的四分之一圓弧掃掠區（半徑=門寬）。"""
    p = door["position"]
    r = door["width"]
    rot = door.get("rotation", 0.0)
    nx, ny = inward_normal(rot) if door.get("swing_in", True) else inward_normal(rot + 180)
    base_ang = math.atan2(ny, nx)
    hinge_sign = -1.0 if door.get("hinge", "left") == "left" else 1.0
    pts = [(p["x"], p["y"])]
    for i in range(segments + 1):
        a = base_ang + hinge_sign * (math.pi / 2.0) * (i / segments)
        pts.append((p["x"] + r * math.cos(a), p["y"] + r * math.sin(a)))
    return Polygon(pts)


def room_polygon(architecture: Dict) -> "Polygon":
    """優先用明確的 room_polygon；否則由牆中心線外框粗略推導。"""
    rp = architecture.get("room_polygon")
    if rp:
        return Polygon(rp)
    # 後備：用所有牆 footprint 的凸包
    walls = [wall_footprint(w) for w in architecture.get("walls", [])]
    if not walls:
        raise ValueError("architecture 缺少 room_polygon 且無牆可推導")
    return unary_union(walls).convex_hull
