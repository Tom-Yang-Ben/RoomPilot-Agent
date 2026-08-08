from __future__ import annotations

import hashlib
import json
import re
import subprocess

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"


def _space_heading_html(html: str) -> str:
    heading_start = html.index('class="rp-pane-heading"', html.index('id="space-step"'))
    stage_start = html.index('id="space-plan-stage"')
    return html[heading_start:stage_start]


def test_scene_entrypoint_cache_key_matches_bundle_content() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    bundle = (STATIC / "scene_v2.js").read_bytes()
    css = (STATIC / "site.css").read_bytes()
    expected_bundle = hashlib.sha256(bundle).hexdigest()[:12]
    expected_css = hashlib.sha256(css).hexdigest()[:12]

    assert f'src="/static/scene_v2.js?v=sha256-{expected_bundle}"' in html
    assert f'href="/static/site.css?v=sha256-{expected_css}"' in html


def test_space_editor_room_taxonomy_desync_is_recorded() -> None:
    """第 4 步採 backup/yen-2026-08-06 版：房名 <option> 寫死在 scene.html。

    已知缺口（本測試就是它的登記處）：寫死的選單與 scene_v2.js 的
    ROOM_NAME_OPTIONS 是兩份互不同步的詞彙表。saveRoom() 只認 JS 表
    （`ROOM_NAME_OPTIONS.find((item) => item.id === element.roomName.value)`），
    因此只在 HTML 出現的選項會查表失敗、跳「請選擇空間名稱。」而存不進去；
    只在 JS 表出現的類別則永遠無法被選到。使用者資料不會遺失，但選單有死選項。

    若日後要修，正解是把 select 留空、由 JS 依 ROOM_NAME_OPTIONS 生成
    （見 ben 步驟 1–4 移植的 renderRoomNameSelect）。
    """
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert '<select id="room-name">' in html
    assert '<option value="entryway">' in html

    table = source.split("const ROOM_NAME_OPTIONS = Object.freeze([", 1)[1].split("]);", 1)[0]
    js_ids = set(re.findall(r'id:\s*"([a-z_]+)"', table))
    select_html = html.split('<select id="room-name">', 1)[1].split("</select>", 1)[0]
    html_ids = set(re.findall(r'<option value="([a-z_]+)">', select_html))

    # saveRoom() 的值域仍由 JS 表決定，這條不能鬆動。
    assert "ROOM_NAME_OPTIONS.find((item) => item.id === element.roomName.value)" in source

    # 登記目前的脫鉤範圍；數量一變（有人修了或又惡化）就要回來更新這裡。
    assert html_ids - js_ids == {
        "dining_room", "primary_bedroom", "secondary_bedroom",
        "multi_purpose", "circulation", "study",
    }, "HTML 專有（選了會存不進去）的選項集合改變了"
    assert js_ids - html_ids == {"hallway", "bedroom", "stair", "garage"}, (
        "JS 表專有（永遠選不到）的類別集合改變了"
    )


