from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath

from PIL import Image, ImageStat, PngImagePlugin


SIZE_RE = re.compile(
    r"(?P<first>\d+(?:\.\d+)?)\s*[x×X]\s*(?P<second>\d+(?:\.\d+)?)\s*cm",
    re.IGNORECASE,
)
CCITY_PREFIXES = ("ccity-tile-flooring/", "ccity-wood-look-tiles/")
STATIC_PREFIX = "/static/"
PROCESSED_ROOT = PurePosixPath("surface_assets/_processed")
DEFAULT_GROUT_WIDTH_MM = 3.0
PLANK_ASPECT_RATIO = 3.0
PROCESSOR_VERSION = "1.1.0"

REFERENCE_SOURCES = {
    "dimensions": "supplier_source_size_and_product_url",
    "grout": "https://www.mapei.com/sg/en/blog/detail/tech-talk/2020/03/03/reasons-why-tiles-buckle",
    "grout_context": "https://tcnatile.com/resource-center/faq/grout/",
    "plank_offset": "https://cdnmedia.mapei.com/docs/librariesprovider10/line-technical-documentation-documents/installing-wood-look-porcelain-plank-tile.pdf",
}


class SurfaceMaterialProcessingError(ValueError):
    pass


def installation_spec_for_surface(surface: dict) -> dict:
    source_size = str(surface.get("source_size") or "").strip()
    match = SIZE_RE.fullmatch(source_size)
    if match is None:
        raise SurfaceMaterialProcessingError(
            f"missing supplier tile size: {surface.get('surface_id')}"
        )
    first = float(match.group("first"))
    second = float(match.group("second"))
    width = max(first, second)
    height = min(first, second)
    aspect_ratio = width / height
    is_plank = aspect_ratio >= PLANK_ASPECT_RATIO
    return {
        "tile_size_cm": {
            "width": width,
            "height": height,
            "source_text": source_size,
        },
        "dimension_source": "supplier_catalog",
        "dimension_confidence": "verified_source_text",
        "grout_width_mm": DEFAULT_GROUT_WIDTH_MM,
        "grout_width_source": "roompilot_default_mapei_floor_minimum",
        "layout_pattern": "running_bond_33" if is_plank else "straight_grid",
        "row_offset_fraction": 1 / 3 if is_plank else 0,
        "rotation_deg": 0,
        "orientation_rule": (
            "long_edge_parallel_to_room_long_axis" if is_plank else "align_to_room_axes"
        ),
        "designer_confirmation_required": True,
        "construction_note_zh": (
            "尺寸來自供應商資料；3 mm 縫寬與排列是 RoomPilot 設計預設，"
            "施工前須依實際磚差、翹曲、基面及供應商規範確認。"
        ),
    }


def _average_grout_color(tile: Image.Image) -> tuple[int, int, int, int]:
    rgb = tile.convert("RGB")
    average = [round(value) for value in ImageStat.Stat(rgb).mean]
    luminance = sum(average) / 3
    target = 112 if luminance > 145 else 180
    mixed = [round(value * 0.78 + target * 0.22) for value in average]
    return (*mixed, 255)


def _hex_color(color: tuple[int, int, int, int]) -> str:
    return "#" + "".join(f"{channel:02x}" for channel in color[:3])


