from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from roompilot.server.main import app
from roompilot.server.project_store import ProjectStore
from roompilot.server.runtime_paths import legacy_runtime_dirs, project_runtime_dir


client = TestClient(app)


def _selection_candidate(fid: str, kind: str) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": kind,
        "variant_id": "standard",
        "name_zh_raw": fid,
        "size_cm": {"width": 120, "depth": 60, "height": 80},
    }


def test_agent_furniture_selection_falls_back_when_llm_violates_room_rules() -> None:
    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "living-1", "room_type": "living_room"}],
            "offers": {
                "living-1": [
                    _selection_candidate("sofa-1", "sofa"),
                    _selection_candidate("bed-1", "bed"),
                ]
            },
            "llm_selection": {
                "selections": [{"room_id": "living-1", "items": [{"furniture_id": "bed-1"}]}]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    assert payload["warnings"]
    assert [
        item["furniture_id"]
        for item in payload["rooms"][0]["items"]
    ] == ["sofa-1"]


def test_agent_furniture_selection_uses_server_side_local_rules_without_llm() -> None:
    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
            "offers": {
                "bedroom-1": [
                    _selection_candidate("bed-1", "bed"),
                    _selection_candidate("nightstand-1", "bedside-table"),
                    _selection_candidate("bed-2", "bed-frame"),
                ]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    assert [
        item["furniture_id"]
        for item in payload["rooms"][0]["items"]
    ] == ["bed-1", "nightstand-1"]


def test_worktree_uses_the_main_repository_runtime_directory(tmp_path: Path) -> None:
    repository = tmp_path / "RoomPilot-Agent"
    worktree = repository / ".worktrees" / "bella-test1"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text(
        f"gitdir: {(repository / '.git' / 'worktrees' / 'bella-test1').as_posix()}\n",
        encoding="utf-8",
    )

    assert project_runtime_dir(worktree) == repository / ".runtime"

    (worktree / ".runtime").mkdir()
    sibling_runtime = repository / ".worktrees" / "cody" / ".runtime"
    sibling_runtime.mkdir(parents=True)
    external_runtime = tmp_path / "external-worktree" / ".runtime"
    external_runtime.mkdir(parents=True)
    registration = repository / ".git" / "worktrees" / "external"
    registration.mkdir(parents=True)
    (registration / "gitdir").write_text(
        str(external_runtime.parent / ".git"),
        encoding="utf-8",
    )
    assert legacy_runtime_dirs(worktree) == [
        worktree / ".runtime",
        sibling_runtime,
        external_runtime,
    ]


def test_legacy_worktree_projects_are_migrated_with_their_uploads(tmp_path: Path) -> None:
    legacy = ProjectStore(tmp_path / "worktree-runtime")
    project = legacy.create_project(name="舊分支專案")
    legacy.update_workflow(
        project["project_id"],
        current_step="realistic_3d",
        workflow={"realistic_3d": {"activeStylePackId": "scandinavian-01"}},
    )
    legacy.save_upload(
        project["project_id"],
        filename="plan.png",
        extension=".png",
        mime_type="image/png",
        content=_png_bytes(),
    )

    shared = ProjectStore(tmp_path / "shared-runtime")
    assert shared.import_runtime(legacy.runtime_dir) == 1

    restored = ProjectStore(tmp_path / "shared-runtime")
    loaded = restored.get_project(project["project_id"])
    upload = restored.get_upload(project["project_id"])
    assert loaded["current_step"] == "realistic_3d"
    assert loaded["workflow"]["realistic_3d"]["activeStylePackId"] == "scandinavian-01"
    assert upload["path"].is_file()
    assert upload["path"].parent == restored.upload_dir / project["project_id"]

    legacy_upload = legacy.get_upload(project["project_id"])["path"]
    legacy_upload.unlink()
    legacy.update_workflow(
        project["project_id"],
        workflow={"realistic_3d": {"activeStylePackId": "scandinavian-02"}},
    )
    assert restored.import_runtime(legacy.runtime_dir) == 1
    assert restored.get_upload(project["project_id"])["path"].is_file()


def test_project_store_compacts_corrupted_furniture_labels(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "runtime")
    project = store.create_project(name="文字持久化驗收")

    saved = store.update_workflow(
        project["project_id"],
        workflow={
            "white_model_3d": {
                "sceneData": {
                    "scene_objects": [
                        {
                            "furniture_id": "bed-1",
                            "normalized_type": "bed",
                            "name_zh_raw": "Ã" * 10_000,
                        }
                    ]
                }
            }
        },
    )

    item = saved["workflow"]["white_model_3d"]["sceneData"]["scene_objects"][0]
    assert item["name_zh_raw"] == "bed"
    assert len(saved["workflow"]["white_model_3d"]["sceneData"]["scene_objects"][0]["name_zh_raw"]) < 512


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 16), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _create_project() -> dict:
    response = client.post(
        "/api/projects",
        json={"name": f"驗收專案-{uuid4().hex[:8]}", "notes": "九步流程測試"},
    )
    assert response.status_code == 201
    return response.json()["project"]


def test_project_is_created_and_can_be_loaded_again() -> None:
    project = _create_project()

    loaded = client.get(f"/api/projects/{project['project_id']}")

    assert loaded.status_code == 200
    assert loaded.json()["project"] == project
    assert project["current_step"] == "project"
    assert project["created_at"]
    assert project["updated_at"]


def test_pending_save_replay_rejects_a_stale_server_version_atomically() -> None:
    project = _create_project()
    project_id = project["project_id"]

    base = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {"space_confirmation": {"rooms": [{"id": "room-1"}]}},
        },
    ).json()["project"]
    advanced = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {"requirements": {"completed": True}},
        },
    )
    assert advanced.status_code == 200

    stale_replay = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {"space_confirmation": {"rooms": []}},
            "base_updated_at": base["updated_at"],
            "replay_pending": True,
        },
    )

    assert stale_replay.status_code == 409
    assert stale_replay.json()["detail"] == "project_version_conflict"
    restored = client.get(f"/api/projects/{project_id}").json()["project"]
    assert restored["current_step"] == "requirements"
    assert restored["workflow"]["space_confirmation"]["rooms"] == [{"id": "room-1"}]
    assert restored["workflow"]["requirements"]["completed"] is True

    matching_replay = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {"space_confirmation": {"rooms": [{"id": "room-2"}]}},
            "base_updated_at": advanced.json()["project"]["updated_at"],
            "replay_pending": True,
        },
    )
    assert matching_replay.status_code == 200
    assert matching_replay.json()["project"]["workflow"]["space_confirmation"]["rooms"] == [
        {"id": "room-2"}
    ]


