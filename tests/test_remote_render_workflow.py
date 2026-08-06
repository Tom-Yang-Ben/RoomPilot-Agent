from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server.project_store import ProjectStore
from backend.server import render_service
from backend.server.render_service import (
    RenderProviderRejected,
    _render_timeout_seconds,
    prepare_render_payload,
)


def _camera() -> dict:
    return {
        "position_cm": [420, 165, 380],
        "target_cm": [210, 120, 190],
        "fov_deg": 52,
    }


def _payload(project_id: str) -> dict:
    return {
        "schema_version": "1.0",
        "mode": "palette_comparison",
        "project_id": project_id,
        "scene_version": "scene-1:revision-3:card-1",
        "style_card_ids": ["card-1", "card-2"],
        "scene": {"scene_id": "scene-1", "scene_objects": []},
        "locks": {"furniture": True, "structure": True, "surfaces": True},
        "requirements": {
            "basic": {
                "name": "Ada",
                "fullName": "Ada Lovelace",
                "phone": "0900000000",
                "household": "two adults and one child",
            },
            "rooms": {
                "bedroom-1": {
                    "personalNeeds": "quiet reading corner and soft lighting",
                    "address": "No. 1 Test Road",
                }
            },
        },
        "master_view": {"camera": _camera()},
        "room_views": [],
        "reference_png_data_url": "data:image/png;base64,AA==",
    }


def _configuration_snapshot(*room_ids: str) -> dict:
    return {
        "schema_version": 2,
        "snapshot_id": "project-1:scene-1:1",
        "scene_version": "scene-1:revision-3:card-1",
        "fixed_structure": {
            "walls": [],
            "doors": [],
            "windows": [],
            "beams": [],
            "columns": [],
        },
        "rooms": [{"room_id": room_id} for room_id in room_ids],
        "furniture": [],
    }


def test_render_payload_keeps_design_needs_but_removes_identity_fields() -> None:
    payload = _payload("project-1")
    payload["render_brief"] = {
        "user_notes": "Keep a warm reading corner.",
        "phone": "0900000000",
    }
    prepared = prepare_render_payload(payload)

    assert "name" not in prepared["requirements"]["basic"]
    assert "fullName" not in prepared["requirements"]["basic"]
    assert "phone" not in prepared["requirements"]["basic"]
    assert prepared["requirements"]["basic"]["household"] == "two adults and one child"
    bedroom = prepared["requirements"]["rooms"]["bedroom-1"]
    assert bedroom["personalNeeds"] == "quiet reading corner and soft lighting"
    assert "address" not in bedroom
    assert prepared["render_brief"]["user_notes"] == "Keep a warm reading corner."
    assert "phone" not in prepared["render_brief"]


def test_render_payload_removes_identity_fields_from_agent_handoff() -> None:
    payload = _payload("project-1")
    payload["agent_generation_handoff"] = {
        "global_profile": {"name": "Ada", "household_size": "2"},
        "rooms": [{"room_id": "bedroom-1", "furniture_preference": {"description": "light wood"}}],
    }

    prepared = prepare_render_payload(payload)

    assert "name" not in prepared["agent_generation_handoff"]["global_profile"]
    assert prepared["agent_generation_handoff"]["rooms"][0]["room_id"] == "bedroom-1"


def test_render_payload_keeps_step_eight_revision_metadata() -> None:
    payload = _payload("project-1")
    payload["render_brief"] = {
        "mode": "room_final",
        "render_action": "revision",
        "room_id": "bedroom-1",
        "prompt_keywords": ["warm wood", "soft lighting"],
        "user_notes": "Make this image brighter.",
    }

    prepared = prepare_render_payload(payload)

    assert prepared["render_brief"]["render_action"] == "revision"
    assert prepared["render_brief"]["prompt_keywords"] == ["warm wood", "soft lighting"]