def test_scene_bundle_parses_as_an_es_module(tmp_path) -> None:
    """Keep a browser-breaking syntax error from hiding behind API-only tests."""
    module_file = tmp_path / "scene_v2.mjs"
    module_file.write_bytes((STATIC / "scene_v2.js").read_bytes())
    result = subprocess.run(
        ["node", "--check", str(module_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_requirements_step_has_randomized_test_skip_button() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="randomize-requirements"' in html
    assert "async function randomizeRequirementsForTesting" in source
    assert "ROOM_REQUIREMENT_POLAR_AXES" in source
    assert "state.basicConfirmed = true" in source
    assert "requirement.confirmed = true" in source
    assert 'showQuestionnaireStage("summary")' in source


def test_questionnaire_allows_empty_furniture_for_rooms_without_required_furniture() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "const furnitureRequired = questionnaireFurnitureProgram(room).required.length > 0;" in source
    assert "furniture: !furnitureRequired || furnitureCount > 0," in source


def test_layout_surface_overlay_uses_the_runtime_material_catalog() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    overlay = source.split("function materialPreviewForLayout", 1)[1].split(
        "function renderFurnitureLibrary", 1
    )[0]

    assert "catalogMaterialOptionsForPack(kind, activeQuestionnairePack())" in overlay
    assert "uniqueMaterialOptions" not in overlay


def test_optional_questionnaire_panels_do_not_block_project_restore() -> None:
    source = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")

    assert "element.questionnaireGenerativeEquipment?.addEventListener" in source
    assert "element.questionnaireGenerationNotes?.addEventListener" in source
    assert "element.questionnaireMaterialPairs?.addEventListener" in source
    assert "control?.addEventListener(\"input\"" in source
    assert "element.questionnaireCeilingQuickChoices?.addEventListener" in source
    assert "element.questionnaireMaterialCatalogSearch?.addEventListener" in source


def test_questionnaire_rag_uses_non_blocking_fast_retrieval() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "async function startQuestionnaireRag" in source
    assert 'body: JSON.stringify({ query, top_k: 6, fast: true })' in source
    assert "void startQuestionnaireRag(room)" in source


def test_legacy_weighted_answers_remain_compatible_without_forcing_a_b_ui() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert "PREFERENCE_WEIGHT_OPTIONS" in source
    assert "function selectPreferenceWeight" in source
    assert "preferenceWeight: weight" in source
    assert "preferenceDirection: answerWeightDirection(weight)" in source
    assert "preference_weight: Number(answer.preferenceWeight ?? 0)" in source
    assert "preference_direction: answer.preferenceDirection" in source
    assert ".rp-preference-weight" in css
    assert 'data-preference-weight="${item.value}"' not in source


def test_random_requirement_shortcut_randomizes_wall_and_floor_material_options() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT = 4" in source
    assert "function questionnaireMaterialOptionsForPack" in source
    assert 'const wallOption = randomItem(questionnaireMaterialOptionsForPack("wall", pack), null)' in source
    assert 'const floorOption = randomItem(questionnaireMaterialOptionsForPack("floor", pack), null)' in source
    assert "const options = questionnaireMaterialOptionsForPack(kind, pack)" in source
    assert "defaultWallMaterial: wallMaterial" in source
    assert "floorMaterial" in source


def test_questionnaire_material_card_keeps_the_catalog_color_and_its_own_note() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    material_option = source.split("function materialOptionForPack", 1)[1].split(
        "function questionnaireMaterialOptionsForPack", 1
    )[0]
    assert "packMaterialColor" not in source
    assert "color: packMaterialColor" not in material_option
    assert "note: option.note" in material_option
    assert "recommendation: pack.name" in material_option
    assert "background-color:${escapeHtml(option.color)}" in source
    assert 'element.selectedWallSurface.hidden = true;' in source
    assert "questionnaireCatalogSourceLabel" not in source
    assert "catalogSurfaceIsUsableInRoom" in source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "grid-auto-rows: 86px;" in css
    assert "width: 76px;" in css
    assert "height: 68px;" in css
    assert "background-size: cover;" in css
    assert "background-blend-mode: multiply;" not in css


def test_room_questionnaire_recommends_exact_surface_catalog_records() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    helper = source.split("function catalogMaterialOptionsForPack", 1)[1].split(
        "function randomWholeHouseAnswers", 1
    )[0]

    assert "state.surfaceCatalog || state.sceneData?.surface_catalog" in helper
    assert "surface.surface_id" in helper
    assert "surface.preview_url && surface.texture_url" in helper
    assert "surface.suitable_styles" in helper
    assert "STYLE_MATERIAL_OPTIONS" not in helper
    assert 'api("/api/scene/bootstrap")' in source


def test_room_surfaces_keep_one_main_wall_and_floor_with_functional_exceptions() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "const INDEPENDENT_FLOOR_ROOM_TYPES" in source
    assert '"bathroom"' in source
    assert '"kitchen"' in source
    assert '"entryway"' in source
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
    # bella 版:只有乾區房(非獨立地板房)貢獻並沿用全屋主牆/地面
    assert ".filter((room) => !roomAllowsIndependentFloor(room))" in source
    assert "if (mainFloor && !next.floor?.materialId && !next.floor?.color)" in source
    # 明確牆覆蓋以旗標判定,沿用主牆時不覆寫使用者的牆面
    assert "return surfaces.wallOverrideExplicit === true;" in source
    assert "const restoredWallSurfaceRepairs" in source
    assert "const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {})" in source
    assert "const surfaces = normalizedRoomSurfaces(room, rawSurfaces || {})" in source


def test_circulation_style_inherits_living_room_until_user_confirms_override() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function isCirculationRoom" in source
    assert "function copyLivingRoomStyleToCirculation" in source
    assert "function synchronizeCirculationStyles" in source
    assert "circulationStyleOverrideApproved" in source
    assert "走道目前沿用" in source


def test_interior_walls_butt_against_exterior_inner_face_without_a_visible_gap() -> None:
    # 已確認的牆端點即是真實交界:純函式層不得把內牆退縮半個牆厚,
    # 否則內外牆之間出現白縫。牆段盒必須跨滿整段長度。
    result = run_workflow_script(
        f"""
        import {{ buildSceneModel, shellConfig }} from {json.dumps((STATIC / "scene_shell_geometry.js").as_uri())};
        const model = buildSceneModel({{
          walls: [
            {{ id: "exterior", start: {{x: -200, z: 0}}, end: {{x: 200, z: 0}} }},
            {{ id: "interior", start: {{x: 0, z: 0}}, end: {{x: 0, z: 180}} }},
          ],
        }}, shellConfig({{}}));
        const interior = model.boxes.find((box) => (
          box.role === "wall-section" && box.meta.segmentIndex === 1
        ));
        console.log(JSON.stringify(interior.size));
        """
    )
    assert result[0] == 180


def test_whole_house_wall_finish_keeps_texture_while_avoiding_lighting_variation() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createWallMaterial(wallOption, surfaceCatalog, { tintOnly = false } = {})" in source
    assert "const usesOneWholeHouseWall" in source
    assert "map: material.map || null," in source
    assert "{ tintOnly: false }" in source
    assert "function stabilizeWholeHouseWallAppearance(material)" in source
    assert "new THREE.MeshBasicMaterial" in source
    assert "toneMapped: false" in source
    assert "exteriorWallMaterial = stabilizeWholeHouseWallAppearance(exteriorWallMaterial);" in source


def test_questionnaire_exposes_database_furniture_choices_for_each_room() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert 'id="questionnaire-furniture-options"' in html
    assert 'id="questionnaire-furniture-status"' in html
    assert 'id="questionnaire-furniture-preference"' in html
    assert 'id="refresh-questionnaire-furniture"' in html
    assert 'id="questionnaire-room-usage-options"' in html
    assert 'id="questionnaire-wall-preference"' in html
    assert 'id="questionnaire-floor-preference"' in html
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


def test_questionnaire_renders_room_material_choices_and_pair_recommendations() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="questionnaire-material-pairs"' in html
    assert 'id="questionnaire-wall-options"' in html
    assert 'id="questionnaire-floor-options"' in html
    assert 'renderQuestionnaireMaterialOptions("wall", pack);' in source
    assert 'renderQuestionnaireMaterialOptions("floor", pack);' in source
    assert "renderQuestionnaireMaterialPairs(pack);" in source
    assert ".slice(0, 1);" in source


def test_questionnaire_restores_visual_ceiling_selection_flow() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="questionnaire-ceiling-quick-choices"' in html
    assert 'id="questionnaire-ceiling-picker-dialog"' in html
    assert 'id="questionnaire-ceiling-picker-options"' in html
    assert 'class="rp-questionnaire-native-ceiling-control"' in html
    assert "renderQuestionnaireCeilingQuickChoices(draft);" in source
    assert "openQuestionnaireCeilingDesignStyle" in source


def test_questionnaire_selected_catalog_furniture_drives_step_six_exactly() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    auto_layout = source.split("async function autoLayoutFurniture()", 1)[1].split(
        "async function relayoutFurnitureForScheme", 1
    )[0]

    assert "requirement?.furniture?.selected" in auto_layout
    assert "userSelectedSpecs" in auto_layout
    assert "catalogItem?.user_selected === true" in auto_layout
    assert "item.selectionPriority" in auto_layout
    assert "selected_furniture_exact" in source


def test_room_requirement_round_trip_preserves_selected_and_deferred_furniture() -> None:
    module_uri = (STATIC / "scene_room_requirements.js").as_uri()
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

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
            "scene_unit_contracts.js",
            "scene_calibration.js",
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
        "scene_shell_geometry.js": [
            "scene_architecture.js",
            "scene_window_types.js",
        ],
        "scene_structure_preview.js": ["scene_structure_geometry.js"],
    }

    for importer_name, dependency_names in dependency_edges.items():
        importer = (STATIC / importer_name).read_text(encoding="utf-8")
        for dependency_name in dependency_names:
            dependency = (STATIC / dependency_name).read_bytes()
            expected = hashlib.sha256(dependency).hexdigest()[:12]
            assert (
                f'./{dependency_name}?v=sha256-{expected}' in importer
            ), f"{importer_name} has a stale cache key for {dependency_name}"


def test_placement_busy_overlay_announces_waiting_during_layout() -> None:
    """agent 還在擺放時,畫面必須明確顯示「請稍候」並擋住操作;
    擺完才一次呈現最終結果(不逐步上畫面)。"""
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert 'id="placement-busy"' in html
    assert 'id="placement-busy-text"' in html
    assert "AI 正在擺放家具" in html
    assert "function beginPlacementBusy" in source
    assert "function endPlacementBusy" in source
    # 四個擺位入口都要有等待提示:問卷確認、2D 確認生成、重新配置、逐房擇優
    assert source.count("beginPlacementBusy(") >= 4
    assert source.count("endPlacementBusy(") >= source.count("beginPlacementBusy(") - 1
    assert ".rp-placement-busy" in css


def test_repair_replaced_or_removed_furniture_leaves_no_2d_ghosts() -> None:
    """修復換款或移除後 2D 清單與 3D 不得對不上(廚房鬼影)。bella 逐件增量
    架構天生無鬼影:換款保持同一 furniture_id(只換 catalog_furniture_id)並
    就地 upsert 2D,不會產生殘留新舊兩件;移除則同步從 2D 與 3D 逐件清除。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    # 換款:furniture_id 不變 → 不會留下舊件鬼影,2D 就地 upsert
    replace = source.split("async function replaceSceneFurniture", 1)[1].split(
        "\nasync function ", 1
    )[0]
    assert "furniture_id: current.furniture_id," in replace
    assert "catalog_furniture_id: replacement.furniture_id," in replace
    assert "upsertFurniture2dFromSceneObject(" in replace
    # 移除:2D 與 3D 逐件同步清除(例外一:增量 removeObject,不整場重載)
    delete = source.split("async function deleteSelectedSceneFurniture", 1)[1].split(
        "\nasync function ", 1
    )[0]
    assert "removeFurniture2dBySceneObject(" in delete
    assert "whiteViewer.removeObject(selected.furniture_id)" in delete


def test_confirm_room_views_self_heals_and_reports_blockers() -> None:
    """第 7 步「確認所有房間視角並進入第 8 步」不得無聲失敗(bella 語意):
    有房間尚未鎖定視角時自我修復——跳到第一個缺視角的房間,並把缺哪些
    房間寫進面板狀態列;全部就緒才鎖定代表相機並排程保存。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    confirm = source.split("function confirmProposalRoomViews()")[1].split(
        "\nfunction "
    )[0]

    # 自我修復:跳到第一個未確認視角的房間,不無聲返回
    assert "state.rooms.filter((room) => !validProposalRoomView(room))" in confirm
    assert "selectProposalRoomView(missing[0].id)" in confirm
    # 報告 blocker:面板狀態列說明缺哪些房間
    assert '請先確認 ${missing.map((room) => room.label).join("、")} 的視角。' in confirm
    # 全部就緒才鎖相機並排程保存
    assert "proposalViewer.lockRenderCamera(true)" in confirm
    assert 'scheduleSave("proposal_review")' in confirm


def test_room_view_suggestions_use_world_coordinates() -> None:
    """逐房建議視角必須換算成 three.js 世界座標(世界 z = −場景 z):
    不取負的話第 7/8 步視角上下鏡像,「廚房視角」會框到對面的房間。
    bella 版:座標統一經 roomScenePolygon 翻 Z,再由 roomCameraForAnchor
    以房間多邊形內插算相機位置與目標。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    polygon = source.split("function roomScenePolygon(room)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    # 世界 Z = -場景 Z(scene_viewer 渲染前翻 Z,相機用世界 Z)
    assert "z: center.y - Number(point.y)," in polygon
    # 相機由翻轉後的多邊形算位置與目標,而非未翻轉的原始座標
    anchor = source.split("function roomCameraForAnchor(room, anchorIndex = 0)", 1)[1].split(
        "\nfunction ", 1
    )[0]
    assert "const target = roomSceneTarget(room);" in anchor
    assert "const position = insetRoomCameraPoint(room, anchorIndex);" in anchor
    assert "position_cm: [position.x, 145, position.z]," in anchor
    assert "target_cm: [target.x, 92, target.z]," in anchor


def test_proposal_review_caches_the_scene_per_version() -> None:
    """第 7 步色卡切換要有暫存記憶:同一場景版本只載一次(切色卡不重載、
    不白屏),真的需要載入(換方案/場景重建)才重載並顯示請稍候;
    並發載入以 in-flight promise 去重,避免互相清場造成永久空白。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function ensureProposalSceneLoaded" in source
    assert "proposalSceneVersionLoaded" in source
    assert "場景還在準備中，請稍候…" in source
    assert source.count("proposalSceneVersionLoaded = null") >= 2   # 重建/編輯都失效
    prepare = source.split("async function prepareProposalReview")[1].split(
        "\nfunction "
    )[0]
    assert "ensureProposalSceneLoaded()" in prepare
    assert "proposalViewer.loadScene(" not in prepare              # 只經快取入口載入
    # 6→7 真正載入時要有全畫面等待遮罩(快取命中不閃);載完提示就緒
    ensure = source.split("async function ensureProposalSceneLoaded")[1].split(
        "\nasync function "
    )[0]
    assert "beginPlacementBusy(" in ensure
    assert "endPlacementBusy(" in ensure
    assert "正在準備第 7 步 3D 場景" in ensure
    # loadScene resolve 時首幀還沒畫出來(shader 首次 render 才編譯)——
    # 遮罩必須撐到動畫幀真的呈現;失敗與缺場景都要明說,不得靜默空白
    assert "requestAnimationFrame" in ensure
    assert "3D 場景載入失敗" in ensure
    prepare_head = source.split("async function prepareProposalReview")[1]
    assert "尚未有可用的 3D 場景" in prepare_head.split("\nfunction ")[0]


def test_scheme_choice_is_fixed_after_entering_step_seven() -> None:
    """流程規範:方案 A/B 於第 6 步選定;第 7 步依選定方案比較三張色卡、
    第 8 步依選定色卡逐房生圖 —— 第 7 步面板不再出現 A/B 切換鈕,
    殘餘入口(其他面板的鈕)也必須被擋下並說明。"""
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    proposal_panel = html.split('id="proposal-review-step"')[1].split("</section>")[0]
    assert "data-design-scheme" not in proposal_panel
    assert 'currentStep === "proposal_review" || currentStep === "ai_render"' in source
    assert "方案已於第 6 步選定" in source


def test_step_eight_render_image_replaces_viewer_and_toggles() -> None:
    """第 8 步版面:生圖完成後取代左側 3D 場景(圖疊在 viewer 容器上),
    點圖切回 3D、點「查看生圖」隨時切回,且左側的圖跟著選取房間連動。"""
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    viewer_markup = html.split('id="ai-render-viewer"')[1][:900]
    assert 'id="ai-render-image-stage"' in viewer_markup       # 圖疊在 3D viewer 內
    assert 'id="ai-render-image-toggle"' in viewer_markup
    assert "function updateAiRenderImageStage" in source
    assert "aiRenderImageVisible = done > 0" in source          # 生圖完成即取代 3D
    assert source.count("updateAiRenderImageStage()") >= 4      # 生成/選房/雙向切換都同步


def test_realistic_entry_reveals_the_scene_exactly_once() -> None:
    """進即時寫實一次呈現(bella 架構):realistic_3d 映射白模面板,材質走白模
    側欄「牆面與地面」分頁。進場把問卷表面一次套進場景(applyQuestionnaire
    SurfaceOverridesToScene),再以增量 updateRoomSurfaces 呈現,絕不整場
    重載自我刷新——白模已在畫面上,只換表面。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    entry = source.split("async function confirmWhiteModel()")[1].split(
        "\nasync function "
    )[0]
    # 進場一次把問卷表面套進場景,再逐房增量更新表面(例外一:不得整場 loadScene)
    assert "applyQuestionnaireSurfaceOverridesToScene();" in entry
    assert "await whiteViewer.updateRoomSurfaces(state.sceneData);" in entry
    assert "realisticViewer.loadScene(" not in entry
    assert "whiteViewer.loadScene(" not in entry
    # 進第 7 步的守門與面板切換(不自我刷新場景)
    assert 'state.workflow.goTo("realistic_3d")' in entry
    assert 'showStep("realistic_3d", { preparePanel: false });' in entry


def test_room_layout_always_includes_essential_furniture_specs() -> None:
    """必備家具不被靜默擠掉(bella 語意):bella 不強塞保底家具(尊重使用者
    選件與 selected_furniture_exact),但把床/沙發/餐桌列為配置排序的基礎
    優先級,放不下時最後才讓步,不會先被雜項佔位擠出。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    priority = source.split("function configurationFurniturePriority(item)", 1)[1].split(
        "function compareConfigurationFurniturePriority", 1
    )[0]

    assert "const essentialTypes = new Set([" in priority
    assert '"bed"' in priority
    assert '"sofa"' in priority
    assert '"dining-table"' in priority
    assert "essentialTypes.has(item.type) ? 0 : 1" in priority
    assert "item.userRequired === true ? 0 : 1" in priority


def test_scheme_variants_share_confirmed_architecture() -> None:
    module_uri = (STATIC / "scene_design_schemes.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ structuresForScheme }} from {json.dumps(module_uri)};
        const structures = {{
          walls: [{{ id: "wall-1", demolition_candidate: true }}],
          doors: [{{ id: "door-1", host_wall_id: "wall-1" }}],
          windows: [], beams: [{{ id: "beam-1" }}], columns: [{{ id: "column-1" }}],
        }};
        console.log(JSON.stringify({{
          a: structuresForScheme(structures, "A"),
          b: structuresForScheme(structures, "B"),
        }}));
        """
    )

    assert result["a"] == result["b"]
    assert result["b"]["walls"][0]["id"] == "wall-1"
    assert result["b"]["doors"][0]["host_wall_id"] == "wall-1"


def test_space_save_does_not_duplicate_furniture_or_scene_payloads() -> None:
    module_uri = (STATIC / "scene_design_schemes.js").as_uri()
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
    module_uri = (STATIC / "scene_structure_utils.js").as_uri()
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
    module_uri = (STATIC / "scene_structure_utils.js").as_uri()
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
    module_uri = (STATIC / "scene_structure_utils.js").as_uri()
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function normalizeSceneDoorSegments(sceneData)" in source
    assert "dedupeDoorCandidates(sceneData.floorplan.door_segments)" in source
    assert "normalizeSceneDoorSegments(state.sceneData)" in source


def test_dimensioned_plan_draws_colored_room_outlines_and_size_lines() -> None:
    module_uri = (STATIC / "scene_dimensioned_plan.js").as_uri()
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
    module_uri = (STATIC / "scene_window_types.js").as_uri()
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
    module_uri = (STATIC / "scene_structure_utils.js").as_uri()
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
    module_uri = (STATIC / "scene_unit_contracts.js").as_uri()
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
    module_uri = (STATIC / "scene_unit_contracts.js").as_uri()
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
    module_uri = (STATIC / "scene_unit_contracts.js").as_uri()
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
    module_uri = (STATIC / "scene_unit_contracts.js").as_uri()
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function sceneDataFromGenerateResponse(payload)" in source
    assert "return payload?.scene_json || payload;" in source
    assert "state.sceneData = sceneDataFromGenerateResponse(payload);" in source
    assert "state.sceneData = payload;" not in source


def test_project_restore_normalizes_saved_scene_before_loading_viewers() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "normalizeSavedSceneData" in controller
    assert (
        "const legacySceneData = normalizeSavedSceneData(serverState.white_model_3d?.sceneData);"
        in controller
    )
    assert "state.sceneData = normalizeSavedSceneData(restoredScheme?.sceneData) || legacySceneData;" in controller


def test_window_editor_exposes_floor_to_ceiling_type_and_visual_asset() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="window-type-field"' in html
    assert 'id="selected-window-type"' in html
    assert 'value="floor_to_ceiling"' in html
    assert 'id="window-type-preview"' in html
    assert "黑鋁框左右兩扇玻璃參考" in html
    assert (STATIC / "structure_assets" / "floor-to-ceiling-window.png").is_file()
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


def test_accurate_floorplan_uses_confirmed_segment_walls_without_door_cutting() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    shell = (STATIC / "scene_shell_geometry.js").read_text(encoding="utf-8")

    assert (
        "Persisted Step 4 wall segments already contain true door gaps."
        in viewer
    )
    assert (
        "const builtWallMass = !singleRoomMode && hasAccurateFloorplan && !wallSegments.length"
        in viewer
    )
    assert "buildSegmentWalls(" in viewer
    assert "buildStandaloneOpeningAssemblies(" in viewer
    assert "const mullionPositions = [0];" in viewer
    # 牆段只被 hosted 窗切分;門縫由第 4 步牆段自帶,門只補門楣。
    assert "Step 4 已確認的牆段自帶門縫" in shell
    assert "const intervals = windows" in shell
    assert '"door-lintel"' in shell

    # 行為驗證(純函式層,供 node 單測沿用):牆段中間的門不切牆,門楣件照出。
    result = run_workflow_script(
        f"""
        import {{ buildSceneModel, shellConfig }} from {json.dumps((STATIC / "scene_shell_geometry.js").as_uri())};
        const model = buildSceneModel({{
          walls: [{{ id: "wall-1", start: {{x: -200, z: 0}}, end: {{x: 200, z: 0}} }}],
          doors: [{{
            id: "door-1", width_cm: 90, height_cm: 210, host_wall_id: "wall-1",
            start: {{x: -45, z: 0}}, end: {{x: 45, z: 0}},
          }}],
        }}, shellConfig({{}}));
        const sections = model.boxes.filter((box) => box.role === "wall-section");
        const lintels = model.boxes.filter((box) => box.role === "door-lintel");
        console.log(JSON.stringify({{
          sections: sections.length,
          fullSpan: sections[0]?.size?.[0] || 0,
          lintels: lintels.length,
        }}));
        """
    )
    assert result["sections"] == 1
    assert result["fullSpan"] == 400
    assert result["lintels"] == 1


def test_ceiling_picker_uses_the_selected_ceiling_photo_not_a_lighting_sprite() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    style_packs = (STATIC / "scene_style_packs.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    picker = controller.split("function openQuestionnaireCeilingDesignStyle", 1)[1].split(
        "function selectQuestionnaireCeilingDesignPack", 1
    )[0]
    # bella 版:每張卡以 design pack id 為視覺 key(非天花風格),照片而非燈具 sprite。
    assert 'data-ceiling-design-visual="${escapeHtml(design.id)}"' in picker
    assert '照明：${escapeHtml(lighting?.label || "未指定")}' in picker
    assert 'id: "floating-downlight"' in style_packs
    assert 'id: "floating-no-main"' in style_packs
    assert "ceiling-floating-reference-v2.png" in css


def test_3d_door_openings_are_deduped_after_topology_gap_conversion() -> None:
    # viewer 內聯管線:門先經 doorOpeningForWallTopology 映射到第 4 步牆縫,
    # 再由 dedupeArchitecturalOpeningsFor3d 去重(ID 保護 + 覆蓋比對)。
    # 純函式層的 Union-Find 群聚(clusterOpeningSegments)保留給 node 單測。
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    shell = (STATIC / "scene_shell_geometry.js").read_text(encoding="utf-8")

    assert "const doorSegments = dedupeArchitecturalOpeningsFor3d(" in viewer
    assert "(door) => doorOpeningForWallTopology(wallSegments, door, wallThickness)" in viewer
    assert (
        "doorOpeningForWallTopology(walls, door, cfg.wallThicknessCm)" in shell
    )
    assert "clusterOpeningSegments(" in shell

    result = run_workflow_script(
        f"""
        import {{ clusterOpeningSegments, DEFAULT_SCENE_CONFIG }} from {json.dumps((STATIC / "scene_shell_geometry.js").as_uri())};
        const reps = clusterOpeningSegments([
          {{ id: "door-1", start: {{x: 0, z: 0}}, end: {{x: 92, z: 0}} }},
          {{ start: {{x: 2, z: 6}}, end: {{x: 90, z: 6}} }},
        ], DEFAULT_SCENE_CONFIG, "door");
        console.log(JSON.stringify(reps.map((rep) => rep.id || null)));
        """
    )
    assert result == ["door-1"]


def test_3d_door_openings_merge_overlapping_spans_on_the_same_host_wall() -> None:
    # 重複辨識可能偏離牆線幾公分,但仍是同一道實體門:無 ID 的重複線
    # 依「中點距 ≤30cm 且夾角 ≤10°」合併,代表段取較長者。
    result = run_workflow_script(
        f"""
        import {{ clusterOpeningSegments, DEFAULT_SCENE_CONFIG }} from {json.dumps((STATIC / "scene_shell_geometry.js").as_uri())};
        const reps = clusterOpeningSegments([
          {{ id: "door-7", start: {{x: 100, z: 200}}, end: {{x: 192, z: 200}} }},
          {{ start: {{x: 104, z: 208}}, end: {{x: 188, z: 208}} }},
          {{ id: "door-8", start: {{x: 320, z: 200}}, end: {{x: 410, z: 200}} }},
        ], DEFAULT_SCENE_CONFIG, "door");
        console.log(JSON.stringify(reps.map((rep) => rep.id)));
        """
    )
    assert result == ["door-7", "door-8"]


def test_3d_door_openings_keep_each_confirmed_step4_door_id() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    shell = (STATIC / "scene_shell_geometry.js").read_text(encoding="utf-8")

    # 第 4 步擁有門的身份:兩個非空且不同的 ID 永不合併(純函式層群聚守則)。
    assert "if (leftId && rightId && leftId !== rightId) continue;" in shell
    assert "第 4 步擁有門窗身份" in shell

    result = run_workflow_script(
        f"""
        import {{ clusterOpeningSegments, DEFAULT_SCENE_CONFIG }} from {json.dumps((STATIC / "scene_shell_geometry.js").as_uri())};
        const reps = clusterOpeningSegments([
          {{ id: "door-a", start: {{x: 0, z: 0}}, end: {{x: 90, z: 0}} }},
          {{ id: "door-b", start: {{x: 0, z: 12}}, end: {{x: 90, z: 12}} }},
        ], DEFAULT_SCENE_CONFIG, "door");
        console.log(JSON.stringify(reps.map((rep) => rep.id)));
        """
    )
    assert result == ["door-a", "door-b"]

    # 診斷輸出仍逐 ID 對帳實際渲染的門組件。
    assert "function openingAnchorOnWall" in viewer
    assert "anchorDistance <= 1" in viewer
    assert "mergedDoorIds" in viewer
    assert "roompilotArchitecturalId" in viewer
    assert "expectedIds: expectedDoorIds" in viewer
    assert "renderedIds: renderedDoorIds" in viewer
    assert "leafCount" in viewer
    assert "renderedDoors," in viewer


def test_3d_world_coordinate_conversion_flips_door_swing_endpoint() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "swing_end: segment.swing_end ? flipPointZ(segment.swing_end)" in viewer


def test_step4_shows_open_leaf_in_blue_and_closed_radius_in_green() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'const openLeafLine = `<line x1="${hinge.x}" y1="${hinge.y}" x2="${end.x}" y2="${end.y}"' in source
    assert 'stroke="#1598dc"' in source
    assert "const closedLeafLine = item.swing_end ? `<line" in source
    assert 'x2="${swingEnd.x}" y2="${swingEnd.y}"' in source
    assert 'stroke="#258b45"' in source
    assert '${dragTarget}${line}${openLeafLine}${closedLeafLine}<path' in source


def test_step6_uses_only_the_confirmed_step4_wall_opening_snapshot() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    architecture = (STATIC / "scene_architecture.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function captureConfirmedStructureSnapshot()" in controller
    assert "confirmed_structure_snapshot: state.confirmedStructureSnapshot" in controller
    assert "state.confirmedStructureSnapshot = captureConfirmedStructureSnapshot();" in controller
    assert "state.confirmedStructureSnapshot || state.structures" in controller
    assert "Old saved projects did not persist this snapshot." in controller
    assert "if (opening?.step4_confirmed === true) return false;" in architecture
    assert "A Step 4-confirmed door never creates a wall cut." in architecture
    assert 'doorway_source: "confirmed_wall_gap"' in controller
    assert "confirmed_wall_opening: confirmedWallOpeningForSnapshot(" in controller
    assert "function hydrateConfirmedStructureSnapshot(" in controller
    assert "persisted_step4_wall_gap" in architecture
    # step4_skip_wall_cut 的開口過濾移入純函式層(activeOpenings)。
    shell = (STATIC / "scene_shell_geometry.js").read_text(encoding="utf-8")
    assert "opening.step4_skip_wall_cut !== true" in shell


def test_step4_can_lock_a_manually_corrected_door_opening() -> None:
    viewer = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert 'id="lock-selected-door-opening"' in html
    assert "function lockSelectedDoorOpening()" in viewer
    assert 'item.opening_source = "manual_confirmed";' in viewer
    # 綁定走 optional chaining：離屏／縮圖版面沒有這顆鈕，缺元素時不得整段 bindEvents 中斷。
    assert (
        '$("#lock-selected-door-opening")?.addEventListener("click", lockSelectedDoorOpening);'
        in viewer
    )


def test_requirements_generate_the_white_model_without_an_intermediate_2d_confirmation() -> None:
    viewer = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert "async function generateWhiteModelFromRequirements" in viewer
    assert "const generated = await generateWhiteModelFromRequirements({" in viewer
    assert 'state.workflow?.goTo("layout_2d")' in viewer
    assert 'ensureSchemeB(state.designSchemes, { reason: "questionnaire_alternative" });' in viewer
    assert viewer.count('await confirmLayout2d({ allowPendingFurniture: true });') >= 2
    assert 'state.designSchemes.schemes.B && !state.designSchemes.schemes.B.stale' in viewer
    assert "問卷需求的 2D+3D 配置已建立，可開始調整。" in viewer
    assert 'state.workflow.currentStep === "white_model_3d"' in viewer
    assert 'state.workflow.currentStep === "layout_2d"' in viewer
    assert "returnToRequirementsOnFailure: true" in viewer
    # bella 版:待處理閘門同時判 allowPendingFurniture 與 strictSelectedFurniture
    assert "if (invalid.length && (!allowPendingFurniture || strictSelectedFurniture))" in viewer
    assert "if (generatedInvalid.length && (!allowPendingFurniture || strictSelectedFurniture))" in viewer
    assert "if (missingCatalogModels.length && (!allowPendingFurniture || strictSelectedFurniture))" in viewer
    assert "const sceneFurniture = allowPendingFurniture" in viewer
    assert "selectedFurniture.filter((item) => item.model_url)" in viewer
    assert "尚未找到可用的資料庫 GLB" in viewer
    assert "selected_furniture_exact: strictSelectedFurniture || allowPendingFurniture" in viewer
    assert "完成需求，建立配置方案" in html


def test_requirement_generation_defers_a_single_failed_room_without_breaking_step_six() -> None:
    viewer = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    auto_layout = viewer.split("async function autoLayoutFurniture()", 1)[1].split(
        "async function relayoutFurnitureForScheme", 1
    )[0]
    assert 'console.warn("Room furniture layout deferred", room.id, error);' in auto_layout
    assert "item.placementFailed = true;" in auto_layout
    assert "item.placementReason = errorMessage(error);" in auto_layout
    # 單房失敗只標記,不整批重繪(無 renderLayout2d),autoLayout 結尾仍以
    # 房間篩選 + 家具清單重繪收尾,不因單房丟例外而中斷第 6 步。
    assert "renderLayout2d();" not in viewer
    assert "renderLayoutRoomFilter();\n  renderLayoutFurniture();\n  scheduleSave(\"layout_2d\");" in auto_layout


def test_questionnaire_selects_one_whole_house_style_before_room_specific_finishes() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert 'id="whole-house-style-editor"' in html
    assert 'id="whole-house-style-selection"' in html
    assert 'id="whole-house-wall-options"' not in html
    assert 'id="whole-house-floor-options"' not in html
    assert 'id="whole-house-ceiling-material"' not in html
    assert 'data-questionnaire-stage="profile" class="is-active"' in html
    assert 'data-questionnaire-stage="rooms" disabled' in html
    assert '確認全屋風格，開始逐房設定' in html
    assert "function applyWholeHouseFinishes()" in source
    assert "applyWholeHouseFinishes();" in source
    assert 'if (stage === "profile") return true;' in source
    assert 'if (stage === "rooms") return state.basicConfirmed;' in source
    assert 'showQuestionnaireStage("rooms");' in source
    assert 'if (state.questionnaireStage === "rooms")' in source
    assert "逐房用途與家具" in html


def test_scale_confirmation_reuses_existing_recognition_without_reuploading_the_floorplan() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    calibration = source.split("async function applyCalibration()", 1)[1].split(
        "function planGeometry", 1
    )[0]

    assert "function applyCalibrationToAnalysis" in source
    assert "state.analysis = applyCalibrationToAnalysis(state.analysis, calibration)" in calibration
    assert 'api("/api/floorplan/analyze"' not in calibration
    assert "/floorplan/source" not in calibration


def test_step_six_defaults_to_free_rotation_with_grouped_tools() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-view-mode="orbit" class="is-active">自由旋轉' in html
    assert 'data-view-mode="dollhouse"' not in html
    assert 'class="rp-toolbar-group" aria-label="檢視方式"' in html
    assert 'class="rp-toolbar-group" aria-label="操作方式"' in html
    assert 'whiteViewer.setViewMode("dollhouse")' not in viewer


def test_step_four_has_a_dimensioned_floorplan_confirmation_page() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="load-sample-630"' not in html
    assert "function loadSample630" not in source
    assert '$("#load-sample-630")' not in source


def test_scene_sidebar_numbers_match_viewer_markers() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'class="rp-object-number">#${index + 1}' in source
    assert "function configurationFurnitureNumber" in source
    assert "const furnitureNumber = configurationFurnitureNumber(item, index)" in source
    assert "const furnitureNumber = configurationFurnitureNumber(item)" in source
    assert '"bed-frame": "雙人床"' in source
    assert '"floor-lamp": "落地燈"' in source
    assert '"large-medium-rug": "地毯"' in source
    assert "sceneObjectDisplayName(item, index)" in source


def test_structure_step_explains_pending_manual_door_directions() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "待確認：" in source
    assert "一鍵確認全部門" in html
    assert "confirmAllButton.disabled = !collection.length || allConfirmed" in source
    assert "`一鍵確認全部${meta.label}`" in source
    assert "開門側與鉸鏈端" in source


def test_scene_uses_the_final_eight_step_flow_and_exact_upload_contract() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    for label in (
        "1 建立專案",
        "2 上傳平面圖",
        "3 確定尺寸",
        "4 空間與結構",
        "5 需求問卷",
        "6 配置與預覽",
        "7 方案鎖定與視角",
        "8 AI 渲染與成果包",
    ):
        assert label in html

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")
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


def test_2d_furniture_plan_coordinates_match_the_visible_image_layer() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function addFurniturePickProxy" in source
    assert "roompilotPickProxy" in source
    assert "modelRoot.traverse" in source
    assert "object.raycast = () => {}" in source
    assert "pickFurnitureWrapper()" in source
    assert "getSelectedFurnitureId" in source
    assert "projectFurnitureCenters()" in source


def test_2d_furniture_selection_syncs_to_matching_3d_scene_object() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function sceneObjectIndexByFurnitureId" in source
    assert "String(item.furniture_id) === String(furnitureId)" in source
    assert "function selectSceneObjectByFurnitureId" in source
    assert "function syncSelected2dFurnitureToScene" in source
    assert "syncSelected2dFurnitureToScene({ focus: true })" in source
    assert "syncSelected2dFurnitureToScene({ focus: false })" in source


def test_3d_scene_selection_syncs_back_to_2d_furniture_state() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
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
    module_uri = (STATIC / "scene_configuration_sync.js").as_uri()
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

    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    assert controller.count("upsertFurniture2dFromSceneObject(") >= 4
    assert "removeFurniture2dBySceneObject(" in controller
    assert "furniture2dDefaultsForSceneObject" in controller
    assert "syncFinalValidationToConfiguration" in controller


def test_step_six_progress_entry_prefers_the_integrated_3d_workspace() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'if (step === "layout_2d")' in source
    assert 'state.workflow?.canEnter("white_model_3d")' in source
    assert 'goTo("white_model_3d")' in source


def test_single_furniture_reflow_is_locked_until_the_request_finishes() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "configurationReflowInFlight.has(furnitureKey)" in source
    assert "configurationReflowInFlight.add(furnitureKey)" in source
    assert "configurationReflowInFlight.delete(furnitureKey)" in source
    assert "finally {" in source
    assert "reflowLocked ? \"disabled\"" in source


def test_3d_viewer_flips_scene_z_at_the_visual_boundary_only() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function sceneToWorldPosition" in viewer
    assert "z: -Number(position.z || 0)" in viewer
    assert "function worldToScenePosition" in viewer
    assert "z: Math.round(-Number(position.z || 0) * 100) / 100" in viewer
    assert "function sceneDataForWorld" in viewer
    assert "lastWorldSceneData = sceneDataForWorld(sceneData)" in viewer
    assert "createRoom(lastWorldSceneData)" in viewer
    assert "const worldPosition = sceneToWorldPosition(item.position_cm || {})" in viewer
    assert "callback(worldToScenePosition(planeHit))" in viewer
    assert "function topdownPointerDeltaCm" in viewer
    assert "dragState.startPosition.x + topdownDelta.x" in viewer
    assert "const newPositionCm = worldToScenePosition(wrapper.position)" in viewer
    assert "const verdict = await validatePlacement(item, newPositionCm, newRotationDeg)" in viewer
    assert "item.position_cm = newPositionCm" in viewer


def test_3d_viewer_keeps_manual_furniture_controls_and_number_markers() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createNumberMarker" in viewer
    assert "roompilotNumberMarker" in viewer
    assert "beginPlacement" in viewer
    assert "function addSceneFurniture" in controller
    assert "function deleteSelectedSceneFurniture" in controller
    assert 'id="delete-replacement-furniture"' in (
        STATIC / "scene.html"
    ).read_text(encoding="utf-8")


def test_2d_collision_footprint_respects_furniture_rotation() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    collision_function = source.split("function itemCollision", 1)[1].split(
        "function renderLayoutFurniture", 1
    )[0]

    assert "furnitureCollisionFootprintCm(item)" in collision_function
    assert "furnitureCollisionFootprintCm(other)" in collision_function
    assert "item.widthCm / 2" not in collision_function
    assert "item.depthCm / 2" not in collision_function


def test_2d_layout_defaults_to_showing_every_generated_furniture_item() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    auto_layout = source.split("async function autoLayoutFurniture", 1)[1].split(
        "function renderLayoutRoomFilter", 1
    )[0]

    assert 'state.activeLayoutRoomId = "all";' in auto_layout
    assert "state.furniture2d[0]?.roomId" not in auto_layout


def test_2d_furniture_scale_uses_the_visible_image_content_not_css_letterboxing() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    scale_function = source.split("function layoutPixelsPerCm", 1)[1].split(
        "function itemCollision", 1
    )[0]

    assert "imageContentRect(element.layoutImage)" in scale_function
    assert "element.layoutImage.getBoundingClientRect()" not in scale_function


def test_2d_furniture_normal_and_invalid_colours_are_visually_distinct() -> None:
    css = (STATIC / "site.css").read_text(encoding="utf-8")
    normal_rule = css.split(".rp-2d-furniture {", 1)[1].split("}", 1)[0]
    invalid_rule = css.split(".rp-2d-furniture.is-invalid {", 1)[1].split("}", 1)[0]

    assert "border: 2px solid #53646a;" in normal_rule
    assert "border-color: #b94935;" in invalid_rule


def test_room_name_drives_default_furniture_when_the_type_is_not_available() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    assert {item[0] for item in result["kitchen"]} == {"dining-table", "dining-chair", "appliance-cabinet"}
    assert {item[0] for item in result["storage"]} == {"storage-cabinet"}
    assert {item[0] for item in result["bathroom"]} >= {"bathroom-vanity", "mirror-cabinet"}
    assert {item[0] for item in result["living"]} >= {"sofa", "coffee-table", "tv-bench"}
    assert {item[0] for item in result["balcony"]} == {"flower-pots-planter"}
    assert result["circulation"] == []


def test_2d_furniture_pointer_selection_reads_the_rendered_data_attribute() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    handler = source.split("function layoutPointerDown", 1)[1].split(
        "function layoutPointerMove", 1
    )[0]

    assert 'target.getAttribute("data-furniture-2d-id")' in handler


def test_catalog_resolution_keeps_each_room_furniture_as_a_unique_scene_instance() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    layout_uri = (STATIC / "scene_layout2d.js").as_uri()
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


def test_2d_payload_marks_user_required_furniture_for_server_resolution() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
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
    assert all(item["type"] != "refrigerator" for item in result["kitchen"])
    assert all(item["type"] != "washer" for item in result["kitchen"])
    assert result["empty"] == []


def test_step_six_prunes_retired_appliances_from_restored_projects() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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


def test_room_review_explains_django_icon_conflict_reasons() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-width-cm"' not in html
    assert 'id="room-depth-cm"' not in html
    assert "拖曳左圖紫色節點後，尺寸與面積會自動重新計算。" in html
    assert "系統依目前框選計算" in source
    assert 'font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>' in source


def test_structure_mode_hides_room_overlays_and_explains_selected_lines() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'spaceMode: "rooms"' in source
    assert 'state.spaceMode === "rooms"' in source
    assert 'state.spaceMode = rooms ? "rooms" : "structure"' in source
    assert "橘黃色線＝目前選取的結構" in html
    assert "橘色門弧＝系統偵測的門候選" in html
    assert '$("#show-all-rooms").hidden = !rooms' in source
    assert "點選牆、門、窗、樑或柱後會以橘黃色標示" in source


def test_door_review_exposes_add_select_edit_rotate_and_delete_controls() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="structure-review-guidance"' in html
    assert "按住左圖拖曳樑的起點至終點，放開即完成" in source
    assert 'reviewGuidance.hidden = kind === "beam" && state.structureTool !== "beam"' in source
    assert "renderDoorReviewList();" in source
    assert "function cancelStructureInteraction()" in source


def test_wall_review_keeps_one_fixed_structure_and_a_dormant_preview() -> None:
    """牆體在第 4 步是全案基準：不提供逐面「可拆／保留」切換。

    第 4 步採 backup/yen-2026-08-06 版後，A/B 格局預覽的標記與函式都在，
    但**沒有任何呼叫點**——yen 本身就是這個狀態，區塊永遠 hidden、兩張 SVG
    永遠空的。這裡把「休眠」釘住：要嘛哪天接上 renderWallRemovalPreviews()
    並改這條測試，要嘛整組移除，別讓它以「看起來有功能」的樣子長期躺著。
    """
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="wall-removal-preview"' in html
    assert 'id="wall-retained-preview-svg"' in html
    assert 'id="wall-demolished-preview-svg"' in html
    assert "僅供規劃比較" in html
    assert "function renderWallRemovalPreviews()" in source
    assert source.count("renderWallRemovalPreviews") == 1, (
        "renderWallRemovalPreviews 目前是死碼；若已接上呼叫點請更新這條測試"
    )
    # 逐面切換 UI 仍不得回來，牆一律鎖定為基準。
    assert "${wallTypeToggle}" not in source
    assert "${wallState}" not in source
    assert "demolition_candidate = false" in source


def test_manual_wall_draw_uses_visible_two_point_flow_and_double_delete_confirmation() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'state.activeStructureKind === "wall" && state.structureTool === "wall"' in source
    assert "state.structureLineStart" in source
    assert "起點已設定，請點終點" in source
    assert "structureLinePreviewEnd" in source
    assert "請再點終點" in source
    assert "牆長至少需 25 公分" in source
    assert "pendingWallDeleteId" in source
    assert "再次點擊確認刪除牆" in source


def test_each_door_requires_explicit_confirmation_and_supports_hinge_end_reversal() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-active-structure"' in html
    assert 'id="structure-review-progress"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'data-confirm-structure="${escapeHtml(item.id)}"' in source
    assert "function confirmDoor(doorId)" in source
    assert "function rotateSelectedDoor180()" in source
    assert "[item.start, item.end] = [item.end, item.start]" in source
    assert "pendingStructureKind" in source
    assert "一鍵確認全部門" in html
    assert "door.confirmed = false" in source


def test_add_door_mode_takes_priority_over_wall_selection_and_can_be_cancelled() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    assert 'openingWidthSlider?.addEventListener("input"' in source
    assert "nearestPointOnLine(requested, item.start, item.end)" in source
    assert "item.width_cm = Math.hypot(" in source
    assert "item.confirmed = false" in source


def test_selected_window_has_drag_handles_wall_snap_and_live_width_control() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="opening-width-controls"' in html
    assert 'id="opening-width-label"' in html
    assert 'id="opening-width-slider"' in html
    assert 'data-opening-handle="start"' in source
    assert 'data-opening-handle="end"' in source
    assert 'data-opening-move-handle="true"' in source
    assert '["door", "window"].includes(state.selectedStructure.kind)' in source


def test_structure_legend_uses_heading_space_and_window_markers_match_review_numbers() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    stage_start = html.index('id="space-plan-stage"')
    stage_end = html.index('id="space-plan-caption"')
    heading_html = _space_heading_html(html)
    stage_html = html[stage_start:stage_end]

    assert 'id="plan-structure-legend"' in heading_html
    assert "hidden" in heading_html
    assert 'id="plan-structure-legend"' not in stage_html
    assert 'data-window-number="${index + 1}"' in source
    assert '$("#plan-structure-legend").hidden = rooms;' in source


def test_room_editor_exists_exactly_once_inside_the_plan_heading_toolbar() -> None:
    """房間編輯器只有一份，且掛在圖面標題工具列（backup/yen-2026-08-06 第 4 步）。

    重點是「只有一份」：先前曾同時存在工具列與引導卡兩份，七組 id 重複，
    querySelector 一半接到工具列、一半接到引導卡。yen 版把它收在
    `.rp-room-toolbar-editor`，引導卡不存在。
    """
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")
    heading_html = _space_heading_html(html)

    assert 'class="rp-plan-heading-tools"' in heading_html
    assert html.count('id="room-editor"') == 1
    assert 'id="room-editor"' in heading_html
    assert 'class="rp-editor-box rp-room-toolbar-editor"' in heading_html
    assert 'id="current-room-review"' not in html
    assert ".rp-room-floating-editor" not in css
    assert "#space-step .rp-plan-heading-tools" in css
    assert "#space-step .rp-room-editor-summary" in css
    assert "display: contents" in css
    assert "#space-step #show-all-rooms" in css


def test_all_structure_kinds_share_numbering_sizing_and_crud_contract() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    preview = (STATIC / "scene_structure_preview.js").read_text(encoding="utf-8")

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
    geometry_uri = (STATIC / "scene_structure_geometry.js").as_uri()
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

    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    assert 'id="structure-wall-collision-error"' in html
    assert 'id="structure-preview-dimension-hint"' in html
    assert "structureWallCollision" in source
    assert "repairLoadedStructureWallCollisions" in source
    assert "resolveStructureSizeDraft" in source
    assert "structureSizeDraft" in source
    assert "setActiveDimension(dimension)" in (
        STATIC / "scene_structure_preview.js"
    ).read_text(encoding="utf-8")
    assert "樑柱不可穿過牆體" in source
    assert "confirmStructure" in source
    assert "finishBeamCreateDrag" in source
    assert "addDroppedStructure" in source


def test_room_confirmation_is_isolated_and_supports_confirm_merge_and_split() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-confirmation-progress"' in html
    assert 'data-room-geometry-mode="merge"' in html
    assert 'data-room-geometry-mode="split"' in html
    assert 'id="apply-room-merge"' in html
    assert 'id="cancel-room-geometry"' in html
    # 逐房確認走清單本身：每張房間卡自帶「確認」與「刪除」鍵。
    assert 'data-room-id="${escapeHtml(room.id)}"' in source
    assert 'data-confirm-room="${escapeHtml(room.id)}"' in source
    assert 'data-delete-room="${escapeHtml(room.id)}"' in source
    assert 'state.spaceMode === "structure" ? renderStructureSvg() : ""' in source
    assert "function confirmRoom(roomId)" in source
    assert "function mergeSelectedRooms()" in source
    assert "function splitSelectedRoom(start, end)" in source
    assert "state.splitPoints.length === 2" in source
    assert "state.rooms.every((room) => room.confirmed === true)" in source
    assert 'id="rooms-confirmed"' not in html


def test_room_polygon_nodes_can_be_merged_or_split_on_an_edge() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="confirm-all-rooms"' in html
    assert "一鍵確認全部房間" in html
    assert "function confirmAllRooms()" in source
    assert 'room.source = "manual_confirmation"' in source
    assert '$("#confirm-all-rooms")?.addEventListener("click", confirmAllRooms)' in source
    assert 'confirmAllRoomsButton.disabled = !state.rooms.length || allConfirmed' in source


def test_loaded_cody_rooms_repair_narrow_spikes_before_rendering() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    module_uri = (STATIC / "scene_room_geometry.js").as_uri()
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
    # bella 版:嚴格帶使用者選件時場景只放已選家具,不硬塞佔位品
    assert "selected_furniture_exact: strictSelectedFurniture || allowPendingFurniture" in source


def test_confirmed_rooms_and_structures_are_the_only_3d_floorplan_source() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function confirmedFloorplanEditor(schemeId = activeSchemeId())" in controller
    # 第 4 步完成後以確認快照為準（舊專案沒有快照才退回 state.structures），
    # 否則第 6 步會讀到使用者在第 4 步之後又動過、但未重新確認的結構。
    assert "state.confirmedStructureSnapshot || state.structures," in controller
    assert "structures: structuresForScheme(" in controller
    assert "floorplan_editor: confirmedFloorplanEditor()" in controller
    assert "floorplan_dxf_text: state.confirmedFloorplan?.dxf_text" not in controller
    assert "floorplan.beam_segments" in viewer
    assert "floorplan.columns" in viewer
    assert 'id="selected-structure-editor"' in (STATIC / "scene.html").read_text(encoding="utf-8")
    assert "function deleteSelectedStructure()" in controller
    assert "function applySelectedStructureSize()" in controller
    assert "structureDrag" in controller


def test_column_height_is_locked_to_the_confirmed_floor_height() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function confirmedRoomHeightCm()" in controller
    assert "heightInput.readOnly = isColumn;" in controller
    assert 'isColumn ? "柱高（依樓高，公分）"' in controller
    assert "height_cm: confirmedRoomHeightCm()" in controller
    assert "heightCm: confirmedRoomHeightCm()" in controller
    assert "目前調整：柱高" not in controller
    assert "調整柱寬與高度" not in controller


def test_project_workflow_brand_confirms_before_returning_home() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    # bella 架構:表面覆蓋改逐房管理(按 room_id 濾除舊值再併入新 override),
    # 不再整場清空;移除界線也走逐房 upsert + 增量 updateRoomSurfaces。
    assert "state.sceneData.surface_overrides = [" in controller
    assert ".filter((item) => String(item.room_id) !== String(room.id))" in controller
    assert "upsertRoomSurfaceOverride(room, { material_boundary: null })" in controller
    assert "state.sceneData.material_boundary = null" in controller
    assert "state.materialBoundary = null" in controller
    assert 'option value="surface"' not in html
    assert 'id="material-boundary-position"' in html
    assert 'id="material-boundary-direction"' in html
    assert "function removeMaterialBoundary()" in controller


def test_step_six_locks_specified_furniture_from_3d_controls() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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


def test_added_and_deleted_furniture_refresh_numbering_and_stay_draggable() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    module_uri = (STATIC / "scene_viewer_reload.js").as_uri()
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
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

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
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createCeilingGeometry(" in viewer
    assert 'ceilingStyle === "cove"' in viewer
    assert 'ceilingStyle === "floating"' in viewer
    assert 'ceilingStyle === "feature-pendant"' in viewer
    assert 'ceilingStyle === "linear"' in viewer
    assert 'ceilingStyle === "wood-grid"' in viewer
    assert "function createStyleLights(" in viewer
    assert 'lightStyle === "track"' in viewer
    assert 'lightStyle === "downlight"' in viewer
    assert 'lightStyle === "paper"' in viewer
    assert "keyLight.shadow.mapSize.set(shadowMapSize, shadowMapSize)" in viewer


def test_viewer_keeps_missing_glbs_editable_without_pretending_the_proxy_is_valid() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    pending = source.split(
        "const blockingRooms = configurationBlockingFurnitureByRoom", 1
    )[1].split("const confirmButton", 1)[0]
    handlers = source.split(
        'element.configurationPendingList.addEventListener("click"', 1
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


def test_room_priority_can_defer_unloadable_models_without_bypassing_review() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    pending = source.split(
        "const blockingRooms = configurationBlockingFurnitureByRoom", 1
    )[1].split("const confirmButton", 1)[0]
    prioritize = source.split(
        "async function prioritizeConfigurationRoomFurniture", 1
    )[1].split("function renderSelectedFurnitureEditor", 1)[0]

    assert 'data-prioritize-configuration-room="' in pending
    assert "group.items.length" in pending
    # bella 版:載不進模型的家具先排除在引擎重排之外(不假裝合法),但仍保留在
    # 清單以 placementFailed 呈現供複核,不繞過審查;逐房擇優後清空 deferred。
    assert "const modelFailureIds = new Set(configurationModelFailures().keys());" in prioritize
    assert "(item) => !modelFailureIds.has(String(item.id))," in prioritize
    assert "placementFailed," in prioritize
    assert "furniture.deferred = [];" in prioritize


def test_unassigned_configuration_pending_actions_are_not_silent_noops() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    pending_grouping = source.split(
        "function configurationBlockingFurnitureByRoom", 1
    )[1].split("function configurationModelFailures", 1)[0]
    reflow = source.split(
        "async function reflowSingleConfigurationFurniture", 1
    )[1].split("function configurationFurniturePriority", 1)[0]
    prioritize = source.split(
        "async function prioritizeUnassignedConfigurationFurniture", 1
    )[1].split("function renderSelectedFurnitureEditor", 1)[0]

    assert 'const UNASSIGNED_CONFIGURATION_ROOM_ID = "unassigned"' in source
    assert "configurationRoomById(item.roomId)" in pending_grouping
    assert "UNASSIGNED_CONFIGURATION_ROOM_ID" in pending_grouping
    assert "unassignedDeferredFurniture" in pending_grouping
    assert "await prioritizeUnassignedConfigurationFurniture()" in prioritize
    assert "configurationFurnitureForRoom(" in prioritize
    # bella 版:未指定空間不靜默移除,而是保留家具並明確要求使用者去指定
    # 房間(setStatus error),不是無聲 noop。
    assert "家具已保留，請先定位或回到逐房需求指定空間。" in prioritize
    assert "目前未指定空間" in reflow


def test_deferred_configuration_furniture_does_not_reblock_after_reload() -> None:
    source = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
    blocking = source.split("function configurationBlockingFurniture()", 1)[1].split(
        "const GENERATIVE_EQUIPMENT_OPTIONS", 1
    )[0]

    assert "const deferredIds = configurationDeferredFurnitureIds();" in blocking
    assert "if (deferredIds.has(String(item.id))) return false;" in blocking


def test_floor01_repair_controls_cover_openings_questionnaire_layout_and_3d_editing() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert "rotateSelectedStructure(-15)" in controller
    assert "rotateSelectedStructure(15)" in controller
    assert 'id="flip-selected-door"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'class="rp-questionnaire-workspace"' in html
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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

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
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    packs = (STATIC / "scene_style_packs.js").read_text(encoding="utf-8")

    assert "STYLE_MATERIAL_OPTIONS" in packs
    assert "materialPreview" in packs
    assert 'id="wall-material-grouped"' in html
    assert 'id="floor-material-grouped"' in html
    assert "renderGroupedMaterialOptions" in controller
    assert "data-material-preview" in controller
    # bella 架構:材質改在白模側欄「牆面與地面」分頁,分風格 + 縮圖預覽,
    # 依問卷/房間用途/全屋風格排序(不再是即時寫實面板的整屋即時預覽文案)。
    assert "依問卷、房間用途與全屋風格排序。" in html


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


def test_proposal_review_exposes_same_style_palette_choices() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert 'id="proposal-palette-grid"' in html
    assert 'id="proposal-palette-status"' in html


def test_master_view_lock_reads_the_current_confirmation_control() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    lock = source.split("function lockMasterRenderView()", 1)[1].split(
        "function renderPaletteOptions()", 1
    )[0]

    assert 'document.querySelector("#proposal-content-confirmed")?.checked === true' in lock
    assert "if (!contentConfirmed)" in lock


def test_step_six_exposes_the_per_room_scheme_selection_workflow() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    for element_id in (
        "open-room-scheme-selection",
        "room-scheme-gate-status",
        "room-scheme-selection-dialog",
        "room-scheme-list",
        "room-scheme-status",
        "room-scheme-choice-grid",
        "room-scheme-warning",
        "room-scheme-complete",
    ):
        assert f'id="{element_id}"' in html


def test_style_card_previews_preserve_the_full_reference_image() -> None:
    css = (STATIC / "site.css").read_text(encoding="utf-8")
    base_rule = css[css.index(".rp-style-card-preview {"):css.index(".rp-style-pack-grid button small {")]
    questionnaire_rule = css[
        css.index(".rp-questionnaire-style-grid .rp-style-card-preview {"):
        css.index(".rp-questionnaire-style-grid .rp-style-swatches {")
    ]

    assert "aspect-ratio: 3 / 2" in base_rule
    assert "object-fit: contain" in base_rule
    assert "aspect-ratio: 3 / 2" in questionnaire_rule
    assert "object-fit: contain" in questionnaire_rule


def test_removed_questionnaire_floorplan_overlay_does_not_break_event_binding() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "requirementsOverlay" not in controller
    assert "renderRequirementsOverlay" not in controller


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
    assert "active_scheme_id: state.designSchemes.active_scheme_id" in source
    assert "furniture: state.furniture2d" in source


def test_step_four_shows_vertical_scheme_comparison_only_when_b_exists() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert 'id="design-scheme-compare"' in html
    assert html.index('id="scheme-a-plan-image"') < html.index('id="scheme-b-plan-image"')
    assert 'id="delete-scheme-b"' in html
    assert "hasRenovationChanges(state.structures)" in source
    assert ".rp-design-scheme-compare" in css
    assert "grid" in css


def test_scheme_b_structure_contract_cascades_added_openings_and_follows_wall() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'scheme_id: "B"' in source
    assert "attachedOpeningUpdates" in source
    assert "applyAttachedOpeningUpdates" in source
    assert "刪除牆時會一併刪除" in source
    assert "牆長不足以容納附著" in source


def test_questionnaire_is_preserved_when_structure_changes_mark_layouts_stale() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "markSchemeLayoutsStale(state.designSchemes, message)" in source
    assert "|| state.basicConfirmed" in source
    assert "|| Object.keys(state.visualAnswers || {}).length > 0" in source


def test_wall_endpoint_edit_and_generative_space_questionnaire_contracts() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert 'data-wall-handle="start"' in source
    assert "let wallResizeDrag = null" in source
    assert "function wallEndpointSnapCandidates" in source
    assert "...state.structures.doors.flatMap" in source
    assert "...state.structures.windows.flatMap" in source
    assert "attachedOpeningUpdates(" in source
    assert "generativeEquipmentGate" in source
    assert "structuralIntentInText" in source
    assert "生圖設備方向：" in source
    assert "固定限制：不得擴建、移動牆門窗、樑或柱" in source
    assert 'id="questionnaire-generative-equipment"' in html
    assert 'id="questionnaire-generation-notes"' in html


def test_steps_six_to_nine_expose_scheme_switching_and_render_lock() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    # A/B 切換只存在第 6 步的三個子面板;第 7 步起不再出現(方案已選定)
    assert html.count('data-design-scheme="A"') == 3
    assert html.count('data-design-scheme="B"') == 3
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "const hasSchemeLayoutState = Boolean(state.designSchemes.schemes.B)" in source
    assert "layout_2d: layoutIsLive || hasSchemeLayoutState" in source
    assert "layoutIsLive || Object.keys(state.designSchemes.schemes).length" not in source
    assert "const emptySchemeB = restoredSchemeB" in source
    assert "if (emptySchemeB) deleteSchemeB(state.designSchemes)" in source


def test_grouped_surface_cards_sync_their_material_ids_into_native_selects() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function syncSurfaceMaterialSelect(" in source
    assert "syncSurfaceMaterialSelect(kind, items, current)" in source
    assert "select.value = materialId" in source
    assert "select.value !== materialId" in source


def test_realtime_style_step_adds_soft_decor_and_flushes_persistence() -> None:
    """bella 拆除了自動軟裝生成(不再打 /api/scene/decorate、不逐房塞入未選家具);
    本測試改守保留下來的離線暫存 flush 與版本衝突重放持久化契約。"""
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    # 逐房擺放語意仍在(生圖/驗證用),風格套用時走 fallback 房清單
    assert "placement_room_id: room.id" in source
    assert "? state.rooms" in source
    # 保留:離線暫存排隊 flush 與版本衝突重放
    assert "saveSequence = saveSequence.catch" in source
    assert "roompilot.pending-save." in source
    assert "for (let attempt = 0; attempt < 3; attempt += 1)" in source
    assert "const pendingSave = localStorage.getItem(pendingSaveStorageKey())" in source
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
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "function proposalRoomCameraCandidates" in source
    assert "function ensureProposalRoomCandidatePreviews" in source
    assert "proposalRoomPreviewCache" in source
    assert "proposalViewer.capturePng()" in source
    # bella 版逐房候選視角標籤:主視角/入口對向/空間側向
    assert "完整主視角" in source
    assert "入口對向視角" in source
    assert "空間側向視角" in source
    assert "function lockSelectedProposalRoomView" in source
    assert "function confirmProposalRoomViews" in source
    assert "尚有 ${missing.map((room) => room.label).join" in source
    assert 'goTo("ai_render")' in source
    assert "proposalRoomPreviewCache.clear();" in source


def test_proposal_review_keeps_a_user_confirmation_during_async_redraw() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    # bella 版:同一 review 的 autosave 重繪走 legacyPrepareProposalReview;
    # 使用者的內容確認勾選必須被保留(OR 舊值),不得被無條件覆蓋。
    review = source.split("async function legacyPrepareProposalReview()", 1)[1].split(
        "function lockMasterRenderView()", 1
    )[0]

    assert "const contentConfirmed = element.proposalContentConfirmed.checked || Boolean(saved);" in review
    assert "element.proposalContentConfirmed.checked = contentConfirmed;" in review
    assert "element.proposalContentConfirmed.checked = Boolean(saved);" not in review


def test_proposal_room_view_panel_has_a_compatible_static_mount() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    panel = source.split("function ensureProposalRoomViewPanel()", 1)[1].split(
        "function renderProposalRoomViewPanel()", 1
    )[0]

    assert '$("#proposal-review-step .rp-control-pane") || $("#proposal-review-step")' in panel


def test_master_view_lock_reports_unexpected_client_errors() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert '$("#lock-master-view")?.addEventListener("click", () => {' in source
    assert 'element.masterViewStatus.textContent = `無法鎖定視角：${errorMessage(error)}`;' in source


def test_master_view_lock_does_not_depend_on_noncritical_scheme_ui_redraw() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    lock = source.split("function lockMasterRenderView()", 1)[1].split(
        "function renderPaletteOptions()", 1
    )[0]

    assert "const completed = state.workflow.complete(\"proposal_review\"" in lock
    assert "try {\n    renderSchemeControls();\n  } catch (error)" in lock
    assert lock.index('const completed = state.workflow.complete("proposal_review"') < lock.index(
        "renderSchemeControls();"
    )


def test_questionnaire_material_pairs_supports_the_legacy_page_shell() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    pairs = source.split("function renderQuestionnaireMaterialPairs(pack)", 1)[1].split(
        "function selectQuestionnaireMaterialPair", 1
    )[0]

    assert "const host = element.questionnaireMaterialPairs;" in pairs
    assert "if (!host) return pairs;" in pairs


def test_questionnaire_finishes_skips_missing_legacy_only_controls() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    finishes = source.split("function renderQuestionnaireFinishes()", 1)[1].split(
        "function renderQuestionnaireSummary", 1
    )[0]

    assert "const legacyFinishShell = [" in finishes
    assert "if (legacyFinishShell.some((control) => !control)) return;" in finishes


def test_step_seven_accepts_confirmed_room_requirements_after_default_fill() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    lock = source.split("function lockMasterRenderView()", 1)[1].split(
        "function renderPaletteOptions()", 1
    )[0]

    assert "const confirmedRoomRequirements = state.rooms.every((room) => (" in lock
    assert "if (!visualProgress.ready && !confirmedRoomRequirements)" in lock

    palette_handler = source.split("function confirmRenderPalette()", 1)[1].split(
        "async function prepareAiRender()", 1
    )[0]
    assert "state.proposalReview.roomViews = {};" not in palette_handler
    assert "將沿用第 7 步鎖定的逐房視角" in palette_handler
