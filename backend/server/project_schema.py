"""Versioned persistence contract for RoomPilot browser projects.

The live application only reads the current schema. Older workflow payloads are
converted by the explicit, reversible ``scripts/migrate_project_schema.py``
command; production startup never scans or imports legacy worktree runtimes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from backend.floorplan.vision.units import canonicalize_analysis_cm


PROJECT_SCHEMA_VERSION = 3
CONFIGURATION_SCHEMA_VERSION = 3
GEOMETRY_SCHEMA_VERSION = "2.0"
STRUCTURE_COLLECTIONS = ("walls", "doors", "windows", "beams", "columns")
RETIRED_STRUCTURE_FIELDS = (
    "scheme_id",
    "demolition_candidate",
    "host_wall_relation_uncertain",
)
DIMENSION_FIELDS = (
    ("width_cm", "width_m"),
    ("thickness_cm", "thickness_m"),
    ("height_cm", "height_m"),
    ("top_cm", "top_m"),
    ("depth_cm", "depth_m"),
    ("size_cm", "size_m"),
    ("sill_height_cm", "sill_height_m"),
    ("head_height_cm", "head_height_m"),
)


class ProjectSchemaUpgradeRequired(RuntimeError):
    """A persisted project must be upgraded before the application can use it."""

    def __init__(self, found_version: int | None, reason: str = "") -> None:
        self.found_version = found_version
        self.reason = reason
        version = "missing" if found_version is None else str(found_version)
        suffix = f": {reason}" if reason else ""
        super().__init__(f"project schema {version} requires migration to v{PROJECT_SCHEMA_VERSION}{suffix}")


@dataclass(frozen=True)
class ProjectWorkflowMigration:
    workflow: dict[str, Any]
    source_version: int | None
    changed: bool


def project_schema_version(workflow: Mapping[str, Any] | None) -> int | None:
    if not isinstance(workflow, Mapping):
        return None
    value = workflow.get("project_schema_version")
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def require_current_project_schema(workflow: Mapping[str, Any] | None) -> None:
    version = project_schema_version(workflow)
    if version != PROJECT_SCHEMA_VERSION:
        raise ProjectSchemaUpgradeRequired(version)
    assert isinstance(workflow, Mapping)
    retired_paths = []
    for key in ("design_schemes", "furniture", "furniture2d"):
        if key in workflow:
            retired_paths.append(key)
    space = workflow.get("space_confirmation")
    if isinstance(space, Mapping) and "design_schemes" in space:
        retired_paths.append("space_confirmation.design_schemes")
    layout = workflow.get("layout_2d")
    if isinstance(layout, Mapping):
        for key in (
            "furniture",
            "furniture2d",
            "schemes",
            "active_scheme_id",
            "locked_scheme_id",
            "room_selections",
            "configuration_snapshot",
        ):
            if key in layout:
                retired_paths.append(f"layout_2d.{key}")
    white_model = workflow.get("white_model_3d")
    if isinstance(white_model, Mapping):
        for key in ("sceneData", "scene_json"):
            if key in white_model:
                retired_paths.append(f"white_model_3d.{key}")
    configuration = workflow.get("configuration")
    if isinstance(configuration, Mapping):
        try:
            configuration_version = int(configuration.get("schema_version") or 0)
        except (TypeError, ValueError):
            configuration_version = 0
        if configuration_version != CONFIGURATION_SCHEMA_VERSION:
            retired_paths.append("configuration.schema_version")

        schemes = configuration.get("schemes")
        if isinstance(schemes, Mapping):
            for scheme_id, scheme in schemes.items():
                if not isinstance(scheme, Mapping):
                    continue
                scene_data = scheme.get("sceneData")
                if not isinstance(scene_data, Mapping):
                    continue
                floorplan = scene_data.get("floorplan")
                if (
                    not isinstance(floorplan, Mapping)
                    or floorplan.get("coordinate_unit") != "cm"
                    or str(floorplan.get("schema_version")) != GEOMETRY_SCHEMA_VERSION
                ):
                    retired_paths.append(
                        f"configuration.schemes.{scheme_id}.sceneData.floorplan"
                    )
                    break

    if isinstance(space, Mapping) and space:
        if (
            space.get("coordinate_unit") != "cm"
            or str(space.get("schema_version")) != GEOMETRY_SCHEMA_VERSION
        ):
            retired_paths.append("space_confirmation.schema_version")

    def meter_path(value: Any, path: str) -> str | None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).endswith("_m") or key in {"m_per_px", "distance_m"}:
                    return f"{path}.{key}"
                nested = meter_path(item, f"{path}.{key}")
                if nested:
                    return nested
        elif isinstance(value, list):
            for index, item in enumerate(value):
                nested = meter_path(item, f"{path}[{index}]")
                if nested:
                    return nested
        return None

    for key in ("recognition", "space_confirmation", "configuration"):
        if key in workflow and (path := meter_path(workflow[key], key)):
            retired_paths.append(path)
            break
    if isinstance(space, Mapping):
        def retired_structure_path(value: Any, path: str) -> str | None:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if key in RETIRED_STRUCTURE_FIELDS:
                        return f"{path}.{key}"
                    nested = retired_structure_path(item, f"{path}.{key}")
                    if nested:
                        return nested
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    nested = retired_structure_path(item, f"{path}[{index}]")
                    if nested:
                        return nested
            return None

        if path := retired_structure_path(space, "space_confirmation"):
            retired_paths.append(path)
    if retired_paths:
        raise ProjectSchemaUpgradeRequired(version, retired_paths[0])


def new_project_workflow() -> dict[str, Any]:
    return {"project_schema_version": PROJECT_SCHEMA_VERSION}


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _point(value: Any, scale: float, *, vertical_key: str = "y") -> dict[str, float]:
    if isinstance(value, Mapping):
        x_value = value.get("x", 0)
        if vertical_key == "z":
            vertical_value = value.get("z", value.get("y", 0))
        else:
            vertical_value = value.get("y", value.get("z", 0))
    elif isinstance(value, (list, tuple)):
        x_value = value[0] if value else 0
        vertical_value = value[1] if len(value) > 1 else 0
    else:
        x_value = 0
        vertical_value = 0
    return {
        "x": round(float(x_value or 0) * scale, 6),
        vertical_key: round(float(vertical_value or 0) * scale, 6),
    }


def _item_scale(item: Mapping[str, Any], parent_unit: str | None) -> float:
    if item.get("coordinate_unit") == "cm":
        return 1.0
    if item.get("coordinate_unit") == "m":
        return 100.0
    if any(str(key).endswith("_m") for key in item):
        return 100.0
    return 1.0 if parent_unit == "cm" else 100.0


def _centimeter_item(item: Mapping[str, Any], parent_unit: str | None) -> dict[str, Any]:
    result = {
        key: deepcopy(value)
        for key, value in item.items()
        if not str(key).endswith("_m")
        and key not in RETIRED_STRUCTURE_FIELDS
    }
    for cm_key, meter_key in DIMENSION_FIELDS:
        cm_value = _finite_number(item.get(cm_key))
        meter_value = _finite_number(item.get(meter_key))
        if cm_value is not None:
            result[cm_key] = cm_value
        elif meter_value is not None:
            result[cm_key] = meter_value * 100
    scale = _item_scale(item, parent_unit)
    for key in ("start", "end", "center", "swing_end"):
        if key in item:
            result[key] = _point(item[key], scale)
    result["coordinate_unit"] = "cm"
    return result


def canonicalize_space_confirmation(saved: Mapping[str, Any] | None) -> dict[str, Any]:
    source = deepcopy(dict(saved or {}))
    parent_unit = source.get("coordinate_unit")
    result = {
        key: value
        for key, value in source.items()
        if key not in {"rooms", "structures", "design_schemes"}
    }
    result["coordinate_unit"] = "cm"
    result["schema_version"] = GEOMETRY_SCHEMA_VERSION
    result["dismissed_auto_room_ids"] = list(
        source.get("dismissed_auto_room_ids") or []
    )

    rooms = []
    for index, room_value in enumerate(source.get("rooms") or []):
        if not isinstance(room_value, Mapping):
            continue
        room = dict(room_value)
        if isinstance(room.get("polygon_cm"), list):
            polygon = room["polygon_cm"]
            scale = 1.0
        elif isinstance(room.get("polygon_m"), list):
            polygon = room["polygon_m"]
            scale = 100.0
        else:
            polygon = room.get("polygon") or room.get("exterior") or []
            scale = _item_scale(room, parent_unit)
        normalized = {
            key: deepcopy(value)
            for key, value in room.items()
            if key not in {"polygon", "polygon_m", "exterior"}
            and not str(key).endswith("_m")
            and key not in RETIRED_STRUCTURE_FIELDS
        }
        normalized["id"] = room.get("id") or room.get("room_id") or f"room-{index + 1}"
        normalized["coordinate_unit"] = "cm"
        normalized["polygon_cm"] = [_point(point, scale) for point in polygon]
        if len(normalized["polygon_cm"]) >= 3:
            rooms.append(normalized)
    result["rooms"] = rooms

    structures = source.get("structures") or {}
    result["structures"] = {
        kind: [
            _centimeter_item(item, parent_unit)
            for item in structures.get(kind) or []
            if isinstance(item, Mapping)
        ]
        for kind in STRUCTURE_COLLECTIONS
    }

    snapshot = source.get("confirmed_structure_snapshot")
    if isinstance(snapshot, Mapping):
        snapshot_result = deepcopy(dict(snapshot))
        snapshot_structures = snapshot.get("structures") or snapshot
        normalized_snapshot = {
            kind: [
                _centimeter_item(item, parent_unit)
                for item in snapshot_structures.get(kind) or []
                if isinstance(item, Mapping)
            ]
            for kind in STRUCTURE_COLLECTIONS
        }
        if "structures" in snapshot:
            snapshot_result["structures"] = normalized_snapshot
        else:
            snapshot_result.update(normalized_snapshot)
        snapshot_result["coordinate_unit"] = "cm"
        result["confirmed_structure_snapshot"] = snapshot_result
    return result


def _scene_point(value: Any, scale: float) -> dict[str, float]:
    return _point(value, scale, vertical_key="z")


def _scene_points(items: list[Mapping[str, Any]], keys: tuple[str, ...]) -> list[Any]:
    return [item[key] for item in items for key in keys if item.get(key) is not None]


def _inferred_scene_scale(
    points: list[Any], floorplan: Mapping[str, Any], fallback: float
) -> float:
    if str(floorplan.get("schema_version")) == GEOMETRY_SCHEMA_VERSION:
        return 1.0
    if fallback == 100.0:
        return 100.0
    coordinates = [_scene_point(point, 1.0) for point in points]
    if not coordinates:
        return fallback
    xs = [point["x"] for point in coordinates]
    zs = [point["z"] for point in coordinates]
    observed = max(
        max(xs) - min(xs),
        max(zs) - min(zs),
        max(abs(value) for value in xs) * 2,
        max(abs(value) for value in zs) * 2,
    )
    expected = max(
        _finite_number(floorplan.get("width_cm")) or 0,
        _finite_number(floorplan.get("depth_cm")) or 0,
    )
    return 100.0 if expected > 0 and 0 < observed <= expected / 20 else fallback


def _normalize_scene_segment(
    segment: Mapping[str, Any], collection_scale: float
) -> dict[str, Any]:
    scale = _item_scale(segment, "cm" if collection_scale == 1 else "m")
    result = _centimeter_item(segment, "cm" if scale == 1 else "m")
    for key in ("start", "end", "swing_end"):
        if key in segment:
            result[key] = _scene_point(segment[key], scale)
    return result


def _normalize_ring(ring: list[Any], scale: float) -> list[list[float]]:
    return [
        [point["x"], point["z"]]
        for point in (_scene_point(value, scale) for value in ring)
    ]


def _normalize_scene_polygon(
    polygon: Mapping[str, Any], collection_scale: float
) -> dict[str, Any]:
    scale = _item_scale(polygon, "cm" if collection_scale == 1 else "m")
    result = deepcopy(dict(polygon))
    result["coordinate_unit"] = "cm"
    result["exterior"] = _normalize_ring(list(polygon.get("exterior") or []), scale)
    result["holes"] = [
        _normalize_ring(list(ring or []), scale)
        for ring in polygon.get("holes") or []
    ]
    return result


def canonicalize_scene_data(saved: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(saved, Mapping):
        return None
    result = deepcopy(dict(saved))
    floorplan = deepcopy(dict(result.get("floorplan") or {}))
    fallback_scale = (
        1.0
        if floorplan.get("coordinate_unit") == "cm"
        or str(floorplan.get("schema_version")) == GEOMETRY_SCHEMA_VERSION
        else 100.0
    )
    normalized_floorplan = deepcopy(floorplan)
    normalized_floorplan["coordinate_unit"] = "cm"
    normalized_floorplan["schema_version"] = GEOMETRY_SCHEMA_VERSION

    for key in (
        "wall_segments",
        "plan_segments",
        "door_segments",
        "window_segments",
        "beam_segments",
    ):
        segments = [item for item in floorplan.get(key) or [] if isinstance(item, Mapping)]
        scale = _inferred_scene_scale(
            _scene_points(segments, ("start", "end")), floorplan, fallback_scale
        )
        normalized_floorplan[key] = [
            _normalize_scene_segment(segment, scale) for segment in segments
        ]

    columns = [
        item for item in floorplan.get("columns") or [] if isinstance(item, Mapping)
    ]
    column_scale = _inferred_scene_scale(
        _scene_points(columns, ("center",)), floorplan, fallback_scale
    )
    normalized_floorplan["columns"] = [
        {
            **_centimeter_item(column, "cm" if column_scale == 1 else "m"),
            **(
                {"center": _scene_point(column["center"], column_scale)}
                if column.get("center") is not None
                else {}
            ),
        }
        for column in columns
    ]

    for key in ("wall_polys", "room_regions"):
        polygons = [
            item for item in floorplan.get(key) or [] if isinstance(item, Mapping)
        ]
        polygon_points = [
            point
            for polygon in polygons
            for ring in [polygon.get("exterior") or [], *(polygon.get("holes") or [])]
            for point in ring
        ]
        scale = _inferred_scene_scale(polygon_points, floorplan, fallback_scale)
        normalized_floorplan[key] = [
            _normalize_scene_polygon(polygon, scale) for polygon in polygons
        ]

    bbox = floorplan.get("bbox")
    if isinstance(bbox, Mapping):
        bbox_scale = _inferred_scene_scale(
            [
                [bbox.get("minx", 0), bbox.get("minz", 0)],
                [bbox.get("maxx", 0), bbox.get("maxz", 0)],
            ],
            floorplan,
            fallback_scale,
        )
        normalized_floorplan["bbox"] = {
            key: float(value) * bbox_scale for key, value in bbox.items()
        }

    for key in ("doors", "windows"):
        segments = [item for item in floorplan.get(key) or [] if isinstance(item, Mapping)]
        points = [
            [segment.get(x_key, 0), segment.get(z_key, 0)]
            for segment in segments
            for x_key, z_key in (("x1", "z1"), ("x2", "z2"))
        ]
        scale = _inferred_scene_scale(points, floorplan, fallback_scale)
        normalized_floorplan[key] = [
            {
                **deepcopy(dict(segment)),
                "coordinate_unit": "cm",
                **{
                    axis: float(segment[axis]) * scale
                    for axis in ("x1", "z1", "x2", "z2")
                    if axis in segment
                },
            }
            for segment in segments
        ]
    result["floorplan"] = normalized_floorplan

    normalized_objects = []
    for value in result.get("scene_objects") or []:
        if not isinstance(value, Mapping):
            continue
        item = deepcopy(dict(value))
        if "position_cm" not in item and isinstance(item.get("position_m"), Mapping):
            item["position_cm"] = _scene_point(item["position_m"], 100.0)
        if "size_cm" not in item and isinstance(item.get("size_m"), Mapping):
            item["size_cm"] = {
                key: float(number) * 100 for key, number in item["size_m"].items()
            }
        for key in list(item):
            if str(key).endswith("_m"):
                item.pop(key, None)
        item["coordinate_unit"] = "cm"
        normalized_objects.append(item)
    result["scene_objects"] = normalized_objects
    return result


WALL_ANCHORED_FURNITURE_TYPES = {
    "appliance-cabinet",
    "bathroom-vanity",
    "bed",
    "bed-frame",
    "bookcase",
    "cabinet",
    "desk",
    "mirror-cabinet",
    "refrigerator",
    "sideboard",
    "sofa",
    "sofa-bed",
    "storage-cabinet",
    "tv-bench",
    "wardrobe",
    "washer",
}


def _rectangular_region_bounds(region: Mapping[str, Any]) -> dict[str, float] | None:
    if region.get("holes"):
        return None
    points = [
        (float(point[0]), float(point[1]))
        for point in region.get("exterior") or []
        if isinstance(point, (list, tuple)) and len(point) >= 2
    ]
    xs = {point[0] for point in points}
    zs = {point[1] for point in points}
    if len(xs) != 2 or len(zs) != 2 or len(set(points)) != 4:
        return None
    return {"min_x": min(xs), "max_x": max(xs), "min_z": min(zs), "max_z": max(zs)}


def repair_legacy_wall_furniture_gaps(
    scene_data: Mapping[str, Any] | None,
    furniture: list[Any] | None,
) -> tuple[dict[str, Any] | None, list[Any], int]:
    """Apply the retired 8 cm wall-gap correction once during schema migration."""
    if not isinstance(scene_data, Mapping):
        return None, deepcopy(list(furniture or [])), 0
    result = deepcopy(dict(scene_data))
    regions = {
        str(region.get("room_id") or region.get("id") or ""): bounds
        for region in result.get("floorplan", {}).get("room_regions") or []
        if isinstance(region, Mapping)
        and (bounds := _rectangular_region_bounds(region)) is not None
    }
    repaired_positions: dict[str, dict[str, float]] = {}
    repaired_objects = []
    for source in result.get("scene_objects") or []:
        item = deepcopy(dict(source)) if isinstance(source, Mapping) else source
        if not isinstance(item, dict):
            repaired_objects.append(item)
            continue
        furniture_id = str(item.get("furniture_id") or "")
        bounds = regions.get(str(item.get("placement_room_id") or ""))
        size = item.get("size_cm") or {}
        position = item.get("position_cm") or {}
        width = _finite_number(size.get("width"))
        depth = _finite_number(size.get("depth"))
        x = _finite_number(position.get("x"))
        z = _finite_number(position.get("z"))
        if (
            not furniture_id
            or bounds is None
            or item.get("placement_engine") != "furniture_engine"
            or item.get("position_locked") is not True
            or str(item.get("normalized_type") or "") not in WALL_ANCHORED_FURNITURE_TYPES
            or not width
            or not depth
            or x is None
            or z is None
        ):
            repaired_objects.append(item)
            continue
        from math import cos, pi, sin

        radians = abs((_finite_number(item.get("rotation_y_deg")) or 0) % 180) * pi / 180
        footprint_width = width * abs(cos(radians)) + depth * abs(sin(radians))
        footprint_depth = width * abs(sin(radians)) + depth * abs(cos(radians))
        gaps = {
            "left": x - footprint_width / 2 - bounds["min_x"],
            "right": bounds["max_x"] - x - footprint_width / 2,
            "top": z - footprint_depth / 2 - bounds["min_z"],
            "bottom": bounds["max_z"] - z - footprint_depth / 2,
        }
        if any(gap < -0.5 for gap in gaps.values()):
            repaired_objects.append(item)
            continue
        next_x, next_z = x, z
        if 7.5 <= gaps["left"] <= 8.5:
            next_x = bounds["min_x"] + footprint_width / 2
        elif 7.5 <= gaps["right"] <= 8.5:
            next_x = bounds["max_x"] - footprint_width / 2
        if 7.5 <= gaps["top"] <= 8.5:
            next_z = bounds["min_z"] + footprint_depth / 2
        elif 7.5 <= gaps["bottom"] <= 8.5:
            next_z = bounds["max_z"] - footprint_depth / 2
        if next_x != x or next_z != z:
            repaired = {"x": round(next_x, 3), "z": round(next_z, 3)}
            item["position_cm"] = {**position, **repaired}
            item["footprint_cm"] = {
                "width": round(footprint_width, 3),
                "depth": round(footprint_depth, 3),
            }
            repaired_positions[furniture_id] = repaired
        repaired_objects.append(item)
    result["scene_objects"] = repaired_objects
    repaired_furniture = []
    for source in furniture or []:
        item = deepcopy(source)
        position = repaired_positions.get(str(item.get("id") or "")) if isinstance(item, dict) else None
        if position:
            item["xCm"] = position["x"]
            item["yCm"] = position["z"]
        repaired_furniture.append(item)
    return result, repaired_furniture, len(repaired_positions)


def _empty_scheme(scheme_id: str) -> dict[str, Any]:
    return {
        "id": scheme_id,
        "kind": "baseline" if scheme_id == "A" else "alternative",
        "label": f"方案 {scheme_id}",
        "furniture": [],
        "sceneData": None,
        "stale": False,
        "staleReason": "",
    }


def _scheme_sources(saved: Mapping[str, Any] | None) -> dict[str, Any]:
    value = dict(saved or {})
    schemes = dict(value.get("schemes") or {})
    aliases = {
        "A": ("A", "schemeA", "scheme_a", "baseline"),
        "B": ("B", "schemeB", "scheme_b", "alternative"),
    }
    result = {}
    for scheme_id, keys in aliases.items():
        source = next(
            (
                schemes.get(key, value.get(key))
                for key in keys
                if isinstance(schemes.get(key, value.get(key)), Mapping)
            ),
            None,
        )
        if source is not None:
            result[scheme_id] = deepcopy(dict(source))
    return result


def _valid_room_selections(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(room_id): str(scheme_id)
        for room_id, scheme_id in value.items()
        if str(room_id).strip() and str(scheme_id) in {"A", "B"}
    }


def _canonical_configuration(
    configuration: Mapping[str, Any] | None,
    space_schemes: Mapping[str, Any] | None,
    root_schemes: Mapping[str, Any] | None,
    layout: Mapping[str, Any] | None,
    white_model: Mapping[str, Any] | None,
    root: Mapping[str, Any],
) -> dict[str, Any]:
    configuration = dict(configuration or {})
    layout = dict(layout or {})
    metadata = dict(space_schemes or root_schemes or configuration)
    sources: dict[str, dict[str, Any]] = {}
    for source in (metadata, configuration, {"schemes": layout.get("schemes") or {}}):
        for scheme_id, scheme in _scheme_sources(source).items():
            sources[scheme_id] = {**sources.get(scheme_id, {}), **scheme}

    legacy_furniture = next(
        (
            deepcopy(value)
            for value in (
                layout.get("furniture"),
                layout.get("furniture2d"),
                root.get("furniture"),
                root.get("furniture2d"),
            )
            if isinstance(value, list)
        ),
        [],
    )
    active_id = str(
        configuration.get("active_scheme_id")
        or layout.get("active_scheme_id")
        or metadata.get("active_scheme_id")
        or "A"
    )
    if active_id not in {"A", "B"}:
        active_id = "A"
    legacy_scene = None
    if isinstance(white_model, Mapping):
        legacy_scene = white_model.get("sceneData") or white_model.get("scene_json")

    schemes = {}
    for scheme_id in ("A", "B"):
        source = sources.get(scheme_id)
        if source is None and scheme_id == "B":
            continue
        scheme = {**_empty_scheme(scheme_id), **(source or {})}
        if scheme_id == "A" and not scheme.get("furniture"):
            scheme["furniture"] = legacy_furniture
        scene_data = scheme.get("sceneData") or scheme.get("scene_json")
        if scene_data is None and scheme_id == active_id:
            scene_data = legacy_scene
        scheme.pop("scene_json", None)
        canonical_scene = canonicalize_scene_data(scene_data)
        canonical_scene, canonical_furniture, _ = repair_legacy_wall_furniture_gaps(
            canonical_scene,
            list(scheme.get("furniture") or []),
        )
        scheme["sceneData"] = canonical_scene
        scheme["furniture"] = canonical_furniture
        scheme["stale"] = scheme.get("stale") is True
        scheme["staleReason"] = str(
            scheme.get("staleReason") or scheme.get("stale_reason") or ""
        )
        scheme.pop("stale_reason", None)
        schemes[scheme_id] = scheme
    if active_id == "B" and "B" not in schemes:
        active_id = "A"

    locked_id = (
        configuration.get("locked_scheme_id")
        or layout.get("locked_scheme_id")
        or metadata.get("locked_scheme_id")
    )
    if locked_id not in schemes:
        locked_id = None
    room_selections = (
        configuration.get("room_selections")
        or layout.get("room_selections")
        or metadata.get("room_selections")
        or {}
    )
    snapshot = (
        configuration.get("configuration_snapshot")
        or layout.get("configuration_snapshot")
        or metadata.get("configuration_snapshot")
    )
    return {
        "schema_version": CONFIGURATION_SCHEMA_VERSION,
        "active_scheme_id": active_id,
        "locked_scheme_id": locked_id,
        "room_selections": _valid_room_selections(room_selections),
        "configuration_snapshot": deepcopy(snapshot) if isinstance(snapshot, Mapping) else None,
        "schemes": schemes,
    }


def migrate_project_workflow(
    workflow: Mapping[str, Any] | None,
) -> ProjectWorkflowMigration:
    original = deepcopy(dict(workflow or {}))
    source_version = project_schema_version(original)
    if source_version is not None and source_version > PROJECT_SCHEMA_VERSION:
        raise ValueError(
            f"project schema v{source_version} is newer than supported v{PROJECT_SCHEMA_VERSION}"
        )
    result = deepcopy(original)

    recognition = result.get("recognition")
    if isinstance(recognition, Mapping):
        result["recognition"] = canonicalize_analysis_cm(recognition)

    space = result.get("space_confirmation")
    space_schemes = space.get("design_schemes") if isinstance(space, Mapping) else None
    if isinstance(space, Mapping):
        result["space_confirmation"] = canonicalize_space_confirmation(space)

    layout = result.get("layout_2d")
    white_model = result.get("white_model_3d")
    configuration = _canonical_configuration(
        result.get("configuration") if isinstance(result.get("configuration"), Mapping) else None,
        space_schemes if isinstance(space_schemes, Mapping) else None,
        result.get("design_schemes") if isinstance(result.get("design_schemes"), Mapping) else None,
        layout if isinstance(layout, Mapping) else None,
        white_model if isinstance(white_model, Mapping) else None,
        result,
    )
    has_configuration_data = any(
        (
            isinstance(result.get("configuration"), Mapping),
            isinstance(space_schemes, Mapping),
            isinstance(result.get("design_schemes"), Mapping),
            isinstance(layout, Mapping),
            isinstance(white_model, Mapping),
        )
    )
    if has_configuration_data:
        result["configuration"] = configuration

    result.pop("design_schemes", None)
    result.pop("furniture", None)
    result.pop("furniture2d", None)
    if isinstance(layout, Mapping):
        canonical_layout = deepcopy(dict(layout))
        for key in (
            "furniture",
            "furniture2d",
            "schemes",
            "active_scheme_id",
            "locked_scheme_id",
            "room_selections",
            "configuration_snapshot",
        ):
            canonical_layout.pop(key, None)
        canonical_layout["schema_version"] = PROJECT_SCHEMA_VERSION
        result["layout_2d"] = canonical_layout
    if isinstance(white_model, Mapping):
        canonical_white_model = deepcopy(dict(white_model))
        canonical_white_model.pop("sceneData", None)
        canonical_white_model.pop("scene_json", None)
        canonical_white_model["schema_version"] = PROJECT_SCHEMA_VERSION
        result["white_model_3d"] = canonical_white_model

    result["project_schema_version"] = PROJECT_SCHEMA_VERSION
    return ProjectWorkflowMigration(
        workflow=result,
        source_version=source_version,
        changed=result != original,
    )
