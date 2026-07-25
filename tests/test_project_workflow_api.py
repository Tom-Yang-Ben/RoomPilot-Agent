from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.server.main import app
from backend.server.project_store import ProjectStore
from backend.server.runtime_paths import legacy_runtime_dirs, project_runtime_dir


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


def test_invited_questionnaire_gets_a_token_scoped_floorplan_locator() -> None:
    project = _create_project()
    project_id = project["project_id"]
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    prepared = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "recognition": {
                    "image_size_px": {"width": 24, "height": 16},
                    "plan_bbox_px": [0, 0, 24, 16],
                    "scale": {"m_per_px": 0.1},
                },
                "space_confirmation": {
                    "rooms": [
                        {
                            "id": "living-1",
                            "label": "客廳",
                            "type": "living_room",
                            "polygon_m": [
                                {"x": 0.0, "y": 0.0},
                                {"x": 2.4, "y": 0.0},
                                {"x": 2.4, "y": 1.6},
                                {"x": 0.0, "y": 1.6},
                            ],
                        }
                    ]
                },
            },
        },
    )
    assert prepared.status_code == 200
    invited = client.post(f"/api/projects/{project_id}/questionnaire-invite").json()
    token = invited["invite_token"]

    response = client.get(f"/api/questionnaire/{token}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["floorplan"] == {
        "source_url": f"/api/questionnaire/{token}/floorplan",
        "image_size_px": {"width": 24, "height": 16},
        "plan_bbox_px": [0, 0, 24, 16],
        "scale": {"cm_per_px": 10.0},
        "coordinate_space": "lower_left_cm",
        "room_height_cm": 270,
    }
    assert payload["rooms"][0]["polygon_cm"][2] == {"x": 240.0, "y": 160.0}
    assert project_id not in response.text
    source = client.get(payload["floorplan"]["source_url"])
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("image/png")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert source.headers["cache-control"] == "private, no-store"
    assert source.headers["referrer-policy"] == "no-referrer"


def test_invited_questionnaire_preserves_current_polygon_cm_contract() -> None:
    project = _create_project()
    project_id = project["project_id"]
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": ("plan.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    prepared = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "recognition": {
                    "image_size_px": {"width": 24, "height": 16},
                    "plan_bbox_px": [0, 0, 24, 16],
                    "scale": {"cm_per_px": 10},
                },
                "space_confirmation": {
                    "rooms": [
                        {
                            "id": "living-1",
                            "label": "客廳",
                            "type": "living_room",
                            "polygon_cm": [
                                {"x": 0, "y": 0},
                                {"x": 240, "y": 0},
                                {"x": 240, "y": 160},
                                {"x": 0, "y": 160},
                            ],
                        }
                    ]
                },
            },
        },
    )
    assert prepared.status_code == 200
    token = client.post(
        f"/api/projects/{project_id}/questionnaire-invite"
    ).json()["invite_token"]

    response = client.get(f"/api/questionnaire/{token}")

    assert response.status_code == 200
    assert response.json()["rooms"][0]["polygon_cm"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 240.0, "y": 0.0},
        {"x": 240.0, "y": 160.0},
        {"x": 0.0, "y": 160.0},
    ]


def test_invited_questionnaire_renders_dxf_as_a_token_scoped_svg_locator() -> None:
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
    floorplan = analyzed.json()["analysis"]["floorplan"]
    width_m = floorplan["width_cm"] / 100
    depth_m = floorplan["depth_cm"] / 100
    confirmed = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {
                            "id": "room-1",
                            "label": "測試房間",
                            "type": "living_room",
                            "polygon_m": [
                                {"x": width_m / 2 - 1, "y": depth_m / 2 - 1},
                                {"x": width_m / 2 + 1, "y": depth_m / 2 - 1},
                                {"x": width_m / 2 + 1, "y": depth_m / 2 + 1},
                                {"x": width_m / 2 - 1, "y": depth_m / 2 + 1},
                            ],
                        }
                    ]
                }
            },
        },
    )
    assert confirmed.status_code == 200
    invitation = client.post(
        f"/api/projects/{project_id}/questionnaire-invite"
    ).json()
    token = invitation["invite_token"]

    context = client.get(f"/api/questionnaire/{token}")

    assert context.status_code == 200
    locator = context.json()["floorplan"]
    assert locator["image_size_px"]["width"] == 1000
    assert locator["image_size_px"]["height"] > 0
    assert locator["scale"]["source"] == "dxf_geometry"
    assert locator["scale"]["distance_cm"] == floorplan["width_cm"]
    assert locator["scale"]["cm_per_px"] == floorplan["width_cm"] / 1000
    assert locator["coordinate_space"] == "lower_left_cm"
    assert "origin_m" not in locator
    source = client.get(locator["source_url"])
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in source.text
    assert "<line" in source.text


