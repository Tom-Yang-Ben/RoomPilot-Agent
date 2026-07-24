from __future__ import annotations

import hashlib
import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.server.main import _build_invited_client_brief, _questionnaire_risks


STATIC = ROOT / "backend" / "server" / "static"


def _asset_hash(filename: str) -> str:
    return hashlib.sha256((STATIC / filename).read_bytes()).hexdigest()[:12]


def test_every_supported_room_uses_two_visual_endpoints_and_explicit_preference_scale() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          ROOM_QUESTION_TEMPLATES,
          questionnaireImageManifest,
          roomTechnicalAxes,
          roomQuestionTemplate,
        }} from {json.dumps(module_uri)};

        const roomTypes = [
          "living_room",
          "bedroom",
          "dining_room",
          "kitchen",
          "bathroom",
          "balcony",
          "storage",
          "circulation",
        ];
        const summary = Object.fromEntries(roomTypes.map((roomType) => {{
          const template = roomQuestionTemplate(roomType);
          return [roomType, {{
            axisCount: template.axes.length,
            ids: template.axes.map((axis) => axis.id),
            endpointsReady: template.axes.every((axis) =>
              axis.options.length === 2
              && axis.options.map((option) => option.pole).join(",") === "a,b"
              && axis.options.every((option) => typeof option.imageKey === "string")
            ),
            preferenceScales: template.axes.map((axis) => axis.preferenceOptions.map((item) => item.value)),
            technicalIds: roomTechnicalAxes(roomType).map((axis) => axis.id),
          }}];
        }}));
        const bedroom = roomQuestionTemplate("bedroom");
        const sleepStorage = bedroom.axes.find((axis) => axis.id === "sleep_storage");
        const kitchen = roomQuestionTemplate("kitchen");
        const enclosure = kitchen.axes.find((axis) => axis.id === "kitchen_enclosure");
        const manifest = questionnaireImageManifest();
        console.log(JSON.stringify({{
          summary,
          sleepStorage,
          enclosure,
          templateCount: Object.keys(ROOM_QUESTION_TEMPLATES).length,
          manifest: {{
            total: manifest.length,
            unique: new Set(manifest.map((item) => item.image_key)).size,
            axisOptions: manifest.filter((item) => item.kind === "axis_option").length,
            materialOptions: manifest.filter((item) => item.kind === "material_option").length,
            nonCanonical: manifest.filter((item) => item.image_key.includes("_")).length,
          }},
        }}));
        """
    )

    assert result["templateCount"] >= 8
    assert result["manifest"]["total"] == result["manifest"]["unique"]
    assert result["manifest"]["axisOptions"] == 86
    assert result["manifest"]["materialOptions"] == 248
    assert result["manifest"]["nonCanonical"] == 0
    assert result["sleepStorage"]["options"][0]["label"] == "舒適休息、空間寬鬆"
    assert "留白睡眠" not in json.dumps(result, ensure_ascii=False)
    assert result["enclosure"]["mode"] == "exclusive"
    assert result["enclosure"]["preferenceOptions"] == []
    for room_type, summary in result["summary"].items():
        assert summary["axisCount"] == 3, room_type
        assert {"ceiling", "lighting"}.isdisjoint(summary["ids"])
        assert {"ceiling", "lighting"} <= set(summary["technicalIds"])
        assert summary["endpointsReady"] is True
        for scale in summary["preferenceScales"]:
            assert scale in (
                [],
                ["lean_a", "balanced", "lean_b"],
            )

    assert "air_conditioning" in result["summary"]["living_room"]["technicalIds"]
    assert "air_conditioning" in result["summary"]["bedroom"]["technicalIds"]
    assert "air_conditioning" in result["summary"]["dining_room"]["technicalIds"]
    for room_type in ("kitchen", "bathroom", "balcony", "storage", "circulation"):
        assert "air_conditioning" not in result["summary"][room_type]["technicalIds"]


def test_designer_room_questionnaire_owns_technical_choices_not_material_confirmation() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    requirements_html = html[
        html.index('id="requirements-step"'):html.index('id="design-preferences-step"')
    ]
    materials_html = html[
        html.index('id="design-preferences-step"'):html.index('id="layout-2d-step"')
    ]

    assert 'id="room-technical-preferences"' in requirements_html
    assert 'data-room-question-stage="technical"' in requirements_html
    assert "天花、冷氣與燈光" in requirements_html
    assert 'id="room-technical-preferences"' not in materials_html
    assert "天花、冷氣與燈光" not in materials_html


def test_room_cannot_finish_until_its_technical_questionnaire_is_answered() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ requirementsGate }} from {json.dumps(module_uri)};

        const room = {{
          id: "bedroom-1",
          label: "臥室",
          type: "bedroom",
        }};
        const baseAnswer = {{
          schemaVersion: "3.0",
          confirmed: true,
          uses: ["睡眠休息"],
          axes: {{
            sleep_storage: "a",
            work_presence: "balanced",
            bed_access: "lean_b",
          }},
        }};
        const before = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms: [room],
          answers: {{ "bedroom-1": baseAnswer }},
        }});
        const after = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms: [room],
          answers: {{
            "bedroom-1": {{
              ...baseAnswer,
              axes: {{
                ...baseAnswer.axes,
                ceiling: "a",
                air_conditioning: "a",
                lighting: "balanced",
              }},
            }},
          }},
        }});
        console.log(JSON.stringify({{ before, after }}));
        """
    )

    assert result["before"]["ready"] is False
    assert result["before"]["unresolvedRoomIds"] == ["bedroom-1"]
    assert result["after"]["ready"] is True
    assert result["after"]["unresolvedRoomIds"] == []