def test_room_render_requires_each_room_view_to_have_a_locked_camera() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["room_views"] = [{"room_id": "bedroom-1", "camera": {"position_cm": [1, 2]}}]

    with pytest.raises(ValueError, match="room_view_camera_required"):
        prepare_render_payload(payload)


def test_room_render_accepts_locked_room_view_cameras() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["room_views"] = [{"room_id": "bedroom-1", "camera": _camera()}]

    prepared = prepare_render_payload(payload)

    assert prepared["room_views"][0]["room_id"] == "bedroom-1"


def test_room_render_accepts_one_confirmed_room_from_a_multi_room_snapshot() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["configuration_snapshot"] = _configuration_snapshot("bedroom-1", "living-1")
    payload["room_views"] = [{"room_id": "bedroom-1", "camera": _camera()}]

    prepared = prepare_render_payload(payload)

    assert [view["room_id"] for view in prepared["room_views"]] == ["bedroom-1"]


def test_room_render_rejects_a_room_missing_from_the_configuration_snapshot() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["configuration_snapshot"] = _configuration_snapshot("bedroom-1")
    payload["room_views"] = [{"room_id": "unknown-room", "camera": _camera()}]

    with pytest.raises(ValueError, match="room_views_unknown_room"):
        prepare_render_payload(payload)


def test_room_render_accepts_complete_version_two_configuration_snapshot() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["configuration_snapshot"] = _configuration_snapshot("bedroom-1")
    payload["room_views"] = [{"room_id": "bedroom-1", "camera": _camera()}]

    prepared = prepare_render_payload(payload)

    assert prepared["configuration_snapshot"]["schema_version"] == 2


def test_room_render_rejects_a_snapshot_from_an_older_scene_version() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["configuration_snapshot"] = _configuration_snapshot("bedroom-1")
    payload["configuration_snapshot"]["scene_version"] = "scene-older"
    payload["room_views"] = [{"room_id": "bedroom-1", "camera": _camera()}]

    with pytest.raises(ValueError, match="configuration_snapshot_scene_version_mismatch"):
        prepare_render_payload(payload)


def test_invalid_remote_renderer_timeout_uses_safe_default(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS", "not-a-number")

    assert _render_timeout_seconds() == 300.0


def test_unconfigured_remote_renderer_reports_explicit_503(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.setattr(render_service, "_first_nonempty_local_env_value", lambda _name: "")
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "Render test"}).json()["project"]

    status = client.get("/api/render-provider/status")
    submitted = client.post(
        f"/api/projects/{project['project_id']}/render-jobs",
        json=_payload(project["project_id"]),
    )

    assert status.status_code == 200
    assert status.json()["configured"] is False
    assert submitted.status_code == 503
    assert submitted.json()["detail"]["code"] == "render_provider_not_configured"


def test_design_delivery_package_returns_room_presentation_and_budget(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "Delivery test"}).json()["project"]

    submitted = client.post(
        f"/api/projects/{project['project_id']}/design-delivery",
        json={
            "style_card": {"id": "warm-wood", "name": "Warm wood"},
            "configuration_snapshot": {
                "snapshot_id": "snap-1",
                "furniture": [
                    {
                        "instance_id": "sofa-1",
                        "name": "沙發",
                        "room_id": "living-1",
                        "price_twd": 12800,
                        "material": "布料",
                    },
                    {"instance_id": "table-1", "name": "邊桌", "room_id": "living-1"},
                ],
            },
            "rooms": [
                {
                    "room_id": "living-1",
                    "room_name": "Living Room",
                    "questionnaire": {
                        "note": "quiet reading and warm light",
                        "lockedFurniture": ["Sofa"],
                    },
                    "render": {
                        "submitted_at": "2026-08-06T00:00:00Z",
                        "revision_submitted_at": "2026-08-06T01:00:00Z",
                    },
                }
            ],
        },
    )

    assert submitted.status_code == 200
    delivery = submitted.json()
    assert delivery["presentation"]["rooms"][0]["room_id"] == "living-1"
    assert delivery["presentation"]["title"] == "RoomPilot 全屋設計與裝潢簡報"
    assert "Ilse Crawford" in delivery["presentation"]["rooms"][0]["designer_reference"]
    assert delivery["engineering_report"]["completion"]["rendered_room_count"] == 1
    assert delivery["security_review"]["status"] == "passed"
    furniture_lines = [
        line for line in delivery["budget"]["lines"] if line["category"] == "furniture"
    ]
    assert {line["status"] for line in furniture_lines} == {"catalog_reference", "pending_quote"}
    assert delivery["budget_report"]["known_furniture_reference_subtotal_twd"] == 12800
    assert delivery["budget_report"]["pending_quote_count"] >= 1
    assert "正式報價" in delivery["budget_report"]["disclaimer"]


