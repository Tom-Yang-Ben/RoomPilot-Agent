"""每條型錄讀取路徑都要走同一道正規化（QA 2026-08-01 #3）。

02eb0d6 只修到 scene/agent/site 三條路徑，REST 的 /api/furniture 仍直接吐
SQL 列：placement_surface 全缺（第 6 步把壁掛與擺飾當落地家具算碰撞而卡在
待處理清單），style_candidates 也沒去重（同一個 style_id 重複灌高排序）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server.main import app


client = TestClient(app)


def _raw_sql_row(furniture_id: str, normalized_type: str) -> dict:
    """模擬 view 直接回來的列：沒有 placement_surface、風格候選重複。"""
    return {
        "furniture_id": furniture_id,
        "normalized_type": normalized_type,
        "name_zh_raw": furniture_id,
        "name_zh": furniture_id,
        "size_cm": {"width": 40, "depth": 30, "height": 10},
        "has_model": True,
        "model_url": f"https://cdn.example/{furniture_id}.glb",
        "style_candidates": [
            {"style_id": "scandinavian", "score": 0.9},
            {"style_id": "scandinavian", "score": 0.4},
            {"style_id": "japanese", "score": 0.7},
        ],
    }


@dataclass
class _FakePage:
    items: tuple[dict, ...]
    page: int = 1
    page_size: int = 24
    total: int = 2
    has_next_page: bool = False
    model_urls: tuple[str, ...] = ()
    type_options: tuple[str, ...] = ("wall-shelf", "sofa")
    category_groups: tuple[dict, ...] = ()
    filter_options: dict = field(default_factory=dict)


@pytest.fixture
def postgres_rows(monkeypatch: pytest.MonkeyPatch):
    rows = (
        _raw_sql_row("shelf-1", "wall-shelf"),
        _raw_sql_row("sofa-1", "sofa"),
    )
    monkeypatch.setattr(main, "postgres_catalog_requested", lambda _dir: True)
    monkeypatch.setattr(
        main, "query_postgres_catalog", lambda _dir, _query: _FakePage(items=rows)
    )
    monkeypatch.setattr(main, "get_postgres_catalog_item", lambda _dir, fid: next(
        (dict(row) for row in rows if row["furniture_id"] == fid), None
    ))
    return rows


def test_rest_catalog_page_carries_placement_surface(postgres_rows) -> None:
    response = client.get("/api/furniture", params={"detail": "scene"})

    assert response.status_code == 200
    surfaces = {
        item["furniture_id"]: item.get("placement_surface")
        for item in response.json()["items"]
    }
    assert all(surfaces.values()), f"placement_surface 仍有缺漏：{surfaces}"
    # 壁掛層架不是落地家具，第 6 步不該拿它的 footprint 去算碰撞。
    assert surfaces["shelf-1"] != surfaces["sofa-1"]


def test_rest_catalog_page_dedupes_style_candidates(postgres_rows) -> None:
    response = client.get("/api/furniture", params={"detail": "scene"})

    assert response.status_code == 200
    for item in response.json()["items"]:
        style_ids = [
            candidate.get("style_id")
            for candidate in item.get("style_candidates") or []
        ]
        assert len(style_ids) == len(set(style_ids)), item["furniture_id"]


def test_single_item_detail_matches_the_list_normalization(postgres_rows) -> None:
    listed = next(
        item
        for item in client.get("/api/furniture", params={"detail": "scene"}).json()["items"]
        if item["furniture_id"] == "shelf-1"
    )
    detail = client.get("/api/furniture/shelf-1").json()

    assert detail["placement_surface"] == listed["placement_surface"]
    detail_styles = [
        candidate.get("style_id") for candidate in detail.get("style_candidates") or []
    ]
    assert len(detail_styles) == len(set(detail_styles))