def test_incomplete_legacy_room_is_not_exported_as_confirmed() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildClientBrief,
          buildQuestionnaireDocument,
        }} from {json.dumps(module_uri)};

        const room = {{
          id: "bedroom-1",
          label: "Bedroom",
          type: "bedroom",
        }};
        const answer = {{
          schemaVersion: "3.0",
          confirmed: true,
          uses: ["sleep"],
          axes: {{
            sleep_storage: "a",
            work_presence: "balanced",
            bed_access: "lean_b",
          }},
        }};
        const brief = buildClientBrief({{
          rooms: [room],
          answers: {{ "bedroom-1": answer }},
        }});
        const document = buildQuestionnaireDocument({{
          projectId: "project-1",
          rooms: [room],
          answers: {{ "bedroom-1": answer }},
        }});
        console.log(JSON.stringify({{
          briefStatus: brief.rooms["bedroom-1"].planning_status,
          documentStatus: document.rooms[0].planning_status,
        }}));
        """
    )

    assert result == {
        "briefStatus": "incomplete",
        "documentStatus": "incomplete",
    }


def test_questionnaire_reconciles_legacy_room_ids_without_reasking_same_space() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ reconcileRoomQuestionnaireState }} from {json.dumps(module_uri)};

        const currentBedroomDraft = {{
          schemaVersion: "3.0",
          confirmed: false,
          axes: {{ sleep_storage: "a" }},
        }};
        const legacyBedroomDraft = {{
          schemaVersion: "3.0",
          confirmed: false,
          axes: {{ sleep_storage: "balanced" }},
        }};
        const legacyKitchenAnswer = {{
          schemaVersion: "3.0",
          confirmed: true,
          axes: {{
            kitchen_enclosure: "a",
            cooking_intensity: "lean_a",
            worktop_storage: "balanced",
          }},
        }};
        const reconciled = reconcileRoomQuestionnaireState({{
          rooms: [
            {{ id: "room-1", label: "臥室", type: "bedroom" }},
            {{ id: "room-2", label: "廚房", type: "kitchen" }},
          ],
          answers: {{
            "bedroom-1": legacyBedroomDraft,
            "kitchen-1": legacyKitchenAnswer,
            "room-1": currentBedroomDraft,
          }},
          keepExistingRoomIds: [
            "bedroom-1",
            "bedroom-2",
            "kitchen-1",
          ],
        }});
        console.log(JSON.stringify(reconciled));
        """
    )

    assert set(result["answers"]) == {"room-1", "room-2"}
    assert result["answers"]["room-1"]["axes"]["sleep_storage"] == "a"
    assert result["answers"]["room-2"]["axes"]["kitchen_enclosure"] == "a"
    assert result["keepExistingRoomIds"] == []
    assert result["discardedRoomIds"] == ["bedroom-1", "bedroom-2"]


def test_questionnaire_reconciles_same_type_rooms_by_saved_geometry_not_list_order() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          questionnaireRoomIdentity,
          reconcileRoomQuestionnaireState,
        }} from {json.dumps(module_uri)};

        const leftBedroom = {{
          id: "old-left",
          label: "臥室 A",
          type: "bedroom",
          polygon_m: [
            {{ x: 0, y: 0 }}, {{ x: 3, y: 0 }},
            {{ x: 3, y: 3 }}, {{ x: 0, y: 3 }},
          ],
        }};
        const rightBedroom = {{
          id: "old-right",
          label: "臥室 B",
          type: "bedroom",
          polygon_m: [
            {{ x: 5, y: 0 }}, {{ x: 8, y: 0 }},
            {{ x: 8, y: 3 }}, {{ x: 5, y: 3 }},
          ],
        }};
        const reconciled = reconcileRoomQuestionnaireState({{
          rooms: [
            {{ ...rightBedroom, id: "room-1" }},
            {{ ...leftBedroom, id: "room-2" }},
          ],
          answers: {{
            "bedroom-1": {{
              schemaVersion: "3.0",
              confirmed: true,
              roomIdentity: questionnaireRoomIdentity(leftBedroom),
              axes: {{ sleep_storage: "a" }},
            }},
            "bedroom-2": {{
              schemaVersion: "3.0",
              confirmed: true,
              roomIdentity: questionnaireRoomIdentity(rightBedroom),
              axes: {{ sleep_storage: "b" }},
            }},
          }},
        }});
        console.log(JSON.stringify(reconciled));
        """
    )

    assert result["answers"]["room-1"]["axes"]["sleep_storage"] == "b"
    assert result["answers"]["room-2"]["axes"]["sleep_storage"] == "a"


def test_questionnaire_reconciles_keep_existing_room_by_saved_geometry() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          questionnaireRoomIdentity,
          reconcileRoomQuestionnaireState,
        }} from {json.dumps(module_uri)};

        const leftBedroom = {{
          id: "old-left",
          label: "臥室（一）",
          type: "bedroom",
          polygon_m: [
            {{ x: 0, y: 0 }}, {{ x: 3, y: 0 }},
            {{ x: 3, y: 3 }}, {{ x: 0, y: 3 }},
          ],
        }};
        const rightBedroom = {{
          id: "old-right",
          label: "臥室（二）",
          type: "bedroom",
          polygon_m: [
            {{ x: 5, y: 0 }}, {{ x: 8, y: 0 }},
            {{ x: 8, y: 3 }}, {{ x: 5, y: 3 }},
          ],
        }};
        const reconciled = reconcileRoomQuestionnaireState({{
          rooms: [
            {{ ...rightBedroom, id: "room-1" }},
            {{ ...leftBedroom, id: "room-2" }},
          ],
          answers: {{
            "bedroom-1": {{
              schemaVersion: "3.0",
              confirmed: false,
              keepExisting: true,
              roomIdentity: questionnaireRoomIdentity(leftBedroom),
              axes: {{}},
            }},
          }},
          keepExistingRoomIds: ["bedroom-1"],
        }});
        console.log(JSON.stringify(reconciled));
        """
    )

    assert result["keepExistingRoomIds"] == ["room-2"]
    assert result["answers"]["room-2"]["keepExisting"] is True
    assert result["discardedRoomIds"] == []


