from __future__ import annotations

import hashlib
import json
import re
import subprocess

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


def _space_heading_html(html: str) -> str:
    heading_start = html.index('class="rp-pane-heading"', html.index('id="space-step"'))
    stage_start = html.index('id="space-plan-stage"')
    return html[heading_start:stage_start]


def test_scene_entrypoint_cache_key_matches_bundle_content() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    bundle = (STATIC_DIR / "scene_v2.js").read_bytes()
    css = (STATIC_DIR / "site.css").read_bytes()
    expected_bundle = hashlib.sha256(bundle).hexdigest()[:12]
    expected_css = hashlib.sha256(css).hexdigest()[:12]

    assert f'src="/static/scene_v2.js?v=sha256-{expected_bundle}"' in html
    assert f'href="/static/site.css?v=sha256-{expected_css}"' in html


def test_scene_bundle_parses_as_an_es_module(tmp_path) -> None:
    """Keep a browser-breaking syntax error from hiding behind API-only tests."""
    module_file = tmp_path / "scene_v2.mjs"
    module_file.write_bytes((STATIC_DIR / "scene_v2.js").read_bytes())
    result = subprocess.run(
        ["node", "--check", str(module_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_requirements_step_has_first_meeting_demo_shortcut() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="randomize-requirements"' in html
    assert "async function randomizeRequirementsForTesting" in source
    assert 'state.firstMeetingStep = "summary"' in source
    assert 'goalIds: ["circulation", "storage", "daylight"]' in source
    assert "likedStylePackIds: packs.slice(0, 2)" in source
    assert "dislikedStylePackId:" in source


def test_legacy_weighted_answers_remain_compatible_without_forcing_a_b_ui() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert "PREFERENCE_WEIGHT_OPTIONS" in source
    assert "function selectPreferenceWeight" in source
    assert "preferenceWeight: weight" in source
    assert "preferenceDirection: answerWeightDirection(weight)" in source
    assert "preference_weight: Number(answer.preferenceWeight ?? 0)" in source
    assert "preference_direction: answer.preferenceDirection" in source
    assert ".rp-preference-weight" in css
    assert 'data-preference-weight="${item.value}"' not in source


def test_random_requirement_shortcut_randomizes_wall_and_floor_material_options() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT = 4" in source
    assert "function questionnaireMaterialOptionsForPack" in source
    assert 'const wallOption = randomItem(questionnaireMaterialOptionsForPack("wall", pack), null)' in source
    assert 'const floorOption = randomItem(questionnaireMaterialOptionsForPack("floor", pack), null)' in source
    assert "const options = questionnaireMaterialOptionsForPack(kind, pack)" in source
    assert "defaultWallMaterial: wallMaterial" in source
    assert "floorMaterial" in source


def test_questionnaire_material_card_keeps_the_catalog_color_and_its_own_note() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    material_option = source.split("function materialOptionForPack", 1)[1].split(
        "function questionnaireMaterialOptionsForPack", 1
    )[0]
    assert "packMaterialColor" not in source
    assert "color: packMaterialColor" not in material_option
    assert "note: option.note" in material_option
    assert "recommendation: pack.name" in material_option
    assert "background-color:${escapeHtml(option.color)}" in source
    assert "全房牆面目前使用：${wallLabel}" in source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "grid-auto-rows: 86px;" in css
    assert "width: 76px;" in css
    assert "height: 68px;" in css
    assert "background-size: auto 230%;" in css
    assert "background-blend-mode: multiply;" not in css


def test_room_surfaces_keep_one_main_wall_and_floor_with_functional_exceptions() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "const INDEPENDENT_FLOOR_ROOM_TYPES" in source
    assert '"bathroom"' in source
    assert '"kitchen"' in source
    assert '"entry"' in source
    assert '"balcony"' in source
    assert "function wholeHouseMainFloorSurface" in source
    assert "function wholeHouseMainWallSurface" in source
    assert "function normalizedRoomSurfaces" in source
    assert "function applyWholeHouseSurfaceConsistency" in source
    assert "function normalizeSavedSceneWallSurfaces" in source
    assert "roomKeepsExplicitWallOverride" in source
    assert "trimAccentWallSurfaces" in source
    assert "wallSurfaceIds: []" in source
    assert "wallOverrides: {}" in source
    assert "if (!roomAllowsIndependentFloor(room) && mainFloor)" in source
    assert "if (mainWall && !roomKeepsExplicitWallOverride(room, next))" in source
    assert "const restoredWallSurfaceRepairs" in source
    assert "const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {})" in source
    assert "const surfaces = normalizedRoomSurfaces(room, rawSurfaces || {})" in source


def test_circulation_style_inherits_living_room_until_user_confirms_override() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function isCirculationRoom" in source
    assert "function copyLivingRoomStyleToCirculation" in source
    assert "function synchronizeCirculationStyles" in source
    assert "circulationStyleOverrideApproved" in source
    assert "走道目前沿用" in source


def test_interior_walls_butt_against_exterior_inner_face_without_a_visible_gap() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    junction_helper = source.split("function interiorWallJunctionInsets", 1)[1].split(
        "function polygonShape", 1
    )[0]
    assert "Number(wallThickness) / 2, 0" in junction_helper
    assert "Number(wallThickness) / 2 + 1" not in junction_helper


def test_whole_house_wall_finish_keeps_texture_while_avoiding_lighting_variation() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createWallMaterial(wallOption, surfaceCatalog, { tintOnly = false } = {})" in source
    assert "const usesOneWholeHouseWall" in source
    assert "map: material.map || null," in source
    assert "{ tintOnly: false }" in source
    assert "function stabilizeWholeHouseWallAppearance(material)" in source
    assert "new THREE.MeshBasicMaterial" in source
    assert "toneMapped: false" in source
    assert "exteriorWallMaterial = stabilizeWholeHouseWallAppearance(exteriorWallMaterial);" in source


def test_questionnaire_exposes_database_furniture_choices_for_each_room() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'id="questionnaire-furniture-options"' in html
    assert 'id="questionnaire-furniture-status"' in html
    assert 'id="questionnaire-furniture-preference"' in html
    assert 'id="refresh-questionnaire-furniture"' in html
    assert 'id="questionnaire-room-usage-options"' in html
    assert "function ensureQuestionnaireFurnitureRecommendations" in source
    assert "function renderQuestionnaireFurnitureRecommendations" in source
    assert "const ROOM_USAGE_OPTIONS" in source
    assert "function renderQuestionnaireRoomUsage" in source
    assert "data-questionnaire-room-usage" in source
    assert 'data-questionnaire-furniture-id="' in source
    assert "user_selected: true" in source
    assert "selection_priority:" in source
    assert "function knownUnavailableCatalogFurnitureIds" in source
    assert "function catalogFallbackOffersForSpec" in source
    assert "recommendation_tier: \"similar\"" in source
    assert "function applyDefaultQuestionnaireFurnitureSelections" in source
    assert "const QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS" in source
    assert 'defaults: ["bed", "wardrobe"]' in source
    assert 'required: ["bed"]' in source
    assert "function questionnaireFurnitureRole" in source
    assert "QUESTIONNAIRE_FURNITURE_SHORT_LABELS" in source
    assert "function questionnaireFurnitureDisplayLabel" in source
    assert "function questionnaireBedSizeFamily" in source
    assert "function questionnaireOffersWithSizeChoices" in source
    assert 'return "單人床"' in source
    assert 'return "標準雙人床"' in source
    assert 'return "加大雙人床"' in source
    assert 'read: [["desk", "compact"], ["office-chair", "task"]]' in source
    assert "data-questionnaire-furniture-variant-type" in source
    assert "function updateQuestionnaireFurnitureVariant" in source
    assert "function updateQuestionnaireFurnitureQuantity" in source
    assert "function refreshQuestionnaireFurnitureRecommendations" in source
    assert "data-questionnaire-furniture-quantity" in source
    assert "preferenceText" in source
    assert "selectedCatalogFurniture.flatMap" in source
    assert "data-open-questionnaire-furniture-catalog" in source
    assert "unavailableCatalogIds.has(String(offer.furniture_id))" in source
    assert "questionnaireOffersWithSizeChoices(spec[0], candidates)" in source
    assert "第 6 步將檢查實際 GLB、門窗與走道" in source
    assert 'id="questionnaire-furniture-preference-tags"' in html
    assert "QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS" in source
    assert 'model_load_verification: "deferred"' in source
    assert ".rp-questionnaire-furniture-options" in css
    assert ".rp-questionnaire-room-usage-options" in css


def test_questionnaire_selected_catalog_furniture_drives_step_six_exactly() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    auto_layout = source.split("async function autoLayoutFurniture()", 1)[1].split(
        "async function relayoutFurnitureForScheme", 1
    )[0]

    assert "requirement?.furniture?.selected" in auto_layout
    assert "userSelectedSpecs" in auto_layout
    assert "catalogItem?.user_selected === true" in auto_layout
    assert "item.selectionPriority" in auto_layout
    assert "selected_furniture_exact" in source


def test_room_requirement_round_trip_preserves_selected_and_deferred_furniture() -> None:
    module_uri = (STATIC_DIR / "scene_room_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          buildRoomRequirementsPayload,
          normalizeRoomRequirements,
        }} from {json.dumps(module_uri)};
        const rooms = [{{
          id: "living-1",
          type: "living_room",
          label: "客廳",
        }}];
        const model = normalizeRoomRequirements({{
          roomRequirements: {{
            "living-1": {{
              confirmed: true,
              furniture: {{
                required: ["sofa"],
                selected: [{{
                  furniture_id: "sofa-db-1",
                  normalized_type: "sofa",
                  model_url: "https://cdn.example/sofa.glb",
                  user_selected: true,
                  selection_priority: 1,
                }}],
                deferred: [{{
                  furniture_id: "table-db-1",
                  normalized_type: "coffee-table",
                  label: "茶几",
                }}],
              }},
              climate: {{ airConditioning: "none" }},
              surfaces: {{
                wallDefault: {{ materialId: "paint" }},
                floor: {{ materialId: "wood" }},
                ceiling: {{
                  materialId: "paint",
                  styleId: "flat",
                  lightingId: "track",
                }},
              }},
            }},
          }},
          globalConfirmed: true,
        }}, rooms);
        console.log(JSON.stringify(buildRoomRequirementsPayload(model)));
        """
    )

    furniture = result["roomRequirements"][0]["furniture"]
    assert furniture["selected"][0]["furniture_id"] == "sofa-db-1"
    assert furniture["selected"][0]["selection_priority"] == 1
    assert furniture["deferred"][0]["label"] == "茶几"


def test_step_six_groups_failures_by_room_and_offers_explicit_resolution() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert "function configurationBlockingFurnitureByRoom" in source
    assert 'data-prioritize-configuration-room="' in source
    assert "同意擇優配置" in source
    assert "function prioritizeConfigurationRoomFurniture" in source
    assert "更換較小款" in source
    assert ".rp-configuration-pending-room" in css


def test_changed_scene_module_cache_keys_match_dependency_content() -> None:
    dependency_edges = {
        "scene_v2.js": [
            "scene_viewer.js",
            "scene_workflow.js",
            "scene_unit_contracts.js",
            "scene_calibration.js",
            "scene_recognition_review.js",
            "scene_tabletop_hosts.js",
            "scene_room_geometry.js",
            "scene_structure_utils.js",
            "scene_structure_preview.js",
            "scene_structure_geometry.js",
            "scene_window_types.js",
            "scene_design_schemes.js",
            "scene_questionnaire_test2.js",
            "scene_configuration_sync.js",
            "scene_viewer_reload.js",
        ],
        "scene_viewer.js": [
            "scene_architecture.js",
            "scene_structure_geometry.js",
            "scene_window_types.js",
            "scene_visual_contracts.js",
        ],
        "scene_structure_preview.js": ["scene_structure_geometry.js"],
    }

    for importer_name, dependency_names in dependency_edges.items():
        importer = (STATIC_DIR / importer_name).read_text(encoding="utf-8")
        for dependency_name in dependency_names:
            dependency = (STATIC_DIR / dependency_name).read_bytes()
            expected = hashlib.sha256(dependency).hexdigest()[:12]
            assert (
                f'./{dependency_name}?v=sha256-{expected}' in importer
            ), f"{importer_name} has a stale cache key for {dependency_name}"


def test_space_save_does_not_duplicate_furniture_or_scene_payloads() -> None:
    module_uri = (STATIC_DIR / "scene_design_schemes.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ compactDesignSchemesForSpace }} from {json.dumps(module_uri)};
        const compact = compactDesignSchemesForSpace({{
          schema_version: 1,
          active_scheme_id: "A",
          locked_scheme_id: null,
          schemes: {{
            A: {{
              id: "A",
              kind: "baseline",
              label: "方案 A",
              furniture: [{{ id: "chair-1" }}],
              sceneData: {{ surface_catalog: {{ huge: true }} }},
              stale: false,
              staleReason: "",
            }},
          }},
        }});
        console.log(JSON.stringify(compact));
        """
    )

    assert result["active_scheme_id"] == "A"
    assert result["schemes"]["A"]["kind"] == "baseline"
    assert result["schemes"]["A"]["furniture"] == []
    assert result["schemes"]["A"]["sceneData"] is None


def test_loaded_door_candidates_drop_low_confidence_wide_and_duplicate_auto_doors() -> None:
    module_uri = (STATIC_DIR / "scene_structure_utils.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ dedupeDoorCandidates }} from {json.dumps(module_uri)};
        const result = dedupeDoorCandidates([
          {{ id: "wide", source: "cody_vision", confidence: 1, width_cm: 186, start: {{x: 0, y: 0}}, end: {{x: 186, y: 0}} }},
          {{ id: "weak", source: "cody_vision", confidence: 0.59, width_cm: 90, start: {{x: 220, y: 0}}, end: {{x: 310, y: 0}} }},
          {{ id: "first", source: "cody_vision", confidence: 0.91, width_cm: 90, host_wall_id: "wall-1", start: {{x: 0, y: 40}}, end: {{x: 90, y: 40}} }},
          {{ id: "better", source: "cody_vision", confidence: 0.96, width_cm: 92, host_wall_id: "wall-1", start: {{x: 10, y: 45}}, end: {{x: 102, y: 45}}, swing_end: {{x: 10, y: 135}} }},
          {{ id: "manual-wide", source: "manual", confidence: 0.1, width_cm: 180, confirmed: true, start: {{x: 400, y: 0}}, end: {{x: 580, y: 0}} }},
        ]);
        console.log(JSON.stringify(result));
        """
    )

    assert [door["id"] for door in result["doors"]] == ["better", "manual-wide"]
    assert result["removed"] == 3


def test_nearby_parallel_door_leaves_remain_distinct() -> None:
    module_uri = (STATIC_DIR / "scene_structure_utils.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ dedupeDoorCandidates }} from {json.dumps(module_uri)};
        const result = dedupeDoorCandidates([
          {{
            id: "door-2",
            source: "cody_vision",
            confidence: 1,
            confirmed: true,
            host_wall_id: "wall-2",
            width_cm: 113.41,
            start: {{x: -9.94, z: 61.39}},
            end: {{x: -123.35, z: 61.39}},
          }},
          {{
            id: "door-3",
            source: "cody_vision",
            confidence: 1,
            confirmed: true,
            host_wall_id: "wall-2",
            width_cm: 104.06,
            start: {{x: -19.29, z: 111.67}},
            end: {{x: -123.35, z: 111.67}},
          }},
        ]);
        console.log(JSON.stringify(result));
        """
    )

    assert len(result["doors"]) == 2
    assert result["removed"] == 0


def test_unconfirmed_nearby_parallel_door_leaves_are_not_merged() -> None:
    module_uri = (STATIC_DIR / "scene_structure_utils.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ dedupeDoorCandidates }} from {json.dumps(module_uri)};
        const result = dedupeDoorCandidates([
          {{
            id: "door-2",
            source: "cody_vision",
            confidence: 1,
            host_wall_id: "wall-2",
            width_cm: 113.41,
            start: {{x: -9.94, z: 61.39}},
            end: {{x: -123.35, z: 61.39}},
          }},
          {{
            id: "door-3",
            source: "cody_vision",
            confidence: 1,
            host_wall_id: "wall-2",
            width_cm: 104.06,
            start: {{x: -19.29, z: 111.67}},
            end: {{x: -123.35, z: 111.67}},
          }},
        ]);
        console.log(JSON.stringify(result));
        """
    )

    assert [door["id"] for door in result["doors"]] == ["door-2", "door-3"]
    assert result["removed"] == 0


def test_restored_scene_data_removes_duplicate_door_segments() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function normalizeSceneDoorSegments(sceneData)" in source
    assert "dedupeDoorCandidates(sceneData.floorplan.door_segments)" in source
    assert "normalizeSceneDoorSegments(state.sceneData)" in source


def test_dimensioned_plan_draws_colored_room_outlines_and_size_lines() -> None:
    module_uri = (STATIC_DIR / "scene_dimensioned_plan.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildDimensionedPlanAnnotations }} from {json.dumps(module_uri)};
        const plan = buildDimensionedPlanAnnotations([
          {{
            id: "living",
            label: "客廳",
            widthCm: 500,
            depthCm: 400,
            areaM2: 20,
            polygonPx: [{{x: 20, y: 20}}, {{x: 520, y: 20}}, {{x: 520, y: 420}}, {{x: 20, y: 420}}],
          }},
          {{
            id: "bedroom",
            label: "臥室",
            widthCm: 400,
            depthCm: 250,
            areaM2: 10,
            polygonPx: [{{x: 540, y: 20}}, {{x: 940, y: 20}}, {{x: 940, y: 270}}, {{x: 540, y: 270}}],
          }},
        ], {{ imageWidth: 1000, imageHeight: 600 }});
        console.log(JSON.stringify(plan));
        """
    )

    assert result["roomCount"] == 2
    assert result["totalAreaM2"] == 30
    assert result["rooms"][0]["color"] != result["rooms"][1]["color"]
    assert 'data-dimension-room="living"' in result["svg"]
    assert "500 cm" in result["svg"]
    assert "400 cm" in result["svg"]
    assert "20.00 m² · ±5%" in result["svg"]
    assert 'class="rp-plan-dimension"' in result["svg"]


def test_floor_to_ceiling_window_preset_reaches_from_floor_to_ceiling() -> None:
    module_uri = (STATIC_DIR / "scene_window_types.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          applyWindowTypePreset,
          windowOpeningMetrics,
          WINDOW_TYPES,
        }} from {json.dumps(module_uri)};
        const floorWindow = applyWindowTypePreset(
          {{ id: "window-1", width_cm: 240 }},
          WINDOW_TYPES.floorToCeiling,
          270,
        );
        const floorMetrics = windowOpeningMetrics(floorWindow, 270);
        const standardMetrics = windowOpeningMetrics({{
          window_type: WINDOW_TYPES.standard,
          sill_height_cm: 90,
          height_cm: 120,
        }}, 270);
        console.log(JSON.stringify({{ floorWindow, floorMetrics, standardMetrics }}));
        """
    )

    assert result["floorWindow"]["window_type"] == "floor_to_ceiling"
    assert result["floorWindow"]["sill_height_cm"] == 0
    assert result["floorWindow"]["height_cm"] == 262
    assert result["floorMetrics"] == {
        "windowType": "floor_to_ceiling",
        "sillHeightCm": 0,
        "headHeightCm": 262,
        "glazingHeightCm": 262,
    }
    assert result["standardMetrics"] == {
        "windowType": "standard",
        "sillHeightCm": 90,
        "headHeightCm": 210,
        "glazingHeightCm": 120,
    }


def test_only_internal_walls_can_be_marked_as_demolition_candidates() -> None:
    module_uri = (STATIC_DIR / "scene_structure_utils.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          canMarkWallForDemolition,
          wallBoundarySide,
        }} from {json.dumps(module_uri)};
        const floorplan = {{ width_cm: 900, depth_cm: 600 }};
        const exterior = {{
          start: {{ x: 0, y: 0 }},
          end: {{ x: 900, y: 0 }},
        }};
        const interior = {{
          start: {{ x: 320, y: 120 }},
          end: {{ x: 320, y: 520 }},
        }};
        console.log(JSON.stringify({{
          exteriorSide: wallBoundarySide(exterior, {{
            widthCm: floorplan.width_cm,
            depthCm: floorplan.depth_cm,
          }}),
          exteriorAllowed: canMarkWallForDemolition(exterior, floorplan),
          interiorSide: wallBoundarySide(interior, {{
            widthCm: floorplan.width_cm,
            depthCm: floorplan.depth_cm,
          }}),
          interiorAllowed: canMarkWallForDemolition(interior, floorplan),
        }}));
        """
    )

    assert result == {
        "exteriorSide": "bottom",
        "exteriorAllowed": False,
        "interiorSide": None,
        "interiorAllowed": True,
    }


