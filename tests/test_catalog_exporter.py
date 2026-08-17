from __future__ import annotations

from pathlib import Path

import pytest

from scripts.sql.export_catalog_from_postgres import (
    build_payload,
    catalog_query,
    default_output_path,
    normalized_catalog_query,
    write_payload,
)
from scripts.sql.import_public_catalog_to_postgres import (
    COLUMNS,
    load_catalog,
    normalize_catalog,
)


def _catalog_row() -> dict:
    row = {column: None for column in COLUMNS}
    row.update(
        {
            "item_id": "fixture-chair",
            "kind": "furniture",
            "name_en": "Fixture Chair",
            "name_zh": "測試椅",
            "catalog_scope": "developer_supplied",
            "width_cm": 45.0,
            "depth_cm": 50.0,
            "height_cm": 82.0,
            "style_codes": ["modern_minimal"],
            "style_confidences": [1.0],
            "room_codes": ["living_room"],
            "rag_text": ["compact chair"],
            "mood_tags": [],
            "features": [],
            "search_keywords": ["chair"],
            "must_against_wall": False,
            "can_rotate": True,
            "usable_for_moodboard": True,
            "is_active": True,
            "source_license": "GPL-3.0-or-later",
            "license_status": "verified",
        }
    )
    return row


def test_export_visibility_is_explicit_and_fail_closed() -> None:
    public_query = catalog_query("public")
    private_query = catalog_query("private")

    assert "is_active" in public_query
    assert "license_status = 'verified'" in public_query
    assert "license_status = 'verified'" not in private_query
    assert public_query.endswith("ORDER BY item_id")
    with pytest.raises(ValueError, match="unsupported visibility"):
        catalog_query("all")

    normalized_query = normalized_catalog_query()
    assert "roompilot.furniture_catalog_api_current" in normalized_query
    assert "permission_required" in normalized_query
    assert "item.raw_data ->> 'source_license'" in normalized_query


def test_export_payload_round_trips_through_the_public_importer(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "catalog.json"
    payload = build_payload([_catalog_row()], "public")

    digest = write_payload(payload, output_path)
    items, metadata = load_catalog(output_path)
    normalized = normalize_catalog(items, metadata)

    assert len(digest) == 64
    assert payload["item_count"] == 1
    assert normalized[0]["item_id"] == "fixture-chair"
    assert normalized[0]["source_license"] == "GPL-3.0-or-later"


def test_export_aligns_legacy_style_confidences_to_style_codes() -> None:
    row = _catalog_row()
    row["style_codes"] = ["modern_minimal", None, "modern_minimal", "industrial"]
    row["style_confidences"] = [0.8, 0.2]

    payload = build_payload([row], "public")

    assert payload["items"][0]["style_confidences"] == [0.8, 1.0]


def test_default_exports_stay_in_the_git_ignored_runtime_tree() -> None:
    assert default_output_path("private").as_posix().endswith(
        ".runtime/exports/furniture_catalog_private.json"
    )
