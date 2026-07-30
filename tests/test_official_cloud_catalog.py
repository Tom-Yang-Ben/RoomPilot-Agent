from __future__ import annotations

import csv
import json

import pytest

from backend.catalog.cloud_catalog import (
    build_official_catalog,
    official_catalog_diagnostics,
)
from backend.server import main


def _clear_catalog_caches(monkeypatch: pytest.MonkeyPatch | None = None) -> None:
    if monkeypatch is not None:
        monkeypatch.setenv("ROOMPILOT_CATALOG_PROVIDER", "json")
    main.load_style_database.cache_clear()
    main._merged_furniture_catalog_cached.cache_clear()
    main._furniture_payload_cache.cache_clear()
    main._catalog_count_summary.cache_clear()


def test_official_catalog_uses_only_the_8557_json_items(monkeypatch):
    _clear_catalog_caches(monkeypatch)
    catalog = main.load_style_database()
    items = catalog["furniture"]

    assert len(items) == 8_557
    assert len({item["furniture_id"] for item in items}) == 8_557
    assert all(item["glb_url"].startswith("https://ddgsm1yg3xikc.cloudfront.net/") for item in items)
    assert all(item["upload_status"] == "uploaded" for item in items)
    assert {item["primary_style"] for item in items} == {
        "scandinavian",
        "japanese",
        "modern_minimal",
        "cream",
        "industrial",
        "american",
    }
    assert all(item["style_assignment_source"] == "official_json_6styles" for item in items)
    assert all(item.get("embedded_text") for item in items)
    assert all(item.get("text_hash") for item in items)
    assert all("legacy_enrichment_ids" not in item for item in items)
    assert catalog["summary"]["manifest_excluded"] == 0
    assert catalog["summary"]["style_presentation_furniture_ignored"] == 0


def test_style_presentation_metadata_does_not_retain_furniture_rows():
    diagnostics = official_catalog_diagnostics(
        main.CLOUD_CATALOG_PATH,
        main.STYLE_PRESENTATION_DB_PATH,
        main.CLOUD_MANIFEST_PATH,
    )

    assert diagnostics == {
        "official_items": 8_557,
        "manifest_items": 8_557,
        "manifest_excluded_items": 0,
        "style_enriched_items": 8_557,
        "style_unclassified_items": 0,
        "style_presentation_furniture_ignored": 0,
    }


def test_style_presentation_cannot_overwrite_official_furniture_fields():
    cloud_catalog = json.loads(main.CLOUD_CATALOG_PATH.read_text(encoding="utf-8"))
    official_item = cloud_catalog["items"][0]
    style_presentation = {
        "catalog_name": "presentation-only",
        "styles": [],
        "taxonomy": {},
        "furniture": [
            {
                "furniture_id": official_item["id"],
                "description": "legacy value must never enter runtime",
                "taxonomy_group": "equipment",
            }
        ],
    }
    with main.CLOUD_MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))

    catalog, diagnostics = build_official_catalog(
        cloud_catalog, style_presentation, manifest_rows
    )
    actual = catalog["furniture"][0]

    assert actual["description"] == official_item["description"]
    assert actual["taxonomy_group"] != "equipment"
    assert diagnostics["style_presentation_furniture_ignored"] == 1


def test_furniture_api_cache_contains_only_verified_cloud_items(monkeypatch):
    _clear_catalog_caches(monkeypatch)
    items = main._furniture_payload_cache()

    assert len(items) == 8_557
    assert all(item["has_model"] is True for item in items)
    assert all(
        item["model_url"].startswith("https://ddgsm1yg3xikc.cloudfront.net/")
        for item in items
    )


def test_furniture_api_exposes_kai_room_role_and_rag_enrichment(monkeypatch):
    _clear_catalog_caches(monkeypatch)
    items = main._furniture_payload_cache()

    enriched = [item for item in items if item.get("rag_text")]

    assert len(enriched) == 8_557
    assert all(item.get("room_types") for item in enriched[:100])
    assert all(item.get("catalog_role") for item in enriched[:100])
    assert all(item.get("description") for item in enriched[:100])
    assert any("bedroom" in item.get("room_types", []) for item in enriched)


def test_runtime_catalog_rejects_manifest_rows_that_are_not_uploaded():
    cloud_catalog = json.loads(main.CLOUD_CATALOG_PATH.read_text(encoding="utf-8"))
    style_presentation = json.loads(
        main.STYLE_PRESENTATION_DB_PATH.read_text(encoding="utf-8")
    )
    with main.CLOUD_MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))

    manifest_rows[0] = dict(manifest_rows[0])
    manifest_rows[0]["upload_status"] = "pending"

    with pytest.raises(ValueError, match="ready CloudFront upload status"):
        build_official_catalog(cloud_catalog, style_presentation, manifest_rows)
