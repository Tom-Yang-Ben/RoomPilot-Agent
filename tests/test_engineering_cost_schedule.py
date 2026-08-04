from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.server.engineering.advanced_rag import AdvancedRAGService
from backend.server.engineering.cost import CostService
from backend.server.engineering.knowledge import JsonEngineeringKnowledgeRepository
from backend.server.engineering.models import ProjectSnapshot
from backend.server.engineering.quantity import QuantityService
from backend.server.engineering.schedule import ScheduleService


KNOWLEDGE_DIR = Path("backend/catalog/data/engineering")


def _snapshot() -> ProjectSnapshot:
    return ProjectSnapshot.model_validate(
        {
            "project_id": "cost-schedule-project",
            "project_name": "成本排程測試",
            "revision": "D2",
            "source_project_revision": 2,
            "pricing_basis_date": date.today().isoformat(),
            "rooms": [
                {
                    "room_id": "living-1",
                    "name": "客廳",
                    "room_type": "living_room",
                    "geometry": {
                        "length_cm": 420,
                        "width_cm": 360,
                        "height_cm": 270,
                    },
                    "materials": [
                        {
                            "material_id": "spc-oak",
                            "part": "floor",
                            "name": "SPC 木紋地板",
                            "waste_rate": 0.08,
                        }
                    ],
                    "furniture": [
                        {
                            "furniture_id": "tv-1",
                            "name": "電視",
                            "category": "television",
                            "width_cm": 120,
                            "depth_cm": 10,
                            "height_cm": 80,
                        }
                    ],
                    "equipment_requirements": [],
                    "mep_points": [],
                    "renders": [],
                }
            ],
        }
    )


def _pipeline():
    knowledge = JsonEngineeringKnowledgeRepository(KNOWLEDGE_DIR)
    snapshot = _snapshot()
    quantities = QuantityService().calculate(snapshot)
    retrieval = AdvancedRAGService(knowledge).retrieve(snapshot, quantities)
    return knowledge, snapshot, quantities, retrieval


def test_production_mode_keeps_missing_prices_and_productivity_unknown() -> None:
    knowledge, snapshot, quantities, retrieval = _pipeline()
    estimate = CostService(knowledge, demo_mode=False).estimate(
        snapshot, quantities, retrieval
    )
    assert estimate.lines
    assert estimate.pending_quote_count == len(estimate.lines)
    assert estimate.known_subtotal == 0
    assert estimate.estimated_total is None
    assert all(item.subtotal is None for item in estimate.lines)
    assert all(item.status == "pending_quote" for item in estimate.lines)
    assert "絕不補猜" in estimate.disclaimer

    schedule = ScheduleService(knowledge, demo_mode=False).plan(
        snapshot, quantities, retrieval
    )
    assert schedule.tasks
    assert schedule.unknown_duration_count == len(schedule.tasks)
    assert schedule.estimated_total_days is None
    assert all(item.total_days is None for item in schedule.tasks)


def test_demo_mode_uses_only_demo_records_and_exact_cost_formula() -> None:
    knowledge, snapshot, quantities, retrieval = _pipeline()
    estimate = CostService(knowledge, demo_mode=True).estimate(
        snapshot, quantities, retrieval
    )
    assert estimate.pending_quote_count == 0
    assert estimate.estimated_total == estimate.known_subtotal
    assert estimate.estimated_total and estimate.estimated_total > 0
    assert all(item.price_region == "DEMO_ONLY" for item in estimate.lines)
    assert "示範資料，非正式報價" in estimate.disclaimer

    spc = next(item for item in estimate.lines if item.work_item_code == "FLOOR-SPC")
    expected = round(
        spc.raw_quantity
        * (1 + spc.waste_rate)
        * (
            spc.material_unit_price
            + spc.labor_unit_price
            + spc.other_unit_price
        ),
        2,
    )
    assert spc.subtotal == expected

    schedule = ScheduleService(knowledge, demo_mode=True).plan(
        snapshot, quantities, retrieval
    )
    assert schedule.unknown_duration_count == 0
    assert schedule.estimated_total_days and schedule.estimated_total_days > 0
    assert all(item.total_days is not None for item in schedule.tasks)
    assert all(item.start_day is not None for item in schedule.tasks)
    assert "示範資料，非正式工期" in schedule.disclaimer
