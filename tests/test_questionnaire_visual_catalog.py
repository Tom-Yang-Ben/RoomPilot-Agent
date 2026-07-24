from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.server.questionnaire_visuals import (
    QuestionnaireVisualStore,
    load_questionnaire_visual_catalog,
)
from backend.server import main


ROOT = Path(__file__).resolve().parents[1]
QUESTIONNAIRE_HELPERS = (
    ROOT / "backend" / "server" / "static" / "scene_questionnaire_test2.js"
)


def _run_questionnaire_helpers(script: str) -> dict:
    module_url = QUESTIONNAIRE_HELPERS.resolve().as_uri()
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            f"""
              import {{
                applyVisualPreferencesToSpecs,
                finishesGate,
                occupantsFromBasicAnswers,
                questionnaireSummary,
                questionsForRooms,
                visualQuestionnaireProgress,
              }} from {json.dumps(module_url)};
              {script}
            """,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_visual_catalog_keeps_all_test2_question_pairs() -> None:
    catalog = load_questionnaire_visual_catalog()

    assert len(catalog["questions"]) == 55
    assert sum(len(question["options"]) for question in catalog["questions"]) == 110
    assert all(len(question["options"]) == 2 for question in catalog["questions"])


def test_ready_questionnaire_images_are_valid_assets() -> None:
    catalog = load_questionnaire_visual_catalog()
    ready = [
        option
        for question in catalog["questions"]
        for option in question["options"]
        if option["generation_status"] == "ready"
    ]

    assert len(ready) == 8
    for option in ready:
        image_path = ROOT / "backend" / "server" / "static" / option["image_path"]
        assert image_path.is_file()
        with Image.open(image_path) as image:
            assert image.size == (1536, 1024)
            assert image.info["RoomPilotWatermark"] == "RoomPilot"
        assert option["image_sha256"] == hashlib.sha256(image_path.read_bytes()).hexdigest()


def test_visual_catalog_api_returns_planned_and_ready_questions(
    monkeypatch,
    tmp_path,
) -> None:
    store = QuestionnaireVisualStore(tmp_path / "questionnaire.sqlite3")
    store.sync(load_questionnaire_visual_catalog())
    monkeypatch.setattr(main, "QUESTIONNAIRE_VISUAL_STORE", store)
    client = TestClient(main.app)

    response = client.get("/api/questionnaire/visual-catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_count"] == 55
    assert payload["image_count"] == 110
    assert payload["ready_image_count"] == 8
    assert len(payload["questions"]) == 55


def test_test2_questionnaire_ui_exposes_all_required_stages() -> None:
    static = ROOT / "backend" / "server" / "static"
    html = (static / "scene.html").read_text(encoding="utf-8")
    javascript = (static / "scene_v2.js").read_text(encoding="utf-8")

    for stage in ("profile", "rooms", "visual", "finishes", "summary"):
        assert f'data-questionnaire-stage="{stage}"' in html
        assert f'data-questionnaire-panel="{stage}"' in html

    assert 'id="visual-question-card"' in html
    assert 'id="questionnaire-style-grid"' in html
    assert 'id="questionnaire-wall-options"' in html
    assert 'id="questionnaire-floor-options"' in html
    assert 'id="questionnaire-wall-color"' in html
    assert 'id="questionnaire-floor-color"' in html
    assert 'id="questionnaire-ceiling-material"' in html
    assert 'id="questionnaire-ceiling-style"' in html
    assert "ensureVisualQuestionnaireLoaded" in javascript
    assert "confirmQuestionnaireFinishes" in javascript
    assert "visual_preferences: visualPreferences" in javascript
    assert "state.sceneData.questionnaire" in javascript
    assert "ceiling_color_hex" in javascript


