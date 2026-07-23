import pytest

from roompilot.engine.dxf_room import build_room_from_dxf


def test_largest_room_converts_dxf_meters_to_engine_centimeters():
    parsed = {
        "bbox": {"minx": -2.5, "minz": -2.0, "maxx": 2.5, "maxz": 2.0},
        "wall_polys": [
            {
                "exterior": [],
                "holes": [[[-2.5, -2.0], [2.5, -2.0], [2.5, 2.0], [-2.5, 2.0]]],
            }
        ],
    }

    result = build_room_from_dxf(parsed)

    assert result.room.width == pytest.approx(500)
    assert result.room.depth == pytest.approx(400)
    assert result.offset == pytest.approx((-250, -200))
    assert result.source_area == pytest.approx(200_000)
    assert result.room.walls[0].thickness == pytest.approx(6)


def test_plan_room_converts_bbox_and_wall_coordinates_to_centimeters():
    parsed = {
        "bbox": {"minx": 1.0, "minz": 2.0, "maxx": 6.0, "maxz": 6.0},
        "wall_polys": [
            {
                "exterior": [[1.0, 2.0], [6.0, 2.0], [6.0, 6.0], [1.0, 6.0]],
                "holes": [],
            }
        ],
    }

    result = build_room_from_dxf(parsed, mode="plan")

    assert result.room.width == pytest.approx(500)
    assert result.room.depth == pytest.approx(400)
    assert result.offset == pytest.approx((100, 200))
    assert result.room.walls[0].x1 == pytest.approx(0)
    assert result.room.walls[0].x2 == pytest.approx(500)
