from pathlib import Path

from fastapi.testclient import TestClient

from roompilot.server.main import app


client = TestClient(app)


CODY4_FLOORPLAN = {
    "width_cm": 949.8,
    "depth_cm": 1044.43,
    "room_regions": [
        {"room_id": "room-1", "room_type": "bedroom", "exterior": [[-4.504, 0.9788], [-0.131, 0.9788], [-0.131, 4.9938], [-4.504, 4.9938]], "holes": []},
        {"room_id": "room-2", "room_type": "kitchen", "exterior": [[0.13, 0.9788], [4.553, 0.9788], [4.553, 4.9938], [0.13, 4.9938]], "holes": []},
        {"room_id": "room-3", "room_type": "storage", "exterior": [[-4.504, -3.1492], [-0.131, -3.1492], [-0.131, 0.7178], [-4.504, 0.7178]], "holes": []},
        {"room_id": "room-4", "room_type": "circulation", "exterior": [[0.13, -0.8482], [1.256, -0.8482], [1.256, 0.7178], [0.13, 0.7178]], "holes": []},
        {"room_id": "room-5", "room_type": "bathroom", "exterior": [[1.518, -0.8482], [4.504, -0.8482], [4.504, 0.7178], [1.518, 0.7178]], "holes": []},
        {"room_id": "room-6", "room_type": "living_room", "exterior": [[0.114, -4.9772], [4.504, -4.9772], [4.504, -1.1102], [0.114, -1.1102]], "holes": []},
        {"room_id": "room-7", "room_type": "balcony", "exterior": [[-4.667, -5.1402], [-0.114, -5.1402], [-0.114, -3.4112], [-4.667, -3.4112]], "holes": []},
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
    source = Path("roompilot/server/static/scene.html").read_text(encoding="utf-8")
    controller = Path("roompilot/server/static/scene_v2.js").read_text(encoding="utf-8")

    assert 'data-view-mode="topdown"' in source
    assert 'data-view-mode="walk"' in source
    assert 'whiteViewer.setViewMode(button.dataset.viewMode)' in controller
    assert 'realisticViewer.setViewMode(button.dataset.realViewMode)' in controller