def test_saved_space_confirmation_migrates_legacy_meters_only_once() -> None:
    module_uri = (STATIC_DIR / "scene_unit_contracts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ normalizeSavedSpaceConfirmation }} from {json.dumps(module_uri)};
        const legacy = normalizeSavedSpaceConfirmation({{
          rooms: [{{
            id: "legacy-room",
            polygon_m: [{{ x: 0, y: 0 }}, {{ x: 6, y: 0 }}, {{ x: 6, y: 4 }}],
          }}],
          structures: {{
            walls: [{{
              start: {{ x: 0, y: 0 }},
              end: {{ x: 6, y: 0 }},
              thickness_m: 0.18,
            }}],
          }},
        }});
        const current = normalizeSavedSpaceConfirmation({{
          coordinate_unit: "cm",
          rooms: [{{
            id: "current-room",
            polygon_cm: [{{ x: 0, y: 0 }}, {{ x: 600, y: 0 }}, {{ x: 600, y: 400 }}],
          }}],
          structures: {{
            walls: [{{
              start: {{ x: 0, y: 0 }},
              end: {{ x: 600, y: 0 }},
              thickness_cm: 18,
            }}],
          }},
        }});
        console.log(JSON.stringify({{ legacy, current }}));
        """
    )

    assert result["legacy"]["coordinate_unit"] == "cm"
    assert result["legacy"]["rooms"][0]["polygon_cm"][1] == {"x": 600, "y": 0}
    assert result["legacy"]["structures"]["walls"][0]["end"] == {"x": 600, "y": 0}
    assert result["legacy"]["structures"]["walls"][0]["thickness_cm"] == 18
    assert result["current"]["rooms"][0]["polygon_cm"][1] == {"x": 600, "y": 0}
    assert result["current"]["structures"]["walls"][0]["end"] == {"x": 600, "y": 0}


def test_saved_space_confirmation_migrates_each_field_by_its_own_unit() -> None:
    module_uri = (STATIC_DIR / "scene_unit_contracts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ normalizeSavedSpaceConfirmation }} from {json.dumps(module_uri)};
        const normalized = normalizeSavedSpaceConfirmation({{
          coordinate_unit: "cm",
          rooms: [
            {{
              id: "legacy-room",
              polygon_m: [{{ x: 0, y: 0 }}, {{ x: 6, y: 0 }}, {{ x: 6, y: 4 }}],
            }},
            {{
              id: "current-room",
              polygon_cm: [{{ x: 0, y: 0 }}, {{ x: 300, y: 0 }}, {{ x: 300, y: 200 }}],
            }},
          ],
          structures: {{
            walls: [{{
              start: {{ x: 0, y: 0 }},
              end: {{ x: 6, y: 0 }},
              thickness_m: 0.18,
            }}],
            columns: [{{
              center: {{ x: 250, y: 180 }},
              width_cm: 35,
              depth_cm: 35,
            }}],
            doors: [{{
              start: {{ x: 1, y: 0 }},
              end: {{ x: 1.9, y: 0 }},
              width_cm: 90,
            }}],
          }},
        }});
        console.log(JSON.stringify(normalized));
        """
    )

    assert result["schema_version"] == "2.0"
    assert result["rooms"][0]["polygon_cm"][1] == {"x": 600, "y": 0}
    assert result["rooms"][1]["polygon_cm"][1] == {"x": 300, "y": 0}
    assert result["structures"]["walls"][0]["end"] == {"x": 600, "y": 0}
    assert result["structures"]["columns"][0]["center"] == {"x": 250, "y": 180}
    assert result["structures"]["doors"][0]["end"] == {"x": 1.9, "y": 0}

    legacy_with_cm_dimensions = run_workflow_script(
        f"""
        import {{ normalizeSavedSpaceConfirmation }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(normalizeSavedSpaceConfirmation({{
          rooms: [{{
            polygon_m: [{{ x: 0, y: 0 }}, {{ x: 6, y: 0 }}, {{ x: 6, y: 4 }}],
          }}],
          structures: {{
            doors: [{{
              start: {{ x: 1, y: 0 }},
              end: {{ x: 1.9, y: 0 }},
              width_cm: 90,
            }}],
          }},
        }})));
        """
    )
    assert legacy_with_cm_dimensions["structures"]["doors"][0]["end"] == {"x": 190, "y": 0}


def test_saved_scene_data_migrates_only_legacy_floorplan_geometry_once() -> None:
    module_uri = (STATIC_DIR / "scene_unit_contracts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ normalizeSavedSceneData }} from {json.dumps(module_uri)};
        const legacy = {{
          floorplan: {{
            width_cm: 600,
            depth_cm: 400,
            wall_segments: [{{
              start: {{ x: -3, z: -2 }},
              end: {{ x: 3, z: -2 }},
            }}],
            wall_polys: [{{
              exterior: [[-3, -2], [3, -2], [3, 2], [-3, 2]],
              holes: [],
            }}],
            room_regions: [{{
              exterior: [[-3, -2], [3, -2], [3, 2], [-3, 2]],
              holes: [],
            }}],
          }},
          scene_objects: [{{
            id: "bed-1",
            position_cm: {{ x: 120, z: -80 }},
            size_cm: {{ width: 180, depth: 200, height: 90 }},
          }}],
        }};
        const once = normalizeSavedSceneData(legacy);
        const twice = normalizeSavedSceneData(once);
        console.log(JSON.stringify({{ once, twice }}));
        """
    )

    assert result["once"]["floorplan"]["coordinate_unit"] == "cm"
    assert result["once"]["floorplan"]["schema_version"] == "2.0"
    assert result["once"]["floorplan"]["wall_segments"][0]["end"] == {"x": 300, "z": -200}
    assert result["once"]["floorplan"]["wall_polys"][0]["exterior"][2] == [300, 200]
    assert result["once"]["floorplan"]["room_regions"][0]["exterior"][2] == [300, 200]
    assert result["once"]["scene_objects"][0]["position_cm"] == {"x": 120, "z": -80}
    assert result["twice"] == result["once"]


def test_saved_scene_data_migrates_mixed_floorplan_fields_independently() -> None:
    module_uri = (STATIC_DIR / "scene_unit_contracts.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ normalizeSavedSceneData }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(normalizeSavedSceneData({{
          floorplan: {{
            coordinate_unit: "cm",
            width_cm: 600,
            depth_cm: 400,
            bbox: {{ minx: -3, minz: -2, maxx: 3, maxz: 2 }},
            wall_segments: [
              {{
                coordinate_unit: "cm",
                start: {{ x: -300, z: -200 }},
                end: {{ x: 300, z: -200 }},
              }},
              {{
                coordinate_unit: "m",
                start: {{ x: -3, z: 2 }},
                end: {{ x: 3, z: 2 }},
              }},
            ],
            wall_polys: [{{
              exterior: [[-3, -2], [3, -2], [3, 2], [-3, 2]],
              holes: [],
            }}],
            room_regions: [{{
              coordinate_unit: "cm",
              exterior: [[-300, -200], [300, -200], [300, 200], [-300, 200]],
              holes: [],
            }}],
            columns: [{{
              coordinate_unit: "m",
              center: {{ x: 2.5, z: 1.5 }},
              width_cm: 35,
              depth_cm: 35,
            }}],
          }},
          scene_objects: [],
        }})));
        """
    )

    floorplan = result["floorplan"]
    assert floorplan["bbox"] == {"minx": -300, "minz": -200, "maxx": 300, "maxz": 200}
    assert floorplan["wall_segments"][0]["end"] == {"x": 300, "z": -200}
    assert floorplan["wall_segments"][1]["end"] == {"x": 300, "z": 200}
    assert floorplan["wall_polys"][0]["exterior"][2] == [300, 200]
    assert floorplan["room_regions"][0]["exterior"][2] == [300, 200]
    assert floorplan["columns"][0]["center"] == {"x": 250, "z": 150}


def test_scene_generate_response_prefers_scene_json_with_legacy_fallback() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function sceneDataFromGenerateResponse(payload)" in source
    assert "return payload?.scene_json || payload;" in source
    assert "state.sceneData = sceneDataFromGenerateResponse(payload);" in source
    assert "state.sceneData = payload;" not in source


def test_project_restore_normalizes_saved_scene_before_loading_viewers() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "normalizeSavedSceneData" in controller
    assert (
        "const legacySceneData = normalizeSavedSceneData(serverState.white_model_3d?.sceneData);"
        in controller
    )
    assert "state.sceneData = normalizeSavedSceneData(restoredScheme?.sceneData) || legacySceneData;" in controller


def test_window_editor_exposes_floor_to_ceiling_type_and_visual_asset() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="window-type-field"' in html
    assert 'id="selected-window-type"' in html
    assert 'value="floor_to_ceiling"' in html
    assert 'id="window-type-preview"' in html
    assert "黑鋁框左右兩扇玻璃參考" in html
    assert (STATIC_DIR / "structure_assets" / "floor-to-ceiling-window.png").is_file()
    assert "function applySelectedWindowType" in controller
    assert "function applyWindowType(windowId, type)" in controller
    assert 'class="rp-window-type-toggle"' in controller
    assert 'data-window-type="${WINDOW_TYPES.standard}"' in controller
    assert 'data-window-type="${WINDOW_TYPES.floorToCeiling}"' in controller
    assert 'aria-pressed="${windowType === WINDOW_TYPES.standard}"' in controller
    assert 'event.target.closest("[data-window-type]")' in controller
    assert "normalizedWindowType(item.window_type) === nextType" in controller
    assert "applyWindowTypePreset" in controller
    assert "windowOpeningMetrics" in viewer