def test_normal_designer_save_rejects_a_supplied_stale_version() -> None:
    project = _create_project()
    project_id = project["project_id"]
    base = project["updated_at"]
    advanced = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "base_updated_at": base,
            "current_step": "requirements",
            "workflow": {"requirements": {"rooms": {"living-1": {"confirmed": True}}}},
        },
    )
    assert advanced.status_code == 200

    stale = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "base_updated_at": base,
            "current_step": "requirements",
            "workflow": {"requirements": {"rooms": {}}},
        },
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == "project_version_conflict"
    restored = client.get(f"/api/projects/{project_id}").json()["project"]
    assert restored["workflow"]["requirements"]["rooms"]["living-1"]["confirmed"] is True


def test_designer_workflow_rejects_invalid_confirmed_questionnaire_answers() -> None:
    project = _create_project()
    project_id = project["project_id"]
    prepared = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {"id": "living-1", "label": "客廳", "type": "living_room"},
                    ],
                },
                "confirmed_floorplan": {
                    "floorplan": {"room_height_cm": 250},
                },
                "requirements": {
                    "schemaVersion": "3.0",
                    "settings": {"minimumFinishedHeightCm": 240},
                    "rooms": {},
                },
            },
        },
    )
    assert prepared.status_code == 200

    rejected = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "requirements": {
                    "schemaVersion": "2.0",
                    "rooms": {
                        "living-1": {
                            "confirmed": True,
                            "uses": ["日常休息"],
                            "axes": {
                                "openness_storage": "a",
                                "social_focus": "a",
                                "seating_flexibility": "a",
                                "ceiling": "b",
                                "air_conditioning": "a",
                                "lighting": "a",
                            },
                        },
                    },
                },
            },
        },
    )

    assert rejected.status_code == 422
    assert rejected.json()["detail"] == {
        "code": "minimum_finished_height_not_met",
        "room_id": "living-1",
        "message": "房間需求未完成，或天花方案低於設計師設定的最低完成淨高。",
    }


def test_questionnaire_invite_expires_and_can_be_revoked_by_its_project() -> None:
    project = _create_project()
    project_id = project["project_id"]
    invited = client.post(f"/api/projects/{project_id}/questionnaire-invite")

    assert invited.status_code == 201
    invitation = invited.json()
    assert invitation["expires_at"] > invitation["created_at"]
    token = invitation["invite_token"]
    assert client.get(f"/api/questionnaire/{token}").status_code == 200

    revoked = client.delete(
        f"/api/projects/{project_id}/questionnaire-invite/{token}"
    )

    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": True}
    denied = client.get(f"/api/questionnaire/{token}")
    assert denied.status_code == 404
    assert denied.json()["detail"] == "questionnaire_invite_not_found"


def test_designer_can_revoke_all_questionnaire_invites_after_refresh() -> None:
    project = _create_project()
    project_id = project["project_id"]
    first = client.post(
        f"/api/projects/{project_id}/questionnaire-invite"
    ).json()["invite_token"]
    second = client.post(
        f"/api/projects/{project_id}/questionnaire-invite"
    ).json()["invite_token"]

    revoked = client.delete(
        f"/api/projects/{project_id}/questionnaire-invites"
    )

    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": 2}
    assert client.get(f"/api/questionnaire/{first}").status_code == 404
    assert client.get(f"/api/questionnaire/{second}").status_code == 404


