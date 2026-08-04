"""問卷擺位偏好必須真的進引擎（QA 2026-08-01 #10）。

scene_v2.js 一直有送 placement_preferences，後端完全不讀 → 整條 no-op。
現在能對應到引擎動作的會生效，對應不到的要明講，不能靜默吞掉。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.server.main import app
from backend.server.scene_service import (
    DEFAULT_WALK_MARGIN_CM,
    WIDE_WALK_MARGIN_CM,
    WINDOW_CLEARANCE_DEPTH_CM,
    resolve_placement_preferences,
)


client = TestClient(app)


def test_wide_circulation_widens_the_walk_margin() -> None:
    margin, clearance, applied, ignored = resolve_placement_preferences(
        {"circulation_priority": "wide"}
    )

    assert margin == WIDE_WALK_MARGIN_CM
    assert clearance == WINDOW_CLEARANCE_DEPTH_CM
    assert applied == ["circulation_priority"]
    assert ignored == []


def test_storage_circulation_keeps_the_default_margin() -> None:
    margin, _clearance, applied, _ignored = resolve_placement_preferences(
        {"circulation_priority": "storage"}
    )

    assert margin == DEFAULT_WALK_MARGIN_CM
    assert applied == ["circulation_priority"]


def test_bed_clearance_never_narrows_an_already_wide_margin() -> None:
    margin, _clearance, applied, _ignored = resolve_placement_preferences(
        {"circulation_priority": "wide", "bed_priority": "large"}
    )

    assert margin == WIDE_WALK_MARGIN_CM
    assert set(applied) == {"circulation_priority", "bed_priority"}


def test_window_seat_storage_drops_the_window_clearance_band() -> None:
    """使用者要窗邊臥榻時，窗前淨空帶就是障礙而不是保護。"""
    _margin, clearance, applied, _ignored = resolve_placement_preferences(
        {"window_zone": "seat_storage"}
    )

    assert clearance == 0.0
    assert applied == ["window_zone"]


def test_unknown_preferences_are_reported_rather_than_swallowed() -> None:
    _margin, _clearance, applied, ignored = resolve_placement_preferences(
        {"lighting_bias": "recessed", "circulation_priority": "wide", "ac_type": "wall"}
    )

    assert applied == ["circulation_priority"]
    assert set(ignored) == {"lighting_bias", "ac_type"}


def test_layout_endpoint_reports_which_preferences_it_applied() -> None:
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan": {"coordinate_unit": "cm", "width_cm": 400, "depth_cm": 400},
            "placement_preferences": {
                "circulation_priority": "wide",
                "lighting_bias": "recessed",
            },
            "scene_objects": [{
                "furniture_id": "sofa-1",
                "normalized_type": "sofa",
                "size_cm": {"width": 180, "depth": 85, "height": 80},
            }],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["placement_preferences_applied"] == ["circulation_priority"]
    assert payload["placement_preferences_ignored"] == ["lighting_bias"]


def test_wide_circulation_keeps_furniture_further_from_the_walls() -> None:
    def furthest_edge(preferences: dict) -> float:
        response = client.post(
            "/api/scene/layout",
            json={
                "floorplan": {"coordinate_unit": "cm", "width_cm": 400, "depth_cm": 400},
                "placement_preferences": preferences,
                "scene_objects": [{
                    "furniture_id": "sofa-1",
                    "normalized_type": "sofa",
                    "size_cm": {"width": 180, "depth": 85, "height": 80},
                }],
            },
        )
        assert response.status_code == 200
        placed = response.json()["scene_objects"][0]
        assert placed.get("placement_failed") is not True
        return max(
            abs(float(placed["position_cm"]["x"])),
            abs(float(placed["position_cm"]["z"])),
        )

    # 走道加寬後家具中心不可能比預設更貼牆。
    assert furthest_edge({"circulation_priority": "wide"}) <= furthest_edge({})
