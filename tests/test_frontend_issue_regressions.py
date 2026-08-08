from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENE_HTML = (ROOT / "backend" / "server" / "static" / "scene.html").read_text(
    encoding="utf-8"
)
SCENE_JS = (ROOT / "backend" / "server" / "static" / "scene_v2.js").read_text(
    encoding="utf-8"
)
SITE_CSS = (ROOT / "backend" / "server" / "static" / "site.css").read_text(
    encoding="utf-8"
)


def function_body(name: str, next_name: str) -> str:
    return SCENE_JS.split(f"function {name}", 1)[1].split(f"function {next_name}", 1)[0]


def test_step_transition_waits_for_preparation_and_locks_navigation() -> None:
    assert 'id="workflow-transition"' in SCENE_HTML
    assert 'role="status"' in SCENE_HTML
    assert "let workflowTransitionPromise = null" in SCENE_JS
    transition = SCENE_JS.split("async function transitionToStep", 1)[1].split(
        "function goTo", 1
    )[0]
    assert transition.index("await prepareWorkflowStep(step)") < transition.index(
        'showStep(step, { preparePanel: false })'
    )
    assert 'document.body.classList.toggle("is-workflow-transitioning"' in SCENE_JS
    assert ".rp-workflow-transition-spinner" in SITE_CSS


def test_step_six_replaces_furniture_selection_with_room_surfaces() -> None:
    assert 'data-scene-sidebar-tab="selection">選取家具' not in SCENE_HTML
    assert 'data-scene-sidebar-tab="surfaces">牆面與地面' in SCENE_HTML
    assert 'id="white-model-surface-entry"' in SCENE_HTML
    assert 'id="open-lighting-adjustment"' not in SCENE_HTML
    assert "調整天花與照明" not in SCENE_HTML
    assert '["plan", "issues", "surfaces"]' in SCENE_JS


def test_locked_step_six_room_keeps_material_edit_action_beside_lock_state() -> None:
    header = SCENE_HTML.split(
        '<header class="rp-step-six-surface-header"', 1
    )[1].split("</header>", 1)[0]
    footer = SCENE_HTML.split(
        '<footer class="rp-step-six-surface-actions">', 1
    )[1].split("</footer>", 1)[0]

    assert 'id="surface-room-lock-state"' in header
    assert 'id="unlock-room-surfaces"' in header
    assert "修改此房間材質" in header
    assert 'id="unlock-room-surfaces"' not in footer

    progress = function_body("renderStepSixSurfaceProgress", "setStepSixSurfaceKind")
    assert (
        "element.unlockRoomSurfaces.hidden = !confirmed || "
        "stepSixSurfacesFinalLocked();"
    ) in progress


def test_step_six_recommendations_only_use_questionnaire_compatible_materials() -> None:
    recommendations = function_body(
        "recommendedStepSixMaterialOptions", "allStepSixMaterialOptions"
    )
    grouped = function_body("renderGroupedMaterialOptions", "stylePackByIdSafe")
    swatches = function_body("renderStepSixColorSwatches", "renderGroupedMaterialOptions")
    compatible = function_body(
        "styleCompatibleMaterialOptionsForPack", "renderMaterialFilterChips"
    )

    assert "styleCompatibleMaterialOptionsForPack(kind, activePack, room)" in recommendations
    assert "catalogOptions.forEach" not in recommendations
    assert "Object.entries(STYLE_MATERIAL_OPTIONS)" not in recommendations
    assert "isPoolSurface" in compatible
    assert "if (isPoolSurface(option)) return false;" in compatible
    assert "recommendedStepSixMaterialOptions(kind, activePack, room)" in grouped
    assert "allStepSixMaterialOptions(kind, activePack, room, catalogItems)" in grouped
    assert "recommendedStepSixMaterialOptions(kind, activePack)" in swatches


def test_room_surface_changes_are_persisted_as_explicit_room_overrides() -> None:
    keeps_override = function_body(
        "roomKeepsExplicitWallOverride", "normalizedRoomSurfaces"
    )
    assert "roomAllowsIndependentFloor" not in keeps_override
    assert "surfaces.wallOverrideExplicit === true" in keeps_override

    normalizer = function_body(
        "normalizeSavedSceneWallSurfaces", "stableStringNumber"
    )
    assert "override.wall_option = nextOption" not in normalizer
    assert "override.wall_color_hex = nextColor" not in normalizer

    apply_surface = SCENE_JS.split("async function applySurfaceOverrides", 1)[1].split(
        "function toggleMaterialBoundary", 1
    )[0]
    assert "state.roomFinishDrafts[String(room.id)]" in apply_surface
    assert "wallOverrideExplicit: true" in apply_surface
    assert "String(item.room_id) !== String(room.id)" in apply_surface


