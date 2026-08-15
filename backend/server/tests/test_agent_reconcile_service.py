"""step6 ↔ agent 擺放對帳的煙霧測試（不需 LLM/RAG，只跑 engine 擺位）。"""
from __future__ import annotations

import pytest

from backend.server import agent_reconcile_service as svc

ITEMS = [
    {
        "furniture_id": "sofa-1",
        "normalized_type": "sofa",
        "name_zh_raw": "三人沙發",
        "size_cm": {"width": 180, "depth": 90, "height": 85},
    },
    {
        "furniture_id": "wd-1",
        "normalized_type": "wardrobe",
        "name_zh_raw": "衣櫃",
        "size_cm": {"width": 120, "depth": 60, "height": 200},
    },
]


def test_adapter_maps_size_and_type():
    furniture_list = svc._to_furniture_list("living", [ITEMS[0]])
    item = furniture_list.items[0]
    assert item.category == "sofa"
    assert (item.width_cm, item.depth_cm, item.height_cm) == (180.0, 90.0, 85.0)
    assert item.room_id == "living"
    assert item.catalog_id == "sofa-1"


def test_reconcile_spacious_room_is_consistent_and_legal():
    report = svc.reconcile_room("living", 600, 500, ITEMS)
    # 核心不變式：agent 的 PlaceFurnitureTool 只提交合法擺放 → 驗證必為 0 硬違規。
    assert report["agent"]["hard_violations"] == []
    # 寬敞房兩件都放得下，兩條路徑家族覆蓋一致 → 對帳一致。
    assert report["step6"]["placed"] == 2
    assert report["agent"]["placed"] == 2
    assert report["consistent"] is True
    assert report["divergence"]["families_only_in_step6"] == []
    assert report["divergence"]["families_only_in_agent"] == []


def test_empty_items_raises():
    with pytest.raises(ValueError):
        svc.reconcile_room("living", 500, 400, [])
