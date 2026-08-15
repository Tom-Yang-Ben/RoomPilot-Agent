from __future__ import annotations

import json
import hashlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.surface_material_processing import (
    PROCESSOR_VERSION,
    _promote_generation,
    build_processed_surface_materials,
    installation_spec_for_surface,
    render_tileable_material,
    uv_repeat_for_span,
)
from backend.server import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_supplier_dimensions_drive_plank_layout_defaults():
    spec = installation_spec_for_surface(
        {
            "surface_id": "sample-plank",
            "source_path": "ccity-tile-flooring/sample.png",
            "source_size": "7.2 x 29.5 cm",
        }
    )

    assert spec["tile_size_cm"] == {
        "width": 29.5,
        "height": 7.2,
        "source_text": "7.2 x 29.5 cm",
    }
    assert spec["dimension_source"] == "supplier_catalog"
    assert spec["dimension_confidence"] == "verified_source_text"
    assert spec["grout_width_mm"] == 3.0
    assert spec["layout_pattern"] == "running_bond_33"
    assert spec["row_offset_fraction"] == pytest.approx(1 / 3)
    assert spec["orientation_rule"] == "long_edge_parallel_to_room_long_axis"
    assert spec["designer_confirmation_required"] is True


def test_square_tile_uses_straight_grid():
    spec = installation_spec_for_surface(
        {
            "surface_id": "sample-square",
            "source_path": "ccity-tile-flooring/sample.png",
            "source_size": "60 x 60 cm",
        }
    )

    assert spec["layout_pattern"] == "straight_grid"
    assert spec["row_offset_fraction"] == 0
    assert spec["tile_size_cm"]["width"] == 60
    assert spec["tile_size_cm"]["height"] == 60


def test_tileable_material_encodes_grout_and_physical_module_size(tmp_path):
    source = tmp_path / "plank.png"
    destination = tmp_path / "processed.png"
    Image.new("RGBA", (300, 72), (132, 104, 76, 255)).save(source)
    spec = installation_spec_for_surface(
        {
            "surface_id": "sample-plank",
            "source_path": "ccity-wood-look-tiles/sample.png",
            "source_size": "20 x 120 cm",
        }
    )

    processing = render_tileable_material(source, destination, spec)

    assert processing["module_size_cm"] == pytest.approx(
        {"width": 360.9, "height": 60.9}
    )
    assert processing["pattern_columns"] == 3
    assert processing["pattern_rows"] == 3
    assert processing["row_offset_fraction"] == pytest.approx(1 / 3)
    with Image.open(destination) as material:
        assert material.width <= 1024
        assert material.height <= 1024
        assert material.getchannel("A").getbbox() == (0, 0, *material.size)
        assert material.info["RoomPilotMaterialPattern"] == "running_bond_33"

    repeat = uv_repeat_for_span(processing, width_m=4.2, depth_m=3.6)
    assert repeat == pytest.approx([420 / 360.9, 360 / 60.9])


def test_committed_public_catalog_defines_only_procedural_materials():
    catalog = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "surface_catalog.json"
        ).read_text(encoding="utf-8")
    )
    assert len(catalog["surfaces"]) == 9
    assert all(surface["texture_url"] is None for surface in catalog["surfaces"])
    assert all(surface["source_license_status"] == "GPL-3.0-only" for surface in catalog["surfaces"])
    assert not (
        PROJECT_ROOT / "backend" / "catalog" / "data" / "surface_material_manifest.json"
    ).exists()


def test_styles_api_exposes_procedural_surface_contract():
    client = TestClient(main.app)
    response = client.get("/api/styles")

    assert response.status_code == 200
    surfaces = {
        surface["surface_id"]: surface
        for surface in response.json()["surface_catalog"]["surfaces"]
    }
    sample = surfaces["light_oak"]
    assert sample["usage"] == ["floor"]
    assert sample["color_hex"].startswith("#")
    assert sample["texture_url"] is None
    assert response.headers["content-encoding"] == "gzip"