def test_accurate_floorplan_uses_segment_walls_when_openings_exist() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert (
        "const hasWallOpenings = doorSegments.length > 0 || windowSegments.length > 0;"
        in viewer
    )
    assert (
        "const builtWallMass = !singleRoomMode && hasAccurateFloorplan && !hasWallOpenings"
        in viewer
    )
    assert "buildSegmentWalls(" in viewer
    assert "const mullionPositions = [0];" in viewer


def test_3d_door_openings_are_deduped_after_topology_gap_conversion() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function dedupeArchitecturalOpeningsFor3d" in viewer
    assert "const doorSegments = dedupeArchitecturalOpeningsFor3d(" in viewer
    assert "doorOpeningForWallTopology(wallSegments, door, wallThickness)" in viewer
    wall_builder = viewer.split("function buildSegmentWalls", 1)[1].split(
        "function buildOpeningAssembly", 1
    )[0]
    assert "const wallDoorSegments = doorSegments.filter" in wall_builder
    assert "opening?.topology_gap !== true" in wall_builder
    assert "const topologyGapDoors = doorSegments.filter" in wall_builder
    assert "opening?.topology_gap === true" in wall_builder
    assert "const missingDoors = doorSegments.filter((opening) =>" in wall_builder
    assert "!renderedOpenings.has(openingId)" in wall_builder
    assert "[...wallDoorSegments.map" in wall_builder


def test_3d_door_openings_merge_overlapping_spans_on_the_same_host_wall() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function openingWallCoverage" in viewer
    assert "function openingsShareWallCoverage" in viewer
    assert "left.topology_gap_key === right.topology_gap_key" in viewer
    assert "overlap >= Math.max(24, narrowerWidth * 0.55)" in viewer
    assert "openingsShareWallCoverage(candidate, opening, wallSegments, wallThickness)" in viewer
    assert "dedupeArchitecturalOpeningsFor3d(" in viewer
    assert "      wallSegments,\n      wallThickness," in viewer


def test_3d_door_openings_keep_distinct_confirmed_step4_ids() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'const openingId = String(opening?.id || "").trim();' in viewer
    assert "if (openingId && candidateId) return candidateId === openingId;" in viewer
    assert "distinct IDs must never be collapsed" in viewer
    assert "roompilotArchitecturalId" in viewer
    assert "expectedIds: expectedDoorIds" in viewer
    assert "renderedIds: renderedDoorIds" in viewer
    assert "leafCount" in viewer
    assert "renderedDoors," in viewer


def test_3d_world_coordinate_conversion_flips_door_swing_endpoint() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "swing_end: segment.swing_end ? flipPointZ(segment.swing_end)" in viewer


def test_step4_shows_the_closed_door_line_from_the_swing_arc() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'const closedLine = item.swing_end' in source
    assert 'stroke="#1598dc"' in source
    assert '${dragTarget}${line}${closedLine}<path' in source


def test_step4_can_lock_a_manually_corrected_door_opening() -> None:
    viewer = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert 'id="lock-selected-door-opening"' in html
    assert "function lockSelectedDoorOpening()" in viewer
    assert 'item.opening_source = "manual_confirmed";' in viewer
    assert '$("#lock-selected-door-opening").addEventListener("click", lockSelectedDoorOpening);' in viewer


def test_requirements_generate_the_white_model_without_an_intermediate_2d_confirmation() -> None:
    viewer = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert "async function generateWhiteModelFromRequirements" in viewer
    assert "const generated = await generateWhiteModelFromRequirements({" in viewer
    assert 'state.workflow?.goTo("layout_2d")' in viewer
    assert 'ensureSchemeB(state.designSchemes, { reason: "questionnaire_alternative" });' in viewer
    assert viewer.count('await confirmLayout2d({ allowPendingFurniture: true });') >= 2
    assert 'state.designSchemes.schemes.B && !state.designSchemes.schemes.B.stale' in viewer
    assert "方案 A、B 的 2D+3D 配置已建立" in viewer
    assert 'state.workflow.currentStep === "white_model_3d"' in viewer
    assert 'state.workflow.currentStep === "layout_2d"' in viewer
    assert "returnToRequirementsOnFailure: true" in viewer
    assert "if (invalid.length && !allowPendingFurniture)" in viewer
    assert "if (generatedInvalid.length && !allowPendingFurniture)" in viewer
    assert "if (missingCatalogModels.length && !allowPendingFurniture)" in viewer
    assert "const sceneFurniture = allowPendingFurniture" in viewer
    assert "selectedFurniture.filter((item) => item.model_url)" in viewer
    assert "尚未找到可用的資料庫 GLB" in viewer
    assert "selected_furniture_exact: !allowPendingFurniture" in viewer
    assert "完成需求並建立 2D+3D 配置" in html


def test_requirement_generation_defers_a_single_failed_room_without_breaking_step_six() -> None:
    viewer = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    auto_layout = viewer.split("async function autoLayoutFurniture()", 1)[1].split(
        "async function relayoutFurnitureForScheme", 1
    )[0]
    assert 'console.warn("Room furniture layout deferred", room.id, error);' in auto_layout
    assert "item.placementFailed = true;" in auto_layout
    assert "item.placementReason = errorMessage(error);" in auto_layout
    assert "renderLayout2d();" not in viewer
    assert "renderLayoutRoomFilter();\n      renderLayoutFurniture();\n      return;" in viewer


def test_questionnaire_applies_whole_house_defaults_before_room_furniture() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert 'id="whole-house-style-editor"' in html
    assert 'id="whole-house-wall-options"' in html
    assert 'id="whole-house-floor-options"' in html
    assert 'data-questionnaire-stage="profile" class="is-active"' in html
    assert 'data-questionnaire-stage="rooms" disabled' in html
    assert 'id="whole-house-style-all"' in html
    assert 'id="whole-house-air-conditioning-all"' in html
    assert "function applyWholeHouseFinishes()" in source
    assert "applyWholeHouseFinishes();" in source
    assert 'if (stage === "profile") return true;' in source
    assert 'if (stage === "rooms") return state.basicConfirmed;' in source
    assert 'showQuestionnaireStage("rooms");' in source
    assert 'if (state.questionnaireStage === "rooms")' in source
    assert "逐房用途與家具" in html


def test_step_six_defaults_to_free_rotation_with_grouped_tools() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-view-mode="orbit" class="is-active">自由旋轉' in html
    assert 'data-view-mode="dollhouse"' not in html
    assert 'class="rp-toolbar-group" aria-label="檢視方式"' in html
    assert 'class="rp-toolbar-group" aria-label="操作方式"' in html
    assert 'whiteViewer.setViewMode("dollhouse")' not in viewer


def test_step_four_has_a_dimensioned_floorplan_confirmation_page() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="space-editor-workspace"' in html
    assert 'id="space-dimension-review"' in html
    assert 'id="dimensioned-plan-stage"' in html
    assert 'id="dimensioned-plan-image"' in html
    assert 'id="dimensioned-plan-overlay"' in html
    assert 'id="dimensioned-plan-legend"' in html
    assert 'id="back-to-space-editor"' in html
    assert 'id="recalibrate-space"' in html
    assert 'id="confirm-dimensioned-plan"' in html
    assert "水平線標示寬度，垂直線標示長度" in html
    assert "±5%" in html
    assert "不可取代現場丈量" in html
    assert "rp-proportion-bar" not in html
    assert "function showDimensionedPlanReview" in source
    assert "function confirmDimensionedPlan" in source
    initial_confirmation = source.split("function confirmSpace()", 1)[1].split(
        "function dimensionedPlanRoomInputs", 1
    )[0]
    final_confirmation = source.split("function confirmDimensionedPlan()", 1)[1].split(
        "function renderWholeHouseQuestionnaire", 1
    )[0]
    assert 'showDimensionedPlanReview();' in initial_confirmation
    assert '.complete("space_confirmation"' not in initial_confirmation
    assert '.complete("space_confirmation"' in final_confirmation
    assert "proportionsConfirmed: true" in final_confirmation
    assert "dimensionedPlanConfirmed: true" in final_confirmation


def test_upload_step_does_not_offer_the_internal_630_sample_button() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="load-sample-630"' not in html
    assert "function loadSample630" not in source
    assert '$("#load-sample-630")' not in source


def test_scene_sidebar_numbers_match_viewer_markers() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'class="rp-object-number">#${index + 1}' in source
    assert "function configurationFurnitureNumber" in source
    assert "const furnitureNumber = configurationFurnitureNumber(item, index)" in source
    assert "const furnitureNumber = configurationFurnitureNumber(item)" in source
    assert '"bed-frame": "雙人床"' in source
    assert '"floor-lamp": "落地燈"' in source
    assert '"large-medium-rug": "地毯"' in source
    assert "sceneObjectDisplayName(item, index)" in source


def test_structure_step_explains_pending_manual_door_directions() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "待確認：" in source
    assert "一鍵確認全部門" in html
    assert "confirmAllButton.disabled = !collection.length || allConfirmed" in source
    assert "`一鍵確認全部${meta.label}`" in source
    assert "門向與鉸鏈端" in source


def test_scene_uses_the_final_eight_step_flow_and_exact_upload_contract() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    # 編號由 <b> 呈現，<span> 只放名稱；兩邊都帶數字會顯示成「① 1 建立專案」。
    for number, label in (
        (1, "建立專案"),
        (2, "上傳平面圖"),
        (3, "確定尺寸"),
        (4, "空間與結構"),
        (5, "需求問卷"),
        (6, "配置與預覽"),
        (7, "方案鎖定與視角"),
        (8, "AI 渲染與成果包"),
    ):
        assert f"<b>{number}</b><span>{label}</span>" in html
        assert f"<span>{number} {label}</span>" not in html

    assert 'data-workflow-count="8"' in html
    assert html.count('data-step="') == 8
    assert "7 3D 白模" not in html
    assert "8 即時寫實" not in html
    assert "9 方案鎖定" not in html
    assert "10 AI 渲染" not in html
    assert "3–4" not in html
    assert 'accept=".dxf,.png,.jpg,.jpeg,image/png,image/jpeg,application/dxf"' in html
    assert 'id="project-step"' in html
    assert 'id="upload-step"' in html
    assert 'id="scale-step"' in html
    assert 'id="space-step"' in html
    assert 'id="requirements-step"' in html
    assert 'id="layout-2d-step"' in html
    assert 'id="white-model-3d-step"' in html
    assert 'id="realistic-3d-step"' in html
    assert 'id="basic-profile-panel"' not in html


def test_step_six_3d_workspace_has_a_collapsible_2d_review_sidebar() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    white_model = html.split('id="white-model-3d-step"', 1)[1].split(
        'id="realistic-3d-step"', 1
    )[0]
    assert 'id="configuration-plan-panel"' in white_model
    assert 'id="configuration-plan-toggle"' in white_model
    assert 'id="configuration-plan-image"' in white_model
    assert 'id="configuration-plan-furniture-layer"' in white_model
    assert 'id="configuration-plan-furniture-list"' in white_model
    assert 'id="configuration-pending-list"' in white_model
    assert white_model.index('class="rp-configuration-plan-sticky"') < white_model.index(
        'id="configuration-plan-furniture-list"'
    )
    assert "尚有未處理家具時不能進入下一步" in white_model

    assert "function renderConfigurationPlan" in source
    assert "function configurationBlockingFurniture" in source
    assert "renderConfigurationPlan();" in source
    assert "confirmButton.disabled = blocking.length > 0" in source
    assert "請先從 2D 待處理清單定位修正" in source
    assert "function reflowSingleConfigurationFurniture" in source
    assert "只重排此家具" in source
    assert "syncOverlayToImage(" in source
    assert "element.configurationPlanStage" in source
    assert "void openFurnitureReplacement();" in source
    assert ".rp-configuration-plan" in css
    assert ".rp-configuration-plan-sticky" in css
    assert "position: sticky;" in css
    assert ".rp-configuration-pending {\n  order: -1;" in css
    assert ".is-collapsed" in css


def test_configuration_markers_focus_3d_and_use_visible_selected_numbers() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")
    handler = source.split("const selectConfigurationFurniture =", 1)[1].split(
        "element.configurationPlanLayer.addEventListener", 1
    )[0]

    assert "event.currentTarget === element.configurationPlanLayer" in handler
    assert (
        "event.currentTarget === element.configurationPlanFurnitureList" in handler
    )
    assert "if (fromFurnitureList) void openFurnitureReplacement()" in handler
    assert "syncSelected2dFurnitureToScene({ focus: true })" in handler
    assert "已在 3D 定位家具" in handler
    assert ".rp-configuration-furniture.is-active b" in css
    assert ".rp-configuration-furniture-list button.is-active > b" in css
    assert "background: #1768a6;" in css


def test_2d_furniture_library_has_top_view_icons_and_real_centimetre_sizes() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ FURNITURE_2D_LIBRARY, createFurniture2DItem }} from {json.dumps(module_uri)};
        const variants = FURNITURE_2D_LIBRARY.flatMap((item) => item.variants);
        const roundTable = createFurniture2DItem("dining-table", "round-4");
        const lSofa = createFurniture2DItem("sofa", "l-shape");
        console.log(JSON.stringify({{
          categoryCount: FURNITURE_2D_LIBRARY.length,
          everyVariantHasIcon: variants.every((item) => item.iconPath?.length > 8),
          everyVariantHasCm: variants.every((item) => item.widthCm > 0 && item.depthCm > 0),
          roundTable,
          lSofa,
        }}));
        """
    )

    assert result["categoryCount"] >= 10
    assert result["everyVariantHasIcon"] is True
    assert result["everyVariantHasCm"] is True
    assert result["roundTable"]["widthCm"] == result["roundTable"]["depthCm"]
    assert result["lSofa"]["widthCm"] >= 240


def test_2d_furniture_plan_coordinates_match_the_visible_image_layer() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ planCmToLayerPixel }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(planCmToLayerPixel(
          {{ x: 420, y: 977 }},
          {{ scale: 1.166365, bbox: [111, 155, 944, 1071] }},
          0.553859555936936,
        )));
        """
    )

    assert round(result["x"], 2) == 304.33
    assert round(result["y"], 2) == 150.75


def test_scene_viewer_uses_stable_furniture_pick_proxies_for_3d_selection() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function addFurniturePickProxy" in source
    assert "roompilotPickProxy" in source
    assert "modelRoot.traverse" in source
    assert "object.raycast = () => {}" in source
    assert "pickFurnitureWrapper()" in source
    assert "getSelectedFurnitureId" in source
    assert "projectFurnitureCenters()" in source


def test_2d_furniture_selection_syncs_to_matching_3d_scene_object() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function sceneObjectIndexByFurnitureId" in source
    assert "String(item.furniture_id) === String(furnitureId)" in source
    assert "function selectSceneObjectByFurnitureId" in source
    assert "function syncSelected2dFurnitureToScene" in source
    assert "syncSelected2dFurnitureToScene({ focus: true })" in source
    assert "syncSelected2dFurnitureToScene({ focus: false })" in source


