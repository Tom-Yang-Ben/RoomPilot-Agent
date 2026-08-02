"""窗前淨空帶分級（2026-08-02 拍板）：落地窗帶 60cm、一般窗帶 70cm。

落地窗擋所有家具，帶太深會廢掉整條牆，拍板 60cm 通行帶（總帳 §2.1 懸案
30/60 取 60）；一般窗維持 70cm 且既有「矮於窗台放行」豁免不變。
"""

from shapely.geometry import Point

from backend.engine.models import Room
from backend.server.scene_service import _window_zones_with_sill


def _floorplan(*segments):
    return {"coordinate_unit": "cm", "window_segments": list(segments)}


def test_floor_to_ceiling_band_is_60_and_standard_band_stays_70():
    room = Room(width=400.0, depth=300.0)
    fp = _floorplan(
        # 落地窗：南側，窗線換算後為 y=0 的 (100,0)-(300,0)
        {
            "start": {"x": -100, "z": -150},
            "end": {"x": 100, "z": -150},
            "window_type": "floor_to_ceiling",
        },
        # 未標型式 → 一般窗（窗台 90）：西側，窗線 x=0 的 (0,100)-(0,200)
        {"start": {"x": -200, "z": -50}, "end": {"x": -200, "z": 50}},
    )
    zones = _window_zones_with_sill(fp, room)
    assert len(zones) == 2
    floor_zone, floor_sill = zones[0]
    std_zone, std_sill = zones[1]
    assert floor_sill == 0.0
    assert std_sill == 90.0
    assert floor_zone.contains(Point(200.0, 55.0))  # 落地窗 60 帶內
    assert not floor_zone.contains(Point(200.0, 65.0))  # 60 帶外（舊 70 帶會誤擋）
    assert std_zone.contains(Point(65.0, 150.0))  # 一般窗 70 帶內
    assert not std_zone.contains(Point(75.0, 150.0))
