from __future__ import annotations

import csv

import pytest

from backend.server.services import cloud_models


@pytest.fixture(autouse=True)
def _isolate_cloud_model_caches():
    cloud_models.clear_cloud_model_caches()
    yield
    cloud_models.clear_cloud_model_caches()


def _write_manifest(path, rows):
    fieldnames = ["item_id", "name_en", "object_key", "upload_status", "delivery_url"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_default_manifest_path_follows_backend_package_layout():
    assert cloud_models.DEFAULT_MANIFEST_PATH == (
        cloud_models.PROJECT_DIR
        / "backend"
        / "catalog"
        / "data"
        / "manifests"
        / "glb_upload_all_result.csv"
    )
    assert cloud_models.DEFAULT_MANIFEST_PATH.is_file()


def test_cloud_model_url_uses_verified_delivery_url(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    expected = "https://cdn.example/models/ikea/furniture/chair.glb"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "chair",
                "name_en": "Chair",
                "object_key": "models/ikea/furniture/chair.glb",
                "upload_status": "already_exists",
                "delivery_url": expected,
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    assert cloud_models.cloud_model_url({"furniture_id": "chair"}) == expected


@pytest.mark.parametrize("status", ["", "pending", "failed"])
def test_unverified_object_key_is_never_published(monkeypatch, tmp_path, status):
    manifest = tmp_path / "upload.csv"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "chair",
                "name_en": "Chair",
                "object_key": "models/ikea/furniture/chair.glb",
                "upload_status": status,
                "delivery_url": "",
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("ROOMPILOT_CLOUDFRONT_BASE_URL", "https://cdn.example")

    assert cloud_models.cloud_model_url({"furniture_id": "chair"}) is None


@pytest.mark.parametrize("status", ["", "pending", "failed"])
def test_unverified_manifest_delivery_url_is_never_published(monkeypatch, tmp_path, status):
    manifest = tmp_path / "upload.csv"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "chair",
                "name_en": "Chair",
                "object_key": "models/ikea/furniture/chair.glb",
                "upload_status": status,
                "delivery_url": "https://cdn.example/models/ikea/furniture/chair.glb",
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    assert cloud_models.cloud_model_url({"furniture_id": "chair"}) is None


def test_merged_priority_id_can_resolve_cloud_model(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    expected = "https://cdn.example/models/abo/furniture/alternate.glb"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "alternate",
                "name_en": "Alternate Chair",
                "object_key": "models/abo/furniture/alternate.glb",
                "upload_status": "uploaded",
                "delivery_url": expected,
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    item = {"furniture_id": "primary", "model_priority_ids": ["alternate"]}
    assert cloud_models.cloud_model_url(item) == expected


def test_legacy_id_matches_only_one_exact_normalized_name(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    expected = "https://cdn.example/models/abo/furniture/chair.glb"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "abo-chair",
                "name_en": "Amazon Brand – Example Chair",
                "object_key": "models/abo/furniture/chair.glb",
                "upload_status": "uploaded",
                "delivery_url": expected,
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    item = {"furniture_id": "ext_123", "name_en": "Amazon Brand - Example Chair"}
    assert cloud_models.cloud_model_url(item) == expected


def test_ambiguous_english_name_is_not_guessed(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "one",
                "name_en": "Same Chair",
                "object_key": "models/abo/furniture/one.glb",
                "upload_status": "uploaded",
                "delivery_url": "https://cdn.example/models/abo/furniture/one.glb",
            },
            {
                "item_id": "two",
                "name_en": "Same Chair",
                "object_key": "models/abo/furniture/two.glb",
                "upload_status": "uploaded",
                "delivery_url": "https://cdn.example/models/abo/furniture/two.glb",
            },
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    assert cloud_models.cloud_model_url({"furniture_id": "legacy", "name_en": "Same Chair"}) is None


def test_local_mode_does_not_expose_manifest_url(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    _write_manifest(
        manifest,
        [
            {
                "item_id": "chair",
                "name_en": "Chair",
                "object_key": "models/ikea/furniture/chair.glb",
                "upload_status": "uploaded",
                "delivery_url": "https://cdn.example/models/ikea/furniture/chair.glb",
            }
        ],
    )
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    assert cloud_models.cloud_model_url({"furniture_id": "chair"}) is None


def test_auto_mode_is_not_a_hidden_local_fallback(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "auto")

    assert cloud_models.model_delivery_mode() == "local"
    assert cloud_models.manifest_status()["provider"] == "local"


def test_catalog_delivery_url_requires_ready_upload_status(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    _write_manifest(manifest, [])
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    item = {
        "furniture_id": "unverified-chair",
        "delivery_url": "https://cdn.example/models/unverified-chair.glb",
        "upload_status": "pending",
    }
    assert cloud_models.cloud_model_url(item) is None


def test_ready_catalog_item_cannot_bypass_empty_manifest(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    _write_manifest(manifest, [])
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("ROOMPILOT_CLOUDFRONT_BASE_URL", "https://cdn.example")

    item = {
        "furniture_id": "unverified-chair",
        "delivery_url": "https://cdn.example/models/unverified-chair.glb",
        "object_key": "models/unverified-chair.glb",
        "upload_status": "uploaded",
    }
    assert cloud_models.cloud_model_url(item) is None


def test_corrupt_manifest_fails_closed_and_reports_not_ready(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    manifest.write_bytes(b"\xff\xfe\x00not-a-csv")
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    assert cloud_models.cloud_model_url({"furniture_id": "chair"}) is None
    status = cloud_models.manifest_status()
    assert status["manifest_ready"] is False
    assert status["verified_model_count"] == 0
    assert status["manifest_error"] == "invalid_or_unreadable"


def test_header_only_manifest_is_not_ready(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.csv"
    _write_manifest(manifest, [])
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront")
    monkeypatch.setenv("ROOMPILOT_GLB_MANIFEST_PATH", str(manifest))

    status = cloud_models.manifest_status()
    assert status["manifest_ready"] is False
    assert status["verified_model_count"] == 0
    assert status["manifest_error"] == "empty"


def test_bundled_kai_aws_manifest_is_the_default_cloud_source(monkeypatch):
    monkeypatch.delenv("ROOMPILOT_MODEL_DELIVERY_MODE", raising=False)
    monkeypatch.delenv("ROOMPILOT_GLB_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("ROOMPILOT_CLOUDFRONT_BASE_URL", raising=False)

    status = cloud_models.manifest_status()

    assert status == {
        "mode": "cloudfront",
        "provider": "aws_cloudfront",
        "manifest_ready": True,
        "manifest_error": None,
        "verified_model_count": 9350,
        "cloudfront_base_url": "https://ddgsm1yg3xikc.cloudfront.net",
    }
