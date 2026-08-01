from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.server.main import app
from backend.server.project_store import ProjectStore
from backend.server.runtime_paths import legacy_runtime_dirs, project_runtime_dir


client = TestClient(app)


def _selection_candidate(fid: str, kind: str, *, with_model: bool = True) -> dict:
    # 正式流程的候選（瀏覽器從 catalog 撈的）一定帶 model_url；缺 model_url
    # 的假候選（furnitureOfferFromSpec）另以 with_model=False 模擬。
    candidate = {
        "furniture_id": fid,
        "normalized_type": kind,
        "variant_id": "standard",
        "name_zh_raw": fid,
        "size_cm": {"width": 120, "depth": 60, "height": 80},
    }
    if with_model:
        candidate["model_url"] = f"https://example.test/{fid}.glb"
        candidate["has_model"] = True
    return candidate


def _family_types(*families: str) -> set[str]:
    from backend.agent.knowledge import FAMILY_OF

    wanted = set(families)
    types = set(wanted)
    types.update(key for key, value in FAMILY_OF.items() if value in wanted)
    return types


def test_agent_furniture_selection_falls_back_when_llm_violates_room_rules(monkeypatch) -> None:
    # 本測試驗「種子 offers＋規則驗證＋補件」的原始契約，隔離 RAG 快取。
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")
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
    items = payload["rooms"][0]["items"]
    # 床不屬於客廳，遭規則剔除；沙發保留；缺席的必備電視櫃由 Agent 從型錄補上。
    assert items[0]["furniture_id"] == "sofa-1"
    backfilled = [item for item in items if item.get("selection_source") == "agent_backfill"]
    assert len(backfilled) == 1
    assert backfilled[0]["normalized_type"] in _family_types("tv-bench")
    assert backfilled[0]["model_url"]
    assert all(item["normalized_type"] != "bed" for item in items)


def test_agent_furniture_selection_uses_server_side_local_rules_without_llm(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")
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
    items = payload["rooms"][0]["items"]
    # 同族系（bed 與 bed-frame）只取第一件；缺席的必備衣櫃由 Agent 從型錄補上。
    assert [item["furniture_id"] for item in items[:2]] == ["bed-1", "nightstand-1"]
    backfilled = [item for item in items if item.get("selection_source") == "agent_backfill"]
    assert len(backfilled) == 1
    assert backfilled[0]["normalized_type"] in _family_types("wardrobe")
    assert backfilled[0]["model_url"]


def test_agent_backfill_replaces_model_less_required_offer_with_catalog_item(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")
    """必備族系的候選全是無 3D 模型的假件時，Agent 要換成型錄真品。

    這正是第 6 步「灰方塊衣櫃」的根因：瀏覽器對不到 catalog 就捏造無
    model_url 的假 offer，舊行為會照單全收讓 3D 畫出灰色方塊。
    """
    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
            "offers": {
                "bedroom-1": [
                    _selection_candidate("bed-1", "bed"),
                    _selection_candidate("nightstand-1", "bedside-table"),
                    _selection_candidate("fake-wardrobe", "wardrobe", with_model=False),
                ]
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    items = payload["rooms"][0]["items"]
    wardrobe_items = [
        item for item in items if item["normalized_type"] in _family_types("wardrobe")
    ]
    assert len(wardrobe_items) == 1
    assert wardrobe_items[0]["furniture_id"] != "fake-wardrobe"
    assert wardrobe_items[0]["model_url"]
    assert wardrobe_items[0]["selection_source"] == "agent_backfill"


def test_agent_backfill_fills_all_minimums_when_offers_are_empty(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")
    """offers 全空時，Agent 依 knowledge 的房型最少配置自己補齊（沒接 RAG 也放得出正確家具）。"""
    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
            "offers": {"bedroom-1": []},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    items = payload["rooms"][0]["items"]
    families = {item["normalized_type"] for item in items}
    assert families & _family_types("bed")
    assert families & _family_types("wardrobe")
    assert families & _family_types("bedside-table")
    assert all(item["model_url"] for item in items)


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
    assert loaded.headers["cache-control"] == "no-store"
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
    assert payload["layout_json"] == payload["analysis"]
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
    payload = response.json()
    floorplan = payload["floorplan"]
    assert payload["scene_json"]["floorplan"] == floorplan
    assert "scene_json" not in payload["scene_json"]
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
    assert payload["scene_objects"] == []

    layout_response = client.post(
        "/api/scene/generate",
        json={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "selected_furniture": [],
            "selected_furniture_exact": True,
            "layout_json": floorplan,
        },
    )

    assert layout_response.status_code == 200
    layout_payload = layout_response.json()
    assert layout_payload["floorplan"] == floorplan
    assert layout_payload["scene_json"]["floorplan"] == floorplan


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
    assert layout.json()["floorplan"]["room_regions"][0]["room_id"] == "living-1"
    assert layout.json()["floorplan"]["wall_segments"]
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


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 16), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_floorplan_upload_accepts_real_jpeg_bytes() -> None:
    project = _create_project()

    accepted = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.jpg", _jpeg_bytes(), "image/jpeg")},
    )

    assert accepted.status_code == 201
    upload = accepted.json()["upload"]
    assert upload["extension"] == ".jpg"

    source = client.get(upload["source_url"])
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("image/jpeg")


def test_floorplan_upload_rejects_jpg_extension_with_non_image_bytes() -> None:
    project = _create_project()

    rejected = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.jpg", b"not an image at all", "image/jpeg")},
    )

    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_floorplan_image"


def test_floorplan_upload_accepts_minimal_text_dxf() -> None:
    project = _create_project()
    minimal = (
        "999\ncomment\n  0\nSECTION\n  2\nENTITIES\n  0\nENDSEC\n  0\nEOF\n"
    ).encode("ascii")

    accepted = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.dxf", minimal, "application/dxf")},
    )

    assert accepted.status_code == 201
    assert accepted.json()["upload"]["extension"] == ".dxf"