def test_questionnaire_builds_engine_ready_brief_and_numbered_safety_reminders() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildClientBrief,
          collectQuestionnaireWarnings,
          questionnaireCompletion,
          resolveAxisChoice,
          roomQuestionTemplate,
          WHOLE_HOUSE_QUESTIONS,
        }} from {json.dumps(module_uri)};

        const kitchen = roomQuestionTemplate("kitchen");
        const enclosure = kitchen.axes.find((axis) => axis.id === "kitchen_enclosure");
        let mutualExclusionError = "";
        try {{
          resolveAxisChoice(enclosure, "both");
        }} catch (error) {{
          mutualExclusionError = error.message;
        }}

        const rooms = [
          {{ id: "kitchen-1", label: "廚房", type: "kitchen" }},
          {{ id: "bedroom-1", label: "主臥", type: "bedroom" }},
        ];
        const answers = {{
          "kitchen-1": {{
            schemaVersion: "3.0",
            confirmed: true,
            uses: ["每日下廚"],
            furniture: ["冰箱", "中島"],
                axes: {{
                  ...Object.fromEntries(kitchen.axes.map((axis) => [
                    axis.id,
                    axis.id === "kitchen_enclosure"
                        ? "a"
                        : "a",
                  ])),
                  ceiling: "a",
                  lighting: "balanced",
                }},
            customNotes: {{
              kitchen_enclosure: "希望中間有可關閉的玻璃窗",
            }},
          }},
        }};
        const basicAnswers = Object.fromEntries(
          WHOLE_HOUSE_QUESTIONS.map((question) => [
            question.id,
            question.type === "multi"
              ? [question.options[0].value]
              : question.options[0].value,
          ])
        );
        basicAnswers.residents = ["adult", "child"];
        basicAnswers.ageNeeds = ["school_age"];
        basicAnswers.scheduleInterference = ["noise_conflict"];
        basicAnswers.homeWorkStudyCount = "one_regular";
        basicAnswers.homeWorkStudyNeeds = ["quiet_focus"];
        basicAnswers.futureChanges = ["children_grow"];
        basicAnswers.hostingFrequency = "small_regular";
        basicAnswers.hostingNeeds = ["meal"];
        basicAnswers.budgetPriority = "balanced";
        basicAnswers.budgetRange = "100_200";
        basicAnswers.targetTimeline = "six_to_twelve_months";
        basicAnswers.immutableNeeds = ["fixed_pipes"];
        basicAnswers.notes = {{ futureChanges: "三年內書房可能改成嬰兒房" }};
        const completion = questionnaireCompletion({{
          basicAnswers,
          rooms,
          answers,
          keepExistingRoomIds: [],
        }});
        const warnings = collectQuestionnaireWarnings({{ rooms, answers }});
        const textWarnings = collectQuestionnaireWarnings({{
          rooms: [rooms[1]],
          answers: {{
            "bedroom-1": {{
              axes: {{}},
              personalNeeds: "新增插座，並把洗手台移位到這個房間",
            }},
          }},
        }});
        const brief = buildClientBrief({{
          basicAnswers,
          rooms,
          answers,
          keepExistingRoomIds: ["bedroom-1"],
          designerNotes: "確認排煙路徑後再定案",
        }});
        console.log(JSON.stringify({{
          mutualExclusionError,
          completion,
          warnings,
          textWarnings,
          brief,
        }}));
        """
    )

    assert result["mutualExclusionError"] == "mutually_exclusive_axis"
    assert result["completion"]["nextIncomplete"]["roomId"] == "bedroom-1"
    assert result["completion"]["completedRooms"] == 1
    assert result["warnings"][0]["position"] == "1/3"
    assert {warning["risk"] for warning in result["warnings"]} == {
        "wall",
        "gas",
        "smoke_exhaust",
    }
    assert {"electricity", "plumbing", "function_relocation"} <= {
        warning["risk"] for warning in result["textWarnings"]
    }
    brief = result["brief"]
    assert brief["schema_version"] == "3.0"
    assert brief["rooms"]["kitchen-1"]["structure_strategy"] == "compare_changed_and_unchanged"
    assert brief["rooms"]["kitchen-1"]["material_preferences"]["status"] == "not_defined"
    assert brief["rooms"]["bedroom-1"]["planning_status"] == "keep_existing"
    assert brief["designer_notes"] == "確認排煙路徑後再定案"
    assert brief["basic_notes"]["futureChanges"] == "三年內書房可能改成嬰兒房"


def test_axis_preference_contract_resolves_extremes_bias_balance_and_exclusive_axes() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          resolveAxisChoice,
          roomQuestionTemplate,
        }} from {json.dumps(module_uri)};

        const bedroom = roomQuestionTemplate("bedroom");
        const sleepStorage = bedroom.axes.find((axis) => axis.id === "sleep_storage");
        const kitchen = roomQuestionTemplate("kitchen");
        const enclosure = kitchen.axes.find((axis) => axis.id === "kitchen_enclosure");
        const cooking = kitchen.axes.find((axis) => axis.id === "cooking_intensity");
        const values = ["a", "lean_a", "balanced", "lean_b", "b"];
        const resolved = Object.fromEntries(
          values.map((value) => [value, resolveAxisChoice(sleepStorage, value)])
        );
        let exclusiveBalanceError = "";
        try {{
          resolveAxisChoice(enclosure, "balanced");
        }} catch (error) {{
          exclusiveBalanceError = error.message;
        }}
        console.log(JSON.stringify({{
          resolved,
          exclusiveBalanceError,
          cookingLeanA: resolveAxisChoice(cooking, "lean_a"),
        }}));
        """
    )

    assert result["resolved"]["a"]["selected_label"] == "舒適休息、空間寬鬆"
    assert result["resolved"]["lean_a"]["selected_label"].startswith("偏重 A")
    assert result["resolved"]["balanced"]["selected_label"] == "兩者平衡"
    assert result["resolved"]["lean_b"]["selected_label"].startswith("偏重 B")
    assert result["resolved"]["b"]["selected_label"] == "完整衣櫃、收納優先"
    assert len(result["resolved"]["balanced"]["image_keys"]) == 2
    assert set(result["cookingLeanA"]["riskTags"]) == {"gas", "smoke_exhaust"}
    assert len(result["cookingLeanA"]["image_keys"]) == 2
    assert result["exclusiveBalanceError"] == "mutually_exclusive_axis"


