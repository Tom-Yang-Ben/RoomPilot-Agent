from pathlib import Path

from scripts.static_source_graph import scene_controller_source

from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)


CODY4_FLOORPLAN = {
    "coordinate_unit": "cm",
    "schema_version": "2.0",
    "width_cm": 949.8,
    "depth_cm": 1044.43,
    "room_regions": [
        {"room_id": "room-1", "room_type": "bedroom", "exterior": [[-450.4, 97.88], [-13.1, 97.88], [-13.1, 499.38], [-450.4, 499.38]], "holes": []},
        {"room_id": "room-2", "room_type": "kitchen", "exterior": [[13.0, 97.88], [455.3, 97.88], [455.3, 499.38], [13.0, 499.38]], "holes": []},
        {"room_id": "room-3", "room_type": "storage", "exterior": [[-450.4, -314.92], [-13.1, -314.92], [-13.1, 71.78], [-450.4, 71.78]], "holes": []},
        {"room_id": "room-4", "room_type": "circulation", "exterior": [[13.0, -84.82], [125.6, -84.82], [125.6, 71.78], [13.0, 71.78]], "holes": []},
        {"room_id": "room-5", "room_type": "bathroom", "exterior": [[151.8, -84.82], [450.4, -84.82], [450.4, 71.78], [151.8, 71.78]], "holes": []},
        {"room_id": "room-6", "room_type": "living_room", "exterior": [[11.4, -497.72], [450.4, -497.72], [450.4, -111.02], [11.4, -111.02]], "holes": []},
        {"room_id": "room-7", "room_type": "balcony", "exterior": [[-466.7, -514.02], [-11.4, -514.02], [-11.4, -341.12], [-466.7, -341.12]], "holes": []},
    ],
}


ROOM_FURNITURE = {
    "room-1": [("bed", 152, 200), ("bedside-table", 45, 40)],
    "room-2": [("refrigerator", 70, 72)],
    "room-3": [("storage-cabinet", 120, 45)],
    "room-5": [("bathroom-vanity", 90, 55)],
    "room-6": [
        ("sofa", 210, 90),
        ("coffee-table", 110, 60),
        ("tv-bench", 180, 45),
        ("flower-pots-planter", 35, 35),
    ],
    "room-7": [("washer", 60, 65), ("flower-pots-planter", 35, 35)],
}


def test_cody4_room_furniture_survives_the_2d_to_3d_engine_gate() -> None:
    placed = []
    for room_id, specs in ROOM_FURNITURE.items():
        objects = [
            {
                "furniture_id": f"{room_id}-{kind}-{index}",
                "normalized_type": kind,
                "name_zh_raw": kind,
                "size_cm": {"width": width, "depth": depth, "height": 80},
                "position_locked": False,
                "placement_room_id": room_id,
            }
            for index, (kind, width, depth) in enumerate(specs, start=1)
        ]
        response = client.post(
            "/api/scene/layout",
            json={
                "floorplan": CODY4_FLOORPLAN,
                "placement_room_id": room_id,
                "scene_objects": objects,
            },
        )
        assert response.status_code == 200
        room_result = response.json()["scene_objects"]
        assert all(item["placement_failed"] is False for item in room_result)
        placed.extend(room_result)

    assert len(placed) == 11
    assert len({item["furniture_id"] for item in placed}) == 11
    assert sum(item["normalized_type"] == "bed" for item in placed) == 1
    assert sum(item["normalized_type"] == "flower-pots-planter" for item in placed) == 2


def test_cody4_3d_view_controls_remain_explicit_ci_contracts() -> None:
    source = Path("backend/server/static/scene.html").read_text(encoding="utf-8")
    controller = scene_controller_source(Path("backend/server/static"))

    assert 'data-view-mode="topdown"' in source
    assert 'data-white-interaction="walk"' in source
    assert 'data-white-interaction="edit"' in source
    assert 'data-view-mode="dollhouse"' not in source
    assert 'whiteViewer.setViewMode(button.dataset.viewMode)' in controller
    assert 'realisticViewer.setViewMode(button.dataset.realViewMode)' in controller
