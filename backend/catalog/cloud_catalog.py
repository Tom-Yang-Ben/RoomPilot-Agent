"""Build the official 8,675-item catalog from Kai's versioned JSON source.

The official JSON is the sole source of furniture identity and enrichment.
The upload-result manifest supplies delivery evidence.  The metadata-only
six-style file provides top-level style presentation definitions; its empty
``furniture`` compatibility array is deliberately ignored.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .postgres_repository import _GROUP_NAMES, _catalog_group


OFFICIAL_CATALOG_COUNT = 8_675
READY_UPLOAD_STATUSES = {
    "uploaded",
    "already_exists",
    "complete",
    "completed",
    "success",
    "skipped_existing",
}


def _official_style_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        confidence = float(item.get("style_confidence") or item.get("confidence") or 1.0)
    except (TypeError, ValueError):
        confidence = 1.0
    reasons = [str(item["style_reason"])] if item.get("style_reason") else []
    candidates: list[dict[str, Any]] = []
    for field in ("style_primary", "style_secondary"):
        style_id = str(item.get(field) or "").strip()
        if style_id and not any(candidate["style_id"] == style_id for candidate in candidates):
            candidates.append(
                {
                    "style_id": style_id,
                    "score": round(confidence, 3),
                    "reasons": reasons,
                }
            )
    return candidates


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_official_catalog(
    cloud_catalog: dict[str, Any],
    style_presentation: dict[str, Any],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the publishable catalog and deterministic integration diagnostics."""
    canonical_items = list(cloud_catalog.get("items") or [])
    ignored_presentation_items = len(style_presentation.get("furniture") or [])

    if len(canonical_items) != OFFICIAL_CATALOG_COUNT:
        raise ValueError(
            f"cloud catalog must contain {OFFICIAL_CATALOG_COUNT} items; "
            f"got {len(canonical_items)}"
        )

    canonical_ids = [str(item.get("id") or "").strip() for item in canonical_items]
    if not all(canonical_ids) or len(set(canonical_ids)) != OFFICIAL_CATALOG_COUNT:
        raise ValueError("cloud catalog item IDs must be present and unique")

    manifest_by_id = {
        str(row.get("item_id") or "").strip(): row
        for row in manifest_rows
        if str(row.get("item_id") or "").strip()
    }
    excluded_ids = {
        str(item.get("id") or "").strip()
        for item in cloud_catalog.get("excluded_items") or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    missing_ids = set(canonical_ids) - set(manifest_by_id)
    unexpected_ids = (set(manifest_by_id) - set(canonical_ids)) - excluded_ids
    if missing_ids or unexpected_ids:
        raise ValueError(
            "official JSON and manifest IDs differ: "
            f"missing={len(missing_ids)}, unexpected={len(unexpected_ids)}"
        )

    canonical_by_id = dict(zip(canonical_ids, canonical_items, strict=True))

    official_items: list[dict[str, Any]] = []
    for item_id in canonical_ids:
        canonical = canonical_by_id[item_id]
        manifest = manifest_by_id[item_id]
        upload_status = str(manifest.get("upload_status") or "").strip().lower()
        if upload_status not in READY_UPLOAD_STATUSES:
            raise ValueError(
                f"catalog item has no ready CloudFront upload status: {item_id}"
            )
        delivery_url = str(
            manifest.get("delivery_url") or canonical.get("glb_url") or ""
        ).strip()
        if not delivery_url.startswith("https://"):
            raise ValueError(f"catalog item has no verified HTTPS GLB URL: {item_id}")

        width = canonical.get("width_cm")
        depth = canonical.get("depth_cm")
        height = canonical.get("height_cm")
        colors = list(canonical.get("colors") or [])
        materials = list(canonical.get("materials") or [])
        room_types = [str(value) for value in canonical.get("room_types") or []]
        normalized_type = str(
            canonical.get("normalized_type")
            or manifest.get("type")
            or canonical.get("canonical_category_zh")
            or "furniture"
        )
        taxonomy_group = str(
            canonical.get("taxonomy_group")
            or _catalog_group(normalized_type, room_types)
        )
        style_candidates = _official_style_candidates(canonical)
        primary_style = str(canonical.get("style_primary") or "").strip() or None
        style_confidence = style_candidates[0]["score"] if style_candidates else 0.0

        item: dict[str, Any] = {
            "furniture_id": item_id,
            "name_en": canonical.get("name_en"),
            "name_zh": canonical.get("name_zh"),
            "name_zh_raw": canonical.get("name_zh"),
            "category_label": canonical.get("canonical_category_zh"),
            "normalized_type": normalized_type,
            "taxonomy_group": taxonomy_group,
            "taxonomy_group_zh": canonical.get("taxonomy_group_zh")
            or _GROUP_NAMES.get(taxonomy_group, taxonomy_group),
            "taxonomy_type_zh": canonical.get("taxonomy_type_zh")
            or canonical.get("canonical_category_zh")
            or normalized_type,
            "color": canonical.get("color") or (colors[0] if colors else ""),
            "colors": colors,
            "material": canonical.get("material")
            or (materials[0] if materials else ""),
            "materials": materials,
            "size_cm": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "width_cm": width,
            "depth_cm": depth,
            "height_cm": height,
            "object_key": manifest.get("object_key") or canonical.get("object_key"),
            "glb_relative_path": manifest.get("object_key")
            or canonical.get("object_key"),
            "glb_absolute_path": delivery_url,
            "glb_url": delivery_url,
            "source_dataset": manifest.get("source_group")
            or manifest.get("source")
            or "",
            "source": manifest.get("source") or "",
            "catalog_scope": canonical.get("catalog_scope") or "furniture",
            "can_rotate": canonical.get("can_rotate", True),
            "must_against_wall": canonical.get("must_against_wall", False),
            "usable_for_moodboard": canonical.get("usable_for_moodboard", True),
            "style_candidates": style_candidates,
            "primary_style": primary_style,
            "style_confidence": style_confidence,
            "style_assignment_source": "official_json_6styles",
            "upload_status": upload_status,
        }

        # Preserve every field delivered by the official JSON. Explicit runtime
        # mappings and verified manifest URLs above keep precedence.
        for field, value in canonical.items():
            if field != "id" and value is not None:
                item.setdefault(field, value)
        official_items.append(item)

    result = {
        key: value
        for key, value in style_presentation.items()
        if key not in {"furniture", "summary"}
    }
    result.update(
        {
            "schema_version": "official-json-8675-v3",
            "catalog_name": "RoomPilot official CloudFront furniture catalog",
            "source_catalog": cloud_catalog.get("dataset_name"),
            "source_style_presentation": style_presentation.get("catalog_name"),
            "furniture": official_items,
            "summary": {
                "total_furniture": len(official_items),
                "cloudfront_ready": len(official_items),
                "style_enriched": sum(bool(item.get("primary_style")) for item in official_items),
                "style_unclassified": sum(not item.get("primary_style") for item in official_items),
                "manifest_excluded": len(set(manifest_by_id) - set(canonical_ids)),
                "style_presentation_furniture_ignored": ignored_presentation_items,
            },
        }
    )
    diagnostics = {
        "official_items": len(official_items),
        "manifest_items": len(manifest_by_id),
        "manifest_excluded_items": len(set(manifest_by_id) - set(canonical_ids)),
        "style_enriched_items": sum(bool(item.get("primary_style")) for item in official_items),
        "style_unclassified_items": sum(not item.get("primary_style") for item in official_items),
        "style_presentation_furniture_ignored": ignored_presentation_items,
    }
    return result, diagnostics


def load_official_catalog(
    cloud_catalog_path: Path,
    style_presentation_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    catalog, _diagnostics = build_official_catalog(
        _load_json(cloud_catalog_path),
        _load_json(style_presentation_path),
        _load_manifest(manifest_path),
    )
    return catalog


def official_catalog_diagnostics(
    cloud_catalog_path: Path,
    style_presentation_path: Path,
    manifest_path: Path,
) -> dict[str, int]:
    _catalog, diagnostics = build_official_catalog(
        _load_json(cloud_catalog_path),
        _load_json(style_presentation_path),
        _load_manifest(manifest_path),
    )
    return diagnostics
