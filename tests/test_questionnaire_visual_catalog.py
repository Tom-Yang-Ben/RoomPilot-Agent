from __future__ import annotations

from scripts.static_source_graph import (
    scene_controller_source,
    scene_stylesheet_source,
    scene_viewer_source,
)

import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

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
                suggestSharedRoomAnswers,
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


def test_confirmed_room_prefills_only_shared_unanswered_questions() -> None:
    result = _run_questionnaire_helpers(
        """
          const questions = [
            {
              question_id: "bedroom:ceiling-lighting",
              source_question_id: "ceiling-lighting",
              room_id: "bedroom",
              space_type: "all_rooms",
              options: [{ option_id: "recessed" }, { option_id: "surface" }],
            },
            {
              question_id: "bathroom:ceiling-lighting",
              source_question_id: "ceiling-lighting",
              room_id: "bathroom",
              space_type: "all_rooms",
              options: [{ option_id: "recessed" }, { option_id: "surface" }],
            },
            {
              question_id: "bathroom:bath-shower",
              source_question_id: "bath-shower",
              room_id: "bathroom",
              space_type: "bathroom",
              options: [{ option_id: "tub" }, { option_id: "shower" }],
            },
            {
              question_id: "bedroom:ceiling-plane",
              source_question_id: "ceiling-plane",
              room_id: "bedroom",
              space_type: "all_rooms",
              allow_both: true,
              options: [{ option_id: "flat" }, { option_id: "dropped" }],
            },
            {
              question_id: "bathroom:ceiling-plane",
              source_question_id: "ceiling-plane",
              room_id: "bathroom",
              space_type: "all_rooms",
              allow_both: true,
              options: [{ option_id: "flat" }, { option_id: "dropped" }],
            },
            {
              question_id: "living:ceiling-lighting",
              source_question_id: "ceiling-lighting",
              room_id: "living",
              space_type: "all_rooms",
              options: [{ option_id: "recessed" }, { option_id: "surface" }],
            },
          ];
          const answers = {
            "bedroom:ceiling-lighting": { optionId: "surface", custom: "方便維修" },
            "bedroom:ceiling-plane": { optionId: "both", custom: "" },
            "living:ceiling-lighting": { optionId: "recessed" },
          };
          console.log(JSON.stringify(suggestSharedRoomAnswers({
            questions,
            answers,
            sourceRoomId: "bedroom",
            targetRoomId: "bathroom",
          })));
        """
    )

    assert result == {
        "bathroom:ceiling-lighting": {
            "optionId": "surface",
            "custom": "方便維修",
            "suggested": True,
            "suggestedFromRoomId": "bedroom",
        },
        "bathroom:ceiling-plane": {
            "optionId": "both",
            "custom": "",
            "suggested": True,
            "suggestedFromRoomId": "bedroom",
        }
    }


def test_questionnaire_images_are_explicitly_planned_not_fabricated() -> None:
    catalog = load_questionnaire_visual_catalog()
    ready = [
        option
        for question in catalog["questions"]
        for option in question["options"]
        if option["generation_status"] == "ready"
    ]

    assert ready == []
    assert not (ROOT / "backend" / "server" / "static" / "questionnaire_images").exists()
    assert all(
        not option.get("image_sha256")
        for question in catalog["questions"]
        for option in question["options"]
    )


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
    assert payload["ready_image_count"] == 0
    assert len(payload["questions"]) == 55


def test_test2_questionnaire_ui_exposes_room_first_required_stages() -> None:
    static = ROOT / "backend" / "server" / "static"
    html = (static / "scene.html").read_text(encoding="utf-8")
    javascript = scene_controller_source(static)

    for stage in ("rooms", "profile", "summary"):
        assert f'data-questionnaire-stage="{stage}"' in html
        assert f'data-questionnaire-panel="{stage}"' in html
    assert 'data-questionnaire-stage="finishes"' not in html
    assert 'data-questionnaire-stage="visual"' not in html
    assert 'id="room-questionnaire"' not in html
    assert 'id="room-furniture-select"' not in html

    assert 'id="visual-question-card"' in html
    assert 'id="questionnaire-style-grid"' in html
    assert 'id="questionnaire-wall-options"' in html
    assert 'id="questionnaire-floor-options"' in html
    assert 'id="questionnaire-wall-color"' in html
    assert 'id="questionnaire-floor-color"' in html
    assert 'id="questionnaire-material-pairs"' in html
    assert 'id="questionnaire-ceiling-material"' in html
    assert 'id="questionnaire-ceiling-style"' in html
    assert 'id="questionnaire-air-conditioning"' in html
    assert 'id="questionnaire-plan-overlay"' in html
    assert 'id="questionnaire-finish-scope"' in html
    assert "ensureVisualQuestionnaireLoaded" in javascript
    assert "confirmQuestionnaireFinishes" in javascript
    assert "buildRoomRequirementsPayload" in javascript
    assert "visual_preferences: visualPreferences" in javascript
    assert "state.sceneData.questionnaire" in javascript
    assert "ceiling_color_hex" in javascript
    assert "questionnaireMaterialPairsForPack" in javascript
    assert "questionnaireMaterialPairCards" in javascript
    assert "isCurrentSelection: true" in javascript
    assert "目前選擇" in javascript
    assert "renderMaterialPairPreviews" in javascript
    assert "CEILING_DESIGN_PACKS" in javascript
    assert "selectQuestionnaireCeilingDesignPack" in javascript
    assert 'data-whole-house-style-pack="${escapeHtml(family.defaultPackId)}"' in javascript


