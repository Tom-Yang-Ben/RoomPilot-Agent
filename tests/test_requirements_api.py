from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.server.main import app
from backend.server.services.requirements_service import analyze_special_requirements


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROOMPILOT_RUNTIME_DIR", str(tmp_path / "runtime"))
    with TestClient(app) as test_client:
        yield test_client


def _project_at_requirements(client: TestClient) -> dict:
    project = client.post("/api/projects", json={"name": "需求問卷案"}).json()["project"]
    response = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={
            "expected_revision": project["revision"],
            "current_step": "requirements",
            "workflow": {
                "completed": [
                    "project",
                    "upload",
                    "recognition",
                    "calibration",
                    "space_confirmation",
                ],
                "data": {
                    "space_confirmation": {
                        "status": "confirmed",
                        "confirmed_by": "user",
                        "floorplan": {
                            "room_regions": [
                                {
                                    "room_id": "room-living",
                                    "room_type": "living_room",
                                    "label_zh": "客廳",
                                    "confirmed": True,
                                },
                                {
                                    "room_id": "room-bed",
                                    "room_type": "bedroom",
                                    "label_zh": "臥室",
                                    "confirmed": True,
                                },
                            ]
                        },
                    },
                    "layout_2d": {"status": "stale"},
                    "white_model_3d": {"status": "stale"},
                },
            },
        },
    )
    assert response.status_code == 200
    return response.json()["project"]


def _answers(project: dict, **overrides) -> dict:
    result = {
        "expected_revision": project["revision"],
        "style_id": "scandinavian",
        "occupants": {"adults": 2, "children": 1, "elderly": 0, "pets": 0},
        "customization_mode": "default",
        "room_requirements": [
            {
                "room_id": "room-living",
                "room_type": "living_room",
                "uses": ["watching_tv"],
                "required_furniture_ids": [],
                "special_materials": [],
                "special_notes": "隱藏欄位不應送出",
            },
            {
                "room_id": "room-bed",
                "room_type": "bedroom",
                "uses": [],
                "required_furniture_ids": [],
                "special_materials": [],
                "special_notes": "",
            },
        ],
        "special_notes": "default 模式不應送出",
    }
    result.update(overrides)
    return result


def test_default_questionnaire_uses_local_rules_then_requires_confirmation(
    client: TestClient,
) -> None:
    project = _project_at_requirements(client)
    answers = _answers(project)

    analyzed = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={**answers, "allow_openrouter": True},
    )

    assert analyzed.status_code == 200
    suggestion = analyzed.json()["suggestion"]
    assert suggestion["status"] == "suggested"
    assert suggestion["source"] == "local_rules"
    assert suggestion["openrouter"]["sent"] is False
    assert suggestion["openrouter"]["status"] == "skipped_no_text"
    assert any(item["type"] == "child_safety" for item in suggestion["constraints"])

    before = client.get(f"/api/projects/{project['project_id']}").json()["project"]
    assert before["revision"] == project["revision"]
    assert before["workflow"]["data"].get("requirements") is None

    confirmed = client.post(
        f"/api/projects/{project['project_id']}/requirements/confirm",
        json={**answers, "suggestion": suggestion},
    )

    assert confirmed.status_code == 200
    payload = confirmed.json()
    assert payload["project"]["current_step"] == "layout_2d"
    assert payload["project"]["revision"] == project["revision"] + 1
    assert payload["project"]["workflow"]["completed"][-1] == "requirements"
    saved = payload["requirements"]
    assert saved["status"] == "confirmed"
    assert saved["confirmed_by"] == "user"
    assert saved["special_notes"] == ""
    assert saved["room_requirements"][0]["uses"] == ["family_gathering", "relaxing"]
    assert saved["room_requirements"][0]["special_notes"] == ""
    assert payload["project"]["workflow"]["data"]["layout_2d"] is None
    assert payload["project"]["workflow"]["data"]["white_model_3d"] is None


