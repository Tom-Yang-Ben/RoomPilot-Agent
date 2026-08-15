from __future__ import annotations

from pathlib import Path

from backend.server.services.cloud_images import (
    cloud_image_urls,
    cloud_primary_image_url,
    image_manifest_status,
)


ROOT = Path(__file__).resolve().parents[1]
def test_private_cloud_image_manifest_is_not_distributed() -> None:
    assert not (ROOT / "backend" / "catalog" / "data" / "manifests").exists()


def test_portable_fixture_has_no_fabricated_cloud_preview() -> None:
    furniture = {"furniture_id": "fixture-sofa-2seat"}
    assert cloud_image_urls(furniture) == {}
    assert cloud_primary_image_url(furniture) is None
    status = image_manifest_status()
    assert status["verified_item_count"] == 0
    assert status["manifest_ready"] is False
