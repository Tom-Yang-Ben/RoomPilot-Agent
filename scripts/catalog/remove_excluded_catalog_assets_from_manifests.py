"""Verify excluded catalog items are absent from upload manifests."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "JSON" / "furniture" / "furniture_official_catagory.json"
MANIFEST_ROOTS = (
    ROOT / "JSON" / "manifests",
    ROOT / "backend" / "catalog" / "data" / "manifests",
)
MANIFEST_FILES = (
    "glb_upload_manifest.csv",
    "glb_upload_all_result.csv",
    "image_upload_manifest.csv",
    "image_upload_all_result.csv",
)


def excluded_item_ids(catalog_path: str | Path = DEFAULT_CATALOG) -> tuple[str, ...]:
    payload = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    rows = payload.get("excluded_items") or []
    ids = {
        str(row.get("id") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    return tuple(sorted(ids))


def matching_line_count(path: str | Path, item_ids: Iterable[str]) -> int:
    wanted = {str(item_id).strip() for item_id in item_ids if str(item_id).strip()}
    if not wanted:
        return 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        return sum(1 for row in rows if str(row.get("item_id") or "").strip() in wanted)


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
