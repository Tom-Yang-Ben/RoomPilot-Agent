from fastapi.testclient import TestClient

from roompilot.server.main import app


client = TestClient(app)


def test_layout_places_furniture_in_requested_room_region() -> None:
    floorplan = {
        "width_cm": 1000,
        "depth_cm": 600,
        "room_regions": [
            {
                "room_id": "living-room",
                "exterior": [[-5, -3], [1, -3], [1, 3], [-5, 3]],
                "holes": [],
            },
            {
                "room_id": "bedroom-1",
                "exterior": [[2, -2], [5, -2], [5, 2], [2, 2]],
                "holes": [],
            },
        ],
    }
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan": floorplan,
            "placement_room_id": "bedroom-1",
            "scene_objects": [
                {
                    "furniture_id": "bed-1",
                    "name_zh_raw": "床",
                    "normalized_type": "bed",
                    "size_cm": {"width": 160, "depth": 200, "height": 82},
                    "position_cm": {"x": 0, "z": 0},
                    "rotation_y_deg": 0,
                }
            ],
        },
    )

    assert response.status_code == 200
    item = response.json()["scene_objects"][0]
    assert item.get("placement_failed") is not True
    # bedroom-1 的中心原點 x 範圍是 2..5m；家具中心應落在該房間，而非較大的客廳。
    assert 200 <= item["position_cm"]["x"] <= 500
