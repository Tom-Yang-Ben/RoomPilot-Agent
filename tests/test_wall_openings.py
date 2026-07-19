from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from roompilot.server.scene_service import _flip_parsed_z
from roompilot.upgrade3d.wall_openings import build_opening_wall_geometry


def _wall_at_height(result: dict, height: float):
    polygons = []
    for solid in result["wall_solids"]:
        if solid["base_y"] <= height < solid["base_y"] + solid["height"]:
            polygons.extend(
                Polygon(poly["exterior"], poly["holes"])
                for poly in solid["polys"]
            )
    return unary_union(polygons)


def _floorplan(*, windows=None, doors=None) -> dict:
    return {
        "wall_height": 2.7,
        "wall_thickness": 0.18,
        "wall_polys": [{
            "exterior": [[-3, -0.1], [3, -0.1], [3, 0.1], [-3, 0.1], [-3, -0.1]],
            "holes": [],
        }],
        "windows": windows or [],
        "doors": doors or [],
    }


def test_window_is_removed_only_between_sill_and_head() -> None:
    result = build_opening_wall_geometry(_floorplan(
        windows=[{"x1": -0.8, "z1": 0, "x2": 0.8, "z2": 0}],
    ))

    centre = Point(0, 0)
    assert _wall_at_height(result, 0.4).contains(centre)
    assert not _wall_at_height(result, 1.2).contains(centre)
    assert _wall_at_height(result, 2.4).contains(centre)
    assert result["opening_geometry"]["window_opening_count"] == 1
    assert result["opening_geometry"]["wall_solid_bands"] == 3


def test_door_opens_from_floor_and_stray_window_does_not_cut_wall() -> None:
    result = build_opening_wall_geometry(_floorplan(
        windows=[{"x1": -0.8, "z1": 4, "x2": 0.8, "z2": 4}],
        doors=[{"x1": 1.0, "z1": 0, "x2": 2.0, "z2": 0}],
    ))

    assert not _wall_at_height(result, 0.4).contains(Point(1.5, 0))
    assert _wall_at_height(result, 2.4).contains(Point(1.5, 0))
    assert result["opening_geometry"]["door_opening_count"] == 1
    assert result["opening_geometry"]["window_count"] == 1
    assert result["opening_geometry"]["window_opening_count"] == 0


def test_z_flip_keeps_opening_aware_wall_solids_in_the_same_frame() -> None:
    parsed = {
        **_floorplan(windows=[{"x1": -0.8, "z1": 0.05, "x2": 0.8, "z2": 0.05}]),
        "wall_segments": [],
        "plan_segments": [],
        "door_segments": [],
        "window_segments": [],
        "texts": [],
        "bbox": {"minx": -3, "minz": -1, "maxx": 3, "maxz": 1},
    }
    parsed.update(build_opening_wall_geometry(parsed))

    flipped = _flip_parsed_z(parsed)

    assert flipped["wall_solids"][0]["polys"][0]["exterior"][0][1] == 0.1
    assert flipped["windows"][0] == {"x1": -0.8, "z1": -0.05, "x2": 0.8, "z2": -0.05}


def test_centimetre_wall_segment_fallback_still_builds_a_real_opening() -> None:
    floorplan = {
        "wall_height": 2.7,
        "wall_thickness": 0.18,
        "bbox": {"minx": -3, "minz": -1, "maxx": 3, "maxz": 1},
        "wall_polys": [],
        "wall_segments": [{
            "start": {"x": -300, "z": 0},
            "end": {"x": 300, "z": 0},
        }],
        "windows": [{"x1": -0.8, "z1": 0, "x2": 0.8, "z2": 0}],
        "doors": [],
    }

    result = build_opening_wall_geometry(floorplan)

    assert result["opening_geometry"]["wall_source"] == "wall_segments"
    assert result["opening_geometry"]["window_opening_count"] == 1
    assert not _wall_at_height(result, 1.2).contains(Point(0, 0))