def test_floorplan_upload_rejects_garbage_dxf_bytes() -> None:
    project = _create_project()

    rejected = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.dxf", b"\x00\x01\x02 definitely not a dxf", "application/dxf")},
    )

    assert rejected.status_code == 422
    detail = rejected.json()["detail"]
    assert detail["code"] == "invalid_floorplan_dxf"
    assert detail["focus"] == "floorplan-file"


def test_floorplan_upload_rejects_binary_dxf_with_ascii_hint() -> None:
    project = _create_project()
    binary = b"AutoCAD Binary DXF\r\n\x1a\x00" + b"\x00" * 32

    rejected = client.post(
        f"/api/projects/{project['project_id']}/floorplan",
        files={"file": ("plan.dxf", binary, "application/dxf")},
    )

    assert rejected.status_code == 415
    detail = rejected.json()["detail"]
    assert detail["code"] == "binary_dxf_unsupported"
    assert "ASCII" in detail["message"]


def _first_catalog_item(normalized_type: str) -> dict:
    from backend.server.main import _furniture_payload_cache

    for item in _furniture_payload_cache():
        if (
            item.get("normalized_type") == normalized_type
            and item.get("model_url")
            and item.get("has_model")
        ):
            return item
    raise AssertionError(f"catalog 缺少可用的 {normalized_type}")


def test_rag_offer_cache_leads_the_selection(tmp_path: Path, monkeypatch) -> None:
    """RAG 快取存在時，該族系的第一名由快取決定（selection_source=rag_cache）。"""
    bed = _first_catalog_item("bed")
    cache = tmp_path / "rag_offer_cache.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": "roompilot.rag_offer_cache.v1",
                "entries": {"bed|scandinavian": [bed["furniture_id"]]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE_PATH", str(cache))

    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
            "offers": {"bedroom-1": []},
            "style_id": "scandinavian",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    items = payload["rooms"][0]["items"]
    bed_items = [item for item in items if item["normalized_type"] in _family_types("bed")]
    assert bed_items and bed_items[0]["furniture_id"] == bed["furniture_id"]
    assert bed_items[0]["selection_source"] == "rag_cache"
    # 快取沒涵蓋的必備族系仍由補件保底
    assert any(item["selection_source"] == "agent_backfill" for item in items)


def test_rag_offer_cache_can_be_disabled(tmp_path: Path, monkeypatch) -> None:
    bed = _first_catalog_item("bed")
    cache = tmp_path / "rag_offer_cache.json"
    cache.write_text(
        json.dumps({"entries": {"bed|scandinavian": [bed["furniture_id"]]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE_PATH", str(cache))
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")

    response = client.post(
        "/api/agent/furniture/select",
        json={
            "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
            "offers": {"bedroom-1": []},
            "style_id": "scandinavian",
        },
    )
    assert response.status_code == 200
    items = response.json()["rooms"][0]["items"]
    assert items and all(item["selection_source"] != "rag_cache" for item in items)


def test_scene_layout_preserves_every_furniture_id(monkeypatch) -> None:
    """/api/scene/layout 的契約：送 N 件、以原 furniture_id 回 N 件。

    前端用原 id 對表更新座標；id 被換掉或少件，家具會直接從畫面消失
    （2026-08-01 換小迴圈誤掛此端點時實際發生）。放不下必須保留原件並標
    placement_failed，不得替換或移除。
    """
    monkeypatch.setenv("ROOMPILOT_RAG_OFFER_CACHE", "0")
    width, depth = 338, 310
    editor = {
        "width_cm": width,
        "depth_cm": depth,
        "coordinate_unit": "cm",
        "rooms": [
            {
                "id": "room-1",
                "label": "主臥",
                "type": "bedroom",
                "polygon_cm": [
                    {"x": 0, "z": 0},
                    {"x": width, "z": 0},
                    {"x": width, "z": depth},
                    {"x": 0, "z": depth},
                ],
            }
        ],
        "structures": {"walls": [], "doors": [], "windows": []},
    }

    def obj(fid, type_, w, d, h):
        return {
            "furniture_id": fid,
            "normalized_type": type_,
            "name_zh_raw": fid,
            "has_model": True,
            "model_url": "https://example.test/x.glb",
            "size_cm": {"width": w, "depth": d, "height": h},
            "position_cm": {"x": 0, "z": 0},
            "rotation_y_deg": 0,
            "position_locked": False,
        }

    sent = [
        obj("room-1-bed-1", "bed", 152, 200, 55),
        obj("room-1-wardrobe-1", "wardrobe", 100, 60, 200),
        # 故意塞一件大到不可能放進去的，逼出「放不下」路徑
        obj("room-1-wardrobe-2", "wardrobe", 400, 200, 200),
    ]
    response = client.post(
        "/api/scene/layout",
        json={
            "floorplan_editor": editor,
            "placement_room_id": "room-1",
            "placement_variant": "A",
            "scene_objects": sent,
        },
    )
    assert response.status_code == 200
    returned = response.json()["scene_objects"]
    assert [item["furniture_id"] for item in returned] == [item["furniture_id"] for item in sent]
    oversized = next(item for item in returned if item["furniture_id"] == "room-1-wardrobe-2")
    assert oversized["placement_failed"] is True
    assert oversized["placement_reason"]
