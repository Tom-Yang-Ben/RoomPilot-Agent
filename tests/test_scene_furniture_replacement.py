from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "backend/server/static/scene.html").read_text(encoding="utf-8")
SOURCE = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")


def test_step6_has_a_dedicated_replacement_drawer() -> None:
    assert 'id="replace-2d-furniture"' in HTML
    assert 'id="furniture-replacement-drawer"' in HTML
    assert 'id="replacement-3d-preview"' in HTML
    assert '<select id="replacement-furniture-search"' in HTML
    assert 'id="replacement-furniture-query"' in HTML
    assert "loadReplacementCandidates" in SOURCE


def test_replacement_filters_context_and_revalidates_with_engine() -> None:
    load = SOURCE.split("async function loadReplacementCandidates", 1)[1].split(
        "async function openFurnitureReplacement", 1
    )[0]
    replace = SOURCE.split("async function replaceSelectedLayoutFurniture", 1)[1].split(
        "function addFurnitureFromLibrary", 1
    )[0]

    assert "canSearchAll ? \"\" : route.query" in SOURCE
    assert 'filterMode === "all" ? "" : style' in load
    assert "catalogType" in load
    assert "query" in load
    assert "searchAll" in load
    assert "全部家具資料庫：僅顯示尺寸可放入本房的 3D 家具" in load
    assert "目前沒有尺寸能放入此房間的 3D 家具。" in load
    assert "const queryOverridesRecommendation = Boolean(query) && !catalogType;" in load
    assert "const broadCatalogMode = queryOverridesRecommendation" in load
    assert "const rankingRequest = broadCatalogMode" in load
    assert 'type: "", queryText: query' in load
    assert "rankCatalogFurniture(catalogCandidates, rankingRequest)" in load
    assert "requestVersion !== replacementSearchRequestVersion" in load
    assert "replacementCandidateFitsRoom" in load
    assert "replacementCandidateIsSmaller" in load
    assert "setSmallerReplacementOption(smallerCandidates, {" in load
    assert 'value = "smaller"' in SOURCE
    assert "目前沒有比這件家具更小" in load
    assert "resolveFurniturePosition(candidate)" in replace
    assert "model_url: catalogItem.model_url" in replace
    assert "state.furniture2d[index] = candidate" in replace
    assert "syncFurnitureInventoryAcrossSchemes()" in replace


def test_replacement_search_reloads_for_mode_changes_and_text_queries() -> None:
    assert 'element.replacementSearch?.addEventListener("change"' in SOURCE
    assert 'element.replacementQuery?.addEventListener("input"' in SOURCE
    assert "replacementQueryTimer = window.setTimeout" in SOURCE
    assert "requestedModeExists" in SOURCE


def test_pending_smaller_replacement_keeps_the_clicked_furniture_and_mode() -> None:
    assert 'data-replace-smaller-configuration-furniture=' in SOURCE
    assert 'mode: "smaller"' in SOURCE
    assert "furnitureId = state.selectedFurniture2dId" in SOURCE
    assert "String(candidate.id) === String(furnitureId)" in SOURCE
    assert 'preserveCurrentSelection: filterMode === "smaller"' in SOURCE


def test_single_item_reflow_stays_in_the_clicked_room_and_persists_to_scheme() -> None:
    reflow = SOURCE.split("async function reflowSingleConfigurationFurniture", 1)[1].split(
        "function configurationFurniturePriority", 1
    )[0]
    resolver = SOURCE.split("async function resolveFurniturePosition", 1)[1].split(
        "async function finishFurnitureDrag", 1
    )[0]

    assert "candidate.roomId === item.roomId" in resolver
    assert 'String(candidate.furniture_id || "") === String(item.id)' in resolver
    assert "const exactIndex = state.sceneData.scene_objects.findIndex(" in SOURCE
    assert "if (exactIndex >= 0) return exactIndex;" in SOURCE
    assert "scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));" in reflow
    assert "scheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));" in reflow


def test_replacement_preview_uses_the_current_room_and_keeps_candidate_details_concise() -> None:
    preview = SOURCE.split("async function previewReplacementCandidate", 1)[1].split(
        "function renderReplacementCandidates", 1
    )[0]

    assert "const baseScene = state.sceneData || activeScheme()?.sceneData" in preview
    assert "buildReplacementRoomPreviewScene(baseScene, current, candidate)" in preview
    assert 'replacementViewer.setViewMode("dollhouse")' in preview
    assert "replacementViewer.capturePng()" not in preview
    assert "data-replacement-thumbnail" not in SOURCE
    replacement_list = SOURCE.split("function renderReplacementCandidates", 1)[1].split(
        "function replacementCandidateIsSmaller", 1
    )[0]
    assert "replacementFurnitureName(candidate)" in replacement_list
    assert "replacementFurnitureSize(candidate)" in replacement_list
    assert "rp-replacement-thumb" not in replacement_list
    assert "function buildReplacementRoomPreviewScene" in SOURCE


def test_replacement_preview_keeps_room_floor_and_replacement_on_the_2d_layout_origin() -> None:
    builder = SOURCE.split("function buildReplacementRoomPreviewScene", 1)[1].split(
        "async function previewReplacementCandidate", 1
    )[0]

    assert '"door_openings"' in builder
    assert ").map((region) => shiftFloorplanRegion(region, offset));" in builder
    assert "const layoutPosition = Number.isFinite(Number(current.xCm))" in builder
    assert "? shiftScenePoint({ x: current.xCm, z: current.yCm }, offset)" in builder
    assert "position_cm: layoutPosition" in builder
    assert "rotation_y_deg: layoutRotation" in builder


def test_glb_search_generates_png_thumbnails_from_models() -> None:
    search = SOURCE.split("async function searchGlbFurniture", 1)[1].split(
        "async function styleFurnitureCandidate", 1
    )[0]

    assert 'id="glb-thumbnail-viewer"' in HTML
    assert "function glbThumbnailScene(item)" in search
    assert "async function populateGlbSearchThumbnails" in search
    assert "glbThumbnailViewer.loadScene(glbThumbnailScene(item))" in search
    assert "glbThumbnailViewer.capturePng()" in search
    assert "data-glb-thumbnail" in search
    assert "glbThumbnailCache" in SOURCE


def test_glb_thumbnail_mode_renders_only_the_furniture() -> None:
    search = SOURCE.split("function glbThumbnailScene", 1)[1].split(
        "async function styleFurnitureCandidate", 1
    )[0]
    viewer = (ROOT / "backend/server/static/scene_viewer.js").read_text(
        encoding="utf-8"
    )
    room_builder = viewer.split("function createRoom(sceneData)", 1)[1].split(
        "function createCeilingGeometry", 1
    )[0]

    assert "catalog_thumbnail_mode: true" in search
    assert "showGuide: false" in search
    assert "const catalogThumbnailMode" in room_builder
    assert "if (!catalogThumbnailMode)" in room_builder
    assert "roomGroup.add(floor)" in room_builder
    assert "roomGroup.add(presentationGround)" in room_builder
    assert "function furnitureAnnotationsEnabled()" in viewer
    assert "if (furnitureAnnotationsEnabled())" in viewer