def test_floorplan_upload_accepts_only_dxf_png_and_jpeg() -> None:
    project = _create_project()

    rejected = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert rejected.status_code == 415
    assert rejected.json()["detail"] == {
        "code": "unsupported_floorplan_type",
        "message": "只支援 DXF、PNG、JPG 或 JPEG 平面圖。",
        "allowed_extensions": [".dxf", ".png", ".jpg", ".jpeg"],
    }

    accepted = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    )

    assert accepted.status_code == 201
    upload = accepted.json()["upload"]
    assert upload["filename"] == "plan.png"
    assert upload["extension"] == ".png"
    assert upload["source_url"].endswith("/floorplan/source")

    source = client.get(upload["source_url"])
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("image/png")


def test_floorplan_analysis_explains_missing_consent_instead_of_stalling() -> None:
    project = _create_project()
    project_id = project["project_id"]
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201

    blocked = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == {
        "code": "floorplan_consent_required",
        "message": "請先同意本專案的平面圖分析條款，才能開始 AI 辨識。",
        "focus": "project-privacy-consent",
    }

    saved = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "upload",
            "workflow": {
                "privacy": {
                    "accepted": True,
                    "project_only": True,
                    "no_training": True,
                    "terms_version": "2026-07-17",
                }
            },
        },
    )
    assert saved.status_code == 200

    analyzed = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert analyzed.status_code == 200
    payload = analyzed.json()
    assert payload["geometry_engine"] == "cody"
    assert payload["analysis"]["recognition_engine"] == "cody"