def test_questionnaire_invite_can_only_read_and_write_project_requirements() -> None:
    project = _create_project()
    project_id = project["project_id"]
    prepared = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {"id": "living-1", "label": "客廳", "type": "living_room"},
                        {"id": "kitchen-1", "label": "廚房", "type": "kitchen"},
                    ],
                    "structures": {"walls": [{"id": "wall-secret"}]},
                },
                "confirmed_floorplan": {
                    "floorplan": {"room_height_cm": 270},
                },
                "requirements": {
                    "basic": {},
                    "rooms": {"living-1": {"priority": "需拆牆並保留主要走道"}},
                    "settings": {"minimumFinishedHeightCm": 260},
                    "designerNotes": "只供設計師查看",
                    "clientBrief": {"designer_only": True},
                },
            },
        },
    )
    assert prepared.status_code == 200

    invited = client.post(f"/api/projects/{project_id}/questionnaire-invite")
    assert invited.status_code == 201
    token = invited.json()["invite_token"]
    assert invited.json()["questionnaire_url"] == f"/questionnaire/{token}"

    context = client.get(f"/api/questionnaire/{token}")
    assert context.status_code == 200
    payload = context.json()
    assert payload["project"] == {"name": project["name"]}
    assert project_id not in context.text
    assert payload["updated_at"]
    assert "designerNotes" not in payload["requirements"]
    assert "clientBrief" not in payload["requirements"]
    assert payload["rooms"] == [
        {"id": "living-1", "label": "客廳", "type": "living_room"},
        {"id": "kitchen-1", "label": "廚房", "type": "kitchen"},
    ]
    assert "structures" not in payload

    page = client.get(f"/questionnaire/{token}")
    assert page.status_code == 200
    assert page.headers["cache-control"] == "private, no-store"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert "RoomPilot 專案需求問卷" in page.text
    assert "只可填寫本專案問卷" in page.text
    assert "scene_v2.js" not in page.text

    rejected_basic = client.put(
        f"/api/questionnaire/{token}",
        json={
            "base_updated_at": payload["updated_at"],
            "requirements": {
                "basic": {"residents": ["adult"]},
                "basicConfirmed": True,
                "rooms": {},
            },
        },
    )
    assert rejected_basic.status_code == 422
    assert rejected_basic.json()["detail"]["code"] == "questionnaire_basic_incomplete"

    valid_basic = {
        "residents": ["adult", "forged"],
        "residentCount": "two",
        "ageNeeds": "aging",
        "scheduleInterference": ["same_schedule", "forged"],
        "homeWorkStudyCount": "one_regular",
        "homeWorkStudyNeeds": ["quiet_focus"],
        "futureChanges": ["stable"],
        "hostingFrequency": "monthly",
        "hostingNeeds": ["meal"],
        "budgetPriority": "balanced",
        "budgetRange": "100_200",
        "targetTimeline": "six_to_twelve_months",
        "immutableNeeds": ["fixed_pipes"],
    }
    rejected_height = client.put(
        f"/api/questionnaire/{token}",
        json={
            "base_updated_at": payload["updated_at"],
            "requirements": {
                "basic": valid_basic,
                "basicConfirmed": True,
                "rooms": {
                    "living-1": {
                        "schemaVersion": "3.0",
                        "confirmed": True,
                        "uses": ["日常休息"],
                        "axes": {
                            "openness_storage": "a",
                            "social_focus": "a",
                            "seating_flexibility": "a",
                            "ceiling": "b",
                            "air_conditioning": "a",
                            "lighting": "a",
                        },
                    },
                },
            },
        },
    )
    assert rejected_height.status_code == 422
    assert rejected_height.json()["detail"]["code"] == "minimum_finished_height_not_met"

    saved = client.put(
        f"/api/questionnaire/{token}",
        json={
            "base_updated_at": payload["updated_at"],
            "requirements": {
                "schemaVersion": "3.0",
                "basic": valid_basic,
                "basicConfirmed": True,
                "rooms": {
                    "living-1": {
                        "schemaVersion": "3.0",
                        "confirmed": True,
                        "roomIdentity": {
                            "type": "living_room",
                            "label": "客廳",
                            "centroid_m": {"x": 5.5, "y": 7.25},
                            "area_m2": 18.75,
                        },
                        "stageNotes": {
                            "uses": "需要瑜珈空間",
                            "furniture": "保留唱片櫃",
                            "forged": "不可保留",
                        },
                        "axes": {
                            "openness_storage": "open_flow",
                            "social_focus": "media",
                            "seating_flexibility": "fixed_sofa",
                            "ceiling": "flat",
                            "air_conditioning": "wall_mounted",
                            "lighting": "recessed_focus",
                            "forged_axis": "forged",
                        },
                        "uses": ["日常休息", "注入"],
                        "furniture": ["沙發", "注入"],
                        "materialPreferences": {
                            "wall": ["paint"],
                            "floor": ["wood"],
                            "furniture": ["fabric"],
                            "cuts": ["電視牆左右分材"],
                        },
                    },
                    "kitchen-1": {
                        "schemaVersion": "3.0",
                        "confirmed": True,
                        "keepExisting": True,
                        "roomIdentity": {
                            "type": "kitchen",
                            "label": "廚房",
                            "centroid_m": {"x": 2.0, "y": 3.0},
                            "area_m2": 7.5,
                        },
                        "axes": {
                            "kitchen_enclosure": "open",
                            "cooking_intensity": "light",
                            "worktop_storage": "worktop",
                            "ceiling": "flat",
                            "lighting": "surface_focus",
                        },
                        "uses": ["每日下廚"],
                        "furniture": ["冰箱"],
                    },
                    "not-a-real-room": {"confirmed": True, "uses": ["注入"]},
                },
                "designerNotes": "惡意覆寫",
                "clientBrief": {"forged": True},
            }
        },
    )
    assert saved.status_code == 200
    restored = client.get(f"/api/projects/{project_id}").json()["project"]
    assert restored["workflow"]["requirements"]["schemaVersion"] == "3.0"
    assert restored["workflow"]["requirements"]["designerNotes"] == "只供設計師查看"
    assert restored["workflow"]["requirements"]["basic"]["residents"] == ["adult"]
    assert restored["workflow"]["requirements"]["basic"]["ageNeeds"] == ["aging"]
    assert restored["workflow"]["requirements"]["basic"]["scheduleInterference"] == [
        "same_schedule"
    ]
    assert restored["workflow"]["requirements"]["rooms"]["living-1"]["priority"] == "需拆牆並保留主要走道"
    assert restored["workflow"]["requirements"]["rooms"]["living-1"]["axes"] == {
        "openness_storage": "a",
        "social_focus": "a",
        "seating_flexibility": "a",
        "ceiling": "a",
        "air_conditioning": "a",
        "lighting": "a",
    }
    assert restored["workflow"]["requirements"]["clientBrief"]["rooms"]["living-1"][
        "preference_axis_details"
    ]["ceiling"] == {
            "preference": "a",
            "selected_label": "維持平整、保留淨高",
            "mode": "continuum",
            "endpoint_a": {
                "value": "flat",
                "label": "維持平整、保留淨高",
                "image_key": "living-room/axis/ceiling/flat",
            },
            "endpoint_b": {
                "value": "functional_drop",
                "label": "局部降板、整合管線",
                "image_key": "living-room/axis/ceiling/functional-drop",
            },
            "other_approach": "",
        }
    assert restored["workflow"]["requirements"]["rooms"]["living-1"]["stageNotes"] == {
        "uses": "需要瑜珈空間",
        "furniture": "保留唱片櫃",
    }
    assert restored["workflow"]["requirements"]["rooms"]["living-1"]["uses"] == [
        "日常休息"
    ]
    assert restored["workflow"]["requirements"]["rooms"]["living-1"][
        "roomIdentity"
    ] == {
        "type": "living_room",
        "label": "客廳",
        "centroid_m": {"x": 5.5, "y": 7.25},
        "area_m2": 18.75,
    }
    assert restored["workflow"]["requirements"]["rooms"]["kitchen-1"][
        "keepExisting"
    ] is True
    assert restored["workflow"]["requirements"]["rooms"]["kitchen-1"][
        "roomIdentity"
    ] == {
        "type": "kitchen",
        "label": "廚房",
        "centroid_m": {"x": 2.0, "y": 3.0},
        "area_m2": 7.5,
    }
    assert restored["workflow"]["requirements"]["clientBrief"]["rooms"]["living-1"][
        "material_preferences"
    ] == {
        "status": "defined",
        "wall": ["paint"],
        "floor": ["wood"],
        "furniture": ["fabric"],
        "color": [],
        "finish": [],
        "cuts": ["電視牆左右分材"],
    }
    kitchen_brief = restored["workflow"]["requirements"]["clientBrief"]["rooms"][
        "kitchen-1"
    ]
    assert kitchen_brief["structure_strategy"] == "compare_changed_and_unchanged"
    assert kitchen_brief["safety_risks"] == ["wall", "gas", "smoke_exhaust"]
    brief_warnings = restored["workflow"]["requirements"]["clientBrief"]["warnings"]
    assert brief_warnings[0]["position"] == "1/4"
    assert brief_warnings[0]["roomId"] == "living-1"
    assert brief_warnings[0]["risk"] == "wall"
    assert "not-a-real-room" not in restored["workflow"]["requirements"]["rooms"]
    assert restored["workflow"]["space_confirmation"]["structures"]["walls"] == [
        {"id": "wall-secret"}
    ]

    stale = client.put(
        f"/api/questionnaire/{token}",
        json={
            "base_updated_at": payload["updated_at"],
            "requirements": {"basic": {}, "rooms": {}},
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "project_version_conflict"

    denied = client.get("/api/questionnaire/not-a-real-token")
    assert denied.status_code == 404
    assert denied.json()["detail"] == "questionnaire_invite_not_found"


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


def test_project_persists_material_preferences_and_three_scheme_workbench() -> None:
    project = _create_project()
    project_id = project["project_id"]
    design_preferences = {
        "schemaVersion": "1.0",
        "styleId": "scandinavian_1",
        "wholeHouse": {
            "wallSurfaceId": "wall-plaster",
            "floorSurfaceId": "floor-oak",
            "wallColor": "#f4efe4",
            "floorColor": "#c9a77d",
        },
        "rooms": {
            "living-1": {
                "wall": ["mineral"],
                "floor": ["wood"],
                "cuts": ["電視牆左右分材"],
            }
        },
    }
    scheme_set = {
        "schemaVersion": "1.0",
        "activeSchemeId": "scheme-2",
        "schemes": [
            {
                "id": f"scheme-{index}",
                "furniture": [],
                "generation": {
                    "source": "rule_fallback",
                    "ragStatus": "pending",
                    "agentStatus": "pending",
                    "placementEngine": "roompilot.engine",
                },
            }
            for index in range(1, 4)
        ],
    }

    response = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "layout_2d",
            "workflow": {
                "design_preferences": design_preferences,
                "layout_2d": {
                    "activeSchemeId": "scheme-2",
                    "schemeSet": scheme_set,
                    "furniture": [],
                },
            },
        },
    )

    assert response.status_code == 200
    restored = client.get(f"/api/projects/{project_id}").json()["project"]
    assert restored["current_step"] == "layout_2d"
    assert restored["workflow"]["design_preferences"] == design_preferences
    assert restored["workflow"]["layout_2d"]["schemeSet"]["activeSchemeId"] == "scheme-2"
    assert [
        scheme["id"]
        for scheme in restored["workflow"]["layout_2d"]["schemeSet"]["schemes"]
    ] == ["scheme-1", "scheme-2", "scheme-3"]


