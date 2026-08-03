"""第 6-8 步整合精靈契約（bella-test1 移植，依本機 frontend/ 路徑與資料形狀調整）。

來源：fd0cee11（逐房方案 A/B 選擇、proposal 色卡、材質配對預覽）與
23de9dda 的 UI 部分（逐房 3D 預覽彈窗、家具編號開關、側欄待處理徽章、
問卷型錄空間分組）。bella 原檔中 render-brief 與 surface/lighting 任務彈窗、
catalog readiness 三組斷言對應的功能不在本次移植範圍（來自未移植的
009b7020），故不在此檔斷言。
"""

from backend.paths import STATIC_DIR


def test_step_six_requires_every_room_to_choose_a_scheme_before_micro_adjustment() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-scheme-selection-dialog"' in html
    assert 'id="room-scheme-list"' in html
    assert 'id="room-scheme-complete"' in html
    assert 'id="open-room-scheme-selection"' in html
    assert "function composeSelectedRoomFurniture()" in source
    assert "allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)" in source
    assert "await confirmLayout2d({ allowPendingFurniture: true })" in source
    assert "configuration_scene_generation_failed" in source
    assert "async function ensureRoomScheme3dPreviews()" in source
    assert "roomSchemePreviewCache" in source
    assert "whiteViewer.capturePng()" in source
    # 進入第 6 步（layout_2d 或直接復原到 white_model_3d）都要先確認逐房方案。
    assert "queueMicrotask(promptRoomSchemeSelection);" in source


def test_room_scheme_selections_persist_and_gate_the_render_lock() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    schemes = (STATIC_DIR / "scene_design_schemes.js").read_text(encoding="utf-8")

    # 逐房選擇與配置快照要進存檔 payload，重新整理後不得遺失。
    assert "room_selections: state.designSchemes.room_selections" in source
    assert "configuration_snapshot: state.designSchemes.configuration_snapshot" in source
    assert "function configurationSnapshot()" in source
    assert "export function selectSchemeForRoom" in schemes
    assert "export function allRoomsHaveSchemeSelections" in schemes
    assert "export function selectedSchemeForRoom" in schemes
    # 第 7 步鎖定視角前必須先選同風格色卡並完成逐房方案選擇。
    assert "請先選擇一張同風格色卡" in source
    assert "請先回第 6 步完成每個房間的 A/B 方案選擇。" in source
    assert "style_card_id: state.proposalReview.confirmedStyleCardId" in source
    assert "configuration_snapshot_id: state.designSchemes.configuration_snapshot.created_at" in source


def test_step_six_auto_uses_scheme_a_when_scheme_b_has_no_complete_scene() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    # 規格 §進入順序 2：方案 B 無可比較內容時明確顯示原因，並預設選用 A。
    assert "function roomHasComparableSchemeB(room)" in source
    assert "function applyUnavailableRoomSchemeDefaults()" in source
    assert "function promptRoomSchemeSelection()" in source
    assert "async function ensureRoomSchemeAlternative()" in source
    assert 'relayoutFurnitureForScheme(schemeA.furniture, "B")' in source
    assert 'selectSchemeForRoom(state.designSchemes, room.id, "A")' in source
    assert "目前沒有完整的方案 B 3D 場景可比較" in source


def test_step_six_room_scheme_dialog_compares_room_local_2d_and_3d_previews() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert "function roomSchemePreviewKey(schemeId, roomId)" in source
    assert "function roomSchemePlanMarkup(room, furniture = [])" in source
    assert "function buildRoomSchemePreviewScene(baseScene, room, furniture = [])" in source
    assert "roomSchemePreviewCache.get(roomSchemePreviewKey(schemeId, room.id))" in source
    assert "roomSchemePreviewCache.set(roomSchemePreviewKey(schemeId, room.id)" in source
    assert "roomSchemePlanMarkup(room, furniture)" in source
    assert "rp-room-scheme-plan" in css
    assert "rp-room-scheme-furniture" in css


def test_room_scheme_dialog_opens_an_interactive_3d_preview_and_readable_legend() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'id="room-scheme-3d-preview-dialog"' in html
    assert 'id="room-scheme-3d-preview"' in html
    assert "function roomSchemeFurnitureLegend(furniture = [])" in source
    assert "async function openRoomScheme3dPreview(schemeId)" in source
    assert "data-room-scheme-preview-3d" in source
    assert 'roomSchemePreviewViewer.setViewMode("orbit")' in source
    assert 'setCameraPreset("inside")' in source
    assert "rp-room-scheme-legend" in css
    assert "rp-room-scheme-3d-preview" in css