def test_design_delivery_redacts_sensitive_payload_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "Security delivery"}).json()["project"]

    submitted = client.post(
        f"/api/projects/{project['project_id']}/design-delivery",
        json={
            "style_card": {"id": "warm", "api_key": "style-secret"},
            "configuration_snapshot": {"snapshot_id": "secure-snapshot", "furniture": []},
            "rooms": [
                {
                    "room_id": "room-1",
                    "room_name": "客廳",
                    "questionnaire": {"note": "三代同堂"},
                    "render": {"submitted_at": "2026-08-06T00:00:00Z", "access_token": "render-secret"},
                }
            ],
        },
    )

    assert submitted.status_code == 200
    delivery = submitted.json()
    assert delivery["security_review"]["status"] == "passed_with_redactions"
    assert "$payload.style_card.api_key" in delivery["security_review"]["redacted_paths"]
    assert "$payload.rooms[0].render.access_token" in delivery["security_review"]["redacted_paths"]
    assert "style-secret" not in submitted.text
    assert "render-secret" not in submitted.text


@pytest.mark.parametrize(
    ("provider_status", "expected_text"),
    [
        (401, "金鑰驗證失敗"),
        (402, "額度不足"),
        (403, "模型權限"),
        (429, "呼叫上限"),
    ],
)
def test_render_provider_rejections_return_safe_traditional_chinese_messages(
    tmp_path,
    monkeypatch,
    provider_status: int,
    expected_text: str,
) -> None:
    async def reject_render(_payload: dict) -> dict:
        raise RenderProviderRejected(f"render_provider_http_{provider_status}")

    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    monkeypatch.setattr(main, "submit_render_jobs", reject_render)
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "Render test"}).json()["project"]

    submitted = client.post(
        f"/api/projects/{project['project_id']}/render-jobs",
        json=_payload(project["project_id"]),
    )

    detail = submitted.json()["detail"]
    assert submitted.status_code == 502
    assert detail["code"] == f"render_provider_http_{provider_status}"
    assert expected_text in detail["message"]
    assert "sk-" not in detail["message"]


def test_scene_contains_review_then_room_render_controls() -> None:
    html = (main.STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (main.STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (main.STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert html.index('id="proposal-review-summary"') < html.index('id="lock-master-view"')
    assert 'data-panel="proposal-review"' in html
    assert 'data-panel="ai-render"' in html
    assert 'id="request-palette-renders"' in html
    assert 'id="save-room-view"' in html
    assert 'id="submit-room-renders"' in html
    assert "function lockMasterRenderView()" in controller
    assert "function roomCameraSuggestion(room)" in controller
    assert "function getCameraState()" in viewer
    assert "function setCameraState(snapshot = {})" in viewer


def test_step_eight_allows_one_post_render_revision_and_delivery_package() -> None:
    controller = (main.STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'render_action: action' in controller
    assert 'openRenderBriefDialog("room_final", "revision")' in controller
    assert 'revision_submitted_at' in controller
    assert '/ai-renders' in controller
    assert 'revision_image_data_url' in controller
    assert '/design-delivery' in controller
    assert 'prompt_keywords' in controller