def test_rerunning_floorplan_analysis_invalidates_stale_structure_confirmation() -> None:
    project = _create_project()
    project_id = project["project_id"]
    floor04 = Path(__file__).resolve().parents[1] / "testdata" / "png" / "floor04.png"
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": (floor04.name, floor04.read_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    consent = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "upload",
            "workflow": {
                "privacy": {
                    "accepted": True,
                    "project_only": True,
                    "no_training": True,
                }
            },
        },
    )
    assert consent.status_code == 200
    assert client.post(f"/api/projects/{project_id}/floorplan/analyze").status_code == 200
    stale = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {
                "recognition": {
                    "doors": [
                        {"id": "legacy-false-door-1"},
                        {"id": "legacy-false-door-2"},
                        {"id": "legacy-false-door-3"},
                    ]
                },
                "confirmed_floorplan": {"doors": [{"id": "old-door"}]},
                "space_confirmation": {"doors": [{"id": "old-door"}]},
                "requirements": {"rooms": [{"id": "old-room"}]},
            },
        },
    )
    assert stale.status_code == 200

    rerun = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert rerun.status_code == 200
    rerun_doors = rerun.json()["analysis"]["doors"]
    assert len(rerun_doors) == 5
    assert all(door["source"] == "cody_vision" for door in rerun_doors)
    assert not {door.get("id") for door in rerun_doors} & {
        "legacy-false-door-1",
        "legacy-false-door-2",
        "legacy-false-door-3",
    }
    restored = client.get(f"/api/projects/{project_id}").json()["project"]
    assert restored["current_step"] == "recognition"
    assert restored["workflow"]["confirmed_floorplan"] is None
    assert restored["workflow"]["space_confirmation"] is None
    assert restored["workflow"]["requirements"] is None


def test_dxf_analysis_returns_canonical_metre_geometry_and_room_regions() -> None:
    project = _create_project()
    project_id = project["project_id"]
    sample = next((Path(__file__).resolve().parents[1] / "testdata" / "dxf").glob("*.dxf"))
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": (sample.name, sample.read_bytes(), "application/dxf")},
    )
    assert uploaded.status_code == 201
    saved = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "upload",
            "workflow": {
                "privacy": {
                    "accepted": True,
                    "project_only": True,
                    "no_training": True,
                }
            },
        },
    )
    assert saved.status_code == 200

    analyzed = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert analyzed.status_code == 200
    payload = analyzed.json()
    floorplan = payload["analysis"]["floorplan"]
    assert payload["geometry_engine"] == "dxf"
    assert floorplan["source"] == "dxf"
    assert floorplan["wall_segments"]
    assert floorplan["room_regions"]
    points = [
        point
        for segment in floorplan["wall_segments"]
        for point in (segment["start"], segment["end"])
    ]
    assert max(abs(point["x"]) for point in points) <= floorplan["width_cm"] / 200 + 0.2
    assert max(abs(point["z"]) for point in points) <= floorplan["depth_cm"] / 200 + 0.2


