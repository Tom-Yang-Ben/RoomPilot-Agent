"""Build opening-aware vertical wall solids from the canonical floor-plan payload.

The DXF parser already gives us a reliable 2D Shapely wall mass.  A single
``ExtrudeGeometry`` of that mass cannot contain a vertical window opening, so we
split the wall by height and subtract the active door/window footprints from
each band.  The browser can then extrude every band without a CSG dependency.

Input coordinates and output dimensions are metres.  This module deliberately
stays on the ``upgrade3d`` side of the metres -> centimetres business boundary.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


DEFAULT_WINDOW_SILL_M = 0.9
DEFAULT_WINDOW_HEIGHT_M = 1.3
DEFAULT_DOOR_HEIGHT_M = 2.1
_EPSILON = 1e-7


def _finite_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if isfinite(number) else fallback


def _segment_points(segment: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    try:
        start = segment.get("start") or segment
        end = segment.get("end") or segment
        x1 = float(start.get("x", start.get("x1")))
        z1 = float(start.get("z", start.get("z1")))
        x2 = float(end.get("x", end.get("x2")))
        z2 = float(end.get("z", end.get("z2")))
    except (AttributeError, TypeError, ValueError):
        return None
    if not all(isfinite(value) for value in (x1, z1, x2, z2)):
        return None
    if (x2 - x1) ** 2 + (z2 - z1) ** 2 <= _EPSILON:
        return None
    return (x1, z1), (x2, z2)


def _payload_polygon(raw: dict[str, Any]) -> Polygon | None:
    exterior = raw.get("exterior") or []
    holes = raw.get("holes") or []
    if len(exterior) < 3:
        return None
    try:
        polygon = Polygon(exterior, holes)
    except (TypeError, ValueError):
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return None if polygon.is_empty else polygon


def _polygon_geometries(geometry) -> Iterable[Polygon]:
    if geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
        return
    for child in getattr(geometry, "geoms", ()):  # MultiPolygon / GeometryCollection
        yield from _polygon_geometries(child)


def _ring_payload(coords) -> list[list[float]]:
    return [[round(float(x), 4), round(float(z), 4)] for x, z in coords]


def _geometry_payload(geometry) -> list[dict[str, Any]]:
    return [
        {
            "exterior": _ring_payload(polygon.exterior.coords),
            "holes": [_ring_payload(ring.coords) for ring in polygon.interiors],
        }
        for polygon in _polygon_geometries(geometry)
        if polygon.area > _EPSILON
    ]


def _wall_lines(floorplan: dict[str, Any]) -> list[LineString]:
    points = [
        segment
        for raw in (floorplan.get("wall_segments") or floorplan.get("plan_segments") or [])
        if (segment := _segment_points(raw)) is not None
    ]
    if not points:
        return []

    xs = [x for segment in points for x, _z in segment]
    zs = [z for segment in points for _x, z in segment]
    segment_span = max(max(xs) - min(xs), max(zs) - min(zs))
    bbox = floorplan.get("bbox") or {}
    bbox_span = max(
        _finite_float(bbox.get("maxx"), 0) - _finite_float(bbox.get("minx"), 0),
        _finite_float(bbox.get("maxz"), 0) - _finite_float(bbox.get("minz"), 0),
    )
    scale = 0.01 if bbox_span > 0 and segment_span > bbox_span * 10 else 1.0
    return [
        LineString([
            (start[0] * scale, start[1] * scale),
            (end[0] * scale, end[1] * scale),
        ])
        for start, end in points
    ]


def _opening_range(
    kind: str,
    segment: dict[str, Any],
    wall_height_m: float,
) -> tuple[float, float]:
    if kind == "window":
        bottom = max(0.0, _finite_float(segment.get("sill_m"), DEFAULT_WINDOW_SILL_M))
        explicit_head = segment.get("head_m")
        if explicit_head is None:
            top = bottom + max(
                0.1,
                _finite_float(segment.get("height_m"), DEFAULT_WINDOW_HEIGHT_M),
            )
        else:
            top = _finite_float(explicit_head, bottom + DEFAULT_WINDOW_HEIGHT_M)
    else:
        bottom = 0.0
        top = _finite_float(segment.get("height_m"), DEFAULT_DOOR_HEIGHT_M)
    return min(bottom, wall_height_m), min(max(top, bottom), wall_height_m)


def build_opening_wall_geometry(floorplan: dict[str, Any]) -> dict[str, Any]:
    """Return ``wall_solids`` and diagnostics for real door/window openings.

    ``wall_solids`` is a list of ``{base_y, height, polys}``.  Each band is a
    watertight 2D wall mass ready for vertical extrusion.  An opening is counted
    as matched only when its buffered footprint actually intersects wall mass;
    stray detections therefore do not punch arbitrary holes into the building.
    """
    wall_height_m = max(0.1, _finite_float(floorplan.get("wall_height"), 2.7))
    wall_thickness_m = max(0.04, _finite_float(floorplan.get("wall_thickness"), 0.18))
    polygons = [
        polygon
        for raw in floorplan.get("wall_polys") or []
        if (polygon := _payload_polygon(raw)) is not None
    ]
    if polygons:
        wall_mass = unary_union(polygons)
        wall_source = "wall_polys"
    else:
        lines = _wall_lines(floorplan)
        wall_mass = (
            unary_union(lines).buffer(
                wall_thickness_m / 2.0,
                cap_style=3,
                join_style=2,
                mitre_limit=5.0,
            )
            if lines
            else None
        )
        wall_source = "wall_segments"
    if wall_mass is None or wall_mass.is_empty:
        return {
            "wall_solids": [],
            "opening_geometry": {
                "status": "wall_mass_missing",
                "window_count": len(floorplan.get("windows") or []),
                "window_opening_count": 0,
                "door_count": len(floorplan.get("doors") or []),
                "door_opening_count": 0,
                "wall_solid_bands": 0,
            },
        }

    if not wall_mass.is_valid:
        wall_mass = wall_mass.buffer(0)

    # Radius is deliberately wider than half the nominal wall thickness: CAD
    # window centre-lines are often drawn on either wall face, not its centre.
    cut_radius = max(0.12, wall_thickness_m * 1.25)
    openings: list[dict[str, Any]] = []
    counts = {"window": 0, "door": 0}
    raw_counts = {
        "window": len(floorplan.get("windows") or []),
        "door": len(floorplan.get("doors") or []),
    }
    for kind, key in (("window", "windows"), ("door", "doors")):
        for index, segment in enumerate(floorplan.get(key) or []):
            points = _segment_points(segment)
            if points is None:
                continue
            bottom, top = _opening_range(kind, segment, wall_height_m)
            if top - bottom <= _EPSILON:
                continue
            cutter = LineString(points).buffer(
                cut_radius,
                cap_style=2,
                join_style=2,
            )
            if wall_mass.intersection(cutter).area <= _EPSILON:
                continue
            counts[kind] += 1
            openings.append(
                {
                    "id": f"{kind}-{index}",
                    "kind": kind,
                    "bottom": bottom,
                    "top": top,
                    "cutter": cutter,
                }
            )

    boundaries = sorted(
        {
            0.0,
            wall_height_m,
            *(opening[edge] for opening in openings for edge in ("bottom", "top")),
        }
    )
    wall_solids: list[dict[str, Any]] = []
    for bottom, top in zip(boundaries, boundaries[1:]):
        if top - bottom <= _EPSILON:
            continue
        middle = (bottom + top) / 2.0
        active = [
            opening["cutter"]
            for opening in openings
            if opening["bottom"] <= middle < opening["top"]
        ]
        band_mass = wall_mass.difference(unary_union(active)) if active else wall_mass
        if not band_mass.is_valid:
            band_mass = band_mass.buffer(0)
        payload = _geometry_payload(band_mass)
        if payload:
            wall_solids.append(
                {
                    "base_y": round(bottom, 4),
                    "height": round(top - bottom, 4),
                    "polys": payload,
                }
            )

    return {
        "wall_solids": wall_solids,
        "opening_geometry": {
            "status": "opening_aware",
            "wall_source": wall_source,
            "window_count": raw_counts["window"],
            "window_opening_count": counts["window"],
            "door_count": raw_counts["door"],
            "door_opening_count": counts["door"],
            "wall_solid_bands": len(wall_solids),
            "window_sill_m": min(DEFAULT_WINDOW_SILL_M, wall_height_m),
            "window_height_m": min(
                DEFAULT_WINDOW_HEIGHT_M,
                max(0.0, wall_height_m - DEFAULT_WINDOW_SILL_M),
            ),
            "door_height_m": min(DEFAULT_DOOR_HEIGHT_M, wall_height_m),
            "cut_depth_m": round(cut_radius * 2.0, 4),
        },
    }