def test_3d_scene_selection_syncs_back_to_2d_furniture_state() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")
    object_list_handler = controller.split("const selectSceneObject =", 1)[1].split(
        "element.objectList?.addEventListener", 1
    )[0]

    assert "onObjectSelect = null" in viewer
    assert "onObjectSelect(selectedWrapper?.userData?.sceneObject || null, lastSceneData)" in viewer
    assert "selectWrapper(wrapper, null, { notify: false })" in viewer
    assert "function syncSceneSelectionTo2dFurniture" in controller
    assert "String(candidate.id) === String(furnitureId)" in controller
    assert "state.selectedFurniture2dId = item.id" in controller
    assert "onObjectSelect: (item) => syncSceneSelectionTo2dFurniture(item)" in controller
    assert "syncSceneSelectionTo2dFurniture" in object_list_handler


def test_scene_configuration_sync_keeps_2d_inventory_aligned_with_scene_objects() -> None:
    module_uri = (STATIC_DIR / "scene_configuration_sync.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          removeFurniture2dBySceneObject,
          upsertFurniture2dFromSceneObject,
        }} from {json.dumps(module_uri)};

        const initial = [{{
          id: "chair-1",
          label: "餐椅",
          roomId: "dining",
          xCm: 10,
          yCm: 20,
          widthCm: 45,
          depthCm: 48,
        }}];
        const moved = upsertFurniture2dFromSceneObject(initial, {{
          furniture_id: "chair-1",
          normalized_type: "dining-chair",
          name_zh_raw: "新餐椅",
          catalog_furniture_id: "catalog-chair",
          model_url: "/chair.glb",
          position_cm: {{ x: 35, z: 45 }},
          rotation_y_deg: 90,
          size_cm: {{ width: 50, depth: 52, height: 82 }},
        }});
        const added = upsertFurniture2dFromSceneObject(moved, {{
          furniture_id: "sofa-1",
          normalized_type: "sofa",
          name_zh_raw: "三人沙發",
          position_cm: {{ x: 100, z: 120 }},
          size_cm: {{ width: 210, depth: 90, height: 85 }},
        }}, {{ roomId: "living", iconPath: "M0 0h48v48H0z" }});
        const failed = upsertFurniture2dFromSceneObject(added, {{
          furniture_id: "sofa-1",
          normalized_type: "sofa",
          name_zh_raw: "三人沙發",
          position_cm: {{ x: 100, z: 120 }},
          size_cm: {{ width: 210, depth: 90, height: 85 }},
          placement_failed: true,
          placement_reason: "與牆面碰撞",
        }});
        const removed = removeFurniture2dBySceneObject(failed, {{ furniture_id: "chair-1" }});
        console.log(JSON.stringify({{ moved, added, failed, removed }}));
        """
    )

    assert result["moved"][0]["label"] == "新餐椅"
    assert result["moved"][0]["roomId"] == "dining"
    assert result["moved"][0]["xCm"] == 35
    assert result["moved"][0]["yCm"] == 45
    assert result["moved"][0]["rotationDeg"] == 90
    assert result["moved"][0]["catalogFurnitureId"] == "catalog-chair"
    assert len(result["added"]) == 2
    assert result["added"][1]["id"] == "sofa-1"
    assert result["added"][1]["roomId"] == "living"
    assert result["failed"][1]["placementFailed"] is True
    assert result["failed"][1]["placementReason"] == "與牆面碰撞"
    assert [item["id"] for item in result["removed"]] == ["sofa-1"]

    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    assert controller.count("upsertFurniture2dFromSceneObject(") >= 4
    assert "removeFurniture2dBySceneObject(" in controller
    assert "furniture2dDefaultsForSceneObject" in controller
    assert "syncFinalValidationToConfiguration" in controller


def test_step_six_progress_entry_reopens_the_dedicated_2d_workspace() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    progress_navigation = source.split(
        '$$(".rp-progress button").forEach((button) => button.addEventListener("click", () => {',
        1,
    )[1].split('$("#reset-project")', 1)[0]

    assert 'goTo("white_model_3d")' not in progress_navigation
    assert "if (state.workflow?.canEnter(step)) goTo(step);" in progress_navigation


def test_single_furniture_reflow_is_locked_until_the_request_finishes() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "configurationReflowInFlight.has(furnitureKey)" in source
    assert "configurationReflowInFlight.add(furnitureKey)" in source
    assert "configurationReflowInFlight.delete(furnitureKey)" in source
    assert "finally {" in source
    # 只鎖住正在重排的那一件；全域鎖會讓一件卡住就停掉整份待處理清單的按鈕。
    assert "reflowing ? \"disabled\"" in source
    assert "reflowLocked" not in source


def test_3d_viewer_flips_scene_z_at_the_visual_boundary_only() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function sceneToWorldPosition" in viewer
    assert "z: -Number(position.z || 0)" in viewer
    assert "function worldToScenePosition" in viewer
    assert "z: Math.round(-Number(position.z || 0) * 100) / 100" in viewer
    assert "function sceneDataForWorld" in viewer
    assert "lastWorldSceneData = sceneDataForWorld(sceneData)" in viewer
    # 房間外殼一律由世界座標資料建；重建與否由 rebuildRoomIfChanged 的指紋決定，
    # 但輸入不能繞過 lastWorldSceneData，否則 Z 翻轉邊界就破了。
    assert "rebuildRoomIfChanged(lastWorldSceneData)" in viewer
    assert "createRoom(worldSceneData)" in viewer
    assert "createRoom(sceneData)" not in viewer.replace("function createRoom(sceneData)", "")
    assert "const worldPosition = sceneToWorldPosition(item.position_cm || {})" in viewer
    assert "callback(worldToScenePosition(planeHit))" in viewer
    assert "function topdownPointerDeltaCm" in viewer
    assert "dragState.startPosition.x + topdownDelta.x" in viewer
    assert "const newPositionCm = worldToScenePosition(wrapper.position)" in viewer
    assert "const verdict = await validatePlacement(item, newPositionCm, newRotationDeg)" in viewer
    assert "item.position_cm = newPositionCm" in viewer


def test_3d_viewer_keeps_manual_furniture_controls_and_number_markers() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createNumberMarker" in viewer
    assert "roompilotNumberMarker" in viewer
    assert "beginPlacement" in viewer
    assert "function addSceneFurniture" in controller
    assert "function deleteSelectedSceneFurniture" in controller
    assert 'id="delete-replacement-furniture"' in (
        STATIC_DIR / "scene.html"
    ).read_text(encoding="utf-8")


def test_2d_collision_footprint_respects_furniture_rotation() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ furnitureCollisionFootprintCm }} from {json.dumps(module_uri)};
        const item = {{ widthCm: 120, depthCm: 45 }};
        console.log(JSON.stringify({{
          zero: furnitureCollisionFootprintCm({{ ...item, rotationDeg: 0 }}),
          clockwise: furnitureCollisionFootprintCm({{ ...item, rotationDeg: 90 }}),
          counterClockwise: furnitureCollisionFootprintCm({{ ...item, rotationDeg: -90 }}),
          flipped: furnitureCollisionFootprintCm({{ ...item, rotationDeg: 180 }}),
        }}));
        """
    )

    assert result == {
        "zero": {"width": 120, "depth": 45},
        "clockwise": {"width": 45, "depth": 120},
        "counterClockwise": {"width": 45, "depth": 120},
        "flipped": {"width": 120, "depth": 45},
    }


def test_2d_collision_checker_uses_rotated_footprints_for_bounds_and_overlap() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    collision_function = source.split("function itemCollision", 1)[1].split(
        "function renderLayoutFurniture", 1
    )[0]

    assert "furnitureCollisionFootprintCm(item)" in collision_function
    assert "furnitureCollisionFootprintCm(other)" in collision_function
    assert "item.widthCm / 2" not in collision_function
    assert "item.depthCm / 2" not in collision_function


def test_2d_layout_defaults_to_showing_every_generated_furniture_item() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    auto_layout = source.split("async function autoLayoutFurniture", 1)[1].split(
        "function renderLayoutRoomFilter", 1
    )[0]

    assert 'state.activeLayoutRoomId = "all";' in auto_layout
    assert "state.furniture2d[0]?.roomId" not in auto_layout


def test_2d_furniture_scale_uses_the_visible_image_content_not_css_letterboxing() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    scale_function = source.split("function layoutPixelsPerCm", 1)[1].split(
        "function itemCollision", 1
    )[0]

    assert "imageContentRect(element.layoutImage)" in scale_function
    assert "element.layoutImage.getBoundingClientRect()" not in scale_function


def test_2d_furniture_normal_and_invalid_colours_are_visually_distinct() -> None:
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")
    normal_rule = css.split(".rp-2d-furniture {", 1)[1].split("}", 1)[0]
    invalid_rule = css.split(".rp-2d-furniture.is-invalid {", 1)[1].split("}", 1)[0]

    assert "border: 2px solid #53646a;" in normal_rule
    assert "border-color: #b94935;" in invalid_rule


def test_room_name_drives_default_furniture_when_the_type_is_not_available() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ recommendedFurnitureForRoom }} from {json.dumps(module_uri)};
        const samples = {{
          bedroom: recommendedFurnitureForRoom({{ type: "default", label: "DORMITORY" }}),
          kitchen: recommendedFurnitureForRoom({{ type: "default", label: "KITCHEN" }}),
          storage: recommendedFurnitureForRoom({{ type: "default", label: "DEPOSIT" }}),
          bathroom: recommendedFurnitureForRoom({{ type: "default", label: "BATHROOM" }}),
          living: recommendedFurnitureForRoom({{ type: "default", label: "LIVING ROOM" }}),
          balcony: recommendedFurnitureForRoom({{ type: "default", label: "BALCONY" }}),
          circulation: recommendedFurnitureForRoom({{ type: "default", label: "CIRCULATION" }}),
        }};
        console.log(JSON.stringify(samples));
        """
    )

    assert {item[0] for item in result["bedroom"]} >= {"bed", "wardrobe"}
    assert {item[0] for item in result["kitchen"]} == {"appliance-cabinet"}
    assert {item[0] for item in result["storage"]} == {"storage-cabinet"}
    assert {item[0] for item in result["bathroom"]} >= {"bathroom-vanity", "mirror-cabinet"}
    assert {item[0] for item in result["living"]} >= {"sofa", "coffee-table", "tv-bench"}
    assert {item[0] for item in result["balcony"]} == {"flower-pots-planter"}
    assert result["circulation"] == []


def test_2d_furniture_pointer_selection_reads_the_rendered_data_attribute() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    handler = source.split("function layoutPointerDown", 1)[1].split(
        "function layoutPointerMove", 1
    )[0]

    assert 'target.getAttribute("data-furniture-2d-id")' in handler


def test_catalog_resolution_keeps_each_room_furniture_as_a_unique_scene_instance() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ createFurniture2DItem, mergeCatalogFurniture }} from {json.dumps(module_uri)};
        const first = createFurniture2DItem("flower-pots-planter", "floor", {{
          id: "living-plant",
          roomId: "living",
          xCm: 120,
          yCm: 80,
        }});
        const second = createFurniture2DItem("flower-pots-planter", "floor", {{
          id: "balcony-plant",
          roomId: "balcony",
          xCm: -220,
          yCm: -410,
        }});
        const catalog = {{
          furniture_id: "catalog-plant",
          normalized_type: "flower-pots-planter",
          model_url: "/models/plant.glb",
          size_cm: {{ width: 19, depth: 19, height: 24 }},
        }};
        console.log(JSON.stringify({{
          first: mergeCatalogFurniture(first, catalog),
          second: mergeCatalogFurniture(second, catalog),
        }}));
        """
    )

    assert result["first"]["furniture_id"] == "living-plant"
    assert result["second"]["furniture_id"] == "balcony-plant"
    assert result["first"]["catalog_furniture_id"] == "catalog-plant"
    assert result["second"]["catalog_furniture_id"] == "catalog-plant"
    assert result["first"]["position_cm"] != result["second"]["position_cm"]
    assert result["first"]["size_cm"] == {"width": 35, "depth": 35, "height": 85}


def test_every_room_default_furniture_has_a_2d_icon_variant() -> None:
    layout_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          FURNITURE_2D_LIBRARY,
          createFurniture2DItem,
          recommendedFurnitureForRoom,
        }} from {json.dumps(layout_uri)};

        const libraryKeys = new Set(FURNITURE_2D_LIBRARY.flatMap((category) =>
          category.variants.map((variant) => `${{category.type}}/${{variant.id}}`)
        ));
        const rooms = [
          "living_room", "bedroom", "dining_room", "kitchen",
          "storage", "bathroom", "balcony", "circulation",
        ].map((type) => ({{ id: type, type }}));
        const recommendations = rooms.flatMap((room) =>
          recommendedFurnitureForRoom(room).map(([type, variant]) => ({{ type, variant }}))
        );
        const samples = recommendations.map((item) =>
          createFurniture2DItem(item.type, item.variant)
        );
        console.log(JSON.stringify({{
          recommendations,
          libraryKeys: [...libraryKeys],
          samples,
        }}));
        """
    )

    missing_variants = [
        item for item in result["recommendations"]
        if f"{item['type']}/{item['variant']}" not in result["libraryKeys"]
    ]
    assert missing_variants == []
    assert result["samples"]


def test_2d_form_replacement_preserves_position_and_uses_new_real_size() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          createFurniture2DItem,
          replaceFurniture2DItem,
        }} from {json.dumps(module_uri)};
        const original = createFurniture2DItem("dining-table", "rect-4", {{
          id: "table-1",
          xCm: 135,
          yCm: -80,
          roomId: "dining-room",
        }});
        const replacement = replaceFurniture2DItem(original, "dining-table", "round-4");
        console.log(JSON.stringify(replacement));
        """
    )

    assert result["id"] == "table-1"
    assert result["xCm"] == 135
    assert result["yCm"] == -80
    assert result["roomId"] == "dining-room"
    assert result["label"] == "四人圓桌"
    assert result["widthCm"] == 110
    assert result["depthCm"] == 110


def test_2d_payload_marks_user_required_furniture_for_server_resolution() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          createFurniture2DItem,
          replaceFurniture2DItem,
          toSceneFurniture,
        }} from {json.dumps(module_uri)};
        const original = createFurniture2DItem("sofa", "compact", {{
          id: "living-sofa",
          userRequired: true,
        }});
        const replacement = replaceFurniture2DItem(original, "sofa", "standard");
        const payload = toSceneFurniture(replacement, {{ positionLocked: false }});
        console.log(JSON.stringify({{
          preservedOnReplacement: replacement.userRequired,
          userRequired: payload.user_required,
          userSpecified: payload.user_specified,
          positionLocked: payload.position_locked,
        }}));
        """
    )

    assert result == {
        "preservedOnReplacement": True,
        "userRequired": True,
        "userSpecified": False,
        "positionLocked": False,
    }


def test_room_usage_recommends_decor_without_restoring_retired_appliances() -> None:
    module_uri = (STATIC_DIR / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          FURNITURE_2D_LIBRARY,
          recommendCompanionFurniture,
        }} from {json.dumps(module_uri)};
        const living = recommendCompanionFurniture("living_room", ["sofa"]);
        const bedroom = recommendCompanionFurniture("bedroom", ["bed"]);
        const kitchen = recommendCompanionFurniture("kitchen", ["dining-table"]);
        const empty = recommendCompanionFurniture("living_room", []);
        const libraryTypes = FURNITURE_2D_LIBRARY.map((item) => item.type);
        console.log(JSON.stringify({{ living, bedroom, kitchen, empty, libraryTypes }}));
        """
    )

    assert "flower-pots-planter" in result["libraryTypes"]
    assert "bedside-table" in result["libraryTypes"]
    assert any(item["type"] == "flower-pots-planter" for item in result["living"])
    assert any(item["type"] == "bedside-table" for item in result["bedroom"])
    assert all(item["type"] != "refrigerator" for item in result["kitchen"])
    assert all(item["type"] != "washer" for item in result["kitchen"])
    assert result["empty"] == []


