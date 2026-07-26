from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "backend/server/static/scene.html").read_text(encoding="utf-8")
SOURCE = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")


def test_step6_has_a_dedicated_replacement_drawer() -> None:
    assert 'id="replace-2d-furniture"' in HTML
    assert 'id="furniture-replacement-drawer"' in HTML
    assert 'id="replacement-3d-preview"' in HTML
    assert '<select id="replacement-furniture-search"' in HTML
    assert "loadReplacementCandidates" in SOURCE


def test_replacement_filters_context_and_revalidates_with_engine() -> None:
    load = SOURCE.split("async function loadReplacementCandidates", 1)[1].split(
        "async function openFurnitureReplacement", 1
    )[0]
    replace = SOURCE.split("async function replaceSelectedLayoutFurniture", 1)[1].split(
        "function addFurnitureFromLibrary", 1
    )[0]

    assert "catalogCandidatesForType(current.type" in load
    assert "catalogType" in load
    assert "styleId: style" in load
    assert "rankCatalogFurniture(catalogCandidates, request)" in load
    assert "replacementCandidateFitsRoom" in load
    assert "resolveFurniturePosition(candidate)" in replace
    assert "model_url: catalogItem.model_url" in replace
    assert "state.furniture2d[index] = candidate" in replace
    assert "syncFurnitureInventoryAcrossSchemes()" in replace


def test_replacement_preview_uses_the_current_room_and_generates_png_thumbnail() -> None:
    preview = SOURCE.split("async function previewReplacementCandidate", 1)[1].split(
        "function renderReplacementCandidates", 1
    )[0]

    assert "const baseScene = state.sceneData || activeScheme()?.sceneData" in preview
    assert "JSON.parse(JSON.stringify(baseScene))" in preview
    assert "previewScene.scene_objects[currentIndex] = replacement" in preview
    assert "replacementViewer.capturePng()" in preview
    assert 'replacementViewer.setViewMode("dollhouse")' in preview
    assert "data-replacement-thumbnail" in SOURCE
