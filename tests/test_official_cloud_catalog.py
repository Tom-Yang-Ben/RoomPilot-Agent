from __future__ import annotations

import csv
import json

import pytest

from backend.catalog.cloud_catalog import (
    build_official_catalog,
    official_catalog_diagnostics,
)
from backend.server import main


def _clear_catalog_caches() -> None:
    main.load_style_database.cache_clear()
    main._merged_furniture_catalog_cached.cache_clear()
    main._furniture_payload_cache.cache_clear()
    main._catalog_count_summary.cache_clear()


def test_official_catalog_uses_only_the_9350_cloud_items():
    _clear_catalog_caches()
    catalog = main.load_style_database()
    items = catalog["furniture"]

    assert len(items) == 9_350
    assert len({item["furniture_id"] for item in items}) == 9_350
    assert all(item["glb_url"].startswith("https://ddgsm1yg3xikc.cloudfront.net/") for item in items)
    assert all(item["upload_status"] == "uploaded" for item in items)
    assert catalog["summary"]["legacy_rows_excluded"] == 1_514


def test_legacy_catalog_is_enrichment_only():
    diagnostics = official_catalog_diagnostics(
        main.CLOUD_CATALOG_PATH,
        main.STYLE_ENRICHMENT_DB_PATH,
        main.CLOUD_MANIFEST_PATH,
    )

    assert diagnostics == {
        "official_items": 9_350,
        "manifest_items": 9_350,
        "style_enriched_items": 9_021,
        "style_unclassified_items": 329,
        "legacy_exact_matches": 1_774,
        "legacy_unique_name_matches": 7_262,
        "legacy_rows_excluded": 1_514,
    }


def test_furniture_api_cache_contains_only_verified_cloud_items():
    _clear_catalog_caches()
    items = main._furniture_payload_cache()

    assert len(items) == 9_350
    assert all(item["has_model"] is True for item in items)
    assert all(
        item["model_url"].startswith("https://ddgsm1yg3xikc.cloudfront.net/")
        for item in items
    )


def test_runtime_catalog_rejects_manifest_rows_that_are_not_uploaded():
    cloud_catalog = json.loads(main.CLOUD_CATALOG_PATH.read_text(encoding="utf-8"))
    style_enrichment = json.loads(
        main.STYLE_ENRICHMENT_DB_PATH.read_text(encoding="utf-8")
    )
    with main.CLOUD_MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))

    manifest_rows[0] = dict(manifest_rows[0])
    manifest_rows[0]["upload_status"] = "pending"

    with pytest.raises(ValueError, match="ready CloudFront upload status"):
        build_official_catalog(cloud_catalog, style_enrichment, manifest_rows)
