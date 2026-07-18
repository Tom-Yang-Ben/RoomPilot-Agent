from __future__ import annotations

import json
import re

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "roompilot" / "server" / "static"


def test_scene_sidebar_numbers_match_viewer_markers() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'class="rp-object-number">#${index + 1}' in source
    assert '"bed-frame": "雙人床"' in source
    assert '"floor-lamp": "落地燈"' in source
    assert '"large-medium-rug": "地毯"' in source
    assert "sceneObjectDisplayName(item, index)" in source


def test_structure_step_explains_pending_manual_door_directions() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "門向待人工確認" in source
    assert "點門後按「切換門向」" in source


def test_scene_uses_the_final_nine_step_flow_and_exact_upload_contract() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    for label in (
        "1 建立專案",
        "2 上傳平面圖",
        "3–4 確定尺寸",
        "5 空間與結構",
        "6 需求問卷",
        "7 2D 家具配置",
        "8 3D 白模",
        "9 即時寫實",
    ):
        assert label in html

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


def test_2d_furniture_library_has_top_view_icons_and_real_centimetre_sizes() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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


def test_every_room_questionnaire_furniture_choice_has_a_2d_icon_variant() -> None:
    layout_uri = (STATIC / "scene_layout2d.js").as_uri()
    requirements_uri = (STATIC / "scene_requirements.js").as_uri()
    scene_source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    label_map = {
        label: (kind, variant)
        for label, kind, variant in re.findall(
            r'"([^"]+)":\s*\[\s*"([^"]+)",\s*"([^"]+)"\s*\]',
            scene_source,
        )
    }
    result = run_workflow_script(
        f"""
        import {{ FURNITURE_2D_LIBRARY, createFurniture2DItem }} from {json.dumps(layout_uri)};
        import {{ ROOM_QUESTION_TEMPLATES }} from {json.dumps(requirements_uri)};

        const choices = [...new Set(Object.values(ROOM_QUESTION_TEMPLATES).flatMap((template) => template.furniture))];
        const libraryKeys = new Set(FURNITURE_2D_LIBRARY.flatMap((category) =>
          category.variants.map((variant) => `${{category.type}}/${{variant.id}}`)
        ));
        const samples = [
          createFurniture2DItem("bedside-table", "compact"),
          createFurniture2DItem("kitchen-island", "standard"),
          createFurniture2DItem("bathroom-vanity", "standard"),
        ];
        console.log(JSON.stringify({{ choices, libraryKeys: [...libraryKeys], samples }}));
        """
    )

    missing_labels = [label for label in result["choices"] if label not in label_map]
    missing_variants = [
        label for label in result["choices"]
        if label in label_map and f"{label_map[label][0]}/{label_map[label][1]}" not in result["libraryKeys"]
    ]
    assert missing_labels == []
    assert missing_variants == []
    assert {item["label"] for item in result["samples"]} == {"床頭櫃", "廚房中島", "浴櫃"}


def test_2d_form_replacement_preserves_position_and_uses_new_real_size() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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


def test_room_usage_recommends_visible_appliances_and_decor_without_overriding_empty_rooms() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    assert any(item["type"] == "refrigerator" for item in result["kitchen"])
    assert result["empty"] == []


def test_2d_library_exposes_an_explicit_add_mode_separate_from_replacement() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-2d-furniture-mode"' in html
    assert "state.selectedFurniture2dId = null" in source
    assert "現在是新增模式" in source


def test_space_confirmation_can_add_a_missed_room_and_invalidates_downstream() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-missed-room"' in html
    assert "function addMissedRoom()" in source
    assert "room-manual-" in source
    assert "invalidateDownstreamFrom(\"space_confirmation\"" in source
    assert "請拖曳節點、命名並重新確認空間與結構" in source