def test_basic_questionnaire_separates_people_behaviour_budget_and_timeline() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ WHOLE_HOUSE_QUESTIONS }} from {json.dumps(module_uri)};
        const questions = Object.fromEntries(
          WHOLE_HOUSE_QUESTIONS.map((question) => [question.id, {{
            type: question.type,
            required: question.required,
            optionCount: question.options.length,
            exclusiveValues: question.exclusiveValues || [],
          }}])
        );
        console.log(JSON.stringify({{
          ids: WHOLE_HOUSE_QUESTIONS.map((question) => question.id),
          questions,
        }}));
        """
    )

    assert result["ids"] == [
        "residents",
        "residentCount",
        "ageNeeds",
        "scheduleInterference",
        "homeWorkStudyCount",
        "homeWorkStudyNeeds",
        "futureChanges",
        "hostingFrequency",
        "hostingNeeds",
        "budgetPriority",
        "budgetRange",
        "targetTimeline",
        "immutableNeeds",
    ]
    assert result["questions"]["scheduleInterference"]["type"] == "multi"
    assert result["questions"]["homeWorkStudyNeeds"]["type"] == "multi"
    assert result["questions"]["hostingNeeds"]["type"] == "multi"
    assert result["questions"]["budgetRange"]["optionCount"] >= 5
    assert result["questions"]["targetTimeline"]["optionCount"] >= 5
    assert "same_schedule" in result["questions"]["scheduleInterference"]["exclusiveValues"]


def test_ceiling_choice_blocks_when_estimated_finished_height_is_below_designer_limit() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          validateCeilingPreference,
          validateQuestionnaireCeilings,
        }} from {json.dumps(module_uri)};
        const bedroom = {{
          id: "bedroom-1",
          label: "主臥",
          type: "bedroom",
        }};
        console.log(JSON.stringify({{
          flat: validateCeilingPreference({{
            rawHeightCm: 250,
            minimumFinishedHeightCm: 240,
            choice: "a",
          }}),
          dropped: validateCeilingPreference({{
            rawHeightCm: 250,
            minimumFinishedHeightCm: 240,
            choice: "b",
          }}),
          finalGate: validateQuestionnaireCeilings({{
            rooms: [bedroom],
            answers: {{
              "bedroom-1": {{
                confirmed: true,
                axes: {{ ceiling: "b" }},
              }},
            }},
            roomHeightCm: 250,
            minimumFinishedHeightCm: 240,
          }}),
        }}));
        """
    )

    assert result["flat"]["ready"] is True
    assert result["flat"]["estimatedFinishedHeightCm"] == 250
    assert result["dropped"]["ready"] is False
    assert result["dropped"]["code"] == "minimum_finished_height"
    assert result["dropped"]["estimatedFinishedHeightCm"] == 225
    assert result["finalGate"]["ready"] is False
    assert result["finalGate"]["firstInvalid"]["roomId"] == "bedroom-1"


def test_room_summary_explains_selection_basis_and_preserves_other_approach() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildRoomPreferenceSummary,
          roomQuestionTemplate,
        }} from {json.dumps(module_uri)};
        const room = {{ id: "bedroom-1", label: "主臥", type: "bedroom" }};
        const template = roomQuestionTemplate(room.type);
        const answer = {{
          axes: Object.fromEntries(template.axes.map((axis) => [
            axis.id,
            axis.mode === "exclusive" ? "a" : "lean_a",
          ])),
          customNotes: {{
            sleep_storage: "床尾仍保留一座矮櫃，不做到頂。",
          }},
        }};
        console.log(JSON.stringify(buildRoomPreferenceSummary(room, answer)));
        """
    )

    assert result["headline"].startswith("主臥")
    assert result["decisions"][0]["preference"] == "lean_a"
    assert result["decisions"][0]["basis"]
    assert result["other_approaches"] == [
        "睡眠與收納：床尾仍保留一座矮櫃，不做到頂。"
    ]


def test_questionnaire_normalizes_exclusive_quick_choices_and_rejects_legacy_answers() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          normalizeQuickValues,
          questionnaireCompletion,
          roomQuestionTemplate,
          WHOLE_HOUSE_QUESTIONS,
        }} from {json.dumps(module_uri)};
        const age = WHOLE_HOUSE_QUESTIONS.find((item) => item.id === "ageNeeds");
        const template = roomQuestionTemplate("dormitory");
        const basicAnswers = Object.fromEntries(
          WHOLE_HOUSE_QUESTIONS.map((item) => [item.id, item.type === "multi" ? ["ok"] : "ok"])
        );
        const completion = questionnaireCompletion({{
          basicAnswers,
          rooms: [{{ id: "room-1", label: "臥室", type: "dormitory" }}],
          answers: {{
            "room-1": {{ confirmed: true, uses: ["睡眠休息"] }},
          }},
        }});
        console.log(JSON.stringify({{
          normalized: normalizeQuickValues(age, ["none", "aging"]),
          firstUse: template.uses[0],
          completion,
        }}));
        """
    )

    assert result["normalized"] == ["aging"]
    assert result["firstUse"] == "睡眠休息"
    assert result["completion"]["ready"] is False
    assert result["completion"]["nextIncomplete"]["roomId"] == "room-1"


