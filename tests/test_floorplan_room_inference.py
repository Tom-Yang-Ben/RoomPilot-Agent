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


def test_one_ocr_label_cannot_be_claimed_by_two_rooms() -> None:
    """QA #6：房名文字被重複認領，主臥標籤落到隔壁小房。

    OCR 房名的錨點是文字方塊中心，不是房間幾何中心。舊寫法命中後不把候選移出清單，
    同一個「主臥室」會被兩個空間同時認領，連 id 都重複。
    """
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
                "id": "bedroom-1",
                "type": "bedroom",
                "label": "主臥室",
                "centroid_m": {"x": 1.5, "y": 2},
                "confidence": 0.93,
            }
        ],
    )

    assert len(rooms) == 2
    labelled = [room for room in rooms if room["label"] == "主臥室"]
    assert len(labelled) == 1, "同一個房名不得被兩個空間同時認領"
    assert len({room["id"] for room in rooms}) == 2, "房間 id 不得重複"


def test_room_label_goes_to_the_room_it_sits_deepest_inside() -> None:
    """同一個空間內有多個房名時，取信心值最高者；同分取離邊界最遠者。"""
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
                "id": "bedroom-weak",
                "type": "bedroom",
                "label": "次臥",
                "centroid_m": {"x": 1.5, "y": 2},
                "confidence": 0.42,
            },
            {
                "id": "bedroom-strong",
                "type": "bedroom",
                "label": "主臥室",
                "centroid_m": {"x": 1.4, "y": 2.1},
                "confidence": 0.95,
            },
        ],
    )

    left = next(
        room for room in rooms if min(point["x"] for point in room["polygon_m"]) < 1.0
    )
    assert left["label"] == "主臥室"
