from __future__ import annotations

from datetime import date

from backend.server.engineering.models import ProjectSnapshot
from backend.server.engineering.quantity import QuantityService
from backend.server.engineering.rules import ExistingEngineRuleService


def _snapshot(*, furniture: list[dict] | None = None) -> ProjectSnapshot:
    return ProjectSnapshot.model_validate(
        {
            "project_id": "phase2-project",
            "project_name": "Phase 2",
            "revision": "D4",
            "source_project_revision": 4,
            "pricing_basis_date": date.today().isoformat(),
            "rooms": [
                {
                    "room_id": "living-1",
                    "name": "L 型客廳",
                    "room_type": "living_room",
                    "geometry": {
                        "length_cm": 400,
                        "width_cm": 400,
                        "height_cm": 270,
                        "opening_area_m2": 2,
                        "polygon_cm": [
                            {"x_cm": 0, "y_cm": 0},
                            {"x_cm": 400, "y_cm": 0},
                            {"x_cm": 400, "y_cm": 200},
                            {"x_cm": 200, "y_cm": 200},
                            {"x_cm": 200, "y_cm": 400},
                            {"x_cm": 0, "y_cm": 400},
                        ],
                    },
                    "materials": [],
                    "furniture": furniture or [],
                    "equipment_requirements": [],
                    "mep_points": [],
                    "renders": [],
                }
            ],
        }
    )


def _furniture(item_id: str, x_cm: float, y_cm: float) -> dict:
    return {
        "furniture_id": item_id,
        "name": item_id,
        "category": "sofa",
        "width_cm": 120,
        "depth_cm": 60,
        "height_cm": 80,
        "x_cm": x_cm,
        "y_cm": y_cm,
        "rotation_deg": 0,
    }


def test_quantity_uses_polygon_cm_not_bounding_box() -> None:
    result = QuantityService().calculate(_snapshot())
    room = result.rooms[0]
    assert room.geometry_source == "polygon_cm"
    assert room.floor_area_m2 == 12
    assert room.ceiling_area_m2 == 12
    assert room.perimeter_m == 16
    assert room.gross_wall_area_m2 == 43.2
    assert room.net_wall_area_m2 == 41.2


def test_rule_service_delegates_overlap_to_existing_engine() -> None:
    snapshot = _snapshot(
        furniture=[
            _furniture("sofa-a", 0, 0),
            _furniture("sofa-b", 0, 0),
        ]
    )
    quantities = QuantityService().calculate(snapshot)
    result = ExistingEngineRuleService().validate(snapshot, quantities)
    engine_failures = [
        item
        for item in result.results
        if item.rule == "furniture_geometry_legality" and not item.passed
    ]
    assert engine_failures
    assert all(item.rule_source == "ancai_engine" for item in engine_failures)
    assert any("重疊" in item.message for item in engine_failures)
    assert result.engine_adapter.endswith("validate_single_placement")


def test_existing_placement_failure_is_not_silently_accepted() -> None:
    item = _furniture("blocked-sofa", 0, 0)
    item["placement_failed"] = True
    item["placement_reason"] = "找不到合法擺放位置"
    snapshot = _snapshot(furniture=[item])
    result = ExistingEngineRuleService().validate(
        snapshot, QuantityService().calculate(snapshot)
    )
    risk = next(item for item in result.results if item.rule == "existing_placement_failed")
    assert risk.passed is False
    assert risk.severity == "high"
    assert risk.rule_source == "ancai_engine"