def test_questionnaire_catalog_json_remains_the_versioned_source() -> None:
    path = (
        ROOT
        / "backend"
        / "server"
        / "data"
        / "questionnaire_visual_catalog.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["question_count"] == 55
    assert payload["image_count"] == 110
    assert {
        option["generation_status"]
        for question in payload["questions"]
        for option in question["options"]
    } == {"planned", "ready"}


def test_questionnaire_helpers_filter_rooms_and_enforce_both_gates() -> None:
    result = _run_questionnaire_helpers(
        """
          const questions = [
            { question_id: "bed", space_type: "primary_bedroom" },
            { question_id: "living", space_type: "living_room" },
            { question_id: "shared", space_type: "all_rooms" },
          ];
          const selected = questionsForRooms(questions, [
            { id: "room-1", type: "bedroom" },
          ]);
          const bedrooms = questionsForRooms([
            { question_id: "primary", space_type: "primary_bedroom" },
            { question_id: "secondary", space_type: "secondary_bedroom" },
          ], [
            { id: "room-1", type: "bedroom" },
            { id: "room-2", type: "bedroom" },
          ]);
          const visual = visualQuestionnaireProgress({
            questions: selected,
            answers: { bed: { optionId: "left" } },
            skippedSpaceTypes: ["all_rooms"],
          });
          const incompleteFinishes = finishesGate({
            stylePackId: "pack-1",
            wallMaterial: "paint",
            wallColor: "#ffffff",
          });
          const completeFinishes = finishesGate({
            stylePackId: "pack-1",
            wallMaterial: "paint",
            wallColor: "#ffffff",
            floorMaterial: "wood",
            floorColor: "#a08060",
            ceilingMaterial: "flat-paint",
            ceilingStyle: "flat",
            lightStyle: "warm",
            confirmed: true,
          });
          console.log(JSON.stringify({
            questionIds: selected.map((item) => item.question_id),
            bedroomQuestionIds: bedrooms.map((item) => item.question_id),
            visual,
            incompleteFinishes,
            completeFinishes,
          }));
        """
    )

    assert result["questionIds"] == ["bed", "shared"]
    assert result["bedroomQuestionIds"] == ["primary", "secondary"]
    assert result["visual"] == {"completed": 2, "total": 2, "ready": True}
    assert result["incompleteFinishes"]["ready"] is False
    assert result["incompleteFinishes"]["missing"] == [
        "floor_material",
        "floor_color",
        "ceiling_material",
        "ceiling_style",
        "light_style",
    ]
    assert result["completeFinishes"] == {"ready": True, "missing": []}


def test_basic_answers_are_converted_to_scene_occupants() -> None:
    result = _run_questionnaire_helpers(
        """
          console.log(JSON.stringify({
            soloWithPet: occupantsFromBasicAnswers({
              household: "一人",
              membersAndPets: "有貓",
            }),
            threeGenerations: occupantsFromBasicAnswers({
              household: "三代同堂",
              membersAndPets: "有長輩",
            }),
          }));
        """
    )

    assert result["soloWithPet"] == {
        "adults": 1,
        "children": 0,
        "elderly": 0,
        "pets": 1,
    }
    assert result["threeGenerations"] == {
        "adults": 2,
        "children": 1,
        "elderly": 1,
        "pets": 0,
    }


def test_scene_generate_preserves_complete_test2_questionnaire() -> None:
    client = TestClient(main.app)
    test2 = {
        "catalog_version": "1.0.0",
        "basic": {"household": "一人"},
        "rooms": {"living-1": {"confirmed": True}},
        "visual_preferences": [{"question_id": "living-focus", "option_id": "social"}],
        "finishes": {"wallColor": "#ffffff"},
    }

    response = client.post(
        "/api/scene/generate",
        json={
            "client_brief": {
                "space": {"type": "living_room"},
                "style": {"preferred": ["modern"]},
                "occupants": {"adults": 1, "children": 0, "elderly": 0, "pets": 0},
            },
            "questionnaire": test2,
            "room_width_cm": 420,
            "room_depth_cm": 360,
            "required_furniture": [],
            "selected_furniture": [],
            "selected_furniture_exact": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["questionnaire"]["test2_questionnaire"] == test2
    assert response.json()["questionnaire"]["occupants"]["adults"] == 1


def test_questionnaire_summary_localizes_balanced_visual_choice() -> None:
    result = _run_questionnaire_helpers(
        """
          const summary = questionnaireSummary({
            basic: { household: "兩位大人" },
            roomAnswers: { bedroom: { confirmed: true } },
            visualQuestions: [{
              question_id: "q-1",
              title_zh: "明亮或沉穩",
              options: [],
            }],
            visualAnswers: { "q-1": { optionId: "both", custom: "依房間調整" } },
            finishes: { stylePackId: "pack-1" },
            stylePacks: [{
              id: "pack-1",
              styleLabel: "現代",
              name: "明亮留白",
            }],
          });
          console.log(JSON.stringify(summary));
        """
    )

    assert result["visualSelections"] == [
        {
            "questionId": "q-1",
            "question": "明亮或沉穩",
            "answer": "兩者平衡",
            "custom": "依房間調整",
        }
    ]
    assert result["finishes"]["style"] == "現代｜明亮留白"


def test_extreme_preferences_change_furniture_specs_before_layout() -> None:
    result = _run_questionnaire_helpers(
        """
          const specs = applyVisualPreferencesToSpecs(
            [
              ["sofa", "two-seat", "room answer", false],
              ["dining-table", "rect-4", "room answer", false],
            ],
            [{
              engine_effects: {
                sofa_layout: "sectional",
                dining_capacity: 6,
                entry_storage_priority: "high",
              },
            }],
          );
          console.log(JSON.stringify(specs));
        """
    )

    assert result[0][:2] == ["sofa", "l-shape"]
    assert result[1][:2] == ["dining-table", "rect-6"]
    assert result[2][0:2] == ["storage-cabinet", "tall"]
    assert result[2][3] is True


def test_viewer_consumes_questionnaire_ceiling_finish() -> None:
    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")

    assert "sceneData.design_choices?.ceiling_color_hex" in viewer
    assert "sceneData.design_choices?.ceiling_material" in viewer
    assert "panel.userData.ceilingMaterial" in viewer


def test_questionnaire_state_survives_project_save_and_reload() -> None:
    client = TestClient(main.app)
    created = client.post(
        "/api/projects",
        json={"name": f"Test2 questionnaire {uuid4().hex[:8]}"},
    ).json()["project"]
    requirements = {
        "basic": {"household": "兩位大人"},
        "basicConfirmed": True,
        "rooms": {
            "living-1": {
                "confirmed": True,
                "uses": ["日常生活"],
                "furniture": ["L 型沙發"],
            }
        },
        "keepExistingRoomIds": [],
        "questionnaireStage": "summary",
        "visualCatalogVersion": "1.0.0",
        "visualAnswers": {
            "living-sofa-layout": {
                "optionId": "sectional",
                "custom": "保留主要走道",
            }
        },
        "skippedVisualSpaceTypes": ["balcony"],
        "finishes": {
            "confirmed": True,
            "stylePackId": "scandinavian-01",
            "wallMaterial": "paint",
            "wallColor": "#f4f1eb",
            "floorMaterial": "wood",
            "floorColor": "#b99b78",
            "ceilingMaterial": "flat-paint",
            "ceilingStyle": "flat",
            "lightStyle": "warm",
            "ceilingColor": "#ffffff",
        },
    }

    saved = client.put(
        f"/api/projects/{created['project_id']}/workflow",
        json={
            "current_step": "requirements",
            "workflow": {"requirements": requirements},
        },
    )
    restored = client.get(
        f"/api/projects/{created['project_id']}"
    ).json()["project"]

    assert saved.status_code == 200
    assert restored["current_step"] == "requirements"
    assert restored["workflow"]["requirements"] == requirements