def test_scene_generation_keeps_user_confirmed_furniture_when_glb_is_unavailable() -> None:
    response = client.post(
        "/api/scene/generate",
        json={
            "space_type": "bedroom",
            "style_preference": "scandinavian",
            "room_width_cm": 301,
            "room_depth_cm": 242,
            "required_furniture": ["bed"],
            "selected_furniture": [
                {
                    "furniture_id": "manual-bed-1",
                    "normalized_type": "bed",
                    "name_zh_raw": "使用者確認的雙人床",
                    "has_model": False,
                    "model_url": None,
                    "size_cm": {"width": 152, "depth": 200, "height": 55},
                    "position_cm": {"x": -50, "z": 0},
                    "rotation_y_deg": 0,
                    "position_locked": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_furniture"][0]["furniture_id"] == "manual-bed-1"
    assert payload["scene_objects"][0]["furniture_id"] == "manual-bed-1"
    assert payload["scene_objects"][0]["model_url"] is None
    assert payload["scene_objects"][0]["position_cm"] == {"x": -50, "z": 0}
    assert payload["scene_objects"][0]["position_locked"] is True


def test_scene_generation_uses_the_user_confirmed_floorplan_as_canonical_geometry() -> None:
    response = client.post(
        "/api/scene/generate",
        json={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "selected_furniture": [],
            "selected_furniture_exact": True,
            "floorplan_editor": {
                "width_cm": 600,
                "depth_cm": 400,
                "room_height_cm": 280,
                "rooms": [
                    {
                        "id": "living-1",
                        "label": "客廳",
                        "polygon_m": [
                            {"x": 0, "y": 0},
                            {"x": 6, "y": 0},
                            {"x": 6, "y": 4},
                            {"x": 0, "y": 4},
                        ],
                    }
                ],
                "structures": {
                    "walls": [
                        {
                            "id": "wall-1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 6, "y": 0},
                            "thickness_m": 0.18,
                        },
                        {
                            "id": "wall-2",
                            "start": {"x": 6, "y": 0},
                            "end": {"x": 6, "y": 4},
                            "thickness_m": 0.18,
                        },
                        {
                            "id": "wall-3",
                            "start": {"x": 6, "y": 4},
                            "end": {"x": 0, "y": 4},
                            "thickness_m": 0.18,
                        },
                        {
                            "id": "wall-4",
                            "start": {"x": 0, "y": 4},
                            "end": {"x": 0, "y": 0},
                            "thickness_m": 0.18,
                        },
                    ],
                    "doors": [
                        {
                            "id": "door-1",
                            "start": {"x": 2.4, "y": 0},
                            "end": {"x": 3.3, "y": 0},
                            "opening_direction": "left",
                        }
                    ],
                    "windows": [
                        {
                            "id": "window-1",
                            "start": {"x": 1, "y": 4},
                            "end": {"x": 2.2, "y": 4},
                        }
                    ],
                    "beams": [
                        {
                            "id": "beam-1",
                            "start": {"x": 0, "y": 2},
                            "end": {"x": 6, "y": 2},
                            "width_m": 0.3,
                            "height_m": 0.4,
                            "top_m": 2.8,
                        }
                    ],
                    "columns": [
                        {
                            "id": "column-1",
                            "center": {"x": 0.4, "y": 0.4},
                            "size_m": 0.58,
                            "depth_m": 0.35,
                            "height_m": 2.45,
                            "rotation_deg": 30,
                        }
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    floorplan = response.json()["floorplan"]
    assert floorplan["source"] == "user_confirmed"
    assert floorplan["width_cm"] == 600
    assert floorplan["depth_cm"] == 400
    assert floorplan["room_height_cm"] == 280
    assert floorplan["wall_segments"][0]["start"] == {"x": -3.0, "z": -2.0}
    assert floorplan["room_regions"][0]["room_id"] == "living-1"
    assert floorplan["room_regions"][0]["exterior"][2] == [3.0, 2.0]
    assert floorplan["beam_segments"][0]["top_m"] == 2.8
    assert floorplan["columns"][0]["center"] == {"x": -2.6, "z": -1.6}
    assert floorplan["columns"][0]["size_m"] == 0.58
    assert floorplan["columns"][0]["depth_m"] == 0.35
    assert floorplan["columns"][0]["height_m"] == 2.45
    assert floorplan["columns"][0]["rotation_deg"] == 30
    assert response.json()["scene_objects"] == []


def test_2d_layout_and_drag_validation_use_the_engine_with_editor_geometry() -> None:
    floorplan_editor = {
        "width_cm": 600,
        "depth_cm": 400,
        "rooms": [
            {
                "id": "living-1",
                "polygon_m": [
                    {"x": 0, "y": 0},
                    {"x": 6, "y": 0},
                    {"x": 6, "y": 4},
                    {"x": 0, "y": 4},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 6, "y": 0}},
                {"start": {"x": 6, "y": 0}, "end": {"x": 6, "y": 4}},
                {"start": {"x": 6, "y": 4}, "end": {"x": 0, "y": 4}},
                {"start": {"x": 0, "y": 4}, "end": {"x": 0, "y": 0}},
            ]
        },
    }
    furniture = {
        "furniture_id": "sofa-1",
        "normalized_type": "sofa",
        "name_zh_raw": "三人沙發",
        "size_cm": {"width": 210, "depth": 90, "height": 82},
        "position_locked": False,
    }

    layout = client.post(
        "/api/scene/layout",
        json={
            "floorplan_editor": floorplan_editor,
            "placement_room_id": "living-1",
            "scene_objects": [furniture],
        },
    )

    assert layout.status_code == 200
    placed = layout.json()["scene_objects"][0]
    assert placed["placement_failed"] is False
    assert placed["position_cm"] != {"x": 0.0, "z": 0.0}

    validation = client.post(
        "/api/scene/validate",
        json={
            "floorplan_editor": floorplan_editor,
            "item": {**placed, "position_locked": True},
            "others": [],
        },
    )

    assert validation.status_code == 200
    assert validation.json() == {"ok": True, "reason": None}
