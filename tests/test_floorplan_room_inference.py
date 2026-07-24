from backend.floorplan.vision.rooms import (
    _remove_narrow_spikes,
    infer_rooms_from_walls,
)


def _wall(start: tuple[float, float], end: tuple[float, float]) -> dict:
    return {
        "start": {"x": start[0], "y": start[1]},
        "end": {"x": end[0], "y": end[1]},
        "thickness_m": 0.12,
    }


def test_cody_wall_enclosures_create_multiple_editable_rooms() -> None:
    rooms = infer_rooms_from_walls(
        [
            _wall((0, 0), (6, 0)),
            _wall((6, 0), (6, 4)),
            _wall((6, 4), (0, 4)),
            _wall((0, 4), (0, 0)),
            _wall((3, 0), (3, 4)),
        ],
        labelled_rooms=[
            {
                "id": "living-room",
                "type": "living_room",
                "label": "客廳",
                "centroid_m": {"x": 1.5, "y": 2},
                "confidence": 0.91,
            }
        ],
    )

    assert len(rooms) == 2
    assert any(room["label"] == "客廳" for room in rooms)
    assert all(len(room["polygon_m"]) >= 4 for room in rooms)
    assert all(room["source"] == "cody_wall_enclosure" for room in rooms)


def test_missing_wall_geometry_does_not_fabricate_rooms() -> None:
    assert infer_rooms_from_walls([]) == []


def test_cody_room_polygons_remove_door_closure_spikes() -> None:
    polygons = [
        [
            {"x": 3.766, "y": 7.884},
            {"x": 3.766, "y": 4.786},
            {"x": 4.635, "y": 4.786},
            {"x": 4.736, "y": 6.902},
            {"x": 4.836, "y": 4.786},
            {"x": 7.141, "y": 4.786},
            {"x": 7.154, "y": 7.884},
        ],
        [
            {"x": 0.189, "y": 4.585},
            {"x": 0.189, "y": 1.6},
            {"x": 3.564, "y": 1.6},
            {"x": 3.564, "y": 3.174},
            {"x": 3.35, "y": 3.275},
            {"x": 3.564, "y": 3.375},
            {"x": 3.564, "y": 4.585},
        ],
        [
            {"x": 3.766, "y": 3.174},
            {"x": 3.766, "y": 1.6},
            {"x": 5.051, "y": 1.499},
            {"x": 3.766, "y": 1.398},
            {"x": 3.766, "y": 0.189},
            {"x": 7.141, "y": 0.189},
            {"x": 7.141, "y": 3.174},
        ],
    ]

    repaired = [_remove_narrow_spikes(polygon) for polygon in polygons]

    assert [len(polygon) for polygon in repaired] == [4, 4, 4]
    assert {"x": 4.736, "y": 6.902} not in repaired[0]
    assert {"x": 3.35, "y": 3.275} not in repaired[1]
    assert {"x": 5.051, "y": 1.499} not in repaired[2]


def test_spike_repair_keeps_legitimate_l_shaped_room() -> None:
    polygon = [
        {"x": 0, "y": 0},
        {"x": 4, "y": 0},
        {"x": 4, "y": 3},
        {"x": 2, "y": 3},
        {"x": 2, "y": 1},
        {"x": 0, "y": 1},
    ]

    assert _remove_narrow_spikes(polygon) == polygon
