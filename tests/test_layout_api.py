from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roompilot.server.main import app
from roompilot.server.scene_service import generate_layout, validate_single_placement


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROOMPILOT_RUNTIME_DIR", str(tmp_path / "runtime"))
    with TestClient(app) as test_client:
        yield test_client


def _model_item(item_type: str | None = None) -> dict:
    from roompilot.server.main import _furniture_payload_cache

    return next(
        dict(item)
        for item in _furniture_payload_cache()
        if item.get("has_model")
        and item.get("model_url")
        and (item_type is None or item.get("normalized_type") == item_type)
    )


def _project_at_layout(client: TestClient, required_id: str | None = None) -> dict:
    project = client.post("/api/projects", json={"name": "2D 配置案"}).json()["project"]
    floorplan = {
        "width_cm": 800,
        "depth_cm": 600,
        "bbox": {"minx": -4, "minz": -3, "maxx": 4, "maxz": 3},
        "wall_height": 2.7,
        "wall_thickness": 0.18,
        "wall_polys": [{
            "exterior": [[-4, -3], [4, -3], [4, -2.8], [-4, -2.8], [-4, -3]],
            "holes": [],
        }],
        "wall_segments": [],
        "door_segments": [],
        "window_segments": [],
        "doors": [],
        "windows": [],
        "room_regions": [{
            "room_id": "room-living",
            "room_type": "living_room",
            "label_zh": "客廳",
            "exterior": [[-4, -3], [4, -3], [4, 3], [-4, 3], [-4, -3]],
            "holes": [],
            "confirmed": True,
        }],
    }
    requirements = {
        "status": "confirmed",
        "confirmed_by": "user",
        "style_id": "scandinavian",
        "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
        "customization_mode": "advanced",
        "room_requirements": [{
            "room_id": "room-living",
            "room_type": "living_room",
            "uses": ["family_gathering"],
            "required_furniture_ids": [required_id] if required_id else [],
            "special_materials": [],
            "special_notes": "",
        }],
        "special_notes": "",
        "special_requirements": {"status": "confirmed", "constraints": []},
    }
    response = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={
            "expected_revision": project["revision"],
            "current_step": "layout_2d",
            "workflow": {
                "completed": ["project", "upload", "recognition", "calibration", "space_confirmation", "requirements"],
                "data": {
                    "space_confirmation": {"status": "confirmed", "confirmed_by": "user", "floorplan": floorplan},
                    "requirements": requirements,
                    "layout_2d": None,
                },
            },
        },
    )
    assert response.status_code == 200
    return response.json()["project"]


def test_layout_proposal_is_read_only_then_user_confirmation_advances_workflow(client: TestClient) -> None:
    required = _model_item("coffee-table")
    project = _project_at_layout(client, str(required["furniture_id"]))
    analyzed = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": project["revision"], "allow_openrouter": False},
    )

    assert analyzed.status_code == 200
    proposal = analyzed.json()["proposal"]
    assert proposal["status"] == "suggested"
    assert proposal["proposal_count"] == 1
    assert proposal["openrouter"]["sent"] is False
    assert all(item["placement_room_id"] == "room-living" for item in proposal["scene_objects"])
    exact = next(item for item in proposal["scene_objects"] if item["furniture_id"] == required["furniture_id"])
    assert exact["user_required"] is True
    assert exact["size_cm"]["width"] > 10
    assert not any(item["placement_failed"] for item in proposal["scene_objects"])

    unchanged = client.get(f"/api/projects/{project['project_id']}").json()["project"]
    assert unchanged["revision"] == project["revision"]
    assert unchanged["workflow"]["data"]["layout_2d"] is None

    confirmed = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "proposal_source": proposal["source"],
            "openrouter": proposal["openrouter"],
            "scene_objects": proposal["scene_objects"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["project"]["current_step"] == "white_model_3d"
    assert payload["project"]["revision"] == project["revision"] + 1
    assert payload["layout"]["status"] == "confirmed"
    assert payload["layout"]["confirmed_by"] == "user"
    assert payload["layout"]["units"] == "cm"
    assert all(item["position_locked"] for item in payload["layout"]["scene_objects"])


def test_white_model_requires_every_furniture_and_real_window_opening(client: TestClient) -> None:
    project = _project_at_layout(client)
    proposal = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": project["revision"]},
    ).json()["proposal"]
    confirmed = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "proposal_source": proposal["source"],
            "openrouter": proposal["openrouter"],
            "scene_objects": proposal["scene_objects"],
        },
    ).json()
    project = confirmed["project"]
    expected_ids = [item["instance_id"] for item in confirmed["layout"]["scene_objects"]]

    incomplete = client.post(
        f"/api/projects/{project['project_id']}/white-model-3d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "renderer": "neutral_geometry",
            "visible_instance_ids": expected_ids[:-1],
        },
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["detail"]["code"] == "white_model_furniture_incomplete"

    accepted = client.post(
        f"/api/projects/{project['project_id']}/white-model-3d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "renderer": "neutral_geometry",
            "visible_instance_ids": expected_ids,
        },
    )
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload["project"]["current_step"] == "viewpoint"
    assert payload["white_model"]["renderer"] == "neutral_geometry"
    assert payload["white_model"]["expected_furniture_count"] == len(expected_ids)
    assert payload["white_model"]["visible_furniture_count"] == len(expected_ids)
    assert payload["white_model"]["wall_geometry"] == "opening_aware_solids"