def test_step_six_prunes_retired_appliances_from_restored_projects() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert '"refrigerator"' in source
    assert '"dishwasher"' in source
    assert '"air-conditioner"' in source
    assert '"/models/ikea/appliance/"' in source
    assert "function pruneRetiredAppliances" in source
    assert "state.furniture2d = removeRetiredAppliancesFromFurniture(state.furniture2d)" in source
    assert "removeRetiredAppliancesFromSceneData(state.sceneData)" in source
    assert "Object.values(state.designSchemes?.schemes || {}).forEach" in source
    assert "const restoredRetiredAppliancesRemoved = pruneRetiredAppliances" in source
    assert "restoredDoorSwingEndpoints > 0" in source
    assert "restoredRetiredAppliancesRemoved > 0" in source
    assert "pruneRetiredAppliances();" in source.split("function renderConfigurationPlan", 1)[1].split(
        "const planSource",
        1,
    )[0]


def test_2d_library_exposes_an_explicit_add_mode_separate_from_replacement() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-2d-furniture-mode"' in html
    assert "state.selectedFurniture2dId = null" in source
    assert "現在是新增模式" in source


def test_space_confirmation_can_add_a_missed_room_and_invalidates_downstream() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-missed-room"' in html
    assert "function addMissedRoom()" in source
    assert "room-manual-" in source
    assert "invalidateDownstreamFrom(\"space_confirmation\"" in source
    assert "請拖曳節點、命名並重新確認空間與結構" in source


def test_room_review_explains_django_icon_conflict_reasons() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert "function roomReviewHint(room)" in source
    assert "function normalizeIconInferredRoomReview(room, polygonCm, index)" in source
    assert "room_icon_function_conflict" in source
    assert "room_icon_area_implausible" in source
    assert "ICON_INFERENCE_MAX_ROOM_AREA_M2" in source
    assert "next.source === \"furniture_icon_inference\"" in source
    assert "savedSpace.rooms.map((room, index)" in source
    assert "normalizeIconInferredRoomReview(room, repairedPolygon, index)" in source
    assert "function splitImplausibleIconRoomsByInteriorWalls(rooms, walls)" in source
    assert "function preparedAutoRoomLabels(rooms, walls)" in source
    assert "preparedAutoRoomLabels(state.rooms, state.structures.walls)" in source
    assert "preparedAutoRoomLabels(state.rooms, state.structures.walls || [])" in source
    assert "function deleteRoom(roomId = state.selectedRoomId)" in source
    assert "data-delete-room" in source
    assert "function updateShowAllRoomsButton()" in source
    assert "目前只有一個空間，沒有其他框選可顯示" in source
    assert "dismissed_auto_room_ids: state.dismissedAutoRoomIds" in source
    assert "dismissed.has(room.id)" in source
    assert "return applyDjangoZoneRoomLabels(" in source
    assert "auto_wall_split_review" in source
    assert "function applyDjangoZoneRoomLabels(rooms)" in source
    assert "django_zone_bed_anchor" in source
    assert "django_zone_storage_candidate" in source
    assert "儲藏室（待確認）" in source
    assert "可能是多個空間，請切割或改名後再確認" in source
    assert "rp-room-review-hint" in css


def test_room_size_is_computed_from_dragged_polygon_instead_of_typed() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-width-cm"' not in html
    assert 'id="room-depth-cm"' not in html
    assert "拖曳左圖紫色節點後，尺寸與面積會自動重新計算。" in html
    assert "系統依目前框選計算" in source
    assert 'font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>' in source


def test_structure_mode_hides_room_overlays_and_explains_selected_lines() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'spaceMode: "rooms"' in source
    assert 'state.spaceMode === "rooms"' in source
    assert 'state.spaceMode = rooms ? "rooms" : "structure"' in source
    assert "橘黃色線＝目前選取的結構" in html
    assert "橘色門弧＝系統偵測的門候選" in html
    assert '$("#show-all-rooms").hidden = !rooms' in source
    assert "點選牆、門、窗、樑或柱後會以橘黃色標示" in source


def test_door_review_exposes_add_select_edit_rotate_and_delete_controls() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-structure-section="door"' in html
    assert 'id="add-active-structure"' in html
    assert 'id="structure-review-list"' in html
    assert 'id="apply-structure-size"' in html
    assert 'id="flip-selected-door"' in html
    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert 'id="delete-selected-structure"' in html
    assert "function renderStructureReviewList()" in source
    assert 'data-structure-review="${escapeHtml(item.id)}"' in source
    assert '["door", "window", "column"].includes(state.structureTool)' in source
    assert 'state.selectedStructure = { id: item.id, kind: tool }' in source


def test_structure_editor_uses_separate_pages_and_exposes_window_controls() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    for kind in ("door", "window", "wall", "beam", "column"):
        assert f'data-structure-section="{kind}"' in html
    assert 'id="structure-review-title"' in html
    assert 'id="structure-review-progress"' in html
    assert 'id="structure-review-list"' in html
    assert 'id="add-active-structure"' in html
    assert 'id="window-sill-height-field"' in html
    assert 'id="window-sill-height-cm"' in html
    assert 'activeStructureKind: "door"' in source
    assert "function setActiveStructureKind(kind)" in source
    assert "function renderStructureReviewList()" in source
    assert "function confirmStructure(kind, structureId)" in source
    assert 'data-confirm-structure="${escapeHtml(item.id)}"' in source
    assert "nextItem.sill_height_cm = sillHeightCm" in source
    assert "Object.assign(item, resolution.item)" in source
    assert 'state.activeStructureKind = tool' in source


def test_beam_drag_guidance_only_appears_during_draw_mode() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="structure-review-guidance"' in html
    assert "按住左圖拖曳樑的起點至終點，放開即完成" in source
    assert 'reviewGuidance.hidden = kind === "beam" && state.structureTool !== "beam"' in source
    assert "renderDoorReviewList();" in source
    assert "function cancelStructureInteraction()" in source


def test_wall_review_exposes_locked_perimeter_and_two_layout_previews() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'id="wall-removal-preview"' in html
    assert 'id="wall-retained-preview-svg"' in html
    assert 'id="wall-demolished-preview-svg"' in html
    assert "可拆牆」只是方案候選，不代表可施工" in html
    assert 'data-wall-demolition="candidate"' in source
    assert "function applyWallDemolitionType" in source
    assert "canMarkWallForDemolition" in source
    assert "最外圍牆不可標記為可拆牆" in source
    assert "renderWallRemovalPreviews" in source
    assert ".rp-wall-removal-compare" in css
    assert ".rp-legend-line.is-removable-wall" in css


def test_each_door_requires_explicit_confirmation_and_supports_hinge_end_reversal() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-active-structure"' in html
    assert 'id="structure-review-progress"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'data-confirm-structure="${escapeHtml(item.id)}"' in source
    assert "function confirmDoor(doorId)" in source
    assert "function rotateSelectedDoor180()" in source
    assert "[item.start, item.end] = [item.end, item.start]" in source
    assert "pendingStructureKind" in source
    assert "一鍵確認全部門" in html
    assert "item.confirmed = false" in source


def test_add_door_mode_takes_priority_over_wall_selection_and_can_be_cancelled() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    pointer_handler = source[source.index("function spacePointerDown"):source.index("function spacePointerMove")]

    assert 'id="cancel-structure-interaction"' in html
    assert "function cancelStructureInteraction()" in source
    assert '["door", "window", "column"].includes(state.structureTool)' in pointer_handler
    assert pointer_handler.index('["door", "window", "column"].includes(state.structureTool)') < pointer_handler.index(
        'const structureNode = event.target.closest("[data-structure-id]")'
    )
    assert "state.selectedStructure = null" in source
    assert "已取消目前操作與結構選取" in source


def test_selected_door_has_large_drag_target_and_resizable_endpoint_handles() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="opening-width-controls"' in html
    assert 'id="opening-width-slider"' in html
    assert 'data-opening-width-step="-5"' in html
    assert 'data-opening-width-step="5"' in html
    assert 'pointer-events="stroke"' in source
    assert 'data-door-handle="start"' in source
    assert 'data-door-handle="end"' in source
    assert "item.swing_end ? cmToPixel(item.swing_end)" in source
    assert "${swingEnd.x} ${swingEnd.y}" in source
    assert "const swingCross =" in source
    assert "swingCross >= 0 ? 1 : 0" in source
    assert 'data-door-move-handle="true"' in source
    assert "let doorResizeDrag = null" in source
    assert "function resizeOpeningFromPointer(" in source
    assert "function snapOpeningToHostWall(" in source
    assert "function setSelectedOpeningWidthCm(" in source
    assert 'openingWidthSlider.addEventListener("input"' in source
    assert "nearestPointOnLine(requested, item.start, item.end)" in source
    assert "item.width_cm = Math.hypot(" in source
    assert "item.confirmed = false" in source


def test_selected_window_has_drag_handles_wall_snap_and_live_width_control() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="opening-width-controls"' in html
    assert 'id="opening-width-label"' in html
    assert 'id="opening-width-slider"' in html
    assert 'data-opening-handle="start"' in source
    assert 'data-opening-handle="end"' in source
    assert 'data-opening-move-handle="true"' in source
    assert '["door", "window"].includes(state.selectedStructure.kind)' in source


def test_structure_legend_uses_heading_space_and_window_markers_match_review_numbers() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    stage_start = html.index('id="space-plan-stage"')
    stage_end = html.index('id="space-plan-caption"')
    heading_html = _space_heading_html(html)
    stage_html = html[stage_start:stage_end]

    assert 'id="plan-structure-legend"' in heading_html
    assert "hidden" in heading_html
    assert 'id="plan-structure-legend"' not in stage_html
    assert 'data-window-number="${index + 1}"' in source
    assert '$("#plan-structure-legend").hidden = rooms;' in source


def test_room_editor_is_embedded_in_the_guided_review_card() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")
    room_panel_start = html.index('id="room-confirmation-panel"')
    room_list_start = html.index('id="room-list"')
    guided_review_html = html[room_panel_start:room_list_start]

    assert 'id="current-room-review"' in guided_review_html
    assert 'id="room-editor"' in guided_review_html
    assert 'class="rp-room-review-editor"' in guided_review_html
    assert 'id="confirm-current-room"' in guided_review_html
    assert 'id="skip-current-room"' in guided_review_html
    assert 'id="room-more-actions"' in html
    assert ".rp-room-floating-editor" not in css
    assert "#space-step .rp-current-room-card" in css
    assert "#space-step .rp-current-room-actions" in css
    assert "#space-step .rp-room-review-queue" in css
    assert "#space-step .rp-space-completion-bar" in css


def test_all_structure_kinds_share_numbering_sizing_and_crud_contract() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-structure-number-kind="${kind}"' in source
    for kind in ("wall", "door", "window", "beam", "column"):
        assert f'structureNumberMarkerSvg("{kind}"' in source
    assert 'id="selected-structure-length-field"' in html
    assert 'id="selected-structure-depth-field"' in html
    assert 'id="structure-3d-preview-panel"' in html
    assert 'id="structure-3d-preview"' in html
    assert "createStructurePreview" in source
    assert "structurePreview.render" in source
    assert "walls: state.structures.walls" in source
    assert "planWidthCm" in source
    assert "planDepthCm" in source
    assert "deleteSelectedStructure" in source
    assert "confirmStructure" in source
    assert "function resizeOpeningFromPointer(" in source
    assert "function setSelectedOpeningWidthCm(" in source
    assert "snapOpeningToHostWall(item" in source
    assert "拖曳此端調整窗寬" in source


def test_beam_supports_drag_to_draw_true_width_and_3d_ceiling_placement() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")
    preview = (STATIC_DIR / "scene_structure_preview.js").read_text(encoding="utf-8")

    assert 'id="add-white-model-beam"' in html
    assert 'id="white-model-beam-width-cm"' in html
    assert 'id="white-model-beam-drop-cm"' in html
    assert "beamDragGeometry" in source
    assert "let structureCreateDrag = null" in source
    assert "function beamBandSvg(" in source
    assert 'data-beam-handle="start"' in source
    assert 'data-beam-handle="end"' in source
    assert "function finishBeamCreateDrag(" in source
    assert 'showStep("space_confirmation")' in source
    assert 'setActiveStructureKind("beam")' in source
    assert "選擇「返回第 4 步修改樑」後" in html
    assert "系統會保留目前家具配置" in html
    assert "不合法的家具會進入右側待處理清單" in html
    assert "第 6 步只局部校正家具" in html
    assert "返回第 4 步修改樑" in html
    assert "function beginBeamPlacement(" in viewer
    assert "beamPlacementRequest" in viewer
    assert "beginBeamPlacement," in viewer
    assert '$("#selected-structure-length-cm").readOnly = isBeam' in source
    assert "element.structureLengthInput" not in source
    for view in ("front", "side", "perspective"):
        assert f'data-structure-preview-view="{view}"' in html
    assert "previewSelectedStructureDraft" in source
    assert 'addEventListener("input", previewSelectedStructureDraft)' in source
    assert "setView(view)" in preview
    assert "focusSelectedStructure" in preview
    assert 'context.visible = view === "perspective"' in preview