def test_room_view_candidates_are_room_bound_and_show_the_full_space() -> None:
    camera = SCENE_JS.split("function roomScenePolygon", 1)[1].split(
        "async function ensureProposalRoomCandidatePreviews", 1
    )[0]
    assert "planCenterCm()" in camera
    assert "insetRoomCameraPoint" in camera
    assert "room_id: room.id" in camera
    assert "fov_deg: 72" in camera
    assert '"full-room-v2"' in camera

    selection = function_body("selectProposalRoomView", "selectProposalRoomCandidate")
    assert "proposalViewer.setCameraState" in selection
    assert "room.id" in selection


def test_step_six_room_camera_uses_the_viewers_world_z_axis() -> None:
    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    camera_polygon = function_body("roomScenePolygon", "scenePointInsideRoom")
    camera_hit_test = function_body("scenePointInsideRoom", "roomSceneTarget")
    camera_target = function_body("roomSceneTarget", "insetRoomCameraPoint")
    walk_payload = function_body("selectedWhiteWalkRoomPayload", "activateWhiteWalkMode")

    assert 'if ("z" in next) next.z = -Number(next.z || 0);' in viewer
    assert "z: center.y - Number(point.y)" in camera_polygon
    assert "y: center.y - Number(point.z)" in camera_hit_test
    assert (
        "z: sum.z - Number(item.position_cm?.z || 0) / furniture.length"
        in camera_target
    )
    assert "z: center.y - roomMiddle.y" in walk_payload
    assert "z: center.y - point.y" in walk_payload


def test_all_frontend_room_displays_validate_the_selected_room_camera() -> None:
    assert "function roomCameraTargetsRoom(room, camera)" in SCENE_JS

    validator = function_body("validProposalRoomView", "selectProposalRoomView")
    step_six = function_body("focusStepSixRoom", "renderRoomSchemeSelectionDialog")
    step_seven = function_body("selectProposalRoomView", "selectProposalRoomCandidate")
    step_eight = function_body("selectRenderRoom", "prepareAiRender")

    assert "roomCameraTargetsRoom(room, camera)" in validator
    assert "roomCameraSuggestion(room)" in step_six
    assert "validProposalRoomView(room)" in step_seven
    assert "view?.camera || roomCameraSuggestion(room)" in step_eight
    assert "if (view) aiRenderViewer.setCameraState" not in step_eight

    assert "selectRoom(roomShape.dataset.roomShape)" in SCENE_JS
    assert "button.dataset.visualRoom" in SCENE_JS
    assert "focusStepSixRoom(roomId)" in SCENE_JS
    assert "selectProposalRoomView(roomButton.dataset.proposalRoom)" in SCENE_JS
    assert "selectRenderRoom(button.dataset.finalRenderRoom)" in SCENE_JS


def test_step_seven_hides_internal_names_and_palette_cards_use_images() -> None:
    panel = function_body("ensureProposalRoomViewPanel", "renderProposalRoomViewPanel")
    render_panel = function_body("renderProposalRoomViewPanel", "confirmProposalRoomViews")
    prepare_render = SCENE_JS.split("async function prepareAiRender", 1)[1].split(
        "function legacyDownloadEngineeringDelivery", 1
    )[0]
    assert "Yen" not in panel
    assert "Yen" not in render_panel
    assert "Yen" not in prepare_render

    palette = function_body("renderPaletteOptions", "legacyRenderPaletteResultsV1")
    assert "pack.sourceImage || pack.referenceImage" in palette
    assert 'class="rp-render-palette-image"' in palette
    assert "palette.join(\" / \")" not in palette


def test_render_confirmation_uses_compact_facts_and_keyword_chips() -> None:
    dialog = function_body("openRenderBriefDialog", "closeRenderBriefDialog")
    assert "rp-render-brief-facts" in dialog
    assert "rp-render-brief-keywords" in dialog
    assert "rp-render-brief-lock-note" in dialog
    assert "使用問卷與 RAG 鎖定配置" not in SCENE_JS
    assert "Yen 鎖定視角" not in dialog
    assert ".rp-render-brief-keywords" in SITE_CSS
