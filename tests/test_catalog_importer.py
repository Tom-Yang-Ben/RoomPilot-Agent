from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sql import import_public_catalog_to_postgres as catalog_import


ROOT = Path(__file__).resolve().parents[1]


def test_project_authored_fixture_passes_generic_import_validation() -> None:
    items, metadata = catalog_import.load_catalog(
        ROOT / "backend" / "catalog" / "data" / "portable_furniture.json"
    )
    rows = catalog_import.normalize_catalog(items, metadata)

    assert len(rows) == 16
    assert len({row["item_id"] for row in rows}) == 16
    assert all(row["source_license"] == "GPL-3.0-or-later" for row in rows)
    assert all(row["license_status"] == "verified" for row in rows)
    assert all(row["width_cm"] > 0 and row["depth_cm"] > 0 for row in rows)


def test_import_validation_rejects_missing_license_and_duplicate_ids() -> None:
    item = {
        "item_id": "chair-1",
        "name_en": "Chair",
        "width_cm": 45,
        "depth_cm": 50,
        "height_cm": 80,
    }
    with pytest.raises(ValueError, match="source_license"):
        catalog_import.normalize_catalog([item], {})

    with pytest.raises(ValueError, match="duplicate item_id"):
        catalog_import.normalize_catalog([item, item], {"license": "CC0-1.0"})


def test_import_validation_blocks_appliances_and_non_positive_dimensions() -> None:
    base = {
        "item_id": "item-1",
        "name_en": "Example",
        "width_cm": 45,
        "depth_cm": 50,
        "height_cm": 80,
        "source_license": "CC0-1.0",
    }
    with pytest.raises(ValueError, match="only kind=furniture"):
        catalog_import.normalize_catalog([{**base, "kind": "appliance"}], {})
    with pytest.raises(ValueError, match="width_cm must be greater than zero"):
        catalog_import.normalize_catalog([{**base, "width_cm": 0}], {})


def test_import_validation_accepts_private_permission_pending_rows() -> None:
    item = {
        "item_id": "private-chair-1",
        "name_en": "Private chair",
        "width_cm": 45,
        "depth_cm": 50,
        "height_cm": 80,
        "source_license": "permission-required",
        "license_status": "permission_required",
    }

    row = catalog_import.normalize_catalog([item], {})[0]
    assert row["is_active"] is True
    assert row["license_status"] == "permission_required"

    with pytest.raises(ValueError, match="license_status"):
        catalog_import.normalize_catalog(
            [{**item, "license_status": "assumed-safe"}], {}
        )


def test_catalog_loader_accepts_furniture_root_and_nested_dimensions(
    tmp_path: Path,
) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "source_license": "CC-BY-4.0",
                "furniture": [
                    {
                        "id": "desk-1",
                        "name": "Desk",
                        "size_cm": {"width": 120, "depth": 60, "height": 75},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    items, metadata = catalog_import.load_catalog(path)
    row = catalog_import.normalize_catalog(items, metadata)[0]
    assert row["item_id"] == "desk-1"
    assert (row["width_cm"], row["depth_cm"], row["height_cm"]) == (120, 60, 75)


def test_upsert_is_atomic_and_does_not_delete_unmentioned_rows() -> None:
    assert "ON CONFLICT (item_id) DO UPDATE" in catalog_import.UPSERT_SQL
    assert "updated_at = NOW()" in catalog_import.UPSERT_SQL
    assert "DELETE" not in catalog_import.UPSERT_SQL
    assert "DROP" not in catalog_import.UPSERT_SQL


def test_generic_schema_matches_importer_contract() -> None:
    schema = catalog_import.DEFAULT_SCHEMA.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_catalog" in schema
    assert "source_license text NOT NULL" in schema
    assert "license_status text NOT NULL DEFAULT 'verified'" in schema
    assert "width_cm double precision NOT NULL CHECK (width_cm > 0)" in schema
    assert "current_setting('roompilot.catalog_visibility', true)" in schema
    assert "roompilot.furniture_catalog_private_current" in schema
    assert "CREATE OR REPLACE VIEW roompilot.furniture_catalog_current" in schema