def test_questionnaire_document_keeps_human_labels_image_keys_and_agent_brief() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildQuestionnaireDocument,
          roomQuestionTemplate,
          roomTechnicalAxes,
          WHOLE_HOUSE_QUESTIONS,
        }} from {json.dumps(module_uri)};

        const room = {{ id: "living-1", label: "客廳", type: "living_room" }};
        const template = roomQuestionTemplate(room.type);
        const basicAnswers = Object.fromEntries(
          WHOLE_HOUSE_QUESTIONS.map((question) => [
            question.id,
            question.type === "multi"
              ? [question.options[0].value]
              : question.options[0].value,
          ])
        );
        basicAnswers.notes = {{ residents: "兩位成人與一隻貓" }};
        const answer = {{
          schemaVersion: "3.0",
          confirmed: true,
          stageNotes: {{
            uses: "需要瑜珈與投影兩種未列出的使用情境",
            furniture: "保留既有唱片櫃並新增展示層架",
          }},
          axes: Object.fromEntries(
            [...template.axes, ...roomTechnicalAxes(room.type)]
              .map((axis) => [axis.id, "a"])
          ),
          customNotes: {{ openness_storage: "電視牆保留單側收納" }},
          uses: ["日常休息"],
          furniture: ["沙發", "茶几"],
          priority: "走道優先",
          personalNeeds: "掃地機需回充",
          materialPreferences: {{
            wall: ["paint"],
            floor: ["wood"],
            furniture: ["fabric"],
            cuts: ["電視牆左右分材"],
          }},
        }};
        const document = buildQuestionnaireDocument({{
          projectId: "project-1",
          basicAnswers,
          rooms: [room],
          answers: {{ "living-1": answer }},
          keepExistingRoomIds: [],
          designerNotes: "確認插座位置",
        }});
        console.log(JSON.stringify(document));
        """
    )

    assert result["document_type"] == "roompilot.requirements_questionnaire"
    assert result["schema_version"] == "3.0"
    assert result["project_id"] == "project-1"
    assert result["image_assets"]["status"] == "partially_ready"
    assert result["basic_questions"][0] == {
        "question_id": "residents",
        "label": "實際居住成員",
        "answer_type": "multi",
        "required": True,
        "selected_values": ["adult"],
        "selected_labels": ["成人"],
        "note": "兩位成人與一隻貓",
    }
    room = result["rooms"][0]
    assert room["planning_status"] == "confirmed"
    assert room["axes"][0]["axis_id"] == "openness_storage"
    assert room["axes"][0]["selected_label"] == "寬大走道、視線通透"
    assert room["axes"][0]["image_keys"] == [
        "living-room/axis/openness-storage/open-flow"
    ]
    assert room["axes"][0]["image_status"] == "ready"
    assert [axis["axis_id"] for axis in room["axes"][-3:]] == [
        "ceiling",
        "air_conditioning",
        "lighting",
    ]
    assert room["axes"][0]["available_options"][1] == {
        "pole": "b",
        "value": "storage_wall",
        "label": "整面收納、機能集中",
        "image_key": "living-room/axis/openness-storage/storage-wall",
        "image_status": "ready",
        "risk_tags": [],
    }
    assert (
        "living-room/axis/openness-storage/storage-wall"
        in result["image_assets"]["required_image_keys"]
    )
    assert room["material_preferences"]["cuts"] == ["電視牆左右分材"]
    assert room["stage_notes"] == {
        "uses": "需要瑜珈與投影兩種未列出的使用情境",
        "furniture": "保留既有唱片櫃並新增展示層架",
    }
    assert result["client_brief"]["rooms"]["living-1"]["stage_notes"] == room["stage_notes"]
    assert result["client_brief"]["rooms"]["living-1"]["furniture_requirements"] == [
        "沙發",
        "茶几",
    ]


def test_invited_and_designer_brief_builders_keep_the_same_room_contract() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    room = {"id": "living-1", "label": "客廳", "type": "living_room"}
    answer = {
        "schemaVersion": "3.0",
        "confirmed": True,
        "uses": ["日常休息"],
        "furniture": ["沙發"],
        "axes": {
            "openness_storage": "lean_a",
            "social_focus": "a",
            "seating_flexibility": "balanced",
            "ceiling": "a",
            "air_conditioning": "a",
            "lighting": "lean_b",
        },
        "customNotes": {"openness_storage": "電視牆保留矮櫃"},
        "stageNotes": {
            "uses": "需要瑜珈與投影",
            "furniture": "保留既有唱片櫃",
        },
    }
    result = run_workflow_script(
        f"""
        import {{ buildClientBrief }} from {json.dumps(module_uri)};
        const brief = buildClientBrief({{
          rooms: [{json.dumps(room, ensure_ascii=False)}],
          answers: {{ "living-1": {json.dumps(answer, ensure_ascii=False)} }},
        }});
        console.log(JSON.stringify(brief.rooms["living-1"]));
        """
    )
    invited = _build_invited_client_brief(
        [room],
        {
            "schemaVersion": "3.0",
            "rooms": {"living-1": answer},
        },
    )["rooms"]["living-1"]

    for key in (
        "preference_axis_details",
        "integrated_summary",
        "stage_notes",
        "structure_strategy",
        "safety_risks",
    ):
        assert invited[key] == result[key]


def test_backend_risk_rules_cover_room_aliases_and_non_extreme_preferences() -> None:
    assert _questionnaire_risks(
        {"id": "bath-1", "label": "浴廁", "type": "toilet"},
        {"axes": {"bath_mode": "lean_a"}},
    ) == ["plumbing", "drainage"]
    assert _questionnaire_risks(
        {"id": "balcony-1", "label": "陽台", "type": "balcony"},
        {"axes": {"balcony_role": "lean_b"}},
    ) == ["plumbing", "drainage"]


def test_client_warning_navigation_restarts_at_first_warning_after_room_switch() -> None:
    source = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")

    assert "const roomChanged = state.activeRoomId !== roomId;" in source
    assert "if (roomChanged) state.activeWarningIndex = 0;" in source


def test_step_six_exposes_guided_navigation_shortcuts_materials_and_brief_preview() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    for expected in (
        "目前只選擇格局；色卡與風格尚未定義。",
        'id="questionnaire-mode"',
        'id="jump-next-incomplete"',
        'id="previous-question-room"',
        'id="copy-room-source"',
        'id="copy-room-answer"',
        'id="random-room-inspiration"',
        'id="keep-room-existing"',
        'id="room-axis-options"',
        'id="room-material-preferences"',
        'id="room-color-preference"',
        'id="room-finish-preference"',
        'id="minimum-finished-height-cm"',
        'id="ceiling-height-reference"',
        'id="questionnaire-warning-position"',
        'id="previous-questionnaire-warning"',
        'id="next-questionnaire-warning"',
        'id="designer-questionnaire-notes"',
        'id="client-brief-preview"',
        'id="download-questionnaire-json"',
        'id="basic-question-progress"',
        'id="previous-basic-question"',
        'id="next-basic-question"',
        'id="room-question-progress"',
        'id="previous-room-question"',
        'id="next-room-question"',
        'id="create-questionnaire-invite"',
        'id="revoke-all-questionnaire-invites"',
    ):
        assert expected in html

    for expected in (
        "questionnaireCompletion(",
        "collectQuestionnaireWarnings(",
        "buildClientBrief(",
        "cloneRoomAnswer(",
        'scheduleSave("requirements")',
        "renderRoomAxes",
        "renderQuestionnaireWarning",
        "jumpToNextIncomplete",
        "renderBasicQuestionStep",
        "renderRoomQuestionStep",
        "buildQuestionnaireDocument(",
        "downloadQuestionnaireJson",
            "captureActiveDesignerRoomDraft",
            "forceReload",
            "requirementsHaveState",
            "validateQuestionnaireCeilings(",
            "updateCeilingHeightReference",
    ):
        assert expected in controller
    assert 'id="room-furniture-select"' not in html

    client_html = (STATIC / "questionnaire.html").read_text(encoding="utf-8")
    client_controller = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")
    for expected in (
        'id="questionnaire-client-random"',
        'id="questionnaire-client-copy-source"',
        'id="questionnaire-client-copy"',
        'id="questionnaire-client-wall"',
        'id="questionnaire-client-floor"',
        'id="questionnaire-client-furniture-material"',
        'id="questionnaire-client-color"',
        'id="questionnaire-client-finish"',
        'id="questionnaire-client-material-cuts"',
        'id="questionnaire-client-basic-progress"',
        'id="questionnaire-client-basic-previous"',
        'id="questionnaire-client-basic-next"',
        'id="questionnaire-client-room-progress"',
        'id="questionnaire-client-room-previous-question"',
        'id="questionnaire-client-room-next-question"',
        'id="questionnaire-client-warning"',
        'id="questionnaire-client-warning-position"',
        'id="questionnaire-client-warning-previous"',
        'id="questionnaire-client-warning-next"',
    ):
        assert expected in client_html
    assert "runSaveAction" in client_controller
    assert "base_updated_at" in client_controller
    assert "renderBasicQuestionStep" in client_controller
    assert "renderRoomQuestionStep" in client_controller
    assert "captureActiveClientRoomDraft" in client_controller
    assert "persist({ quiet: true })" in client_controller
    assert "persistQueue" in client_controller
    assert "clearTimeout(draftPersistTimer);" in client_controller
    assert "validateQuestionnaireTechnicalCeiling({" in client_controller
    assert "validatePreference: validateCeilingPreference" in client_controller
    assert "renderClientQuestionnaireWarning" in client_controller
    assert "state.roomWarnings = summary.warnings" in client_controller
    assert "reconcileRoomQuestionnaireState({" in client_controller
    assert '>選擇 1/3</strong>' in html
    assert '>選擇 1/3</strong>' in client_html


def test_client_questionnaire_never_shows_basic_and_room_panels_at_the_same_time() -> None:
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert "#questionnaire-client-basic[hidden]" in css
    assert "#questionnaire-client-room[hidden]" in css
    assert ".rp-questionnaire-warning[hidden]" in css
    assert "display: none !important;" in css


def test_designer_questionnaire_focuses_one_question_and_locates_the_active_room() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    client_html = (STATIC / "questionnaire.html").read_text(encoding="utf-8")
    client_controller = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    for expected in (
        'id="questionnaire-room-locator"',
        'id="questionnaire-room-locator-title"',
        'id="requirements-plan-stage"',
        'id="requirements-plan-image"',
        'id="requirements-plan-overlay"',
        'id="questionnaire-project-tools"',
        'id="questionnaire-room-tools"',
        'id="room-use-note"',
        'id="room-furniture-note"',
    ):
        assert expected in html

    assert "element.questionnaireRoomLocatorTitle.textContent = room.label" in controller
    assert "element.questionnaireRoomLocator.hidden = false" in controller
    assert "requestAnimationFrame(syncRequirementsLocator)" in controller
    assert "scheduleDesignerQuestionnaireDraftSave" in controller
    assert "clearTimeout(designerDraftSaveTimer)" in controller
    assert "rebaseSerializedSave(serialized)" in controller
    assert "revokeAllQuestionnaireInvites" in controller
    assert 'data-requirement-room="${escapeHtml(room.id)}"' in controller
    for expected in (
        'id="questionnaire-client-room-locator"',
        'id="questionnaire-client-room-locator-title"',
        'id="questionnaire-client-plan-image"',
        'id="questionnaire-client-plan-overlay"',
        'id="questionnaire-client-room-use-note"',
        'id="questionnaire-client-room-furniture-note"',
    ):
        assert expected in client_html
    assert 'data-client-plan-room="${escapeHtml(room.id)}"' in client_controller
    assert "renderClientRoomLocator()" in client_controller
    assert ".rp-room-locator" in css
    assert ".rp-questionnaire-project-tools" in css
    assert "#requirements-plan-overlay {\n  pointer-events: auto;" in css
    client_plan_css = css.split(".rp-client-mini-plan", 1)[1].split("}", 1)[0]
    assert "max-width: 240px" in client_plan_css
    assert "max-height: none" in client_plan_css


def test_room_summary_precedes_the_only_manual_note_and_priority_is_not_reasked() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    summary_at = html.index('id="room-integrated-summary"')
    note_at = html.index('id="room-personal-needs"')
    room_tools_end = html.index("</details>", html.index('id="questionnaire-room-tools"'))

    assert room_tools_end < summary_at < note_at
    assert 'id="room-priority"' not in html
    assert "收納與使用優先順序（選填）" not in html
    assert 'placeholder="沒有補充可留白，系統輸出會記為「無」。"' in html
    assert ">無</textarea>" not in html
    assert "roomPriority" not in controller
    assert "personalNeeds: element.roomPersonalNeeds.value.trim()" in controller
    assert 'existing?.personalNeeds === "無"' in controller


def test_browser_e2e_extra_and_visual_status_require_real_display_urls() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (STATIC / "scene_requirements.js").read_text(encoding="utf-8")

    assert 'e2e = [' in pyproject
    assert '"selenium>=4.45"' in pyproject
    assert "QUESTIONNAIRE_IMAGE_URLS.has(imageKey)" in requirements


def test_empty_room_note_is_exported_as_none_in_all_questionnaire_json() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildClientBrief,
          buildQuestionnaireDocument,
        }} from {json.dumps(module_uri)};

        const room = {{ id: "bedroom-1", label: "臥室", type: "bedroom" }};
        const answer = {{
          schemaVersion: "3.0",
          confirmed: true,
          uses: ["睡眠休息"],
          axes: {{
            sleep_storage: "a",
            work_function: "balanced",
            bed_circulation: "lean_b",
          }},
          personalNeeds: "",
        }};
        const brief = buildClientBrief({{
          rooms: [room],
          answers: {{ "bedroom-1": answer }},
        }});
        const document = buildQuestionnaireDocument({{
          rooms: [room],
          answers: {{ "bedroom-1": answer }},
        }});
        console.log(JSON.stringify({{
          brief: brief.rooms["bedroom-1"].personal_needs,
          document: document.rooms[0].personal_needs,
        }}));
        """
    )

    assert result == {"brief": "無", "document": "無"}


