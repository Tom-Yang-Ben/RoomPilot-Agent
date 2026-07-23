from __future__ import annotations

import json
import zipfile

from scripts.verify_ikea_offline_backup import verify_backup


def _write_catalog(path, items):
    path.write_text(
        json.dumps({"furniture": items}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_backup_verifier_reports_unique_catalog_matches(tmp_path):
    catalog = tmp_path / "catalog.json"
    archive = tmp_path / "backup.zip"
    _write_catalog(
        catalog,
        [
            {"furniture_id": "chair", "glb_relative_path": "座椅/chair.glb"},
            {"furniture_id": "table", "glb_relative_path": "桌子/table.glb"},
        ],
    )
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("IKEA/座椅/chair.glb", b"chair")
        output.writestr("IKEA/桌子/table.glb", b"table")
        output.writestr("IKEA/unused.glb", b"unused")

    result = verify_backup(archive, catalog, expected_sha256=None)

    assert {
        key: result[key]
        for key in (
            "catalog_model_count",
            "matched_archive_entries",
            "unmatched_archive_entries",
            "ambiguous",
            "archive_glb_count",
            "sha256_matches",
        )
    } == {
        "catalog_model_count": 2,
        "matched_archive_entries": 2,
        "unmatched_archive_entries": ["IKEA/unused.glb"],
        "ambiguous": {},
        "archive_glb_count": 3,
        "sha256_matches": True,
    }


def test_backup_verifier_reports_ambiguous_catalog_models(tmp_path):
    catalog = tmp_path / "catalog.json"
    archive = tmp_path / "backup.zip"
    _write_catalog(
        catalog,
        [
            {"furniture_id": "chair-a", "glb_relative_path": "A/chair.glb"},
            {"furniture_id": "chair-b", "glb_relative_path": "B/chair.glb"},
        ],
    )
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("IKEA/chair.glb", b"a")

    result = verify_backup(archive, catalog, expected_sha256=None)

    assert result["catalog_model_count"] == 0
    assert result["unmatched_archive_entries"] == []
    assert result["ambiguous"] == {
        "IKEA/chair.glb": ["chair-a", "chair-b"],
    }
