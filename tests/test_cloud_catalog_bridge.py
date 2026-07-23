from __future__ import annotations

import csv

import pytest
from fastapi import HTTPException

from roompilot.server import main
from roompilot.server.services import cloud_models


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
    manifest = tmp_path / "manifest.csv"
    _manifest(manifest)
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("ROOMPILOT_CLOUDFRONT_BASE_URL", "https://cdn.example")

    payload = main.catalog_status()

    assert payload["furniture"] == {
        "provider": "aws_cloudfront",
        "manifest_ready": True,
        "manifest_error": None,
        "verified_model_count": 1,
        "cloudfront_base_url": "https://cdn.example",
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
        (main.sample_furniture_file, ("legacy-chair.glb",)),
    ],
)
def test_strict_cloudfront_blocks_legacy_local_model_endpoints(monkeypatch, call, args):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")

    with pytest.raises(HTTPException) as exc_info:
        call(*args)

    assert exc_info.value.status_code == 410


def test_strict_cloudfront_sample_list_does_not_advertise_local_glbs(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")

    assert main.sample_furniture() == {
        "furniture": [],
        "provider": "aws_cloudfront",
        "message": "請由家具型錄取得已驗證的 CloudFront model_url。",
    }


def test_strict_catalog_legacy_viewer_alias_contains_only_cloudfront_urls(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    items = [
        {"model_url": "https://cdn.example/models/chair.glb", "has_model": True},
        {"model_url": "/api/furniture/local/model", "has_model": True},
        {"model_url": None, "has_model": False},
    ]

    assert main._legacy_viewer_models(items) == [
        "https://cdn.example/models/chair.glb"
    ]


def test_frontend3d_accepts_cloudfront_model_urls():
    source = (
        main.PROJECT_DIR / "frontend3d" / "src" / "Furniture.jsx"
    ).read_text(encoding="utf-8")
    assert "file.startsWith('https://')" in source
