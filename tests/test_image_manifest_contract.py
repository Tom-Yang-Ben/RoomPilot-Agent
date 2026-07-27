from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
import hashlib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "backend" / "catalog" / "data" / "manifests"
JSON_MANIFEST_DIR = ROOT / "JSON" / "manifests"
IMAGE_MANIFEST = MANIFEST_DIR / "image_upload_manifest.csv"
IMAGE_UPLOAD_RESULT = MANIFEST_DIR / "image_upload_all_result.csv"
GLB_MANIFEST = MANIFEST_DIR / "glb_upload_manifest.csv"
GLB_UPLOAD_RESULT = MANIFEST_DIR / "glb_upload_all_result.csv"
JSON_OFFICIAL_CATALOG = (
    ROOT / "JSON" / "furniture" / "furniture_official_catagory.json"
)
OFFICIAL_CATALOG = (
    ROOT / "backend" / "catalog" / "data" / "furniture_catalog_cloud_9350.json"
)
EXPECTED_ITEM_COUNT = 9_350
EXPECTED_IMAGE_COUNT = EXPECTED_ITEM_COUNT * 3
EXPECTED_IMAGE_ROLES = {"front", "side", "angle-45"}
CLOUDFRONT_IMAGE_BASE = "https://ddgsm1yg3xikc.cloudfront.net/"
CLOUDFRONT_MODEL_BASE = "https://ddgsm1yg3xikc.cloudfront.net/"


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def image_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _load_csv(IMAGE_MANIFEST), _load_csv(IMAGE_UPLOAD_RESULT)


def test_image_manifests_cover_every_official_item_with_three_views(
    image_rows: tuple[list[dict[str, str]], list[dict[str, str]]],
) -> None:
    manifest_rows, result_rows = image_rows
    official = json.loads(OFFICIAL_CATALOG.read_text(encoding="utf-8"))
    official_ids = {str(item["id"]) for item in official["items"]}

    assert len(official_ids) == EXPECTED_ITEM_COUNT
    assert len(manifest_rows) == EXPECTED_IMAGE_COUNT
    assert len(result_rows) == EXPECTED_IMAGE_COUNT

    image_ids = [row["image_id"] for row in result_rows]
    assert len(set(image_ids)) == EXPECTED_IMAGE_COUNT
    assert {row["item_id"] for row in result_rows} == official_ids
    assert Counter(row["image_role"] for row in result_rows) == {
        role: EXPECTED_ITEM_COUNT for role in EXPECTED_IMAGE_ROLES
    }

    roles_by_item: dict[str, set[str]] = defaultdict(set)
    for row in result_rows:
        roles_by_item[row["item_id"]].add(row["image_role"])
    assert all(roles == EXPECTED_IMAGE_ROLES for roles in roles_by_item.values())


def test_image_manifest_and_upload_result_are_one_to_one(
    image_rows: tuple[list[dict[str, str]], list[dict[str, str]]],
) -> None:
    manifest_rows, result_rows = image_rows
    manifest_by_id = {row["image_id"]: row for row in manifest_rows}
    result_by_id = {row["image_id"]: row for row in result_rows}

    assert set(manifest_by_id) == set(result_by_id)
    for image_id, manifest in manifest_by_id.items():
        result = result_by_id[image_id]
        assert manifest["item_id"] == result["item_id"]
        assert manifest["image_role"] == result["image_role"]
        assert manifest["original_image_path"] == result["original_image_path"]
        assert manifest["object_key"] == result["object_key"]


def test_image_paths_are_portable_and_cloud_delivery_matches_object_keys(
    image_rows: tuple[list[dict[str, str]], list[dict[str, str]]],
) -> None:
    _manifest_rows, result_rows = image_rows
    object_keys: set[str] = set()
    delivery_urls: set[str] = set()

    for row in result_rows:
        original_path = PurePosixPath(row["original_image_path"])
        object_key = PurePosixPath(row["object_key"])
        delivery_url = row["delivery_url"]
        delivery_path = PurePosixPath(
            unquote(urlparse(delivery_url).path).lstrip("/")
        )

        assert not original_path.is_absolute()
        assert original_path.parts[0] == "rendered_images"
        assert ".." not in original_path.parts
        assert not object_key.is_absolute()
        assert object_key.parts[:2] == ("images", "glb-three-view")
        assert ".." not in object_key.parts
        assert delivery_url.startswith(CLOUDFRONT_IMAGE_BASE)
        assert delivery_path == object_key
        assert row["content_type"] == "image/png"
        assert row["validation_status"] == "ready"
        assert row["upload_status"] == "uploaded"
        assert not row["upload_error"].strip()
        assert int(row["file_size_bytes"]) > 0

        object_keys.add(row["object_key"])
        delivery_urls.add(delivery_url)

    assert len(object_keys) == EXPECTED_IMAGE_COUNT
    assert len(delivery_urls) == EXPECTED_IMAGE_COUNT


