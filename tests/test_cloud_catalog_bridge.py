from __future__ import annotations

import csv

import pytest
from fastapi import HTTPException

from backend.server import main
from scripts.static_source_graph import scene_viewer_source
from backend.server.services import cloud_models


@pytest.fixture(autouse=True)
def _reset_caches():
    cloud_models.clear_cloud_model_caches()
    yield
    cloud_models.clear_cloud_model_caches()


def _manifest(path, *, item_id="chair", status="uploaded"):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["item_id", "name_en", "object_key", "upload_status", "delivery_url"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "item_id": item_id,
                "name_en": "Cloud Chair",
                "object_key": f"models/ikea/furniture/{item_id}.glb",
                "upload_status": status,
                "delivery_url": f"https://cdn.example/models/ikea/furniture/{item_id}.glb",
            }
        )


def test_main_catalog_item_uses_cloudfront_model_url(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest)
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    item = {"furniture_id": "chair", "name_en": "Cloud Chair", "has_model": True}

    assert main._model_status(item) == (True, "CloudFront GLB 可用")
    assert main._model_url_for_merged_item(item) == (
        "https://cdn.example/models/ikea/furniture/chair.glb"
    )


def test_cloudfront_mode_never_falls_back_to_local_model(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest, item_id="another-chair")
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(main, "_resolve_external_zip_entry", lambda _item: (tmp_path, "chair.glb"))

    item = {"furniture_id": "local-only", "name_en": "Local Only Chair"}

    available, reason = main._model_status(item)
    assert available is False
    assert "CloudFront" in reason
    assert main._model_url_for_merged_item(item) is None


def test_catalog_status_exposes_provider_and_verified_count(monkeypatch, tmp_path):
    monkeypatch.setenv("ROOMPILOT_PROFILE", "portable")
    monkeypatch.setenv("ROOMPILOT_CATALOG_PROVIDER", "fixture")

    payload = main.catalog_status()

    assert payload["profile"] == "portable"
    assert payload["fixture"] is True
    assert payload["furniture"] == {
        "provider": "portable_fixture",
        "manifest_ready": True,
        "verified_model_count": 16,
        "catalog_count": 16,
        "source_of_truth": "project_authored_fixture",
        "render_mode": "procedural_fixture",
    }
    assert payload["surfaces"]["provider"] == "local_pending_aws_manifest"
    assert payload["surfaces"]["wall_count"] > 0
    assert payload["surfaces"]["floor_count"] > 0
    assert payload["doors"] == {
        "provider": "procedural_pending_aws_catalog",
        "catalog_count": 0,
    }
    assert payload["style_cards"]["provider"] == "local_allowed"


@pytest.mark.parametrize(
    ("call", "args"),
    [
        (main.furniture_model_gltf, ("legacy-chair",)),
        (main.furniture_model_buffer, ("legacy-chair",)),
        (main.furniture_model_image, ("legacy-chair", 0)),
    ],
)
def test_strict_cloudfront_blocks_legacy_local_model_endpoints(monkeypatch, call, args):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")

    with pytest.raises(HTTPException) as exc_info:
        call(*args)

    assert exc_info.value.status_code == 410


def test_only_the_formal_static_frontend_is_distributed():
    assert not (main.PROJECT_DIR / "frontend").exists()
    viewer = scene_viewer_source(main.STATIC_DIR)
    assert "loadGltfCached(loader, item.model_url)" in viewer
    assert 'item.render_mode === "procedural_fixture"' in viewer
