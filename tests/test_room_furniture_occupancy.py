"""住戶人數要影響配置（QA 2026-08-01 #4 的殘留）。

實測：兒童房照樣放雙人床、八人份問卷的餐椅只有一張。原因是
recommendedFurnitureForRoom 完全不看住戶資料。
"""

from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


LAYOUT_MODULE = STATIC_DIR / "scene_layout2d.js"


def _recommend(room: dict, occupancy: dict) -> list[list[str]]:
    module_uri = LAYOUT_MODULE.as_uri()
    return run_workflow_script(
        f"""
        import {{ recommendedFurnitureForRoom }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(
          recommendedFurnitureForRoom({json.dumps(room)}, {json.dumps(occupancy)})
        ));
        """
    )


def _variant_of(specs: list[list[str]], furniture_type: str) -> str | None:
    return next((spec[1] for spec in specs if spec[0] == furniture_type), None)


def _count_of(specs: list[list[str]], furniture_type: str) -> int:
    return sum(1 for spec in specs if spec[0] == furniture_type)


def test_children_secondary_bedroom_gets_a_single_bed_and_a_desk() -> None:
    specs = _recommend(
        {"type": "bedroom"},
        {"adults": 2, "children": 2, "bedroomRole": "secondary"},
    )

    assert _variant_of(specs, "bed") == "single"
    assert _variant_of(specs, "desk") == "compact"


def test_primary_bedroom_keeps_a_double_bed_for_two_adults() -> None:
    specs = _recommend(
        {"type": "bedroom"},
        {"adults": 2, "children": 2, "bedroomRole": "primary"},
    )

    assert _variant_of(specs, "bed") == "double"
    assert _count_of(specs, "desk") == 0


def test_single_occupant_primary_bedroom_does_not_get_a_double_bed() -> None:
    specs = _recommend({"type": "bedroom"}, {"adults": 1, "bedroomRole": "primary"})

    assert _variant_of(specs, "bed") == "single"


def test_dining_chairs_follow_the_number_of_people() -> None:
    for seats, expected_table in ((2, "round-4"), (4, "round-4"), (5, "rect-4"), (6, "rect-6")):
        specs = _recommend({"type": "dining_room"}, {"diningSeats": seats})
        assert _count_of(specs, "dining-chair") == seats, seats
        assert _variant_of(specs, "dining-table") == expected_table, seats


def test_dining_seats_are_clamped_to_what_the_catalog_supports() -> None:
    crowded = _recommend({"type": "dining_room"}, {"diningSeats": 40})
    minimal = _recommend({"type": "dining_room"}, {"diningSeats": 1})
    # 0 代表「沒答」而不是「零人用餐」，退回預設四人份。
    unanswered = _recommend({"type": "dining_room"}, {"diningSeats": 0})

    assert _count_of(crowded, "dining-chair") == 6
    assert _count_of(minimal, "dining-chair") == 2
    assert _count_of(unanswered, "dining-chair") == 4


def test_missing_occupancy_still_returns_a_usable_default() -> None:
    specs = _recommend({"type": "dining_room"}, {})

    assert _count_of(specs, "dining-chair") == 4
    assert _variant_of(specs, "dining-table") == "round-4"


def test_scene_bundle_feeds_occupancy_into_the_recommendation() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function occupancyForRoom" in source
    assert "function bedroomRoleFor" in source
    assert "recommendedFurnitureForRoom(room, occupancyForRoom(room))" in source
    # 沒有帶住戶資料的呼叫就是舊行為。
    assert "recommendedFurnitureForRoom(room)," not in source