def render_tileable_material(
    source: Path,
    destination: Path,
    installation: dict,
) -> dict:
    source = Path(source)
    destination = Path(destination)
    tile_size = installation["tile_size_cm"]
    tile_width_cm = float(tile_size["width"])
    tile_height_cm = float(tile_size["height"])
    grout_cm = float(installation["grout_width_mm"]) / 10
    running_bond = installation["layout_pattern"] == "running_bond_33"
    columns = 3 if running_bond else 2
    rows = 3 if running_bond else 2
    target_long_px = 300 if running_bond else 480
    pixels_per_cm = target_long_px / tile_width_cm
    tile_width_px = target_long_px
    tile_height_px = max(16, round(tile_height_cm * pixels_per_cm))
    grout_px = max(1, round(grout_cm * pixels_per_cm))
    pitch_x = tile_width_px + grout_px
    pitch_y = tile_height_px + grout_px
    atlas_width = pitch_x * columns
    atlas_height = pitch_y * rows

    with Image.open(source) as image:
        tile = image.convert("RGBA")
    source_rotation_deg = 0
    if tile.height > tile.width and tile_width_cm > tile_height_cm:
        tile = tile.transpose(Image.Transpose.ROTATE_90)
        source_rotation_deg = 90
    tile = tile.resize(
        (tile_width_px, tile_height_px),
        Image.Resampling.LANCZOS,
    )
    grout_color = _average_grout_color(tile)
    atlas = Image.new("RGBA", (atlas_width, atlas_height), grout_color)
    offset_fraction = float(installation["row_offset_fraction"])

    for row in range(rows):
        offset = round(row * pitch_x * offset_fraction) if running_bond else 0
        y = row * pitch_y + grout_px
        for column in range(-2, columns + 2):
            x = column * pitch_x + offset + grout_px
            atlas.paste(tile, (x, y), tile)

    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("RoomPilotMaterialPattern", installation["layout_pattern"])
    metadata.add_text(
        "RoomPilotTileSizeCm",
        f"{tile_width_cm:g}x{tile_height_cm:g}",
    )
    metadata.add_text("RoomPilotGroutWidthMm", f"{installation['grout_width_mm']:g}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(destination, format="PNG", pnginfo=metadata, optimize=True)
    module_width_cm = columns * (tile_width_cm + grout_cm)
    module_height_cm = rows * (tile_height_cm + grout_cm)
    return {
        "method": "roompilot_tile_atlas_v1",
        "layout_pattern": installation["layout_pattern"],
        "row_offset_fraction": offset_fraction,
        "pattern_columns": columns,
        "pattern_rows": rows,
        "tile_size_cm": {"width": tile_width_cm, "height": tile_height_cm},
        "grout_width_mm": installation["grout_width_mm"],
        "grout_color_hex": _hex_color(grout_color),
        "source_rotation_deg": source_rotation_deg,
        "atlas_size_px": {"width": atlas_width, "height": atlas_height},
        "module_size_cm": {
            "width": round(module_width_cm, 4),
            "height": round(module_height_cm, 4),
        },
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def uv_repeat_for_span(
    processing: dict,
    *,
    width_m: float,
    depth_m: float,
) -> list[float]:
    module = processing["module_size_cm"]
    return [
        (float(width_m) * 100) / float(module["width"]),
        (float(depth_m) * 100) / float(module["height"]),
    ]


def _static_path(static_root: Path, url: str) -> Path:
    if not url.startswith(STATIC_PREFIX):
        raise SurfaceMaterialProcessingError(f"unsupported local material url: {url}")
    return static_root / Path(*PurePosixPath(url.removeprefix(STATIC_PREFIX)).parts)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _promote_generation(
    *,
    staged_assets: Path,
    processed_root: Path,
    staged_catalog: Path,
    catalog_path: Path,
    staged_manifest: Path,
    manifest_path: Path,
) -> None:
    promotions = [
        (staged_assets, processed_root),
        (staged_catalog, catalog_path),
        (staged_manifest, manifest_path),
    ]
    backups: list[tuple[Path, Path]] = []
    promoted: list[Path] = []
    try:
        for staged, target in promotions:
            backup = target.with_name(target.name + ".roompilot-backup")
            _remove_path(backup)
            if target.exists():
                target.replace(backup)
                backups.append((backup, target))
            staged.replace(target)
            promoted.append(target)
    except Exception:
        for target in reversed(promoted):
            _remove_path(target)
        for backup, target in reversed(backups):
            if backup.exists():
                backup.replace(target)
        raise
    else:
        for backup, _target in backups:
            _remove_path(backup)


def build_processed_surface_materials(
    *,
    catalog_path: Path,
    static_root: Path,
    manifest_path: Path,
) -> dict:
    catalog_path = Path(catalog_path)
    static_root = Path(static_root)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    manifest_items: list[dict] = []
    processed_root = static_root / Path(*PROCESSED_ROOT.parts)
    staged_assets = processed_root.with_name(processed_root.name + ".roompilot-staging")
    staged_catalog = catalog_path.with_name(catalog_path.name + ".roompilot-next")
    staged_manifest = Path(manifest_path).with_name(
        Path(manifest_path).name + ".roompilot-next"
    )
    _remove_path(staged_assets)
    _remove_path(staged_catalog)
    _remove_path(staged_manifest)

    try:
        for surface in catalog.get("surfaces", []):
            source_path = str(surface.get("source_path") or "")
            if not source_path.startswith(CCITY_PREFIXES):
                continue
            installation = installation_spec_for_surface(surface)
            source_preview_url = str(surface.get("preview_url") or surface["texture_url"])
            raw_texture_url = str(
                surface.get("source_texture_url") or surface["texture_url"]
            )
            source_image = _static_path(static_root, source_preview_url)
            relative_source = PurePosixPath(source_path)
            destination_relative = (
                PROCESSED_ROOT
                / relative_source.parent
                / relative_source.with_suffix(".png").name
            )
            staged_destination = (
                staged_assets
                / Path(*relative_source.parent.parts)
                / relative_source.with_suffix(".png").name
            )
            processing = render_tileable_material(
                source_image,
                staged_destination,
                installation,
            )
            processed_url = f"{STATIC_PREFIX}{destination_relative.as_posix()}"
            processing_audit = {
                **processing,
                "processor_version": PROCESSOR_VERSION,
                "source_preview_url": source_preview_url,
                "processed_url": processed_url,
                "repeat_strategy": "physical_module_size",
            }
            compact_processing = {
                "module_size_cm": processing_audit["module_size_cm"],
            }
            compact_installation = {
                "tile_size_cm": {
                    "width": installation["tile_size_cm"]["width"],
                    "height": installation["tile_size_cm"]["height"],
                },
                "grout_width_mm": installation["grout_width_mm"],
                "layout_pattern": installation["layout_pattern"],
                "orientation_rule": installation["orientation_rule"],
                "designer_confirmation_required": installation[
                    "designer_confirmation_required"
                ],
            }

            surface["source_texture_url"] = raw_texture_url
            surface["texture_url"] = processed_url
            surface["installation"] = compact_installation
            surface["material_processing"] = compact_processing
            surface.setdefault("repeat", {})["floor"] = [1.0, 1.0]
            manifest_items.append(
                {
                    "surface_id": surface["surface_id"],
                    "source_size": surface["source_size"],
                    "source_preview_url": source_preview_url,
                    "source_texture_url": raw_texture_url,
                    "source_sha256": hashlib.sha256(source_image.read_bytes()).hexdigest(),
                    "processed_url": processed_url,
                    "processor_version": PROCESSOR_VERSION,
                    "installation": installation,
                    "material_processing": processing_audit,
                }
            )
    except Exception:
        _remove_path(staged_assets)
        raise

    manifest_items.sort(key=lambda item: item["surface_id"])
    catalog["tile_installation_defaults"] = {
        "version": PROCESSOR_VERSION,
        "applies_to": "ccity floor and wood-look tiles",
        "grout_width_mm": DEFAULT_GROUT_WIDTH_MM,
        "designer_confirmation_required": True,
        "reference_sources": REFERENCE_SOURCES,
    }
    manifest = {
        "version": PROCESSOR_VERSION,
        "material_count": len(manifest_items),
        "defaults": catalog["tile_installation_defaults"],
        "processing_config": {
            "processor_version": PROCESSOR_VERSION,
            "default_grout_width_mm": DEFAULT_GROUT_WIDTH_MM,
            "plank_aspect_ratio": PLANK_ASPECT_RATIO,
            "plank_layout_pattern": "running_bond_33",
            "other_layout_pattern": "straight_grid",
        },
        "items": manifest_items,
    }
    _write_json(staged_catalog, catalog)
    _write_json(staged_manifest, manifest)
    _promote_generation(
        staged_assets=staged_assets,
        processed_root=processed_root,
        staged_catalog=staged_catalog,
        catalog_path=catalog_path,
        staged_manifest=staged_manifest,
        manifest_path=Path(manifest_path),
    )
    return {"processed_materials": len(manifest_items)}