def _scene_stylesheet(static) -> str:
    return scene_stylesheet_source(static)


def test_ceiling_choices_use_procedural_placeholders_without_photos() -> None:
    static = ROOT / "backend" / "server" / "static"
    stylesheet = _scene_stylesheet(static)

    assert 'ceiling-reference-real-homes-v1.png' not in stylesheet
    for style in ("exposed", "flat", "cove", "floating", "linear", "feature-pendant", "wood-grid"):
        assert f'data-ceiling-style-visual="{style}"]' in stylesheet
        assert f'data-ceiling-style-visual="{style}"]' in stylesheet
    assert "/static/questionnaire_images/" not in stylesheet


def test_every_ceiling_design_pack_has_its_own_picker_photo() -> None:
    """點進施工形式後的搭配卡用 data-ceiling-design-visual,與外層施工形式卡的
    data-ceiling-style-visual 是兩套鍵。只補外層那套時,對話框裡每張卡都沒有圖
    (2026-08-09 實際發生:CSS 只有 7 條 style-visual、0 條 design-visual)。
    每一組 CEILING_DESIGN_PACKS 都必須有自己的規則,引用的圖檔也必須存在。"""
    static = ROOT / "backend" / "server" / "static"
    stylesheet = _scene_stylesheet(static)
    packs_source = (static / "scene_style_packs.js").read_text(encoding="utf-8")

    block = packs_source.split("CEILING_DESIGN_PACKS = Object.freeze([", 1)[1].split("]);", 1)[0]
    pack_ids = re.findall(r'\{\s*id:\s*"([^"]+)"', block)
    assert len(pack_ids) >= 14, pack_ids

    for pack_id in pack_ids:
        assert f'data-ceiling-design-visual="{pack_id}"]' in stylesheet, pack_id

    # 規則存在不等於圖片存在——缺檔時卡片一樣是空白。
    for image in sorted(set(re.findall(r'url\("/static/questionnaire_images/([^"]+)"\)', stylesheet))):
        assert (static / "questionnaire_images" / image).is_file(), image


def test_questionnaire_ui_keeps_visual_catalog_for_rag_but_not_as_required_questions() -> None:
    static = ROOT / "backend" / "server" / "static"
    html = (static / "scene.html").read_text(encoding="utf-8")
    javascript = scene_controller_source(static)

    assert "全屋設定" in html
    assert "逐房需求與材質" in html
    assert 'id="questionnaire-air-conditioning"' in html
    assert 'id="questionnaire-furniture-preference-tags"' in html
    assert 'const profileQuestions = WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle");' in javascript
    assert 'answers.overallStyle = selectedFamily?.label || "";' in javascript
    assert "state.visualQuestions = [];" in javascript
    assert "state.visualQuestions = questionsForIndividualRooms" not in javascript
    assert "element.visualQuestionCard.hidden = true;" in javascript
    assert "選用途與家具；材質和照明在下方調整。" in javascript
    assert "請先完成這個房間的極與極題目。" not in javascript
    assert "applyAirConditioningToEligibleRooms" in javascript


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
    } == {"planned"}


def test_questionnaire_helpers_filter_rooms_and_enforce_both_gates() -> None:
    result = _run_questionnaire_helpers(
        """
          const questions = [
            { question_id: "bed", space_type: "bedroom" },
            { question_id: "living", space_type: "living_room" },
            { question_id: "shared", space_type: "all_rooms" },
          ];
          const selected = questionsForRooms(questions, [
            { id: "room-1", type: "bedroom" },
          ]);
          const bedrooms = questionsForRooms([
            { question_id: "bedroom", space_type: "bedroom" },
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
    assert result["bedroomQuestionIds"] == ["bedroom"]
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
            visualQuestions: [{
              question_id: "q-1",
              space_type: "primary_bedroom",
              title_zh: "明亮或沉穩",
              options: [],
            }],
            visualAnswers: { "q-1": { optionId: "both", custom: "依房間調整" } },
            skippedSpaceTypes: [],
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
    assert result["answeredSpaceCount"] == 1
    assert result["skippedSpaceCount"] == 0
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
    viewer = scene_viewer_source(ROOT / "backend" / "server" / "static")

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
