"""Resolve verified CloudFront PNG previews for furniture assets."""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - server extra includes python-dotenv
    load_dotenv = None


PROJECT_DIR = Path(__file__).resolve().parents[3]
if load_dotenv is not None:
    load_dotenv(PROJECT_DIR / ".env", override=False)

DEFAULT_IMAGE_MANIFEST_PATH = (
    PROJECT_DIR
    / "backend"
    / "catalog"
    / "data"
    / "manifests"
    / "image_upload_all_result.csv"
)
DEFAULT_CLOUDFRONT_BASE_URL = "https://ddgsm1yg3xikc.cloudfront.net"
PREFERRED_IMAGE_ROLE = "front"

_REMOTE_READY_STATUSES = {
    "already_exists",
    "complete",
    "completed",
    "skipped_existing",
    "success",
    "uploaded",
}
_VALIDATION_READY_STATUSES = {"", "ready", "success", "valid"}


def _https_url(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return None
    return text


def _cloudfront_base_url() -> str | None:
    return _https_url(
        os.getenv("ROOMPILOT_CLOUDFRONT_BASE_URL", DEFAULT_CLOUDFRONT_BASE_URL)
    )


def _manifest_path() -> Path | None:
    raw = os.getenv("ROOMPILOT_IMAGE_MANIFEST_PATH", "").strip()
    if not raw:
        return DEFAULT_IMAGE_MANIFEST_PATH
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _delivery_url_from_row(row: dict[str, str], base_url: str | None) -> str | None:
    upload_status = str(row.get("upload_status") or "").strip().lower()
    validation_status = str(row.get("validation_status") or "").strip().lower()
    if upload_status not in _REMOTE_READY_STATUSES:
        return None
    if validation_status not in _VALIDATION_READY_STATUSES:
        return None
    direct = _https_url(row.get("delivery_url"))
    if direct:
        return direct
    object_key = str(row.get("object_key") or "").strip().replace("\\", "/").lstrip("/")
    if base_url and object_key:
        return urljoin(f"{base_url.rstrip('/')}/", object_key)
    return None


def _candidate_ids(furniture: dict) -> list[str]:
    values: list[object] = [furniture.get("furniture_id"), furniture.get("item_id")]
    values.extend(furniture.get("model_priority_ids") or [])
    values.extend(furniture.get("merged_furniture_ids") or [])
    values.extend(furniture.get("legacy_enrichment_ids") or [])
    return list(
        dict.fromkeys(str(value).strip() for value in values if str(value or "").strip())
    )


@lru_cache(maxsize=8)
def _manifest_index(
    manifest_path_text: str,
    modified_ns: int,
    file_size: int,
    base_url: str | None,
) -> dict[str, object]:
    del modified_ns, file_size
    by_id: dict[str, dict[str, str]] = {}
    with Path(manifest_path_text).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not {"item_id", "image_role", "upload_status"}.issubset(fields) or not (
            {"delivery_url", "object_key"} & fields
        ):
            raise ValueError("image manifest schema is incomplete")
        for row in reader:
            item_id = str(row.get("item_id") or "").strip()
            role = str(row.get("image_role") or "").strip()
            url = _delivery_url_from_row(row, base_url)
            if item_id and role and url:
                by_id.setdefault(item_id, {})[role] = url

    return {
        "by_id": by_id,
        "error": None if by_id else "empty",
    }


@lru_cache(maxsize=1)
def _current_manifest_index() -> dict[str, object]:
    path = _manifest_path()
    if path is None or not path.is_file():
        return {"by_id": {}, "error": "missing"}
    stat = path.stat()
    try:
        return _manifest_index(
            str(path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
            _cloudfront_base_url(),
        )
    except (OSError, UnicodeError, csv.Error, ValueError):
        return {"by_id": {}, "error": "invalid_or_unreadable"}


def cloud_image_urls(furniture: dict) -> dict[str, str]:
    """Return verified PNG preview URLs keyed by image role."""
    index = _current_manifest_index()
    for item_id in _candidate_ids(furniture):
        urls = index["by_id"].get(item_id)
        if urls:
            return dict(urls)
    return {}


def cloud_primary_image_url(furniture: dict) -> str | None:
    urls = cloud_image_urls(furniture)
    return (
        urls.get(PREFERRED_IMAGE_ROLE)
        or urls.get("angle-45")
        or urls.get("side")
        or next(iter(urls.values()), None)
    )


def image_manifest_status() -> dict:
    path = _manifest_path()
    index = _current_manifest_index()
    by_id = index["by_id"]
    image_count = sum(len(roles) for roles in by_id.values())
    return {
        "manifest_ready": bool(path and path.is_file() and not index.get("error") and by_id),
        "manifest_error": index.get("error"),
        "verified_item_count": len(by_id),
        "verified_image_count": image_count,
        "cloudfront_base_url": _cloudfront_base_url(),
    }


def clear_cloud_image_caches() -> None:
    _current_manifest_index.cache_clear()
    _manifest_index.cache_clear()
