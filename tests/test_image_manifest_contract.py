from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_private_catalog_manifests_are_not_distributed() -> None:
    assert not (ROOT / "JSON").exists()
    assert not (ROOT / "backend" / "catalog" / "data" / "manifests").exists()


def test_portable_fixture_declares_procedural_rendering_only() -> None:
    payload = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "portable_furniture.json")
        .read_text(encoding="utf-8")
    )
    items = payload["items"]

    assert payload["license"] == "GPL-3.0-only"
    assert payload["copyright"] == "AIPE03 第四組"
    assert len(items) == 16
    assert all(item["render_mode"] == "procedural_fixture" for item in items)
    assert all(item["model_url"] is None for item in items)
    assert all("glb_url" not in item for item in items)


def test_full_catalog_assets_are_an_operator_supplied_boundary() -> None:
    documentation = (ROOT / "docs" / "FULL_PROFILE.md").read_text(encoding="utf-8")
    assert "PostgreSQL" in documentation
    assert "不會靜默" in documentation
    assert "不附資料庫 dump" in documentation
