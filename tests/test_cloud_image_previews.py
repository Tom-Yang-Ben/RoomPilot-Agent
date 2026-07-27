from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from backend.server.services.cloud_images import (
    cloud_image_urls,
    cloud_primary_image_url,
    image_manifest_status,
)


ROOT = Path(__file__).resolve().parents[1]
IMAGE_UPLOAD_RESULT = (
    ROOT / "backend" / "catalog" / "data" / "manifests" / "image_upload_all_result.csv"
)
CATALOG_COUNT = 9_350
IMAGE_ROLES = {"front", "side", "angle-45"}


def _load_rows() -> list[dict[str, str]]:
    with IMAGE_UPLOAD_RESULT.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_cloud_image_manifest_covers_each_furniture_with_three_png_views() -> None:
    rows = _load_rows()

    assert len(rows) == CATALOG_COUNT * len(IMAGE_ROLES)
    assert Counter(row["image_role"] for row in rows) == {
        role: CATALOG_COUNT for role in IMAGE_ROLES
    }
    assert {row["content_type"] for row in rows} == {"image/png"}
    assert {row["validation_status"] for row in rows} == {"ready"}
    assert {row["upload_status"] for row in rows} == {"uploaded"}
    assert all(row["delivery_url"].startswith("https://") for row in rows)

    roles_by_item: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        roles_by_item[row["item_id"]].add(row["image_role"])

    assert len(roles_by_item) == CATALOG_COUNT
    assert all(roles == IMAGE_ROLES for roles in roles_by_item.values())


def test_cloud_image_service_returns_front_as_primary_preview() -> None:
    first_item_id = _load_rows()[0]["item_id"]
    furniture = {"furniture_id": first_item_id}

    urls = cloud_image_urls(furniture)

    assert set(urls) == IMAGE_ROLES
    assert cloud_primary_image_url(furniture) == urls["front"]
    assert image_manifest_status()["verified_item_count"] == CATALOG_COUNT