def test_manual_upstream_edits_clear_stale_3d_steps_before_saving() -> None:
    workflow_uri = (STATIC / "scene_workflow.js").as_uri()
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(workflow_uri)};
        const workflow = createWorkflow({{ projectId: "invalidate-project", storage: null }});
        workflow.complete("project", {{ name: "驗收" }});
        workflow.complete("upload", {{ filename: "plan.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{ roomsConfirmed: true, structureConfirmed: true }});
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
    module_uri = (STATIC / "scene_requirements.js").as_uri()
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
    module_uri = (STATIC / "scene_requirements.js").as_uri()
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "目前沒有指定家具，先放入可刪除的雙人沙發" not in source
    assert "selected_furniture_exact: true" in source


def test_confirmed_rooms_and_structures_are_the_only_3d_floorplan_source() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function confirmedFloorplanEditor()" in controller
    assert "floorplan_editor: confirmedFloorplanEditor()" in controller
    assert "floorplan_dxf_text: state.confirmedFloorplan?.dxf_text" not in controller
    assert "floorplan.beam_segments" in viewer
    assert "floorplan.columns" in viewer
    assert 'id="selected-structure-editor"' in (STATIC / "scene.html").read_text(encoding="utf-8")
    assert "function deleteSelectedStructure()" in controller
    assert "function applySelectedStructureSize()" in controller
    assert "structureDrag" in controller


def test_dxf_rooms_and_structures_are_normalized_for_the_corner_origin_editor() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "floorplan.room_regions || []" in controller
    assert "room.polygon_m || room.polygon || room.exterior" in controller
    assert "room.id || room.room_id" in controller
    assert "floorplan.wall_segments || floorplan.plan_segments" in controller
    assert "floorplan.door_segments || []" in controller
    assert "floorplan.window_segments || []" in controller
    assert "x + (centered ? widthM / 2 : 0)" in controller
    assert "y + (centered ? depthM / 2 : 0)" in controller
    assert "configureDxfPreview" in controller


def test_2d_automatic_and_manual_positions_are_validated_by_the_engine() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/layout"' in source
    assert 'api("/api/scene/validate"' in source
    assert "placement_room_id" in source
    assert "floorplan_editor: confirmedFloorplanEditor()" in source


def test_all_18_style_cards_build_complete_four_colour_pbr_style_packs() -> None:
    module_uri = (STATIC / "scene_style_packs.js").as_uri()
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
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

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


def test_3d_furniture_can_be_deleted_and_each_item_keeps_its_own_material_override() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="delete-white-model-furniture"' in html
    assert 'id="delete-realistic-furniture"' in html
    assert "function deleteSelectedSceneFurniture()" in controller
    assert "objects.splice(state.selectedSceneIndex, 1)" in controller
    assert "function saveSelectedSceneAppearance()" in controller
    assert "function loadSelectedSceneAppearance()" in controller


def test_3d_catalog_supports_engine_validated_replacement_addition_and_final_gate() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'data-replace-furniture-id="' in controller
    assert 'data-add-furniture-id="' in controller
    assert "function addSceneFurniture(" in controller
    assert "whiteViewer.beginPlacement" in controller
    assert 'api("/api/scene/validate"' in controller
    assert 'const finalValidation = await api("/api/scene/layout"' in controller
    assert "item.placement_failed || !item.position_locked" in controller
    assert "function beginPlacement(" in viewer
    assert 'renderer.domElement.style.cursor = "crosshair"' in viewer


def test_ceiling_conflicts_use_real_obstruction_geometry_and_installation_depth() -> None:
    module_uri = (STATIC / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ detectCeilingConflicts }} from {json.dumps(module_uri)};
        const result = detectCeilingConflicts({{
          ceilingStyle: "cove",
          roomHeightCm: 280,
          beams: [{{
            id: "beam-1",
            kind: "beam",
            label: "梁 1",
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
    assert "梁底 240 cm" in result["conflicts"][0]["reason"]
    assert "圖面估計" in result["conflicts"][0]["reason"]
    assert result["conflicts"][1]["overlapCm"] == 3


def test_ceiling_and_light_choices_create_distinct_three_geometry() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

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


def test_viewer_never_silently_drops_missing_furniture_and_lock_keeps_zoom() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "createFallbackFurnitureProxy" in source
    assert "if (item.placement_failed)" in source
    assert "家具位置無法通過碰撞與淨空檢查" in source
    assert "visibleFurnitureCount" in source
    assert "fallbackFurnitureCount" in source
    assert "controls.enableRotate = false" in source
    assert "controls.enablePan = false" in source
    assert "controls.enableZoom = true" in source
    assert "getDiagnostics" in source
    assert "selectObjectByIndex" in source


def test_floor01_repair_controls_cover_openings_questionnaire_layout_and_3d_editing() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert "rotateSelectedStructure(-15)" in controller
    assert "rotateSelectedStructure(15)" in controller
    assert "窗寬、門寬與門向都可修正" in html
    assert 'class="rp-questionnaire-workspace"' in html
    assert 'id="requirements-plan-stage"' not in html
    assert 'id="room-furniture-select"' in html
    assert "selectedOptions" in controller
    assert 'id="layout-room-filter"' in html
    assert "state.activeLayoutRoomId" in controller
    assert "placement_room_id: room.id" in controller
    assert 'data-object-rotate="-15"' in viewer
    assert 'data-object-rotate="15"' in viewer
    assert "Shift+R 反向 15 度" in viewer


def test_realtime_style_material_choices_are_grouped_by_style_with_previews() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    packs = (STATIC / "scene_style_packs.js").read_text(encoding="utf-8")

    assert "STYLE_MATERIAL_OPTIONS" in packs
    assert "materialPreview" in packs
    assert 'id="wall-material-grouped"' in html
    assert 'id="floor-material-grouped"' in html
    assert "renderGroupedMaterialOptions" in controller
    assert "data-material-preview" in controller
    assert "3D 上即時預覽此風格的牆面、地板與燈光" in html


def test_realtime_style_cards_show_reference_images_and_sync_full_scene_rules() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

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
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "element.requirementsOverlay?.addEventListener" in controller


def test_project_resume_restores_flow_rooms_and_generated_scene() -> None:
    workflow_uri = (STATIC / "scene_workflow.js").as_uri()
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

    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    assert "_flow: state.workflow?.toJSON()" in source
    assert "confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null" in source
    assert "layout_2d: layoutIsLive ? { furniture: state.furniture2d } : null" in source
    assert "realistic_3d: realisticIsLive" in source
    assert "sceneData: state.sceneData" in source
    assert "renderRestoredStep()" in source
    assert "recoverConfirmedFloorplan" in source
    assert "await whiteViewer.loadScene(state.sceneData)" in source
    assert "await realisticViewer.loadScene(state.sceneData)" in source


def test_realtime_style_step_adds_soft_decor_and_flushes_persistence() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/decorate"' in source
    assert "for (const room of targetRooms)" in source
    assert "placement_room_id: room.id" in source
    assert "!state.keepExistingRoomIds.includes(room.id)" in source
    assert "await ensureAutomaticSoftDecor(pack)" in source
    assert "item.auto_decor_role && item.placement_failed" in source
    assert "saveSequence = saveSequence.catch" in source
    assert "roompilot.pending-save." in source
    assert "for (let attempt = 0; attempt < 3; attempt += 1)" in source
    assert "const pendingSave = localStorage.getItem(pendingSaveStorageKey())" in source
    assert 'window.addEventListener("beforeunload"' in source
    assert "pendingSaveCount === 0" in source
    assert "[element.scaleImage, element.spaceImage, element.requirementsImage, element.layoutImage]" in source
    assert ".filter(Boolean)" in source
