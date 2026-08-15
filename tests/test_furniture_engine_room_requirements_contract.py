from __future__ import annotations

import json

from test_scene_workflow import ROOT


CONTRACT = ROOT / "docs" / "contracts" / "FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md"
EXAMPLE = ROOT / "docs" / "contracts" / "furniture_engine_room_requirements.example.json"


def test_furniture_engine_contract_documents_required_boundaries() -> None:
    content = CONTRACT.read_text(encoding="utf-8")

    for required_text in (
        "slot_id",
        "catalog_item_id",
        "never_fallback_to_white_model",
        "catalog_item_must_match_slot_type",
        "門片開啟弧線",
        "window_clearance",
        "第 5 步不得因家具尺寸風險、碰撞風險或缺少 GLB 而停住問卷",
        "第 6 步待處理項目未清空前，不可進入第 7 步",
    ):
        assert required_text in content


def test_furniture_engine_example_keeps_slot_size_and_catalog_separate() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    bedroom = next(room for room in payload["rooms"] if room["room_type"] == "bedroom")
    bed = next(slot for slot in bedroom["furniture_slots"] if slot["slot_id"] == "bed")

    assert payload["schema_version"] == "1.0"
    assert bed["selected_size"] == "double"
    assert bed["catalog_item_id"] is None
    assert bed["fit_risk"] is None
    assert bed["missing_glb"] is False
    assert "single" in bed["size_options"]
    assert "king" in bed["size_options"]
    assert payload["engine_rules"]["catalog_item_must_match_slot_type"] is True
    assert payload["engine_rules"]["never_fallback_to_white_model"] is True
