from __future__ import annotations

from pathlib import Path

from backend.server.services import cloud_images


ROOT = Path(__file__).resolve().parents[1]
def test_remote_image_manifest_has_no_private_default() -> None:
    assert not (ROOT / "backend" / "catalog" / "data" / "manifests").exists()
    assert cloud_images.DEFAULT_IMAGE_MANIFEST_PATH is None
    assert cloud_images.DEFAULT_CLOUDFRONT_BASE_URL is None


def test_portable_fixture_has_no_fabricated_cloud_preview() -> None:
    furniture = {"furniture_id": "fixture-sofa-2seat"}
    assert cloud_images.cloud_image_urls(furniture) == {}
    assert cloud_images.cloud_primary_image_url(furniture) is None
    status = cloud_images.image_manifest_status()
    assert status["verified_item_count"] == 0
    assert status["manifest_ready"] is False
