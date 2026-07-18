from roompilot.floorplan.vision.rooms import infer_rooms_from_walls


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