def test_confirmed_wet_room_materials_reject_unsafe_floor_at_api_boundary() -> None:
    project = _create_project()
    project_id = project["project_id"]
    wall_surface_id = "wall_ambientcg_plaster006"
    unsafe_floor_id = "wood_cc0_wood_textures_bamboo001c"
    safe_floor_id = "tile_ccity_tile_flooring_cal12658"

    def payload(floor_surface_id: str) -> dict:
        return {
            "current_step": "design_preferences",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {"id": "bathroom-1", "label": "浴室", "type": "bathroom"}
                    ]
                },
                "design_preferences": {
                    "confirmed": True,
                    "styleConfirmed": True,
                    "materialsConfirmed": True,
                    "wholeHouse": {
                        "wallSurfaceId": wall_surface_id,
                        "floorSurfaceId": floor_surface_id,
                    },
                    "rooms": {
                        "bathroom-1": {
                            "confirmed": True,
                            "surfaceOverride": {
                                "wallSurfaceId": wall_surface_id,
                                "floorSurfaceId": floor_surface_id,
                            },
                        }
                    },
                },
            },
        }

    rejected = client.put(
        f"/api/projects/{project_id}/workflow",
        json=payload(unsafe_floor_id),
    )

    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_room_material_selection"
    assert rejected.json()["detail"]["room_id"] == "bathroom-1"
    assert rejected.json()["detail"]["surface"] == "floor"

    accepted = client.put(
        f"/api/projects/{project_id}/workflow",
        json=payload(safe_floor_id),
    )
    assert accepted.status_code == 200