def test_room_axes_render_two_image_endpoints_preference_row_and_collapsed_other_approach() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    client_controller = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")
    wizard = (STATIC / "questionnaire_wizard.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert 'id="designer-note-tool"' in html
    assert 'class="rp-designer-note-tool"' in html
    assert "設計師筆記" in html
    assert html.index('id="designer-note-tool"') > html.index('id="realistic-3d-step"')
    assert 'class="rp-axis-custom-approach"' in wizard
    assert "補充我的想法（選填）" in wizard
    assert "補充我的想法（已填）" in wizard
    assert "可補充 A／B 未涵蓋的做法，設計師會記錄進需求。" in wizard
    assert 'placeholder="${escapeQuestionnaireHtml(customExample)}"' in wizard
    assert "設計師端尚未送出的草稿" not in wizard
    assert "<legend>希望有哪些家具？沒有需求可不選</legend>" in html
    assert (
        "<legend>希望有哪些家具？沒有需求可不選</legend>"
        in (STATIC / "questionnaire.html").read_text(encoding="utf-8")
    )
    client_html = (STATIC / "questionnaire.html").read_text(encoding="utf-8")
    assert 'data-client-room-stage="technical"' in client_html
    assert "天花、冷氣與燈光" in client_html
    assert '...$$("[data-client-room-stage]")' in client_controller
    assert "data-client-technical-axis" in client_controller
    assert 'stage.dataset.clientRoomStage === "technical"' in client_controller
    assert "validateQuestionnaireTechnicalCeiling" in client_controller
    assert "renderQuestionnaireTechnicalChoices" in wizard
    assert "renderQuestionnaireTechnicalChoices" in controller
    assert "renderQuestionnaireTechnicalChoices" in client_controller
    assert "偏重補充" not in wizard
    assert "renderQuestionnaireAxisCustomApproach" in controller
    assert "renderQuestionnaireAxisCustomApproach" in client_controller
    assert "updateQuestionnaireAxisCustomApproach" in controller
    assert "updateQuestionnaireAxisCustomApproach" in client_controller
    assert "rp-axis-endpoints" in wizard
    assert "rp-axis-preference-scale" in wizard
    assert "選項 ${option.pole.toUpperCase()}" in wizard
    assert "偏重 A" in (STATIC / "scene_requirements.js").read_text(encoding="utf-8")
    assert "兩者平衡" in (STATIC / "scene_requirements.js").read_text(encoding="utf-8")
    assert "偏重 B" in (STATIC / "scene_requirements.js").read_text(encoding="utf-8")
    assert "updateDesignerNoteState" in controller
    assert "element.designerNoteTool.hidden = !state.projectId" in controller
    assert "room.polygon_m.map(meterToPixel)" not in controller
    assert "(room.polygon_cm || []).map(cmToPixel)" in controller
    assert "existing?.customNotes?.[axisDefinition.id] ? \"open\" : \"\"" not in controller
    assert "existing?.customNotes?.[axis.id] ? \"open\" : \"\"" not in client_controller

    floating_css = css.split(".rp-designer-note-tool {", 1)[1].split("}", 1)[0]
    assert "position: fixed" in floating_css
    assert "z-index:" in floating_css
    assert ".rp-axis-custom-approach" in css
    assert ".rp-axis-endpoints" in css
    assert ".rp-axis-preference-scale" in css


def test_invited_client_normalizes_legacy_technical_axis_values() -> None:
    client_controller = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")

    assert "hydrateQuestionnaireTechnicalChoices" in client_controller
    assert "normalizeChoice: normalizeAxisChoice" in client_controller


def test_browser_e2e_is_a_required_ci_gate() -> None:
    workflow = (ROOT / ".github" / "workflows" / "browser-e2e.yml").read_text(
        encoding="utf-8"
    )

    assert 'ROOMPILOT_BROWSER_E2E: "1"' in workflow
    assert "tests/test_browser_step6_step7_e2e.py" in workflow


def test_shared_questionnaire_wizard_clamps_navigation_and_validates_required_stage() -> None:
    module_uri = (STATIC / "questionnaire_wizard.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          showQuestionnaireStep,
          questionnaireRoomAnswerChanged,
          questionnaireRoomAnswerHasDraft,
          questionnairePlanPoint,
          questionnairePolygonLabelPoint,
          validateQuestionnaireStage,
        }} from {json.dumps(module_uri)};
        const makeStage = (dataset, checked = false) => ({{
          hidden: false,
          dataset,
          querySelector(selector) {{
            if (selector === "input:checked") return checked ? {{ value: "selected" }} : null;
            if (selector === "legend") return {{ textContent: "開放感與收納" }};
            return null;
          }},
        }});
        const stages = [makeStage({{ roomAxis: "first" }}), makeStage({{ roomAxis: "second" }})];
        const shown = showQuestionnaireStep(stages, 99);
        const invalid = validateQuestionnaireStage(stages[0], {{
          axisDatasetKey: "roomAxis",
          usesDatasetKey: "roomQuestionStage",
        }});
        const valid = validateQuestionnaireStage(makeStage({{ roomAxis: "first" }}, true), {{
          axisDatasetKey: "roomAxis",
          usesDatasetKey: "roomQuestionStage",
        }});
        const draft = {{
          axes: {{ openness: "open" }},
          uses: [],
          materialPreferences: {{}},
        }};
        const concaveRoom = [
          {{ x: 0, y: 0 }},
          {{ x: 6, y: 0 }},
          {{ x: 6, y: 2 }},
          {{ x: 2, y: 2 }},
          {{ x: 2, y: 6 }},
          {{ x: 0, y: 6 }},
        ];
        const labelPoint = questionnairePolygonLabelPoint(concaveRoom);
        const dxfFloorplan = {{
          scale: {{ cm_per_px: 1 }},
          plan_bbox_px: [0, 0, 1000, 500],
          coordinate_space: "lower_left_cm",
        }};
        console.log(JSON.stringify({{
          shown: {{ index: shown.index, total: shown.total }},
          hidden: stages.map((stage) => stage.hidden),
          invalid,
          valid,
          draftHasContent: questionnaireRoomAnswerHasDraft(draft),
          draftChanged: questionnaireRoomAnswerChanged(draft, {{ axes: {{}} }}),
          labelPoint,
          dxfCorners: [
            questionnairePlanPoint({{ x: 0, y: 0 }}, dxfFloorplan),
            questionnairePlanPoint({{ x: 1000, y: 500 }}, dxfFloorplan),
          ],
        }}));
        """
    )

    assert result["shown"] == {"index": 1, "total": 2}
    assert result["hidden"] == [True, False]
    assert result["invalid"] == {
        "ready": False,
        "kind": "axis",
        "label": "開放感與收納",
    }
    assert result["valid"]["ready"] is True
    assert result["draftHasContent"] is True
    assert result["draftChanged"] is True
    assert (
        result["labelPoint"]["x"] <= 2
        or result["labelPoint"]["y"] <= 2
    )
    assert result["dxfCorners"] == [{"x": 0, "y": 500}, {"x": 1000, "y": 0}]


def test_questionnaire_assets_use_content_hash_cache_keys() -> None:
    client_html = (STATIC / "questionnaire.html").read_text(encoding="utf-8")
    client_controller = (STATIC / "questionnaire_client.js").read_text(encoding="utf-8")
    designer_controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    requirements_hash = _asset_hash("scene_requirements.js")
    wizard_hash = _asset_hash("questionnaire_wizard.js")
    workflow_hash = _asset_hash("scene_workflow.js")
    client_hash = _asset_hash("questionnaire_client.js")

    assert (
        f'src="/static/questionnaire_client.js?v=sha256-{client_hash}"'
        in client_html
    )
    assert (
        f'from "./questionnaire_wizard.js?v=sha256-{wizard_hash}"'
        in client_controller
    )
    assert (
        f'from "./questionnaire_wizard.js?v=sha256-{wizard_hash}"'
        in designer_controller
    )
    assert (
        f'from "./scene_requirements.js?v=sha256-{requirements_hash}"'
        in client_controller
    )
    assert (
        f'from "./scene_requirements.js?v=sha256-{requirements_hash}"'
        in designer_controller
    )
    assert (
        f'from "./scene_workflow.js?v=sha256-{workflow_hash}"'
        in client_controller
    )
    assert (
        f'from "./scene_workflow.js?v=sha256-{workflow_hash}"'
        in designer_controller
    )
