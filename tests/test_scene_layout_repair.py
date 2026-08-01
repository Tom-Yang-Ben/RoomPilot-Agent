"""第 6 步互動編輯也要跑擺放修復迴圈（QA 2026-08-01 #4 的殘留）。

resolve_placements 原本只掛在 /api/scene/generate，所以第 6 步換上一件放不下的
家具（QA 實測 180cm 電視櫃）只會留下一張紅色待處理卡，永遠等不到自動換小款。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server.main import app


client = TestClient(app)


def _floorplan_editor(width_cm: int = 300, depth_cm: int = 300) -> dict:
    return {
        "coordinate_unit": "cm",
        "width_cm": width_cm,
        "depth_cm": depth_cm,
        "room_height_cm": 270,
        "rooms": [{
            "id": "living-1",
            "polygon_cm": [
                {"x": 0, "y": 0},
                {"x": width_cm, "y": 0},
                {"x": width_cm, "y": depth_cm},
                {"x": 0, "y": depth_cm},
            ],
        }],
        "structures": {"walls": [], "doors": [], "windows": [], "beams": [], "columns": []},
    }


def _oversized_tv_bench() -> dict:
    """比房間還大的電視櫃：引擎一定回 placement_failed。"""
    return {
        "furniture_id": "living-1-tv-bench-1",
        "catalog_furniture_id": "abo-tv-huge",
        "name_zh_raw": "超大電視櫃",
        "normalized_type": "tv-bench",
        "size_cm": {"width": 900, "depth": 400, "height": 50},
    }


def _small_tv_bench_pool() -> tuple[dict, ...]:
    return (
        {
            "furniture_id": "abo-tv-small",
            "normalized_type": "tv-bench",
            "name_zh_raw": "窄版電視櫃",
            "size_cm": {"width": 120, "depth": 40, "height": 50},
            "has_model": True,
            "model_url": "/dataset/abo-tv-small.glb",
        },
    )


def _post(scene_objects: list[dict]) -> dict:
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan_editor": _floorplan_editor(),
            "placement_room_id": "living-1",
            "scene_objects": scene_objects,
        },
    )
    assert response.status_code == 200
    return response.json()


def _sofa() -> dict:
    """電視櫃是副件，沒有沙發當主件就會直接退場而不是換小款。"""
    return {
        "furniture_id": "living-1-sofa-1",
        "catalog_furniture_id": "abo-sofa-1",
        "name_zh_raw": "沙發",
        "normalized_type": "sofa",
        "size_cm": {"width": 180, "depth": 85, "height": 80},
    }


def _by_id(objects: list[dict]) -> dict[str, dict]:
    return {str(item["furniture_id"]): item for item in objects}


def test_layout_swaps_in_a_smaller_model_instead_of_leaving_it_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_furniture_payload_cache", _small_tv_bench_pool)

    payload = _post([_sofa(), _oversized_tv_bench()])

    report = payload["placement_resolution_report"]
    assert [entry["action"] for entry in report] == ["replace"]
    assert "窄版電視櫃" in report[0]["message_zh"]

    placed = _by_id(payload["scene_objects"])["living-1-tv-bench-1"]
    # 前端的身分鍵不能被換掉，否則畫面上那一件會變成另一件。
    assert placed["catalog_furniture_id"] == "abo-tv-small"
    assert placed["placement_failed"] is False
    assert "instance_id" not in placed


def test_layout_removes_what_cannot_be_downsized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_furniture_payload_cache", tuple)

    payload = _post([_sofa(), _oversized_tv_bench()])

    assert [entry["action"] for entry in payload["placement_resolution_report"]] == ["remove"]
    assert list(_by_id(payload["scene_objects"])) == ["living-1-sofa-1"]


def test_layout_escalates_user_specified_furniture_instead_of_replacing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_furniture_payload_cache", _small_tv_bench_pool)

    payload = _post([{**_oversized_tv_bench(), "user_specified": True}])

    report = payload["placement_resolution_report"]
    assert [entry["action"] for entry in report] == ["escalate"]
    # 使用者指定的家具留在場上並保持 placement_failed，讓待處理清單說得出原因。
    placed = payload["scene_objects"][0]
    assert placed["furniture_id"] == "living-1-tv-bench-1"
    assert placed["catalog_furniture_id"] == "abo-tv-huge"
    assert placed["placement_failed"] is True


def test_layout_without_failures_reports_nothing_and_keeps_identity() -> None:
    payload = _post([{
        "furniture_id": "living-1-sofa-1",
        "catalog_furniture_id": "abo-sofa-1",
        "name_zh_raw": "沙發",
        "normalized_type": "sofa",
        "size_cm": {"width": 180, "depth": 85, "height": 80},
    }])

    assert payload["placement_resolution_report"] == []
    placed = payload["scene_objects"][0]
    assert placed["furniture_id"] == "living-1-sofa-1"
    assert placed["catalog_furniture_id"] == "abo-sofa-1"
    assert placed.get("placement_failed") is not True
