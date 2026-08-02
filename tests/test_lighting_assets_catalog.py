"""燈具 lane 的分類邏輯與交付清單門檻。

背景：2026-07-30 的型錄切換把 793 筆燈具記錄從 items 移除，資產卻已在 CloudFront。
`lighting_assets_manifest.csv` 是把那批資產接回契約的交付憑據，這裡守住它的完整性。
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from backend.catalog.lighting_classification import (
    CONTRACT_LIGHTING_TYPES,
    LIGHTING_TYPES,
    classify_lighting_type,
    is_contract_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "backend/catalog/data/manifests/lighting_assets_manifest.csv"


def _rows() -> list[dict[str, str]]:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_canonical_category_decides_type_before_any_text_guessing() -> None:
    assert classify_lighting_type("檯燈")[0] == "table"
    assert classify_lighting_type("落地燈")[0] == "floor"
    assert classify_lighting_type("壁燈")[0] == "wall"
    assert classify_lighting_type("吊燈")[0] == "pendant"
    assert classify_lighting_type("吸頂燈")[0] == "downlight"
    # 契約沒有 task 這一類，工作燈擺桌面所以歸 table。
    assert classify_lighting_type("工作燈")[0] == "table"
    assert classify_lighting_type("燈罩與燈座")[0] == "shade_base"


def test_vlm_description_outranks_the_corrupted_product_name() -> None:
    """被移除的那批記錄帶著「床 - 」錯誤前綴，只看品名會判錯。"""
    lighting_type, basis = classify_lighting_type(
        "燈具",
        "簡約現代吊燈，採用拋光鎳金屬頂蓋搭配灰色球形燈罩。",
        "床 - Amazon Basics Poly Globe Pendant Light",
    )
    assert lighting_type == "pendant"
    assert basis == "VLM 描述"


def test_non_lighting_sweepings_are_not_promoted_into_the_lane() -> None:
    """移除規則掃進來的啞鈴、花園凳不能變成燈具。"""
    assert classify_lighting_type("燈具", "這是一組氯丁橡膠啞鈴重量。")[0] == "not_lighting"
    assert classify_lighting_type("燈具", "陶瓷花園凳，可當邊桌使用。")[0] == "not_lighting"


def test_candle_lanterns_are_held_for_review_rather_than_called_fixtures() -> None:
    """茶燈燈籠會發光但不是電氣燈具，不該混進可交付燈具。"""
    lighting_type, _ = classify_lighting_type("立鏡", "", "BORRBY 茶燈燈籠，室內外黑色，20 公分")
    assert lighting_type == "unclassified_lighting"
    assert not is_contract_fixture(lighting_type)


def test_manifest_exists_with_the_contract_required_columns() -> None:
    """LIGHTING_CEILING_CATALOG_CONTRACT 與 KAI.md 都指名這份檔案。"""
    assert MANIFEST.is_file(), "lighting_assets_manifest.csv 不存在"
    required = {
        "item_id",
        "glb_url",
        "thumbnail_url",
        "checksum",
        "license",
        "lighting_type",
        "verification_status",
    }
    with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
        header = set(next(csv.reader(handle)))
    assert required <= header, sorted(required - header)


def test_every_manifest_row_is_deliverable_and_uniquely_identified() -> None:
    rows = _rows()
    assert rows, "manifest 是空的"
    ids = [row["item_id"] for row in rows]
    assert len(ids) == len(set(ids)), "item_id 有重複"
    for row in rows:
        assert row["lighting_type"] in LIGHTING_TYPES, row["item_id"]
        # 資產必須真的取得到，否則這份清單沒有交付價值。
        assert row["glb_url"].startswith("https://"), row["item_id"]
        assert row["thumbnail_url"].startswith("https://"), row["item_id"]
        assert row["checksum"], row["item_id"]
        assert row["license"], row["item_id"]


def test_verification_status_gates_exactly_the_contract_enum() -> None:
    """契約：verification_status != verified 不得進 RAG 或第 6 步自動配置。"""
    for row in _rows():
        expected = "verified" if is_contract_fixture(row["lighting_type"]) else "needs_review"
        assert row["verification_status"] == expected, row["item_id"]
        if row["verification_status"] == "verified":
            assert row["lighting_type"] in CONTRACT_LIGHTING_TYPES


def test_lighting_ids_never_overlap_the_furniture_catalog() -> None:
    """燈具與家具是兩條 lane；同一個 id 同時出現代表分流出錯。"""
    furniture = {
        row["item_id"]
        for row in csv.DictReader(
            (ROOT / "JSON/manifests/glb_upload_all_result.csv").open(encoding="utf-8-sig")
        )
    }
    overlap = {row["item_id"] for row in _rows()} & furniture
    assert not overlap, sorted(overlap)[:5]


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_LIGHTING") != "1",
    reason="set ROOMPILOT_TEST_POSTGRES_LIGHTING=1 to check the imported lighting lane",
)
def test_live_lighting_view_only_exposes_verified_contract_fixtures() -> None:
    from backend.catalog.postgres_repository import _borrow_connection, _dict_cursor

    with _borrow_connection(ROOT) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM roompilot.lighting_assets")
            total = int(cursor.fetchone()["n"])
            cursor.execute(
                "SELECT DISTINCT lighting_type FROM roompilot.lighting_assets_current"
            )
            exposed = {row["lighting_type"] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT COUNT(*) AS n FROM roompilot.lighting_assets_current "
                "WHERE verification_status <> 'verified'"
            )
            leaked = int(cursor.fetchone()["n"])

    assert total == len(_rows())
    assert exposed <= set(CONTRACT_LIGHTING_TYPES)
    assert leaked == 0