def test_glb_manifest_and_upload_result_match_the_official_catalog() -> None:
    manifest_rows = _load_csv(GLB_MANIFEST)
    result_rows = _load_csv(GLB_UPLOAD_RESULT)
    official = json.loads(OFFICIAL_CATALOG.read_text(encoding="utf-8"))
    official_ids = {str(item["id"]) for item in official["items"]}
    manifest_by_id = {row["item_id"]: row for row in manifest_rows}
    result_by_id = {row["item_id"]: row for row in result_rows}

    assert len(manifest_rows) == EXPECTED_ITEM_COUNT
    assert len(result_rows) == EXPECTED_ITEM_COUNT
    assert set(manifest_by_id) == official_ids
    assert set(result_by_id) == official_ids

    object_keys: set[str] = set()
    delivery_urls: set[str] = set()
    for item_id, manifest in manifest_by_id.items():
        result = result_by_id[item_id]
        original_path = PurePosixPath(result["original_glb_path"])
        object_key = PurePosixPath(result["object_key"])
        delivery_url = result["delivery_url"]
        delivery_path = PurePosixPath(
            unquote(urlparse(delivery_url).path).lstrip("/")
        )

        assert manifest["original_glb_path"] == result["original_glb_path"]
        assert manifest["object_key"] == result["object_key"]
        assert manifest["upload_status"] == "pending"
        assert not original_path.is_absolute()
        assert original_path.parts[0] == "downloaded-files"
        assert ".." not in original_path.parts
        assert not object_key.is_absolute()
        assert object_key.parts[0] == "models"
        assert ".." not in object_key.parts
        assert delivery_url.startswith(CLOUDFRONT_MODEL_BASE)
        assert delivery_path == object_key
        assert result["content_type"] == "model/gltf-binary"
        assert result["validation_status"] == "ready"
        assert result["upload_status"] == "uploaded"
        assert not result["upload_error"].strip()
        assert int(result["file_size_bytes"]) > 0

        object_keys.add(result["object_key"])
        delivery_urls.add(delivery_url)

    assert len(object_keys) == EXPECTED_ITEM_COUNT
    assert len(delivery_urls) == EXPECTED_ITEM_COUNT


def test_json_handoff_manifests_match_the_backend_official_manifests() -> None:
    for filename in (
        "glb_upload_manifest.csv",
        "glb_upload_all_result.csv",
        "image_upload_manifest.csv",
        "image_upload_all_result.csv",
    ):
        assert _sha256(JSON_MANIFEST_DIR / filename) == _sha256(
            MANIFEST_DIR / filename
        )


def test_json_official_catalog_contains_vlm_enrichment_and_matching_assets() -> None:
    payload = json.loads(JSON_OFFICIAL_CATALOG.read_text(encoding="utf-8"))
    items = list(payload["items"])
    result_rows = _load_csv(JSON_MANIFEST_DIR / "glb_upload_all_result.csv")
    result_by_id = {row["item_id"]: row for row in result_rows}
    item_ids = [str(item["id"]) for item in items]

    assert payload["count"] == EXPECTED_ITEM_COUNT
    assert "vlm_annotated" in payload["schema_version"]
    assert len(items) == EXPECTED_ITEM_COUNT
    assert len(set(item_ids)) == EXPECTED_ITEM_COUNT
    assert set(item_ids) == set(result_by_id)

    required_enrichment = (
        "style_primary",
        "style_secondary",
        "description",
        "room_types",
        "role",
        "confidence",
        "desc_source",
    )
    for item in items:
        assert all(item.get(field) not in (None, "", []) for field in required_enrichment)
        assert item["desc_source"] == "glb_render"
        assert item["glb_url"] == result_by_id[item["id"]]["delivery_url"]
        assert item["object_key"] == result_by_id[item["id"]]["object_key"]

    assert sum(bool(item.get("rag_text")) for item in items) >= 9_200
