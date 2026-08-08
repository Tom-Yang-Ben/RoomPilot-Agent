from __future__ import annotations

from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)


def _generate(payload_extra: dict) -> dict:
    response = client.post(
        "/api/scene/generate",
        json={
            "client_brief": {
                "space": {"type": "living_room", "width_cm": 600, "depth_cm": 400},
                "style": {"preferred": ["scandinavian"], "colors": [], "materials": []},
                "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
                "needs": [],
                "constraints": [],
            },
            "room_width_cm": 600,
            "room_depth_cm": 400,
            "required_furniture": [],
            "selected_furniture": [],
            "selected_furniture_exact": False,
            **payload_extra,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_removed_furniture_is_not_re_added_by_auto_fill() -> None:
    """「移除此家具」後，下一次重算的自動補件不得把同類型再補回來。

    2026-08-08 Ben 實測：移除的櫃體在下一次 /api/scene/generate 被
    choose_furniture_items 以同款或同類型補回，使用者永遠移除不掉。
    """
    first = _generate({})
    objects = first["scene_objects"]
    assert objects, "auto-fill 應該會為客廳挑出家具"
    target_type = objects[0]["normalized_type"]

    second = _generate({
        "removed_furniture": [
            {"id": "", "catalog_furniture_id": None, "normalized_type": target_type},
        ],
    })
    remaining_types = {item["normalized_type"] for item in second["scene_objects"]}
    assert target_type not in remaining_types


def test_removed_catalog_id_is_excluded_but_type_can_be_rechosen_exactly() -> None:
    """排除移除的 catalog id 後，使用者親手再選同型（exact 清單）仍要生效。"""
    first = _generate({})
    objects = first["scene_objects"]
    assert objects
    target = objects[0]
    target_id = target.get("catalog_furniture_id") or target["furniture_id"]

    reselected = _generate({
        "removed_furniture": [
            {
                "id": str(target_id),
                "catalog_furniture_id": str(target_id),
                "normalized_type": target["normalized_type"],
            },
        ],
        "selected_furniture": [
            {
                "furniture_id": "user-re-added-1",
                "catalog_furniture_id": str(target_id),
                "normalized_type": target["normalized_type"],
                "name_zh_raw": target.get("name_zh_raw") or "使用者重選",
                "position_cm": target.get("position_cm"),
                "size_cm": target.get("size_cm"),
                "model_url": target.get("model_url"),
                "source": "roompilot_2d",
                "position_locked": True,
            },
        ],
    })
    types = [item["normalized_type"] for item in reselected["scene_objects"]]
    assert target["normalized_type"] in types
