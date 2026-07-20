from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from roompilot.server.main import app
from roompilot.server.project_store import ProjectConflictError, ProjectStore


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROOMPILOT_RUNTIME_DIR", str(tmp_path / "runtime"))
    with TestClient(app) as test_client:
        yield test_client


def _create_project(client: TestClient, name: str = "王小姐住宅案") -> dict:
    response = client.post(
        "/api/projects",
        json={"name": name, "notes": "三房兩廳"},
    )
    assert response.status_code == 201
    return response.json()["project"]


def test_scene_route_delivers_the_single_built_react_workflow(client: TestClient) -> None:
    response = client.get("/scene")

    assert response.status_code == 200
    assert "RoomPilot Studio｜AI 室內配置與 3D 提案" in response.text
    assert '/static/frontend3d/assets/' in response.text


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


def test_project_is_created_at_upload_step_and_can_be_loaded(client: TestClient) -> None:
    project = _create_project(client)

    assert len(project["project_id"]) == 32
    assert project["current_step"] == "upload"
    assert project["revision"] == 0
    assert project["workflow"] == {
        "schema_version": 1,
        "completed": ["project"],
        "data": {"project": {"name": "王小姐住宅案"}},
    }

    loaded = client.get(f"/api/projects/{project['project_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["project"] == project


def test_blank_project_name_returns_actionable_error(client: TestClient) -> None:
    response = client.post("/api/projects", json={"name": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "project_name_required",
        "message": "請輸入專案名稱。",
        "focus": "project-name",
    }


def test_project_input_limits_and_unknown_fields_are_rejected(client: TestClient) -> None:
    too_long = client.post("/api/projects", json={"name": "專" * 121})
    unknown = client.post("/api/projects", json={"name": "住宅案", "owner": "x"})

    assert too_long.status_code == 422
    assert unknown.status_code == 422


def test_missing_project_has_stable_error_contract(client: TestClient) -> None:
    response = client.get("/api/projects/not-found")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "project_not_found"


def test_workflow_update_uses_optimistic_revision(client: TestClient) -> None:
    project = _create_project(client)
    project_id = project["project_id"]
    update = {
        "expected_revision": project["revision"],
        "current_step": "upload",
        "workflow": {
            "frontend3d": {
                "schemaVersion": 1,
                "source": {"kind": "sample", "planName": "floor21.dxf"},
            }
        },
    }

    saved = client.put(f"/api/projects/{project_id}/workflow", json=update)
    assert saved.status_code == 200
    assert saved.json()["project"]["revision"] == 1
    assert saved.json()["project"]["workflow"]["frontend3d"]["source"]["planName"] == "floor21.dxf"

    conflict = client.put(f"/api/projects/{project_id}/workflow", json=update)
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["code"] == "project_revision_conflict"
    assert detail["project"]["revision"] == 1


def test_floorplan_upload_is_stored_and_increments_revision(client: TestClient) -> None:
    project = _create_project(client)
    project_id = project["project_id"]

    rejected = client.post(
        f"/api/projects/{project_id}/floorplan",
        data={"expected_revision": project["revision"]},
        files={"file": ("plan.pdf", b"%PDF", "application/pdf")},
    )
    assert rejected.status_code == 415
    assert rejected.json()["detail"]["code"] == "unsupported_floorplan_type"

    accepted = client.post(
        f"/api/projects/{project_id}/floorplan",
        data={"expected_revision": project["revision"]},
        files={"file": ("plan.dxf", b"0\nSECTION\n0\nEOF\n", "application/dxf")},
    )
    assert accepted.status_code == 201
    assert accepted.json()["project"]["revision"] == 1
    assert accepted.json()["upload"]["filename"] == "plan.dxf"

    source = client.get(accepted.json()["upload"]["source_url"])
    assert source.status_code == 200
    assert source.content == b"0\nSECTION\n0\nEOF\n"

    conflict = client.post(
        f"/api/projects/{project_id}/floorplan",
        data={"expected_revision": project["revision"]},
        files={"file": ("new-plan.dxf", b"new", "application/dxf")},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "project_revision_conflict"
    assert client.get(accepted.json()["upload"]["source_url"]).content == source.content


def test_project_floorplan_analysis_persists_canonical_result_without_large_blobs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roompilot.server import main as server_main

    project = _create_project(client, "PNG 辨識案")
    uploaded = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        data={"expected_revision": project["revision"]},
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    uploaded_project = uploaded.json()["project"]

    analysis = {
        "source": "image",
        "floorplan": {
            "source": "recognized-image",
            "scale_m": 6.3,
            "stats": {"width_m": 6.3, "depth_m": 4.2},
            "wall_segments": [],
            "wall_polys": [],
            "windows": [],
            "doors": [],
        },
        "dxf_text": "0\nSECTION\n0\nEOF\n",
        "scale": {"confidence": "high"},
        "preview_png_base64": "large-preview-must-not-be-persisted",
        "vlm": None,
    }
    monkeypatch.setattr(
        server_main,
        "_recognize_floorplan_bytes",
        lambda *_args, **_kwargs: analysis,
    )

    analyzed = client.post(
        f"/api/projects/{project['project_id']}/floorplan/analyze",
        json={
            "expected_revision": uploaded_project["revision"],
            "scale_m": None,
            "thickness": 0.18,
            "height": 2.7,
        },
    )
    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["analysis"]["dxf_text"].startswith("0\nSECTION")
    assert payload["project"]["current_step"] == "recognition"
    assert payload["project"]["revision"] == 2
    assert payload["project"]["workflow"]["completed"] == [
        "project",
        "upload",
        "recognition",
    ]
    persisted = payload["project"]["workflow"]["data"]["recognition"]
    assert persisted["filename"] == "plan.png"
    assert persisted["floorplan"]["scale_m"] == 6.3
    assert "dxf_text" not in persisted
    assert "preview_png_base64" not in persisted

    stale = client.post(
        f"/api/projects/{project['project_id']}/floorplan/analyze",
        json={"expected_revision": uploaded_project["revision"]},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "project_revision_conflict"

    replacement = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        data={"expected_revision": payload["project"]["revision"]},
        files={"file": ("replacement.png", _png_bytes(), "image/png")},
    )
    assert replacement.status_code == 201
    replaced_project = replacement.json()["project"]
    assert replaced_project["current_step"] == "upload"
    assert replaced_project["workflow"]["completed"] == ["project", "upload"]
    assert "recognition" not in replaced_project["workflow"]["data"]


def test_project_dxf_analysis_uses_the_real_roompilot_parser(client: TestClient) -> None:
    sample = (
        Path(__file__).resolve().parents[1]
        / "testdata"
        / "pic"
        / "temp"
        / "01-HomePlanCadBlock.dxf"
    )
    project = _create_project(client, "DXF 真實解析案")
    uploaded = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        data={"expected_revision": project["revision"]},
        files={"file": (sample.name, sample.read_bytes(), "application/dxf")},
    )
    assert uploaded.status_code == 201

    analyzed = client.post(
        f"/api/projects/{project['project_id']}/floorplan/analyze",
        json={"expected_revision": uploaded.json()["project"]["revision"]},
    )

    assert analyzed.status_code == 200
    analysis = analyzed.json()["analysis"]
    assert analysis["source"] == "dxf"
    assert analysis["dxf_text"]
    assert analysis["floorplan"]["wall_segments"]
    assert analysis["floorplan"]["stats"]["width_m"] > 0
    assert analysis["floorplan"]["room_regions"]
    assert analysis["openrouter"]["sent"] is False


def test_space_confirmation_persists_only_user_confirmed_geometry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roompilot.server import main as server_main

    project = _create_project(client, "空間確認案")
    uploaded = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        data={"expected_revision": 0},
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    ).json()["project"]
    room = {
        "room_id": "room-a",
        "exterior": [[-3, -2], [3, -2], [3, 2], [-3, 2], [-3, -2]],
        "holes": [],
        "area_m2": 24,
        "centroid": {"x": 0, "z": 0},
        "room_type": "living_room",
        "label": "LIVING",
        "label_zh": "客廳",
        "kind": "living",
        "label_source": "ai_suggestion",
        "confidence": 0.82,
        "confirmed": False,
    }
    analysis = {
        "source": "image",
        "floorplan": {
            "scale_m": 6.0,
            "wall_thickness": 0.18,
            "wall_height": 2.7,
            "bbox": {"minx": -3, "minz": -2, "maxx": 3, "maxz": 2},
            "wall_polys": [],
            # dxf_parser 歷史格式：client wall segments 是公分，但 bbox 是公尺。
            "wall_segments": [{
                "start": {"x": -300, "z": 0},
                "end": {"x": 300, "z": 0},
            }],
            "room_regions": [room],
            "doors": [],
            "windows": [],
            "stats": {"rooms": 1, "doors": 0, "windows": 0},
        },
        "dxf_text": "0\nEOF\n",
        "scale": {"confidence": "high"},
        "vlm": {"model": "vision-model"},
        "openrouter": {
            "provider": "openrouter",
            "requested": True,
            "sent": True,
            "status": "suggested",
            "model": "vision-model",
        },
    }
    received = {}

    def recognize(*_args, **kwargs):
        received.update(kwargs)
        return analysis

    monkeypatch.setattr(server_main, "_recognize_floorplan_bytes", recognize)
    analyzed_response = client.post(
        f"/api/projects/{project['project_id']}/floorplan/analyze",
        json={"expected_revision": uploaded["revision"], "allow_openrouter": True},
    )
    assert analyzed_response.status_code == 200
    analyzed = analyzed_response.json()["project"]
    assert received["allow_openrouter"] is True

    blocked_before_calibration = client.post(
        f"/api/projects/{project['project_id']}/floorplan/confirm",
        json={
            "expected_revision": analyzed["revision"],
            "rooms": [{"room_id": "room-a", "room_type": "bedroom"}],
        },
    )
    assert blocked_before_calibration.status_code == 409
    assert blocked_before_calibration.json()["detail"]["code"] == "calibration_required"

    rejected_off_wall = client.post(
        f"/api/projects/{project['project_id']}/floorplan/calibrate",
        json={
            "expected_revision": analyzed["revision"],
            "reference_cm": {
                "x1_cm": -100,
                "z1_cm": 50,
                "x2_cm": 100,
                "z2_cm": 50,
            },
            "actual_length_cm": 400,
        },
    )
    assert rejected_off_wall.status_code == 422
    assert rejected_off_wall.json()["detail"]["code"] == "calibration_reference_not_on_wall"

    calibrated_response = client.post(
        f"/api/projects/{project['project_id']}/floorplan/calibrate",
        json={
            "expected_revision": analyzed["revision"],
            "reference_cm": {
                "x1_cm": -100,
                "z1_cm": 0,
                "x2_cm": 100,
                "z2_cm": 0,
            },
            "actual_length_cm": 400,
        },
    )
    assert calibrated_response.status_code == 200
    calibrated = calibrated_response.json()
    analyzed = calibrated["project"]
    assert calibrated["calibration"]["scale_cm"] == 1200
    assert calibrated["calibration"]["measured_length_before_cm"] == 200
    assert calibrated["calibration"]["reference_cm"]["x1_cm"] == -100
    assert calibrated["calibration"]["scale_factor"] == 2
    assert analyzed["workflow"]["data"]["calibration"]["scale_m"] is None
    assert received["allow_openrouter"] is False
    assert analyzed["workflow"]["completed"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
    ]

    confirmed_response = client.post(
        f"/api/projects/{project['project_id']}/floorplan/confirm",
        json={
            "expected_revision": analyzed["revision"],
            "rooms": [{"room_id": "room-a", "room_type": "bedroom"}],
            "doors": [{"x1": -1, "z1": -2, "x2": -0.1, "z2": -2}],
            "windows": [{"x1": 1, "z1": 2, "x2": 2, "z2": 2}],
        },
    )

    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()
    final_room = confirmed["confirmation"]["floorplan"]["room_regions"][0]
    assert final_room["room_type"] == "bedroom"
    assert final_room["confirmed"] is True
    assert final_room["label_source"] == "user_confirmation"
    assert final_room["suggested_room_type"] == "living_room"
    assert confirmed["project"]["workflow"]["data"]["recognition"]["floorplan"]["room_regions"][0]["confirmed"] is False
    assert confirmed["project"]["workflow"]["data"]["space_confirmation"]["floorplan"]["doors"][0]["x1"] == -1
    assert "space_confirmation" in confirmed["project"]["workflow"]["completed"]

    stale = client.post(
        f"/api/projects/{project['project_id']}/floorplan/confirm",
        json={
            "expected_revision": analyzed["revision"],
            "rooms": [{"room_id": "room-a", "room_type": "bedroom"}],
        },
    )
    assert stale.status_code == 409


def test_space_confirmation_rejects_unknown_rooms_and_out_of_bounds_segments(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roompilot.server import main as server_main

    project = _create_project(client, "錯誤確認案")
    uploaded = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        data={"expected_revision": 0},
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    ).json()["project"]
    monkeypatch.setattr(
        server_main,
        "_recognize_floorplan_bytes",
        lambda *_args, **_kwargs: {
            "source": "image",
            "floorplan": {
                "scale_m": 4,
                "wall_thickness": 0.18,
                "wall_height": 2.7,
                "bbox": {"minx": -2, "minz": -2, "maxx": 2, "maxz": 2},
                "wall_segments": [{"x1": -2, "z1": 0, "x2": 2, "z2": 0}],
                "room_regions": [{"room_id": "room-a", "exterior": [[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]], "holes": [], "room_type": "other"}],
                "doors": [],
                "windows": [],
            },
            "openrouter": {"requested": False, "sent": False},
        },
    )
    analyzed = client.post(
        f"/api/projects/{project['project_id']}/floorplan/analyze",
        json={"expected_revision": uploaded["revision"]},
    ).json()["project"]

    calibrated = client.post(
        f"/api/projects/{project['project_id']}/floorplan/calibrate",
        json={
            "expected_revision": analyzed["revision"],
            "reference_cm": {
                "x1_cm": -100,
                "z1_cm": 0,
                "x2_cm": 100,
                "z2_cm": 0,
            },
            "actual_length_cm": 200,
        },
    ).json()["project"]
    analyzed = calibrated

    unknown = client.post(
        f"/api/projects/{project['project_id']}/floorplan/confirm",
        json={
            "expected_revision": analyzed["revision"],
            "rooms": [{"room_id": "room-other", "room_type": "other"}],
        },
    )
    outside = client.post(
        f"/api/projects/{project['project_id']}/floorplan/confirm",
        json={
            "expected_revision": analyzed["revision"],
            "rooms": [{"room_id": "room-a", "room_type": "other"}],
            "doors": [{"x1": 20, "z1": 20, "x2": 21, "z2": 20}],
        },
    )

    assert unknown.status_code == 422
    assert outside.status_code == 422


def test_store_persists_across_instances_and_compacts_bad_labels(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    first = ProjectStore(runtime)
    project = first.create_project(name="續作驗收")
    saved = first.update_workflow(
        project["project_id"],
        expected_revision=0,
        workflow={
            "frontend3d": {
                "furnitureItems": [
                    {
                        "furniture_id": "bed-1",
                        "normalized_type": "bed",
                        "name_zh_raw": "Ã" * 10_000,
                    }
                ]
            }
        },
    )

    restored = ProjectStore(runtime).get_project(project["project_id"])
    item = restored["workflow"]["frontend3d"]["furnitureItems"][0]
    assert restored == saved
    assert item["name_zh_raw"] == "bed"


def test_store_rejects_stale_revision_without_overwriting(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "runtime")
    project = store.create_project(name="並行驗收")
    store.update_workflow(
        project["project_id"],
        expected_revision=0,
        workflow={"tab": {"value": "new"}},
    )

    with pytest.raises(ProjectConflictError):
        store.update_workflow(
            project["project_id"],
            expected_revision=0,
            workflow={"tab": {"value": "stale"}},
        )
    assert store.get_project(project["project_id"])["workflow"]["tab"]["value"] == "new"