def test_batch_failure_does_not_replace_existing_materials_or_catalog(tmp_path):
    static_root = tmp_path / "static"
    source_root = static_root / "surface_assets" / "_cropped" / "ccity-tile-flooring"
    source_root.mkdir(parents=True)
    Image.new("RGBA", (60, 60), (90, 100, 110, 255)).save(source_root / "ok.png")
    (source_root / "broken.png").write_bytes(b"not-an-image")
    final_root = static_root / "surface_assets" / "_processed"
    final_root.mkdir(parents=True)
    (final_root / "sentinel.txt").write_text("old-generation", encoding="utf-8")
    catalog_path = tmp_path / "surface_catalog.json"
    original_catalog = {
        "surfaces": [
            {
                "surface_id": name,
                "source_path": f"ccity-tile-flooring/{name}.png",
                "source_size": "60 x 60 cm",
                "preview_url": f"/static/surface_assets/_cropped/ccity-tile-flooring/{name}.png",
                "texture_url": f"/static/surface_assets/ccity-tile-flooring/{name}.png",
            }
            for name in ("ok", "broken")
        ]
    }
    catalog_path.write_text(json.dumps(original_catalog), encoding="utf-8")
    manifest_path = tmp_path / "surface_material_manifest.json"

    with pytest.raises(Exception):
        build_processed_surface_materials(
            catalog_path=catalog_path,
            static_root=static_root,
            manifest_path=manifest_path,
        )

    assert json.loads(catalog_path.read_text(encoding="utf-8")) == original_catalog
    assert (final_root / "sentinel.txt").read_text(encoding="utf-8") == "old-generation"
    assert not (final_root / "ccity-tile-flooring" / "ok.png").exists()
    assert not manifest_path.exists()


def test_shape_geometry_uvs_are_normalized_before_physical_repeat(tmp_path):
    source = (
            PROJECT_ROOT / "backend" / "server" / "static" / "scene_texture_uv.js"
    )
    module_path = tmp_path / "scene_texture_uv.mjs"
    module_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    script = f"""
      import {{ normalizedPlanarUvs }} from {json.dumps(module_path.as_uri())};
      const uv = normalizedPlanarUvs([10, -8, 0, 14, -8, 0, 14, -5, 0, 10, -5, 0]);
      process.stdout.write(JSON.stringify(uv));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [0, 0, 1, 0, 1, 1, 0, 1]


def test_promotion_failure_restores_assets_catalog_and_manifest(tmp_path, monkeypatch):
    processed_root = tmp_path / "processed"
    staged_assets = tmp_path / "processed.roompilot-staging"
    catalog_path = tmp_path / "catalog.json"
    staged_catalog = tmp_path / "catalog.json.roompilot-next"
    manifest_path = tmp_path / "manifest.json"
    staged_manifest = tmp_path / "manifest.json.roompilot-next"
    processed_root.mkdir()
    staged_assets.mkdir()
    (processed_root / "generation.txt").write_text("old", encoding="utf-8")
    (staged_assets / "generation.txt").write_text("new", encoding="utf-8")
    catalog_path.write_text("old-catalog", encoding="utf-8")
    staged_catalog.write_text("new-catalog", encoding="utf-8")
    manifest_path.write_text("old-manifest", encoding="utf-8")
    staged_manifest.write_text("new-manifest", encoding="utf-8")
    original_replace = Path.replace

    def fail_third_promotion(path: Path, target: Path):
        if path == staged_manifest:
            raise OSError("injected manifest promotion failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_third_promotion)
    with pytest.raises(OSError, match="injected manifest promotion failure"):
        _promote_generation(
            staged_assets=staged_assets,
            processed_root=processed_root,
            staged_catalog=staged_catalog,
            catalog_path=catalog_path,
            staged_manifest=staged_manifest,
            manifest_path=manifest_path,
        )

    assert (processed_root / "generation.txt").read_text(encoding="utf-8") == "old"
    assert catalog_path.read_text(encoding="utf-8") == "old-catalog"
    assert manifest_path.read_text(encoding="utf-8") == "old-manifest"
    assert not list(tmp_path.glob("*.roompilot-backup"))