def test_partial_room_type_patch_cannot_bypass_confirmed_material_validation() -> None:
    project = _create_project()
    project_id = project["project_id"]
    wall_surface_id = "wall_ambientcg_plaster006"
    wood_floor_id = "wood_cc0_wood_textures_bamboo001c"
    initial = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "design_preferences",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {"id": "room-1", "label": "臥室", "type": "bedroom"}
                    ]
                },
                "design_preferences": {
                    "confirmed": True,
                    "styleConfirmed": True,
                    "materialsConfirmed": True,
                    "wholeHouse": {
                        "wallSurfaceId": wall_surface_id,
                        "floorSurfaceId": wood_floor_id,
                    },
                    "rooms": {
                        "room-1": {
                            "confirmed": True,
                            "surfaceOverride": {
                                "wallSurfaceId": wall_surface_id,
                                "floorSurfaceId": wood_floor_id,
                            },
                        }
                    },
                },
            },
        },
    )
    assert initial.status_code == 200

    bypass_attempt = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "space_confirmation",
            "workflow": {
                "space_confirmation": {
                    "rooms": [
                        {"id": "room-1", "label": "浴室", "type": "bathroom"}
                    ]
                }
            },
        },
    )

    assert bypass_attempt.status_code == 422
    assert (
        bypass_attempt.json()["detail"]["code"]
        == "invalid_room_material_selection"
    )


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