def test_white_model_rejects_confirmed_window_that_does_not_cross_a_wall(client: TestClient) -> None:
    project = _project_at_layout(client)
    workflow = project["workflow"]
    floorplan = workflow["data"]["space_confirmation"]["floorplan"]
    floorplan.update({
        "wall_height": 2.7,
        "wall_thickness": 0.18,
        "wall_polys": [{
            "exterior": [[-4, -3], [4, -3], [4, -2.8], [-4, -2.8], [-4, -3]],
            "holes": [],
        }],
        "windows": [{"x1": -0.5, "z1": 0, "x2": 0.5, "z2": 0}],
    })
    from roompilot.upgrade3d.wall_openings import build_opening_wall_geometry
    floorplan.update(build_opening_wall_geometry(floorplan))
    updated = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={
            "expected_revision": project["revision"],
            "current_step": "layout_2d",
            "workflow": workflow,
        },
    ).json()["project"]
    proposal = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": updated["revision"]},
    ).json()["proposal"]
    confirmed = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/confirm",
        json={
            "expected_revision": updated["revision"],
            "user_reviewed": True,
            "proposal_source": proposal["source"],
            "openrouter": proposal["openrouter"],
            "scene_objects": proposal["scene_objects"],
        },
    ).json()
    response = client.post(
        f"/api/projects/{project['project_id']}/white-model-3d/confirm",
        json={
            "expected_revision": confirmed["project"]["revision"],
            "user_reviewed": True,
            "renderer": "neutral_geometry",
            "visible_instance_ids": [
                item["instance_id"] for item in confirmed["layout"]["scene_objects"]
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "white_model_window_opening_incomplete"


def test_layout_cannot_remove_required_model_or_move_outside_its_room(client: TestClient) -> None:
    required = _model_item("coffee-table")
    project = _project_at_layout(client, str(required["furniture_id"]))
    proposal = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": project["revision"]},
    ).json()["proposal"]
    without_required = [
        item for item in proposal["scene_objects"]
        if item["furniture_id"] != required["furniture_id"]
    ]
    rejected = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "proposal_source": proposal["source"],
            "openrouter": proposal["openrouter"],
            "scene_objects": without_required,
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "required_furniture_missing"

    moved = [dict(item) for item in proposal["scene_objects"]]
    moved[0] = {**moved[0], "position_cm": {"x": 20_000, "z": 20_000}, "position_locked": True}
    validated = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/validate",
        json={
            "expected_revision": project["revision"],
            "item": moved[0],
            "others": moved[1:],
        },
    )
    assert validated.status_code == 200
    assert validated.json()["ok"] is False
    assert "房間範圍" in validated.json()["reason"]


def test_openrouter_selection_is_restricted_to_server_candidate_ids(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roompilot.server import layout_service

    project = _project_at_layout(client)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_LAYOUT_ENABLED", "1")

    def fake_suggestion(payload):
        room = payload["rooms"][0]
        valid_id = room["candidates"][0]["furniture_id"]
        return "mock/layout", {
            "rooms": [{
                "room_id": room["room_id"],
                "furniture_ids": [valid_id, "invented-furniture-id"],
                "hints": [
                    {"furniture_id": valid_id, "anchor": "left", "priority": 1},
                    {"furniture_id": "invented-furniture-id", "anchor": "right", "priority": 0},
                ],
            }],
        }

    monkeypatch.setattr(layout_service, "_openrouter_layout_suggestion", fake_suggestion)
    response = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": project["revision"], "allow_openrouter": True},
    )
    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["source"] == "openrouter"
    assert proposal["openrouter"] == {
        "provider": "openrouter",
        "requested": True,
        "sent": True,
        "status": "suggested",
        "model": "mock/layout",
    }
    assert "invented-furniture-id" not in {item["furniture_id"] for item in proposal["scene_objects"]}


def test_door_clearance_and_fixed_furniture_are_engine_constraints() -> None:
    floorplan = {
        "width_cm": 400,
        "depth_cm": 400,
        "bbox": {"minx": -2, "minz": -2, "maxx": 2, "maxz": 2},
        "wall_segments": [],
        "room_regions": [{
            "room_id": "room-a",
            "exterior": [[-2, -2], [2, -2], [2, 2], [-2, 2], [-2, -2]],
            "holes": [],
        }],
        "door_segments": [{
            "start": {"x": -0.45, "z": -2},
            "end": {"x": 0.45, "z": -2},
        }],
    }
    item = {
        "instance_id": "chair-1",
        "furniture_id": "chair",
        "normalized_type": "dining-chair",
        "name_zh_raw": "餐椅",
        "size_cm": {"width": 50, "depth": 50, "height": 90},
        "position_cm": {"x": 0, "z": -160},
        "rotation_y_deg": 0,
        "placement_room_id": "room-a",
    }
    blocked = validate_single_placement(floorplan, item, [], keep_door_clear=True)
    assert blocked["ok"] is False
    assert "門口淨空" in str(blocked["reason"])

    legacy_cm = {
        **floorplan,
        "door_segments": [{
            "start": {"x": -45, "z": -200},
            "end": {"x": 45, "z": -200},
        }],
    }
    blocked_legacy = validate_single_placement(legacy_cm, item, [], keep_door_clear=True)
    assert blocked_legacy["ok"] is False
    assert "門口淨空" in str(blocked_legacy["reason"])

    fixed = generate_layout(
        400,
        400,
        [{
            **item,
            "position_cm": {"x": 500, "z": 500},
            "position_locked": True,
            "mobility": "fixed",
        }],
    )[0]
    assert fixed["position_cm"] == {"x": 500.0, "z": 500.0}
    assert fixed["placement_failed"] is True
    assert "固定家具" in fixed["placement_reason"]


def test_viewpoint_style_card_and_final_png_preserve_explicit_furniture(
    client: TestClient,
) -> None:
    import io

    from PIL import Image

    required = _model_item("coffee-table")
    project = _project_at_layout(client, str(required["furniture_id"]))
    proposal = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/analyze",
        json={"expected_revision": project["revision"]},
    ).json()["proposal"]
    layout_response = client.post(
        f"/api/projects/{project['project_id']}/layout-2d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "proposal_source": proposal["source"],
            "openrouter": proposal["openrouter"],
            "scene_objects": proposal["scene_objects"],
        },
    ).json()
    project = layout_response["project"]
    original = layout_response["layout"]["scene_objects"]
    required_object = next(item for item in original if item["furniture_id"] == required["furniture_id"])

    white = client.post(
        f"/api/projects/{project['project_id']}/white-model-3d/confirm",
        json={
            "expected_revision": project["revision"],
            "user_reviewed": True,
            "renderer": "neutral_geometry",
            "visible_instance_ids": [item["instance_id"] for item in original],
        },
    ).json()
    viewpoint = client.post(
        f"/api/projects/{project['project_id']}/viewpoint/confirm",
        json={
            "expected_revision": white["project"]["revision"],
            "user_reviewed": True,
            "projection": "perspective",
            "position_cm": {"x": 800, "y": 900, "z": 1100},
            "target_cm": {"x": 0, "y": 100, "z": 0},
            "fov_deg": 45,
        },
    )
    assert viewpoint.status_code == 200, viewpoint.text
    project = viewpoint.json()["project"]
    assert project["current_step"] == "style_render"
    assert viewpoint.json()["viewpoint"]["units"] == "cm"

    styled = client.post(
        f"/api/projects/{project['project_id']}/style-card/apply",
        json={"expected_revision": project["revision"], "card_id": "industrial_1"},
    )
    assert styled.status_code == 200, styled.text
    style_payload = styled.json()["style_render"]
    styled_required = next(
        item for item in style_payload["scene_objects"]
        if item["instance_id"] == required_object["instance_id"]
    )
    assert styled_required["furniture_id"] == required_object["furniture_id"]
    assert styled_required["position_cm"] == required_object["position_cm"]
    assert required_object["instance_id"] in style_payload["protected_instance_ids"]
    unprotected_ids = {
        item["instance_id"] for item in original if item["selection_source"] != "user"
    }
    assert all(change["instance_id"] in unprotected_ids for change in style_payload["replacements"])
    assert style_payload["furniture_policy"]["placement_authority"] == "roompilot.engine"

    png = io.BytesIO()
    Image.new("RGB", (16, 12), "#ccbbaa").save(png, format="PNG")
    project = styled.json()["project"]
    rendered = client.post(
        f"/api/projects/{project['project_id']}/renders",
        data={"expected_revision": project["revision"], "provider": "browser_capture"},
        files={"file": ("final.png", png.getvalue(), "image/png")},
    )
    assert rendered.status_code == 201, rendered.text
    render = rendered.json()["render"]
    assert render["style_card_id"] == "industrial_1"
    downloaded = client.get(render["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content == png.getvalue()
    history = client.get(f"/api/projects/{project['project_id']}/renders").json()["renders"]
    assert [item["render_id"] for item in history] == [render["render_id"]]

    restyled = client.post(
        f"/api/projects/{project['project_id']}/style-card/apply",
        json={
            "expected_revision": rendered.json()["project"]["revision"],
            "card_id": "american_1",
        },
    )
    assert restyled.status_code == 200, restyled.text
    protected_again = next(
        item for item in restyled.json()["style_render"]["scene_objects"]
        if item["instance_id"] == required_object["instance_id"]
    )
    assert protected_again["furniture_id"] == required_object["furniture_id"]
    assert client.get(f"/api/projects/{project['project_id']}/renders").json()["renders"][0]["render_id"] == render["render_id"]


def test_style_card_requires_a_locked_viewpoint(
    client: TestClient,
) -> None:
    project = _project_at_layout(client)
    blocked = client.post(
        f"/api/projects/{project['project_id']}/style-card/apply",
        json={"expected_revision": project["revision"], "card_id": "cream_1"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "viewpoint_required"