def test_room_scheme_previews_share_one_structure_and_shift_both_point_shapes() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    geometry = (STATIC_DIR / "scene_plan_geometry.js").read_text(encoding="utf-8")

    # 方案 A/B 的 3D 預覽共用同一份確認結構（方案卡只呈現家具差異）。
    preview = source.split("async function openRoomScheme3dPreview", 1)[1].split(
        "function renderRoomSchemeSelectionDialog", 1
    )[0]
    assert "state.designSchemes.schemes.A?.sceneData || state.sceneData" in preview
    # 單房裁切＋平移：陣列 [x, y] 與物件 {x, y} 座標都要處理。
    assert "function scenePointCoordinates(point = {})" in geometry
    assert "if (Array.isArray(point))" in geometry
    assert "function shiftFloorplanRegion(region, offset)" in geometry
    builder = source.split("function buildRoomSchemePreviewScene", 1)[1].split(
        "function applyUnavailableRoomSchemeDefaults", 1
    )[0]
    assert "shiftFloorplanRegion(region, offset)" in builder
    assert "floorplan.room_regions = (floorplan.room_regions || [])" in builder
    assert "model_url: item.model_url || existing.model_url" in builder
    assert "catalog_furniture_id: item.catalogFurnitureId" in builder


def test_furniture_numbers_serve_step_six_only_and_never_the_final_view() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="toggle-furniture-numbers"' in html
    assert "showFurnitureNumbers: true" in source
    assert "function syncFurnitureNumberVisibility()" in source
    assert "whiteViewer?.setFurnitureNumberMarkersVisible?.(state.showFurnitureNumbers);" in source
    # 編號預設關閉，只有第 6 步的 whiteViewer 會開；proposal／aiRender viewer
    # 從不呼叫 setFurnitureNumberMarkersVisible，第 7 步最終視角不會有編號。
    assert "let showFurnitureNumberMarkers = false;" in viewer
    assert "setFurnitureNumberMarkersVisible(visible, roomId = \"\")" in viewer
    assert "numberMarkerRoomId" in viewer
    assert "proposalViewer.setFurnitureNumberMarkersVisible" not in source
    assert "aiRenderViewer.setFurnitureNumberMarkersVisible" not in source


def test_step_six_sidebar_has_three_tabs_with_a_pending_issue_badge() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "site.css").read_text(encoding="utf-8")

    assert 'data-scene-sidebar-tab="plan"' in html
    assert 'data-scene-sidebar-tab="issues"' in html
    assert 'data-scene-sidebar-tab="selection"' in html
    assert 'id="scene-sidebar-issue-badge"' in html
    assert 'data-scene-sidebar-panel="issues"' in html
    assert 'data-scene-sidebar-panel="selection"' in html
    assert 'function setSceneSidebarTab(tab = "plan")' in source
    assert '$("#scene-sidebar-issue-badge")' in source
    assert "issueBadge.hidden = blocking.length === 0;" in source
    assert 'data-scene-sidebar-mode="issues"' in css
    assert "rp-scene-sidebar-tabs" in css


def test_questionnaire_catalog_browses_all_spaces_with_purpose_groups() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="questionnaire-catalog-space-groups"' in html
    assert 'id="questionnaire-catalog-purpose-groups"' in html
    assert 'data-questionnaire-catalog-scope="room"' in html
    assert 'data-questionnaire-catalog-scope="all"' in html
    assert "const QUESTIONNAIRE_CATALOG_SPACES" in source
    assert "const QUESTIONNAIRE_CATALOG_PURPOSES" in source
    assert "function renderQuestionnaireCatalogBrowseChoices(room)" in source
    assert "function openQuestionnaireFurnitureCatalog(" in source
    assert "function addQuestionnaireCatalogFurniture(" in source
    # 搜尋「椅子」可跨用途涵蓋工作椅、閱讀椅與椅凳：有搜尋字串時不做用途收斂。
    assert "questionnaireMode && !query && purposeTypes.size" in source


def test_proposal_review_offers_same_style_palette_cards() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="proposal-palette-grid"' in html
    assert 'id="proposal-palette-status"' in html
    assert "function renderProposalPaletteSelection()" in source
    assert "function selectProposalPalette(cardId)" in source
    # 只列全屋主風格的色卡：跨風格的色卡不可被選入。
    assert "pack.styleId !== activePack.styleId) return;" in source