def test_beams_and_columns_cannot_overlap_wall_footprints() -> None:
    geometry_uri = (STATIC_DIR / "scene_structure_geometry.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          findStructureWallCollision,
          resolveStructureWallCollisions,
        }} from {json.dumps(geometry_uri)};
        const wall = {{
          id: "wall-1",
          start: {{ x: 0, y: -200 }},
          end: {{ x: 0, y: 200 }},
          thickness_cm: 20,
        }};
        const cases = {{
          columnThrough: findStructureWallCollision({{
            center: {{ x: 12, y: 0 }},
            size_cm: 35,
            depth_cm: 35,
          }}, "column", [wall]),
          columnTouching: findStructureWallCollision({{
            center: {{ x: 27.5, y: 0 }},
            size_cm: 35,
            depth_cm: 35,
          }}, "column", [wall]),
          beamThrough: findStructureWallCollision({{
            start: {{ x: -100, y: 0 }},
            end: {{ x: 100, y: 0 }},
            thickness_cm: 30,
          }}, "beam", [wall]),
          beamTouching: findStructureWallCollision({{
            start: {{ x: -100, y: 0 }},
            end: {{ x: -10, y: 0 }},
            thickness_cm: 30,
          }}, "beam", [wall]),
          beamSupportedAtEnd: findStructureWallCollision({{
            start: {{ x: 0, y: 0 }},
            end: {{ x: 200, y: 0 }},
            thickness_cm: 30,
          }}, "beam", [wall]),
        }};
        const cornerWalls = [
          wall,
          {{
            id: "wall-2",
            start: {{ x: -200, y: 0 }},
            end: {{ x: 200, y: 0 }},
            thickness_cm: 20,
          }},
        ];
        const resolvedColumn = resolveStructureWallCollisions({{
          center: {{ x: 12, y: 12 }},
          size_cm: 35,
          depth_cm: 35,
        }}, "column", cornerWalls, {{
          preferredPoint: {{ x: 200, y: 200 }},
          maxAutoShiftCm: 75,
        }});
        const unresolvedBeam = resolveStructureWallCollisions({{
          start: {{ x: -100, y: 0 }},
          end: {{ x: 100, y: 0 }},
          thickness_cm: 30,
        }}, "beam", [wall], {{
          preferredPoint: {{ x: 200, y: 0 }},
          maxAutoShiftCm: 40,
        }});
        const resolvedSupportedBeam = resolveStructureWallCollisions({{
          start: {{ x: 0, y: 0 }},
          end: {{ x: 200, y: 0 }},
          thickness_cm: 30,
        }}, "beam", [wall], {{
          preferredPoint: {{ x: 100, y: 100 }},
          maxAutoShiftCm: 40,
        }});
        console.log(JSON.stringify({{
          cases,
          resolvedColumn,
          unresolvedBeam,
          resolvedSupportedBeam,
        }}));
        """
    )

    assert result["cases"]["columnThrough"]["wallId"] == "wall-1"
    assert result["cases"]["columnTouching"] is None
    assert result["cases"]["beamThrough"]["wallId"] == "wall-1"
    assert result["cases"]["beamTouching"] is None
    assert result["cases"]["beamSupportedAtEnd"] is None
    assert result["resolvedColumn"]["resolved"] is True
    assert result["resolvedColumn"]["moved"] is True
    assert result["resolvedColumn"]["item"]["center"]["x"] >= 27
    assert result["resolvedColumn"]["item"]["center"]["y"] >= 27
    assert result["unresolvedBeam"]["resolved"] is False
    assert result["unresolvedBeam"]["moved"] is False
    assert result["resolvedSupportedBeam"]["resolved"] is True
    assert result["resolvedSupportedBeam"]["moved"] is True
    assert result["resolvedSupportedBeam"]["item"]["start"]["x"] >= 10

    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    assert 'id="structure-wall-collision-error"' in html
    assert 'id="structure-preview-dimension-hint"' in html
    assert "structureWallCollision" in source
    assert "repairLoadedStructureWallCollisions" in source
    assert "resolveStructureSizeDraft" in source
    assert "structureSizeDraft" in source
    assert "setActiveDimension(dimension)" in (
        STATIC_DIR / "scene_structure_preview.js"
    ).read_text(encoding="utf-8")
    assert "樑柱不可穿過牆體" in source
    assert "confirmStructure" in source
    assert "finishBeamCreateDrag" in source
    assert "addDroppedStructure" in source


def test_room_confirmation_is_isolated_and_supports_confirm_merge_and_split() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-confirmation-progress"' in html
    assert 'data-room-geometry-mode="merge"' in html
    assert 'data-room-geometry-mode="split"' in html
    assert 'id="apply-room-merge"' in html
    assert 'id="cancel-room-geometry"' in html
    assert 'id="confirm-current-room"' in html
    assert "function confirmCurrentRoomAndAdvance()" in source
    assert "function nextRoomForReview(roomId)" in source
    assert "function skipCurrentRoomReview()" in source
    assert 'state.spaceMode === "structure" ? renderStructureSvg() : ""' in source
    assert "function confirmRoom(roomId)" in source
    assert "function mergeSelectedRooms()" in source
    assert "function splitSelectedRoom(start, end)" in source
    assert "state.splitPoints.length === 2" in source
    assert "state.rooms.every((room) => room.confirmed === true)" in source
    assert 'id="rooms-confirmed"' not in html


def test_room_polygon_nodes_can_be_merged_or_split_on_an_edge() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-room-node-mode="merge"' in html
    assert 'data-room-node-mode="split"' in html
    assert 'id="apply-node-merge"' in html
    assert 'id="cancel-node-edit"' in html
    assert "function mergeSelectedRoomNodes()" in source
    assert "function insertRoomNodeAt(point)" in source
    assert "function nearestPointOnRoomEdge(" in source
    assert "state.selectedRoomNodeIndices.length === 2" in source
    assert 'data-room-point="${index}"' in source
    assert "room.confirmed = false" in source


def test_room_review_can_confirm_all_rooms_at_once() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="confirm-all-rooms"' in html
    assert "一鍵確認全部房間" in html
    assert "function confirmAllRooms()" in source
    assert 'room.source = "manual_confirmation"' in source
    assert '$("#confirm-all-rooms").addEventListener("click", confirmAllRooms)' in source
    assert 'confirmAllRoomsButton.disabled = !state.rooms.length || allConfirmed' in source


def test_loaded_cody_rooms_repair_narrow_spikes_before_rendering() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    module_uri = (STATIC_DIR / "scene_room_geometry.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ repairLoadedRoomPolygon }} from {json.dumps(module_uri)};
        const spike = [
          {{ x: 376.6, y: 788.4 }},
          {{ x: 376.6, y: 478.6 }},
          {{ x: 463.5, y: 478.6 }},
          {{ x: 473.6, y: 690.2 }},
          {{ x: 483.6, y: 478.6 }},
          {{ x: 714.1, y: 478.6 }},
          {{ x: 715.4, y: 788.4 }},
        ];
        const lShape = [
          {{ x: 0, y: 0 }},
          {{ x: 400, y: 0 }},
          {{ x: 400, y: 300 }},
          {{ x: 200, y: 300 }},
          {{ x: 200, y: 100 }},
          {{ x: 0, y: 100 }},
        ];
        const nearOrthogonal = [
          {{ x: 0, y: 180 }},
          {{ x: -17, y: 0 }},
          {{ x: 450, y: 17 }},
          {{ x: 445, y: 185 }},
        ];
        const diagonal = [
          {{ x: 0, y: 100 }},
          {{ x: 100, y: 0 }},
          {{ x: 200, y: 100 }},
          {{ x: 100, y: 200 }},
        ];
        console.log(JSON.stringify({{
          repaired: repairLoadedRoomPolygon(spike),
          lShape: repairLoadedRoomPolygon(lShape),
          nearOrthogonal: repairLoadedRoomPolygon(nearOrthogonal),
          diagonal: repairLoadedRoomPolygon(diagonal),
        }}));
        """
    )

    assert "repairLoadedRoomPolygon" in source
    assert 'room.polygon_source === "cody_wall_enclosure"' in source
    assert "room.confirmed !== true" in source
    assert "geometry_repaired: geometryRepaired" in source
    assert len(result["repaired"]) == 4
    assert {"x": 473.6, "y": 690.2} not in result["repaired"]
    assert result["lShape"] == [
        {"x": 0, "y": 0},
        {"x": 400, "y": 0},
        {"x": 400, "y": 300},
        {"x": 200, "y": 300},
        {"x": 200, "y": 100},
        {"x": 0, "y": 100},
    ]
    assert result["nearOrthogonal"] == [
        {"x": -8.5, "y": 182.5},
        {"x": -8.5, "y": 8.5},
        {"x": 447.5, "y": 8.5},
        {"x": 447.5, "y": 182.5},
    ]
    assert result["diagonal"] == [
        {"x": 0, "y": 100},
        {"x": 100, "y": 0},
        {"x": 200, "y": 100},
        {"x": 100, "y": 200},
    ]


def test_manual_upstream_edits_clear_stale_3d_steps_before_saving() -> None:
    workflow_uri = (STATIC_DIR / "scene_workflow.js").as_uri()
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(workflow_uri)};
        const workflow = createWorkflow({{ projectId: "invalidate-project", storage: null }});
        workflow.complete("project", {{ name: "驗收" }});
        workflow.complete("upload", {{ filename: "plan.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        workflow.complete("requirements", {{ basicConfirmed: true, roomsResolved: true }});
        workflow.complete("layout_2d", {{ confirmed: true }});
        workflow.complete("white_model_3d", {{
          confirmed: true,
          expectedFurnitureCount: 1,
          visibleFurnitureCount: 1,
        }});
        workflow.complete("realistic_3d", {{ confirmed: true }});
        const before = workflow.completed;
        workflow.invalidateFrom("layout_2d");
        console.log(JSON.stringify({{ before, after: workflow.completed, canEnter3d: workflow.goTo("white_model_3d") }}));
        """
    )

    assert "realistic_3d" in result["before"]
    assert result["after"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
        "space_confirmation",
        "requirements",
    ]
    assert result["canEnter3d"] is False
    assert "invalidateDownstreamFrom(\"layout_2d\"" in source


def test_requirements_gate_allows_explicit_keep_existing_for_unfilled_rooms() -> None:
    module_uri = (STATIC_DIR / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ requirementsGate }} from {json.dumps(module_uri)};
        const rooms = [{{ id: "living" }}, {{ id: "bedroom" }}];
        const blocked = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms,
          answers: {{ living: {{ confirmed: true, uses: ["日常休息"] }} }},
          keepExistingRoomIds: [],
        }});
        const allowed = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms,
          answers: {{ living: {{ confirmed: true, uses: ["日常休息"] }} }},
          keepExistingRoomIds: ["bedroom"],
        }});
        console.log(JSON.stringify({{ blocked, allowed }}));
        """
    )

    assert result["blocked"]["ready"] is False
    assert result["blocked"]["unresolvedRoomIds"] == ["bedroom"]
    assert result["allowed"]["ready"] is True


def test_requirements_gate_rejects_a_confirmed_room_without_a_usage_choice() -> None:
    module_uri = (STATIC_DIR / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ requirementsGate }} from {json.dumps(module_uri)};
        const result = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms: [{{ id: "living" }}],
          answers: {{ living: {{ confirmed: true, uses: [], furniture: [] }} }},
        }});
        console.log(JSON.stringify(result));
        """
    )

    assert result["ready"] is False
    assert result["unresolvedRoomIds"] == ["living"]


def test_scene_does_not_force_placeholder_furniture_for_an_empty_plan() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "目前沒有指定家具，先放入可刪除的雙人沙發" not in source
    assert "selected_furniture_exact: !allowPendingFurniture" in source


def test_confirmed_rooms_and_structures_are_the_only_3d_floorplan_source() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function confirmedFloorplanEditor(schemeId = activeSchemeId())" in controller
    assert "structures: structuresForScheme(state.structures, schemeId)" in controller
    assert "floorplan_editor: confirmedFloorplanEditor()" in controller
    assert "floorplan_dxf_text: state.confirmedFloorplan?.dxf_text" not in controller
    assert "floorplan.beam_segments" in viewer
    assert "floorplan.columns" in viewer
    assert 'id="selected-structure-editor"' in (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    assert "function deleteSelectedStructure()" in controller
    assert "function applySelectedStructureSize()" in controller
    assert "structureDrag" in controller


def test_column_height_is_locked_to_the_confirmed_floor_height() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function confirmedRoomHeightCm()" in controller
    assert "heightInput.readOnly = isColumn;" in controller
    assert 'isColumn ? "柱高（依樓高，公分）"' in controller
    assert "height_cm: confirmedRoomHeightCm()" in controller
    assert "heightCm: confirmedRoomHeightCm()" in controller
    assert "目前調整：柱高" not in controller
    assert "調整柱寬與高度" not in controller


def test_project_workflow_brand_confirms_before_returning_home() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert '<a id="exit-project" class="brand app-brand" href="/"' in html
    assert 'aria-label="離開專案並返回首頁"' in html
    assert "async function confirmProjectExit(event)" in controller
    assert "要離開目前專案並返回首頁嗎？" in controller
    assert '$("#exit-project").addEventListener("click", confirmProjectExit);' in controller
    assert "await saveSequence.catch(() => null);" in controller
    assert 'location.assign("/");' in controller
    assert "專案尚未完成保存，請稍後再試。" in controller
    assert "if (projectExitConfirmed)" in controller


def test_dxf_rooms_and_structures_are_normalized_for_the_corner_origin_editor() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "floorplan.room_regions || []" in controller
    assert "room.polygon_cm || room.polygon_m || room.polygon || room.exterior" in controller
    assert "room.id || room.room_id" in controller
    assert "floorplan.wall_segments || floorplan.plan_segments" in controller
    assert "floorplan.door_segments || []" in controller
    assert "floorplan.window_segments || []" in controller
    assert "x + (centered ? widthCm / 2 : 0)" in controller
    assert "y + (centered ? depthCm / 2 : 0)" in controller
    assert "configureDxfPreview" in controller


def test_2d_automatic_and_manual_positions_are_validated_by_the_engine() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/layout"' in source
    assert 'api("/api/scene/validate"' in source
    assert "placement_room_id" in source
    assert "floorplan_editor: confirmedFloorplanEditor()" in source


def test_all_18_style_cards_build_complete_four_colour_pbr_style_packs() -> None:
    module_uri = (STATIC_DIR / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ STYLE_PACKS, applyStylePack }} from {json.dumps(module_uri)};
        const scene = {{
          wall: {{ styleLocked: true, color: "#111111", material: "old-wall" }},
          floor: {{ styleLocked: true, color: "#222222", material: "old-floor" }},
          furniture: [
            {{ id: "locked", styleLocked: true, material: {{ color: "#123456" }} }},
            {{ id: "open", styleLocked: false, material: {{ color: "#ffffff" }} }},
          ],
        }};
        const applied = applyStylePack(scene, STYLE_PACKS[0]);
        console.log(JSON.stringify({{
          count: STYLE_PACKS.length,
          complete: STYLE_PACKS.every((pack) =>
            pack.palette.length === 4
            && pack.sourceImage.startsWith("/static/style_cards/")
            && pack.wall.pbr
            && pack.wall.surfaceOption
            && pack.floor.pbr
            && pack.floor.surfaceOption
            && pack.furniture.materialLanguage.length >= 3
            && Object.keys(pack.furnitureRules).length >= 4
            && pack.decorRules.length >= 3
            && Object.keys(pack.placementRules).length >= 2
            && pack.lighting.hdr
            && pack.lighting.profile
            && pack.lighting.colorTemperatureK > 0
            && pack.rendering.gtao.enabled
          ),
          appliedRules: Boolean(
            applied.furnitureRules
            && applied.decorRules
            && applied.placementRules
            && applied.sourceImage
          ),
          paletteMapped: STYLE_PACKS.every((pack) =>
            pack.furniture.color === pack.palette[1]
            && pack.floor.color === pack.palette[2]
            && pack.furniture.accent === pack.palette[3]
          ),
          uniqueCardRules: ["scandinavian", "japanese", "modern_minimal", "cream", "industrial", "american"]
            .every((styleId) => {{
              const rules = STYLE_PACKS
                .filter((pack) => pack.styleId === styleId)
                .map((pack) => JSON.stringify([pack.furnitureRules.signature, pack.decorRules]));
              return new Set(rules).size === 3;
            }}),
          modernLuxeLighting: STYLE_PACKS.find((pack) => pack.id === "american_3").lighting.profile,
          wall: applied.wall,
          floor: applied.floor,
          lockedColor: applied.furniture[0].material.color,
          openColor: applied.furniture[1].material.color,
        }}));
        """
    )

    assert result["count"] == 18
    assert result["complete"] is True
    assert result["appliedRules"] is True
    assert result["paletteMapped"] is True
    assert result["uniqueCardRules"] is True
    assert result["modernLuxeLighting"] == "gallery_neutral"
    assert result["wall"]["color"] != "#111111"
    assert result["wall"]["material"] != "old-wall"
    assert result["wall"]["styleLocked"] is False
    assert result["floor"]["color"] != "#222222"
    assert result["floor"]["material"] != "old-floor"
    assert result["floor"]["styleLocked"] is False
    assert result["lockedColor"] == "#123456"
    assert result["openColor"] != "#ffffff"