def test_floorplan_analysis_explains_missing_confirmation_instead_of_stalling() -> None:
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
        "code": "floorplan_confirmation_required",
        "message": "請先確認圖檔內容正確，才能開始辨識。",
        "focus": "project-floorplan-confirmation",
    }

    saved = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "upload",
            "workflow": {
                "floorplan_confirmation": {
                    "confirmed": True,
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


def test_dxf_analysis_returns_canonical_centimeter_geometry_and_room_regions() -> None:
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
    assert floorplan["coordinate_unit"] == "cm"
    assert floorplan["wall_segments"]
    assert floorplan["room_regions"]
    points = [
        point
        for segment in floorplan["wall_segments"]
        for point in (segment["start"], segment["end"])
    ]
    assert max(abs(point["x"]) for point in points) <= floorplan["width_cm"] / 2 + 10
    assert max(abs(point["z"]) for point in points) <= floorplan["depth_cm"] / 2 + 10


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


def test_scene_generation_preserves_exact_workbench_surface_choices() -> None:
    response = client.post(
        "/api/scene/generate",
        json={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "selected_furniture": [],
            "selected_furniture_exact": True,
            "wall_option": "wall-mineral-warm-white",
            "floor_option": "floor-oak-natural",
            "wall_color_hex": "#f4efe4",
            "floor_color_hex": "#c9a77d",
        },
    )

    assert response.status_code == 200
    choices = response.json()["design_choices"]
    assert choices["wall_option"] == "wall-mineral-warm-white"
    assert choices["floor_option"] == "floor-oak-natural"
    assert choices["wall_color_hex"] == "#f4efe4"
    assert choices["floor_color_hex"] == "#c9a77d"


def test_scene_generation_uses_the_user_confirmed_floorplan_as_canonical_geometry() -> None:
    response = client.post(
        "/api/scene/generate",
        json={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "selected_furniture": [],
            "selected_furniture_exact": True,
            "floorplan_editor": {
                "coordinate_unit": "cm",
                "width_cm": 600,
                "depth_cm": 400,
                "room_height_cm": 280,
                "rooms": [
                    {
                        "id": "living-1",
                        "label": "客廳",
                        "polygon_cm": [
                            {"x": 0, "y": 0},
                            {"x": 600, "y": 0},
                            {"x": 600, "y": 400},
                            {"x": 0, "y": 400},
                        ],
                    }
                ],
                "structures": {
                    "walls": [
                        {
                            "id": "wall-1",
                            "start": {"x": 0, "y": 0},
                            "end": {"x": 600, "y": 0},
                            "thickness_cm": 18,
                        },
                        {
                            "id": "wall-2",
                            "start": {"x": 600, "y": 0},
                            "end": {"x": 600, "y": 400},
                            "thickness_cm": 18,
                        },
                        {
                            "id": "wall-3",
                            "start": {"x": 600, "y": 400},
                            "end": {"x": 0, "y": 400},
                            "thickness_cm": 18,
                        },
                        {
                            "id": "wall-4",
                            "start": {"x": 0, "y": 400},
                            "end": {"x": 0, "y": 0},
                            "thickness_cm": 18,
                        },
                    ],
                    "doors": [
                        {
                            "id": "door-1",
                            "start": {"x": 240, "y": 0},
                            "end": {"x": 330, "y": 0},
                            "opening_direction": "left",
                        }
                    ],
                    "windows": [
                        {
                            "id": "window-1",
                            "start": {"x": 100, "y": 400},
                            "end": {"x": 220, "y": 400},
                        }
                    ],
                    "beams": [
                        {
                            "id": "beam-1",
                            "start": {"x": 0, "y": 200},
                            "end": {"x": 600, "y": 200},
                            "width_cm": 30,
                            "height_cm": 40,
                            "top_cm": 280,
                        }
                    ],
                    "columns": [
                        {
                            "id": "column-1",
                            "center": {"x": 40, "y": 40},
                            "size_cm": 58,
                            "depth_cm": 35,
                            "height_cm": 245,
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
    assert floorplan["coordinate_unit"] == "cm"
    assert floorplan["wall_segments"][0]["start"] == {"x": -300.0, "z": -200.0}
    assert floorplan["room_regions"][0]["room_id"] == "living-1"
    assert floorplan["room_regions"][0]["exterior"][2] == [300.0, 200.0]
    assert floorplan["beam_segments"][0]["top_cm"] == 280
    assert floorplan["columns"][0]["center"] == {"x": -260.0, "z": -160.0}
    assert floorplan["columns"][0]["size_cm"] == 58
    assert floorplan["columns"][0]["depth_cm"] == 35
    assert floorplan["columns"][0]["height_cm"] == 245
    assert floorplan["columns"][0]["rotation_deg"] == 30
    assert response.json()["scene_objects"] == []


def test_2d_layout_and_drag_validation_use_the_engine_with_editor_geometry() -> None:
    floorplan_editor = {
        "coordinate_unit": "cm",
        "width_cm": 600,
        "depth_cm": 400,
        "rooms": [
            {
                "id": "living-1",
                "polygon_cm": [
                    {"x": 0, "y": 0},
                    {"x": 600, "y": 0},
                    {"x": 600, "y": 400},
                    {"x": 0, "y": 400},
                ],
            }
        ],
        "structures": {
            "walls": [
                {"start": {"x": 0, "y": 0}, "end": {"x": 600, "y": 0}},
                {"start": {"x": 600, "y": 0}, "end": {"x": 600, "y": 400}},
                {"start": {"x": 600, "y": 400}, "end": {"x": 0, "y": 400}},
                {"start": {"x": 0, "y": 400}, "end": {"x": 0, "y": 0}},
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
