"""Resolve verified CloudFront URLs for furniture GLB assets.

The upload-result manifest is the trust boundary.  A catalog path by itself is
never enough to publish a URL: the manifest row must either contain a valid
HTTPS delivery URL or report a successful upload status for its object key.
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata
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
DEFAULT_MANIFEST_PATH = (
    PROJECT_DIR
    / "backend"
    / "catalog"
    / "data"
    / "manifests"
    / "glb_upload_all_result.csv"
)
DEFAULT_CLOUDFRONT_BASE_URL = "https://ddgsm1yg3xikc.cloudfront.net"

_VALID_MODES = {"local", "cloudfront"}
_REMOTE_READY_STATUSES = {
    "already_exists",
    "complete",
    "completed",
    "skipped_existing",
    "success",
    "uploaded",
}


def model_delivery_mode() -> str:
    """Return the configured delivery policy, defaulting to the bundled cloud catalog."""
    value = os.getenv("ROOMPILOT_MODEL_DELIVERY_MODE", "cloudfront").strip().lower()
    return value if value in _VALID_MODES else "local"


def cloudfront_required() -> bool:
    return model_delivery_mode() == "cloudfront"


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
    raw = os.getenv("ROOMPILOT_GLB_MANIFEST_PATH", "").strip()
    if not raw:
        return DEFAULT_MANIFEST_PATH
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _delivery_url_from_row(row: dict[str, str], base_url: str | None) -> str | None:
    status = str(row.get("upload_status") or "").strip().lower()
    if status not in _REMOTE_READY_STATUSES:
        return None
    direct = _https_url(row.get("delivery_url"))
    if direct:
        return direct
    object_key = str(row.get("object_key") or "").strip().replace("\\", "/").lstrip("/")
    if base_url and object_key:
        return urljoin(f"{base_url.rstrip('/')}/", object_key)
    return None


def _normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


@lru_cache(maxsize=8)
def _manifest_index(
    manifest_path_text: str,
    modified_ns: int,
    file_size: int,
    base_url: str | None,
) -> dict[str, object]:
    del modified_ns, file_size
    by_id: dict[str, str] = {}
    name_candidates: dict[str, set[str]] = {}
    with Path(manifest_path_text).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not {"item_id", "upload_status"}.issubset(fields) or not (
            {"delivery_url", "object_key"} & fields
        ):
            raise ValueError("manifest schema is incomplete")
        for row in reader:
            item_id = str(row.get("item_id") or "").strip()
            url = _delivery_url_from_row(row, base_url)
            if item_id and url:
                by_id[item_id] = url
            name = _normalized_name(row.get("name_en"))
            if name and url:
                name_candidates.setdefault(name, set()).add(url)

    by_unique_name = {
        name: next(iter(urls))
        for name, urls in name_candidates.items()
        if len(urls) == 1
    }
    return {
        "by_id": by_id,
        "by_unique_name": by_unique_name,
        "error": None if by_id else "empty",
    }


@lru_cache(maxsize=1)
def _current_manifest_index() -> dict[str, object]:
    path = _manifest_path()
    if path is None or not path.is_file():
        return {"by_id": {}, "by_unique_name": {}, "error": "missing"}
    stat = path.stat()
    try:
        return _manifest_index(
            str(path.resolve()),
            stat.st_mtime_ns,
            stat.st_size,
            _cloudfront_base_url(),
        )
    except (OSError, UnicodeError, csv.Error, ValueError):
        return {"by_id": {}, "by_unique_name": {}, "error": "invalid_or_unreadable"}


def _candidate_ids(furniture: dict) -> list[str]:
    values: list[object] = [furniture.get("furniture_id"), furniture.get("item_id")]
    values.extend(furniture.get("model_priority_ids") or [])
    values.extend(furniture.get("merged_furniture_ids") or [])
    return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))


def cloud_model_url(furniture: dict) -> str | None:
    """Return a verified CloudFront GLB URL for one catalog item."""
    if model_delivery_mode() == "local":
        return None

    index = _current_manifest_index()
    for item_id in _candidate_ids(furniture):
        if item_id in index["by_id"]:
            return index["by_id"][item_id]

    name = _normalized_name(furniture.get("name_en"))
    if name and name in index["by_unique_name"]:
        return index["by_unique_name"][name]

    return None


def cloud_model_status(furniture: dict) -> tuple[bool, str]:
    url = cloud_model_url(furniture)
    if url:
        return True, "CloudFront GLB 可用"

    path = _manifest_path()
    if path is None:
        return False, "CloudFront 模式未設定 manifest。"
    if not path.is_file():
        return False, f"找不到 CloudFront manifest：{path}"
    error = _current_manifest_index().get("error")
    if error == "invalid_or_unreadable":
        return False, "CloudFront manifest 無法讀取或欄位不完整。"
    if error == "empty":
        return False, "CloudFront manifest 沒有已驗證的家具模型。"
    return False, "CloudFront manifest 中找不到此家具的 delivery_url。"


def manifest_status() -> dict:
    """Return non-secret operational data for API health checks and the UI."""
    path = _manifest_path()
    index = _current_manifest_index()
    count = len(index["by_id"])
    error = index.get("error")
    return {
        "mode": model_delivery_mode(),
        "provider": "aws_cloudfront" if model_delivery_mode() != "local" else "local",
        "manifest_ready": bool(path and path.is_file() and not error and count > 0),
        "manifest_error": error,
        "verified_model_count": count,
        "cloudfront_base_url": _cloudfront_base_url(),
    }


def clear_cloud_model_caches() -> None:
    """Reload environment and manifest data on the next access."""
    _current_manifest_index.cache_clear()
    _manifest_index.cache_clear()
