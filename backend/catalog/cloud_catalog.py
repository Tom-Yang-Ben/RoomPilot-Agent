"""Build the official 9,350-item catalog from Kai's cloud asset inventory.

The cloud catalog and upload-result manifest define the publishable furniture
set.  The older six-style catalog is enrichment only: it may contribute style,
taxonomy, and placement hints, but it cannot introduce additional furniture.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


OFFICIAL_CATALOG_COUNT = 9_350
READY_UPLOAD_STATUSES = {
    "uploaded",
    "already_exists",
    "complete",
    "completed",
    "success",
    "skipped_existing",
}

_IDENTITY_FIELDS = {
    "furniture_id",
    "name_en",
    "name_zh",
    "name_zh_raw",
    "category_label",
    "color",
    "colors",
    "material",
    "materials",
    "size_cm",
    "glb_relative_path",
    "glb_absolute_path",
    "model_url",
    "object_key",
}

_ENRICHMENT_FIELDS = {
    "normalized_type",
    "can_rotate",
    "must_against_wall",
    "usable_for_moodboard",
    "style_candidates",
    "primary_style",
    "style_confidence",
    "style_rule_flags",
    "taxonomy_group",
    "taxonomy_group_zh",
    "taxonomy_type_zh",
    "catalog_scope",
    "placement_hints",
    "clearance_zones",
    "layout_relations",
    "rule",
}


def _normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _candidate_parts(candidate: object) -> tuple[str | None, float, list[str]]:
    if isinstance(candidate, dict):
        style_id = str(candidate.get("style_id") or "").strip() or None
        try:
            score = float(candidate.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        return style_id, score, list(candidate.get("reasons") or [])
    if isinstance(candidate, (list, tuple)) and candidate:
        style_id = str(candidate[0] or "").strip() or None
        try:
            score = float(candidate[1] or 0) if len(candidate) > 1 else 1.0
        except (TypeError, ValueError):
            score = 0.0
        return style_id, score, []
    if isinstance(candidate, str):
        return candidate.strip() or None, 1.0, []
    return None, 0.0, []


def _merged_style_candidates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_style: dict[str, dict[str, Any]] = {}
    for entry in entries:
        candidates = list(entry.get("style_candidates") or [])
        primary_style = str(entry.get("primary_style") or "").strip()
        if primary_style:
            candidates.append(
                {
                    "style_id": primary_style,
                    "score": entry.get("style_confidence") or 0,
                    "reasons": [],
                }
            )
        for candidate in candidates:
            style_id, score, reasons = _candidate_parts(candidate)
            if not style_id:
                continue
            existing = by_style.get(style_id)
            if existing is None or score > existing["score"]:
                by_style[style_id] = {
                    "style_id": style_id,
                    "score": round(score, 3),
                    "reasons": sorted(set(reasons)),
                }
            elif reasons:
                existing["reasons"] = sorted(
                    set(existing.get("reasons", [])) | set(reasons)
                )
    return sorted(
        by_style.values(),
        key=lambda candidate: (-candidate["score"], candidate["style_id"]),
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_official_catalog(
    cloud_catalog: dict[str, Any],
    style_enrichment: dict[str, Any],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the publishable catalog and deterministic integration diagnostics."""
    canonical_items = list(cloud_catalog.get("items") or [])
    legacy_items = list(style_enrichment.get("furniture") or [])

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
    if set(manifest_by_id) != set(canonical_ids):
        missing = len(set(canonical_ids) - set(manifest_by_id))
        extra = len(set(manifest_by_id) - set(canonical_ids))
        raise ValueError(
            f"cloud catalog and manifest IDs differ: missing={missing}, extra={extra}"
        )

    canonical_by_id = dict(zip(canonical_ids, canonical_items, strict=True))
    canonical_by_name: dict[str, list[str]] = defaultdict(list)
    for item_id, item in canonical_by_id.items():
        canonical_by_name[_normalized_name(item.get("name_en"))].append(item_id)

    enrichment_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_matches = 0
    unique_name_matches = 0
    unused_legacy = 0
    for entry in legacy_items:
        legacy_id = str(entry.get("furniture_id") or "").strip()
        target_id: str | None = None
        if legacy_id in canonical_by_id:
            target_id = legacy_id
            exact_matches += 1
        else:
            candidates = canonical_by_name.get(
                _normalized_name(entry.get("name_en")),
                [],
            )
            if len(candidates) == 1:
                target_id = candidates[0]
                unique_name_matches += 1
        if target_id is None:
            unused_legacy += 1
            continue
        enrichment_by_id[target_id].append(entry)

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
        entries = enrichment_by_id.get(item_id, [])
        preferred = next(
            (
                entry
                for entry in entries
                if str(entry.get("furniture_id") or "") == item_id
            ),
            entries[0] if entries else {},
        )
        style_candidates = _merged_style_candidates(entries)

        item: dict[str, Any] = {
            "furniture_id": item_id,
            "name_en": canonical.get("name_en"),
            "name_zh": canonical.get("name_zh"),
            "name_zh_raw": canonical.get("name_zh"),
            "category_label": canonical.get("canonical_category_zh"),
            "normalized_type": (
                preferred.get("normalized_type")
                or manifest.get("type")
                or canonical.get("canonical_category_zh")
            ),
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
            "catalog_scope": preferred.get("catalog_scope") or "furniture",
            "can_rotate": preferred.get("can_rotate", True),
            "must_against_wall": preferred.get("must_against_wall", False),
            "usable_for_moodboard": preferred.get("usable_for_moodboard", True),
            "style_candidates": style_candidates,
            "primary_style": (
                style_candidates[0]["style_id"] if style_candidates else None
            ),
            "style_confidence": (
                style_candidates[0]["score"] if style_candidates else 0.0
            ),
            "style_assignment_source": (
                "cloud_9350+legacy_6styles"
                if entries
                else "cloud_9350_unclassified"
            ),
            "legacy_enrichment_ids": [
                str(entry.get("furniture_id"))
                for entry in entries
                if entry.get("furniture_id")
            ],
            "upload_status": upload_status,
        }

        for field in _ENRICHMENT_FIELDS - _IDENTITY_FIELDS:
            if field in {
                "style_candidates",
                "primary_style",
                "style_confidence",
                "catalog_scope",
                "normalized_type",
                "can_rotate",
                "must_against_wall",
                "usable_for_moodboard",
            }:
                continue
            if preferred.get(field) is not None:
                item[field] = preferred[field]
        official_items.append(item)

    result = {
        key: value
        for key, value in style_enrichment.items()
        if key not in {"furniture", "summary"}
    }
    result.update(
        {
            "schema_version": "cloud-9350-enriched-v1",
            "catalog_name": "RoomPilot official CloudFront furniture catalog",
            "source_catalog": cloud_catalog.get("dataset_name"),
            "furniture": official_items,
            "summary": {
                "total_furniture": len(official_items),
                "cloudfront_ready": len(official_items),
                "style_enriched": len(enrichment_by_id),
                "style_unclassified": len(official_items) - len(enrichment_by_id),
                "legacy_rows_excluded": unused_legacy,
            },
        }
    )
    diagnostics = {
        "official_items": len(official_items),
        "manifest_items": len(manifest_by_id),
        "style_enriched_items": len(enrichment_by_id),
        "style_unclassified_items": len(official_items) - len(enrichment_by_id),
        "legacy_exact_matches": exact_matches,
        "legacy_unique_name_matches": unique_name_matches,
        "legacy_rows_excluded": unused_legacy,
    }
    return result, diagnostics


def load_official_catalog(
    cloud_catalog_path: Path,
    style_enrichment_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    catalog, _diagnostics = build_official_catalog(
        _load_json(cloud_catalog_path),
        _load_json(style_enrichment_path),
        _load_manifest(manifest_path),
    )
    return catalog


def official_catalog_diagnostics(
    cloud_catalog_path: Path,
    style_enrichment_path: Path,
    manifest_path: Path,
) -> dict[str, int]:
    _catalog, diagnostics = build_official_catalog(
        _load_json(cloud_catalog_path),
        _load_json(style_enrichment_path),
        _load_manifest(manifest_path),
    )
    return diagnostics