def test_advanced_text_reaches_openrouter_adapter_only_with_consent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.server.services import requirements_service as requirements_module

    project = _project_at_requirements(client)
    calls = []

    def fake_analyze(requirements, *, valid_room_ids, allow_openrouter):
        calls.append((requirements, valid_room_ids, allow_openrouter))
        return {
            "status": "suggested",
            "source": "openrouter",
            "model": "mock/model",
            "summary_zh": "已整理長者需求。",
            "constraints": [{
                "type": "accessibility",
                "room_id": "room-living",
                "description_zh": "保留助行器通行空間。",
                "priority": "high",
                "evidence": ["助行器"],
            }],
            "openrouter": {
                "provider": "openrouter",
                "requested": True,
                "sent": True,
                "status": "suggested",
                "model": "mock/model",
            },
        }

    monkeypatch.setattr(requirements_module, "analyze_special_requirements", fake_analyze)
    answers = _answers(
        project,
        customization_mode="advanced",
        special_notes="長者使用助行器，客廳要留通道。",
    )
    response = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={**answers, "allow_openrouter": True},
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["source"] == "openrouter"
    assert calls[0][2] is True
    assert calls[0][1] == {"room-living", "room-bed"}
    assert calls[0][0]["special_notes"].startswith("長者")


def test_questionnaire_rejects_stale_rooms_unknown_style_and_missing_resident(
    client: TestClient,
) -> None:
    project = _project_at_requirements(client)
    answers = _answers(project)

    unknown_style = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={**answers, "style_id": "invented_style", "allow_openrouter": False},
    )
    wrong_room = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={
            **answers,
            "room_requirements": answers["room_requirements"][:1],
            "allow_openrouter": False,
        },
    )
    no_resident = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={
            **answers,
            "occupants": {"adults": 0, "children": 0, "elderly": 0, "pets": 2},
            "allow_openrouter": False,
        },
    )

    assert unknown_style.status_code == 422
    assert unknown_style.json()["detail"]["code"] == "unknown_style_id"
    assert wrong_room.status_code == 422
    assert wrong_room.json()["detail"]["code"] == "requirements_room_mismatch"
    assert no_resident.status_code == 422


def test_specified_furniture_must_exist_and_have_a_glb(client: TestClient) -> None:
    from backend.server.services.catalog_service import _merged_furniture_catalog_cached

    project = _project_at_requirements(client)
    answers = _answers(project, customization_mode="advanced")
    unknown_rooms = [dict(room) for room in answers["room_requirements"]]
    unknown_rooms[0]["required_furniture_ids"] = ["not-a-real-catalog-id"]
    unknown = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={**answers, "room_requirements": unknown_rooms, "allow_openrouter": False},
    )

    unavailable_id = next(
        str(item["furniture_id"])
        for item in _merged_furniture_catalog_cached()
        if item.get("furniture_id") and not item.get("has_model")
    )
    unavailable_rooms = [dict(room) for room in answers["room_requirements"]]
    unavailable_rooms[0]["required_furniture_ids"] = [unavailable_id]
    unavailable = client.post(
        f"/api/projects/{project['project_id']}/requirements/analyze",
        json={**answers, "room_requirements": unavailable_rooms, "allow_openrouter": False},
    )

    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "unknown_furniture_id"
    assert unavailable.status_code == 422
    assert unavailable.json()["detail"]["code"] == "furniture_model_unavailable"


def test_special_requirement_service_never_calls_ai_without_advanced_text_and_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        "backend.server.services.requirements_service._openrouter_suggestion",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    base = {
        "occupants": {"adults": 1, "children": 0, "elderly": 0, "pets": 0},
        "customization_mode": "advanced",
        "room_requirements": [{
            "room_id": "room-a",
            "room_type": "living_room",
            "uses": ["family_gathering"],
            "required_furniture_ids": [],
            "special_materials": [],
            "special_notes": "輪椅需要通行",
        }],
        "special_notes": "",
    }

    without_consent = analyze_special_requirements(
        base,
        valid_room_ids={"room-a"},
        allow_openrouter=False,
    )
    default_mode = analyze_special_requirements(
        {**base, "customization_mode": "default"},
        valid_room_ids={"room-a"},
        allow_openrouter=True,
    )

    assert calls == []
    assert without_consent["source"] == "local_rules"
    assert any(item["type"] == "accessibility" for item in without_consent["constraints"])
    assert default_mode["openrouter"]["status"] == "skipped_no_text"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_REQUIREMENTS_ENABLED", "1")
    with_consent = analyze_special_requirements(
        base,
        valid_room_ids={"room-a"},
        allow_openrouter=True,
    )
    assert len(calls) == 1
    assert with_consent["openrouter"]["sent"] is True
    assert with_consent["openrouter"]["status"] == "unavailable"