def test_realistic_viewer_uses_a_real_pbr_environment_and_gtao_pipeline() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "RoomEnvironment" in viewer
    assert "PMREMGenerator" in viewer
    assert "scene.environment =" in viewer
    assert "lighting.hdr" in viewer
    assert "generatedHdrEnvironment" in viewer
    assert "pmremGenerator.fromScene(environmentScene" in viewer
    assert "activeHdrProfile" in viewer
    assert "EffectComposer" in viewer
    assert "RenderPass" in viewer
    assert "GTAOPass" in viewer
    assert "OutputPass" in viewer
    assert "composer.render" in viewer
    assert "ACESFilmicToneMapping" in viewer
    assert "render-performance" in viewer
    assert "wall_color_hex" in controller
    assert "floor_color_hex" in controller


def test_style_switch_changes_unlocked_models_and_material_surface_types() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="wall-material"' in html
    assert 'id="floor-material"' in html
    assert "replaceUnlockedFurnitureForStyle" in controller
    assert "style=${encodeURIComponent(pack.styleId)}" in controller
    assert "item.user_specified || item.model_locked" in controller
    assert "design_choices.wall_option = resolveSurfaceOption(" in controller
    assert "design_choices.floor_option = resolveSurfaceOption(" in controller
    assert "selected.material_override" in controller
    assert "createMaterialBoundarySurfaces" in viewer
    assert "createRoomSurfaceOverrides" in viewer
    assert "wallMaterialResolver" in viewer
    assert "sceneData.surface_overrides" in controller
    assert "state.sceneData.surface_overrides = []" in controller
    assert "state.sceneData.material_boundary = null" in controller
    assert "state.materialBoundary = null" in controller
    assert 'option value="surface"' not in html
    assert 'id="material-boundary-position"' in html
    assert 'id="material-boundary-direction"' in html
    assert "function removeMaterialBoundary()" in controller


def test_step_six_locks_specified_furniture_from_3d_controls() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="mark-specified-furniture"' not in html
    assert 'id="specified-furniture-reviewed"' not in html
    assert 'id="specified-furniture-status"' in html
    assert "鎖定目前家具為指定需求" not in html
    assert "function markSelectedFurnitureAsSpecified" not in controller
    assert "data-object-lock" in viewer
    assert "鎖定此家具" in viewer
    assert "取消鎖定此家具" in viewer
    assert "item.user_specified = !locked" in viewer
    assert "item.user_required = !locked" in viewer
    assert "item.model_locked = !locked" in viewer
    assert "notifySceneChange(item)" in viewer
    assert "renderSceneObjectList()" in controller


def test_3d_furniture_can_be_deleted_and_each_item_keeps_its_own_material_override() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="delete-replacement-furniture"' in html
    assert 'id="scene-object-list"' not in html
    assert "先由系統選配，再點家具更換" not in html
    assert 'id="configuration-plan-furniture-list"' in html
    assert 'id="delete-realistic-furniture"' in html
    assert "function deleteSelectedSceneFurniture()" in controller
    assert "objects.splice(state.selectedSceneIndex, 1)" in controller
    assert "function setReplacementDrawerOpen(open)" in controller
    assert "function saveSelectedSceneAppearance()" in controller
    assert "function loadSelectedSceneAppearance()" in controller


def test_3d_catalog_supports_engine_validated_replacement_addition_and_final_gate() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'data-replace-furniture-id="' in controller
    assert 'data-add-furniture-id="' in controller
    assert "function addSceneFurniture(" in controller
    assert "whiteViewer.beginPlacement" in controller
    assert 'api("/api/scene/validate"' in controller
    assert 'const finalValidation = await api("/api/scene/layout"' in controller
    assert "item.placement_failed || !item.position_locked" in controller
    assert "function beginPlacement(" in viewer
    assert 'renderer.domElement.style.cursor = "crosshair"' in viewer


def test_added_and_deleted_furniture_refresh_numbering_and_stay_draggable() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function activateWhiteFurnitureEditing()" in controller
    assert "whiteViewer.setInteractionMode(\"edit\")" in controller
    edit_mode = controller.split(
        "function activateWhiteFurnitureEditing()",
        1,
    )[1].split("async function deleteSelectedSceneFurniture()", 1)[0]
    assert "whiteViewer.setViewMode(" not in edit_mode
    assert "button.dataset.viewMode === \"dollhouse\"" not in edit_mode
    assert "const furnitureNumber = state.selectedSceneIndex + 1;" in controller
    assert "家具 ${furnitureNumber} 已新增" in controller

    delete_block = controller.split(
        "async function deleteSelectedSceneFurniture()",
        1,
    )[1].split("async function searchGlbFurniture()", 1)[0]
    assert "renderConfigurationPlan();" in delete_block
    assert "selectSceneObjectByFurnitureId(" in delete_block

    add_block = controller.split(
        "function addSceneFurniture(furnitureId)",
        1,
    )[1].split("async function confirmWhiteModel()", 1)[0]
    assert "renderConfigurationPlan();" in add_block
    assert "activateWhiteFurnitureEditing();" in add_block


def test_catalog_edits_keep_the_current_3d_camera_framing() -> None:
    module_uri = (STATIC_DIR / "scene_viewer_reload.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ reloadViewerPreservingState }} from {json.dumps(module_uri)};
        const calls = [];
        const camera = {{ view_mode: "orbit", position_cm: [120, 200, 80] }};
        const scene = {{ scene_objects: [{{ furniture_id: "chair-1" }}] }};
        const viewer = {{
          getCameraState() {{ calls.push("get-camera"); return camera; }},
          async loadScene(value) {{ calls.push(value === scene ? "load-scene" : "wrong-scene"); }},
          setCameraState(value) {{ calls.push(value === camera ? "restore-camera" : "wrong-camera"); }},
          setInteractionMode(value) {{ calls.push("interaction:" + value); }},
        }};
        const returned = await reloadViewerPreservingState(viewer, scene, {{
          interactionMode: "edit",
        }});
        console.log(JSON.stringify({{ calls, returned }}));
        """
    )

    assert result["calls"] == [
        "get-camera",
        "load-scene",
        "restore-camera",
        "interaction:edit",
    ]
    assert result["returned"] == {
        "view_mode": "orbit",
        "position_cm": [120, 200, 80],
    }


def test_saved_layout_can_rebuild_a_missing_white_model_scene() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "async function recoverSceneDataFromSavedLayout()" in controller
    assert "floorplan: layout.floorplan" in controller
    assert "scene_objects: layout.scene_objects || []" in controller
    recovery_block = controller.split(
        "async function recoverSceneDataFromSavedLayout()",
        1,
    )[1].split("function installUnloadGuard()", 1)[0]
    assert "!state.furniture2d.length" not in recovery_block
    assert "await recoverSceneDataFromSavedLayout();" in controller
    assert 'console.warn("Unable to rebuild saved 3D scene from layout."' in controller
    assert "if (sceneRecoveryError)" in controller


def test_ceiling_conflicts_use_real_obstruction_geometry_and_installation_depth() -> None:
    module_uri = (STATIC_DIR / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ detectCeilingConflicts }} from {json.dumps(module_uri)};
        const result = detectCeilingConflicts({{
          ceilingStyle: "cove",
          roomHeightCm: 280,
          beams: [{{
            id: "beam-1",
            kind: "beam",
            label: "樑 1",
            topCm: 280,
            bottomCm: 240,
            estimated: true,
          }}],
          cabinets: [{{
            id: "cabinet-1",
            kind: "cabinet",
            label: "高櫃",
            topCm: 265,
          }}],
          lights: [{{
            id: "downlight",
            kind: "light",
            label: "崁燈",
            requiredPlenumCm: 12,
          }}],
        }});
        console.log(JSON.stringify(result));
        """
    )

    assert result["finishedHeightCm"] == 262
    assert [item["objectId"] for item in result["conflicts"]] == [
        "beam-1",
        "cabinet-1",
    ]
    assert "樑底 240 cm" in result["conflicts"][0]["reason"]
    assert "圖面估計" in result["conflicts"][0]["reason"]
    assert result["conflicts"][1]["overlapCm"] == 3


