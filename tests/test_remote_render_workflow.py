from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server.project_store import ProjectStore
from backend.server.render_service import _render_timeout_seconds, prepare_render_payload


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


def test_render_payload_keeps_design_needs_but_removes_identity_fields() -> None:
    prepared = prepare_render_payload(_payload("project-1"))

    assert "name" not in prepared["requirements"]["basic"]
    assert "fullName" not in prepared["requirements"]["basic"]
    assert "phone" not in prepared["requirements"]["basic"]
    assert prepared["requirements"]["basic"]["household"] == "two adults and one child"
    bedroom = prepared["requirements"]["rooms"]["bedroom-1"]
    assert bedroom["personalNeeds"] == "quiet reading corner and soft lighting"
    assert "address" not in bedroom


def test_render_payload_removes_identity_fields_from_agent_handoff() -> None:
    payload = _payload("project-1")
    payload["agent_generation_handoff"] = {
        "global_profile": {"name": "Ada", "household_size": "2"},
        "rooms": [{"room_id": "bedroom-1", "furniture_preference": {"description": "light wood"}}],
    }

    prepared = prepare_render_payload(payload)

    assert "name" not in prepared["agent_generation_handoff"]["global_profile"]
    assert prepared["agent_generation_handoff"]["rooms"][0]["room_id"] == "bedroom-1"


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


def test_room_render_camera_uses_world_z_against_centered_scene_region() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["scene"]["floorplan"] = {
        "coordinate_unit": "cm",
        "width_cm": 200,
        "depth_cm": 300,
        "room_regions": [{
            "room_id": "bedroom-1",
            "exterior": [[-100, 50], [100, 50], [100, 150], [-100, 150]],
        }],
    }
    payload["room_views"] = [{
        "room_id": "bedroom-1",
        "camera": {
            "position_cm": [60, 145, -70],
            "target_cm": [0, 82, -100],
            "fov_deg": 58,
        },
    }]

    prepared = prepare_render_payload(payload)

    assert prepared["room_views"][0]["camera"]["target_cm"][2] == -100


def test_room_render_rejects_camera_outside_matching_room_region() -> None:
    payload = _payload("project-1")
    payload["mode"] = "room_final"
    payload["scene"]["floorplan"] = {
        "coordinate_unit": "cm",
        "room_regions": [{
            "room_id": "bedroom-1",
            "exterior": [[-100, -100], [100, -100], [100, 100], [-100, 100]],
        }],
    }
    payload["room_views"] = [{
        "room_id": "bedroom-1",
        "camera": {
            "position_cm": [180, 145, 0],
            "target_cm": [0, 82, 0],
            "fov_deg": 58,
        },
    }]

    with pytest.raises(ValueError, match="room_view_camera_outside_room"):
        prepare_render_payload(payload)


def test_invalid_remote_renderer_timeout_uses_safe_default(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS", "not-a-number")

    assert _render_timeout_seconds() == 60.0


def test_unconfigured_remote_renderer_reports_explicit_503(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    # 2026-07-30 起「未設定」的定義擴大：自訂遠端 URL 與內建生圖金鑰
    # （OPENROUTER_API_KEY，見 render_providers.py）都不存在才回 503。
    # 開發機 .env 常備有真實金鑰，這裡必須顯式清掉。
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
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


def test_scene_contains_review_then_room_render_controls() -> None:
    html = (main.STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (main.STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (main.STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert html.index('id="proposal-review-summary"') < html.index('id="lock-master-view"')
    assert 'data-panel="proposal-review"' in html
    assert 'data-panel="ai-render"' in html
    assert 'id="request-palette-renders"' in html
    # 視角編輯收斂到第 7 步；第 8 步只留「回第 7 步調整」與批次送出。
    assert 'id="save-room-view"' not in html
    assert 'id="adjust-room-views"' in html
    assert 'id="submit-room-renders"' in html
    assert "function lockMasterRenderView()" in controller
    assert "function roomCameraSuggestion(room)" in controller
    assert "function getCameraState()" in viewer
    assert "function setCameraState(snapshot = {})" in viewer