def test_ceiling_and_light_choices_create_distinct_three_geometry() -> None:
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createCeilingGeometry(" in viewer
    assert 'ceilingStyle === "cove"' in viewer
    assert 'ceilingStyle === "floating"' in viewer
    assert 'ceilingStyle === "linear"' in viewer
    assert 'ceilingStyle === "wood-grid"' in viewer
    assert "function createStyleLights(" in viewer
    assert 'lightStyle === "track"' in viewer
    assert 'lightStyle === "downlight"' in viewer
    assert 'lightStyle === "paper"' in viewer
    assert "keyLight.shadow.mapSize.set(shadowMapSize, shadowMapSize)" in viewer


def test_viewer_keeps_missing_glbs_editable_without_pretending_the_proxy_is_valid() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    load_scene = source.split("async function loadScene", 1)[1].split(
        "let lastSceneData", 1
    )[0]
    assert "createFallbackFurnitureProxy(" in load_scene
    assert '"資料庫尚未提供 GLB"' in load_scene
    assert '"GLB 載入失敗，請更換家具或檢查資料庫模型權限"' in load_scene
    assert "wrapper.userData.modelLoadFailed = true" in source
    assert "wrapper.userData.sceneObject = item" in source
    assert "addFurniturePickProxy(wrapper, item)" in source
    assert "wrapper?.userData.modelLoadFailed === true" in load_scene
    assert "if (item.placement_failed)" in source
    assert "家具位置無法通過碰撞與淨空檢查" in source
    assert "visibleFurnitureCount" in source
    assert "fallbackFurnitureCount" in source
    assert "controls.enableRotate = false" in source
    assert "controls.enablePan = false" in source
    assert "controls.enableZoom = true" in source
    assert "getDiagnostics" in source
    assert "selectObjectByIndex" in source


def test_configuration_pending_actions_distinguish_model_and_placement_failures() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    pending = source.split(
        "const blockingRooms = configurationBlockingFurnitureByRoom", 1
    )[1].split("const confirmButton", 1)[0]
    handlers = source.split(
        'if (!event.target.closest(CONFIGURATION_PENDING_LIST_SELECTOR)) return;', 1
    )[1].split(
        'element.configurationPlanImage.addEventListener("load"', 1
    )[0]

    assert "modelFailures.has(furnitureKey)" in pending
    assert 'data-replace-configuration-furniture="' in pending
    assert "更換家具" in pending
    assert 'data-reflow-configuration-furniture="' in pending
    assert "只重排此家具" in pending
    assert 'closest("[data-replace-configuration-furniture]")' in handlers
    assert "void openFurnitureReplacement()" in handlers


def test_step_six_pending_rows_offer_removal_and_an_escape_hatch() -> None:
    """待處理清單必須自己就能走完：移除單件，或整批暫緩後進入第 7 步。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    pending = source.split(
        "const blockingRooms = configurationBlockingFurnitureByRoom", 1
    )[1].split("const confirmButton", 1)[0]

    assert 'data-remove-configuration-furniture="' in pending
    assert "移除此家具" in pending
    assert "data-defer-all-configuration-furniture" in pending
    assert "暫緩全部待處理家具並繼續" in pending
    assert "async function removeConfigurationFurniture" in source
    assert "async function deferAllBlockingConfigurationFurniture" in source
    # 暫緩只是把家具移出本次配置並記進 deferred，不放寬 backend/engine 的合法性閘門。
    assert "confirmButton.disabled = blocking.length > 0" in source
    assert ".rp-configuration-pending-escape" in css


def test_step_six_repair_actions_cannot_fail_silently() -> None:
    """每條失敗路徑都要寫進目前步驟看得到的欄位，而不是靜默 return 或寫去第 5 步。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    handlers = source.split(
        'if (!event.target.closest(CONFIGURATION_PENDING_LIST_SELECTOR)) return;', 1
    )[1].split("element.configurationPlanImage.addEventListener(\"load\"", 1)[0]

    assert "function reportConfigurationActionError" in source
    assert "reportConfigurationActionError(errorMessage(error))" in handlers
    # 委派掛在 document 捕獲階段：清單是 innerHTML 全量重繪，掛在清單節點上的監聽
    # 會跟著被換掉的節點一起消失（問卷家具卡片已用過同一個模式）。
    assert 'document.addEventListener("click", (event) => {' in source
    assert 'CONFIGURATION_PENDING_LIST_SELECTOR = "#configuration-pending-list"' in source
    assert "event.target.closest(CONFIGURATION_PENDING_LIST_SELECTOR)" in source
    # 按住按鈕期間凍結重繪，否則瀏覽器不會送出 click，整段動作靜默消失。
    assert "function writeConfigurationPendingList" in source
    assert "configurationPendingPointerDown" in source
    assert "element.configurationPendingList.innerHTML = markup" in source
    # 重排的鎖必須是單件的：全域鎖會讓一件卡住就停掉整份清單的按鈕。
    assert "configurationReflowInFlight.size > 0" not in source
    # dataset 的 id 一律是字串，嚴格相等比對會讓「更換較小款」靜默找不到家具。
    assert "function furniture2dById" in source
    replacement = source.split("async function openFurnitureReplacement", 1)[1].split(
        "async function replaceSelectedLayoutFurniture", 1
    )[0]
    assert "element.layoutError.textContent" not in replacement
    assert "reportConfigurationActionError" in replacement


def test_remote_render_failures_land_in_a_slot_the_viewer_cannot_overwrite() -> None:
    """第 8 步的 502／409 曾經完全沉默：錯誤被寫進 3D 檢視器的狀態列，下一則訊息就蓋掉。"""
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="ai-render-error"' in html
    assert 'id="proposal-review-error"' in html
    # #ai-render-status 是交給 createSceneViewer 的檢視器狀態列，不能拿來放錯誤。
    # 要守的是狀態列仍交給檢視器、錯誤另有專屬欄位；建立選項可以增加。
    assert 'createSceneViewer($("#ai-render-viewer"), element.aiRenderStatus' in source
    assert "function reportRenderActionError" in source
    assert "element.aiRenderStatus.textContent = errorMessage(error)" not in source
    # 後端的 code 也要帶出來，才知道是 image_provider_no_image_returned 這類原因。
    assert "error.detail?.code" in source

    save = source.split("async function saveViewerPngToProject", 1)[1].split(
        "async function refreshSavedRenders", 1
    )[0]
    assert "error?.status !== 409" in save
    assert "state.project = latest.project" in save


def test_replacement_drawer_explains_an_empty_candidate_list() -> None:
    """候選清單空白時必須說出是哪一關擋掉的，而不是留一片空白讓使用者猜。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    loader = source.split("async function loadReplacementCandidates", 1)[1].split(
        "function renderReplacementTypeOptions", 1
    )[0]

    assert "furniture2dById(state.selectedFurniture2dId)" in loader
    # 房間比對原本是嚴格相等，型別一不同就靜默 return，抽屜整片空白。
    assert "String(candidate.id) === String(current.roomId)" in loader
    assert "showReplacementEmptyState(" in loader
    assert "function replacementEmptyStateMarkup" in source
    assert "家具資料庫沒有回傳這個類型的候選" in source
    assert "都沒有可用的 3D 模型" in source
    assert "沒有可用的房間尺寸" in source


def test_room_priority_can_defer_unloadable_models_without_bypassing_review() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    pending = source.split(
        "const blockingRooms = configurationBlockingFurnitureByRoom", 1
    )[1].split("const confirmButton", 1)[0]
    prioritize = source.split(
        "async function prioritizeConfigurationRoomFurniture", 1
    )[1].split("function renderSelectedFurnitureEditor", 1)[0]

    assert 'data-prioritize-configuration-room="' in pending
    assert "group.items.length" in pending
    assert "configurationModelFailures()" in prioritize
    assert "modelFailureIds.has(String(item.id))" in prioritize
    assert "模型無法載入" in prioritize
    assert "furniture.deferred = deferred.map" in prioritize


def test_floor01_repair_controls_cover_openings_questionnaire_layout_and_3d_editing() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert "rotateSelectedStructure(-15)" in controller
    assert "rotateSelectedStructure(15)" in controller
    assert 'id="flip-selected-door"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'id="first-meeting-questionnaire"' in html
    assert 'class="rp-questionnaire-workspace rp-legacy-questionnaire" hidden' in html
    assert 'data-questionnaire-panel="rooms"' in html
    assert 'id="visual-space-nav"' in html
    assert 'id="room-furniture-select"' not in html
    assert "visualPreferencesForRoom(room)" in controller
    assert 'id="layout-room-filter"' in html
    assert "state.activeLayoutRoomId" in controller
    assert "placement_room_id: room.id" in controller
    assert 'data-object-rotate="-15"' in viewer
    assert 'data-object-rotate="15"' in viewer
    assert "Shift+R 反向 15 度" in viewer


def test_3d_view_controls_offer_free_rotation_and_grouped_workflows() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'data-view-mode="orbit"' in html
    assert 'data-view-mode="dollhouse"' not in html
    assert 'data-real-view-mode="orbit"' in html
    assert 'data-proposal-view-mode="orbit"' in html
    assert html.count("自由旋轉") >= 3
    assert "全屋家具配置" not in html
    assert 'data-real-view-mode="dollhouse"' not in html
    assert 'data-proposal-view-mode="dollhouse"' not in html
    assert 'whiteViewer.setViewMode("dollhouse")' not in controller
    assert 'class="rp-toolbar-group" aria-label="檢視方式"' in html
    assert 'class="rp-toolbar-group" aria-label="操作方式"' in html
    assert 'realisticViewer.setViewMode("dollhouse")' not in controller
    assert 'const viewMode = createViewModeState("orbit");' in viewer
    reset_camera = viewer.split("function resetCamera", 1)[1].split(
        "function setCameraPreset", 1
    )[0]
    assert 'setViewMode("orbit")' in reset_camera


def test_realtime_style_material_choices_are_grouped_by_style_with_previews() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    packs = (STATIC_DIR / "scene_style_packs.js").read_text(encoding="utf-8")

    assert "STYLE_MATERIAL_OPTIONS" in packs
    assert "materialPreview" in packs
    assert 'id="wall-material-grouped"' in html
    assert 'id="floor-material-grouped"' in html
    assert "renderGroupedMaterialOptions" in controller
    assert "data-material-preview" in controller
    assert "3D 上即時預覽此風格的牆面、地板與燈光" in html


def test_realtime_style_cards_show_reference_images_and_sync_full_scene_rules() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'class="rp-style-card-preview"' in controller
    assert 'src="${escapeHtml(pack.sourceImage)}"' in controller
    assert "furniture_rules: pack.furnitureRules" in controller
    assert "decor_rules: pack.decorRules" in controller
    assert "placement_rules: pack.placementRules" in controller
    assert "source_image: pack.sourceImage" in controller
    assert "軟裝與擺放規則已載入" in controller
    assert "data-style-card-recommended" in controller
    assert ".rp-style-card-preview" in css


def test_removed_questionnaire_floorplan_overlay_does_not_break_event_binding() -> None:
    controller = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "requirementsOverlay" not in controller
    assert "renderRequirementsOverlay" not in controller


def test_project_resume_restores_flow_rooms_and_generated_scene() -> None:
    workflow_uri = (STATIC_DIR / "scene_workflow.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow, restoreWorkflow }} from {json.dumps(workflow_uri)};
        const storage = {{
          values: new Map(),
          getItem(key) {{ return this.values.get(key) ?? null; }},
          setItem(key, value) {{ this.values.set(key, value); }},
          removeItem(key) {{ this.values.delete(key); }},
        }};
        const original = createWorkflow({{ projectId: "resume-project", storage }});
        original.complete("project", {{ name: "續作專案" }});
        original.complete("upload", {{ filename: "plan.png" }});
        original.complete("recognition", {{ engine: "cody" }});
        original.complete("calibration", {{ distanceCm: 630 }});
        original.goTo("space_confirmation");
        const restored = restoreWorkflow({{
          projectId: "resume-project",
          storage: null,
          snapshot: original.toJSON(),
        }});
        console.log(JSON.stringify({{
          currentStep: restored.currentStep,
          completed: restored.completed,
          canEnterSpace: restored.canEnter("space_confirmation"),
        }}));
        """
    )

    assert result["currentStep"] == "space_confirmation"
    assert result["completed"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
    ]
    assert result["canEnterSpace"] is True

    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    assert "_flow: state.workflow?.toJSON()" in source
    assert "confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null" in source
    assert "active_scheme_id: state.designSchemes.active_scheme_id" in source
    assert "furniture: state.furniture2d" in source


def test_step_four_shows_vertical_scheme_comparison_only_when_b_exists() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'id="design-scheme-compare"' in html
    assert html.index('id="scheme-a-plan-image"') < html.index('id="scheme-b-plan-image"')
    assert 'id="delete-scheme-b"' in html
    assert "hasRenovationChanges(state.structures)" in source
    assert ".rp-design-scheme-compare" in css
    assert "grid" in css


def test_scheme_b_structure_contract_cascades_added_openings_and_follows_wall() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'scheme_id: "B"' in source
    assert "attachedOpeningUpdates" in source
    assert "applyAttachedOpeningUpdates" in source
    assert "刪除牆時會一併刪除" in source
    assert "牆長不足以容納附著" in source


def test_questionnaire_is_preserved_when_structure_changes_mark_layouts_stale() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "markSchemeLayoutsStale(state.designSchemes, message)" in source
    assert "|| state.basicConfirmed" in source
    assert "|| Object.keys(state.visualAnswers || {}).length > 0" in source


def test_steps_six_to_nine_expose_scheme_switching_and_render_lock() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert html.count('data-design-scheme="A"') >= 4
    assert html.count('data-design-scheme="B"') >= 4
    assert 'id="locked-scheme-label"' in html
    assert "placement_variant: activeSchemeId()" in source
    assert 'placement_variant: schemeId' in source
    assert "state.designSchemes.locked_scheme_id = activeSchemeId()" in source
    assert "scheme_id: state.designSchemes.locked_scheme_id || activeSchemeId()" in source
    assert "realistic_3d: realisticIsLive" in source
    assert "sceneData: state.sceneData" in source
    assert "renderRestoredStep()" in source
    assert "recoverConfirmedFloorplan" in source
    assert "await whiteViewer.loadScene(state.sceneData)" in source
    assert "await realisticViewer.loadScene(state.sceneData)" in source
    assert 'state.proposalReview.masterView?.scheme_id === "B"' in source
    assert 'state.workflow?.invalidateFrom?.("proposal_review")' in source


def test_empty_scheme_a_does_not_persist_layout_before_layout_work_exists() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "const hasSchemeLayoutState = Boolean(state.designSchemes.schemes.B)" in source
    assert "layout_2d: layoutIsLive || hasSchemeLayoutState" in source
    assert "layoutIsLive || Object.keys(state.designSchemes.schemes).length" not in source
    assert "const emptySchemeB = restoredSchemeB" in source
    assert "if (emptySchemeB) deleteSchemeB(state.designSchemes)" in source


def test_grouped_surface_cards_sync_their_material_ids_into_native_selects() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function syncSurfaceMaterialSelect(" in source
    assert "syncSurfaceMaterialSelect(kind, items, current)" in source
    assert "select.value = materialId" in source
    assert "select.value !== materialId" in source


def test_realtime_style_step_adds_soft_decor_and_flushes_persistence() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/decorate"' in source
    assert "for (const room of targetRooms)" in source
    assert "placement_room_id: room.id" in source
    assert "? state.rooms" in source
    assert "await ensureAutomaticSoftDecor(pack)" in source
    assert "item.auto_decor_role && item.placement_failed" in source
    assert "saveSequence = saveSequence.catch" in source
    assert "safeStorageSetItem(localStorage, pendingSaveStorageKey(), serialized)" in source
    assert "roompilot.pending-save." in source
    assert "for (let attempt = 0; attempt < 3; attempt += 1)" in source
    assert "const pendingSave = safeStorageGetItem(localStorage, pendingSaveStorageKey())" in source
    assert "base_updated_at: state.project?.updated_at || null" in source
    assert "shouldReplayPendingSave(pendingSave, result.project)" in source
    assert "replay_pending: true" in source
    assert "error.status !== 409" in source
    assert "result = await api(`/api/projects/${state.projectId}`)" in source
    assert "較舊的離線暫存未覆蓋目前版本" in source
    assert 'window.addEventListener("beforeunload"' in source
    assert "pendingSaveCount === 0" in source
    assert "[element.scaleImage, element.spaceImage, element.layoutImage]" in source
    assert ".filter(Boolean)" in source


def test_step_seven_requires_one_locked_room_view_before_batch_rendering() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "function proposalRoomCameraCandidates" in source
    assert "function ensureProposalRoomCandidatePreviews" in source
    assert "proposalRoomPreviewCache" in source
    assert "proposalViewer.capturePng()" in source
    assert "入口視角" in source
    assert "對角視角" in source
    assert "活動視角" in source
    assert "function lockSelectedProposalRoomView" in source
    assert "function confirmProposalRoomViews" in source
    assert "尚有 ${missing.map((room) => room.label).join" in source
    assert 'goTo("ai_render")' in source
    assert "proposalRoomPreviewCache.clear();" in source

    palette_handler = source.split("function confirmRenderPalette()", 1)[1].split(
        "async function prepareAiRender()", 1
    )[0]
    assert "state.proposalReview.roomViews = {};" not in palette_handler
    assert "將沿用第 7 步鎖定的逐房視角" in palette_handler


def test_scheme_generation_degrades_per_item_instead_of_total_failure() -> None:
    """2026-07 盤點方案 B 修復：任一件家具失敗不得再讓整包方案歸零。

    失敗件改列該房「暫不放入」（deferred）清單，其餘照常成案；
    自動推薦另設尺寸預檢，小房間從源頭不被推薦塞不下的家具。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert "? null : placedFurniture" not in source, "全有或全無的 null 回傳必須拆除"
    assert "function deferFailedPlacements(" in source
    assert "function specFitsRoomDimensions(" in source
    assert "已列入「暫不放入」" in source
    assert "方案 B 無法在保留問卷家具需求下產生合法配置" not in source
    assert "目前格局無法在保留問卷需求下產生方案 B 的合法配置" not in source


def test_step_four_plan_stays_fixed_and_resyncs_overlays_after_panel_changes() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert "function observePlanStageResizes()" in source
    assert "new ResizeObserver(scheduleOverlaySync)" in source
    assert "planStageResizeObserver.observe(stage)" in source
    assert 'window.addEventListener("resize", scheduleOverlaySync)' in source
    assert "#space-step .rp-space-review-workspace" in css
    assert "align-items: start;" in css.split(
        "#space-step .rp-space-review-workspace", 1
    )[1].split("}", 1)[0]


def test_primary_bedroom_is_chosen_by_area_not_recognition_order() -> None:
    """QA #6：辨識順序第一間臥室被當成主臥，7.29 m² 因此蓋過 8.04 m² 的真主臥。"""
    module_uri = (STATIC_DIR / "scene_questionnaire_test2.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ questionsForIndividualRooms }} from {json.dumps(module_uri)};
        const square = (metres) => {{
          const side = Math.sqrt(metres) * 100;
          return [
            {{ x: 0, y: 0 }}, {{ x: side, y: 0 }}, {{ x: side, y: side }}, {{ x: 0, y: side }},
          ];
        }};
        const rooms = [
          {{ id: "small", type: "bedroom", polygon_cm: square(7.29) }},
          {{ id: "large", type: "bedroom", polygon_cm: square(8.04) }},
        ];
        const questions = [
          {{ question_id: "q-primary", space_type: "primary_bedroom" }},
          {{ question_id: "q-secondary", space_type: "secondary_bedroom" }},
        ];
        const mapped = questionsForIndividualRooms(questions, rooms);
        console.log(JSON.stringify(mapped.map((item) => [item.room_id, item.source_question_id])));
        """
    )

    assert ["large", "q-primary"] in [list(entry) for entry in result]
    assert ["small", "q-secondary"] in [list(entry) for entry in result]


def test_step_one_button_continues_loaded_project_instead_of_creating_again() -> None:
    """URL 已帶專案時，第 1 步按鈕是「繼續」不是「再建一個」。

    2026-08-03 QA 實測：每按一次「建立專案並繼續」就多一個同名專案。
    """
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    block = source.split("async function createProject(", 1)[1].split(
        "function floorplanExtension(", 1
    )[0]

    assert "if (state.projectId && state.project)" in block
    guard = block.split('await api("/api/projects"', 1)[0]
    assert "return;" in guard, "已載入專案時必須在 POST 之前就返回"
    assert "繼續此專案" in source, "按鈕標籤要隨載入狀態切換"


def test_restore_skips_floorplan_source_until_upload_completed() -> None:
    """還沒上傳平面圖的專案不能去抓 source。

    端點對無上傳專案回 409，抓了會把整段還原誤判為失敗——新專案一進來
    就顯示「畫面還原失敗：HTTP 409」（2026-08-03 QA）。
    """
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    block = source.split("hydrateSceneWallMass();", 1)[1].split(
        "await renderRestoredStep()", 1
    )[0]

    assert block.index('completed.includes("upload")') < block.index("floorplan/source"), (
        "抓 floorplan/source 前必須先確認 upload 步驟已完成"
    )
