from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "backend/server/static/scene.html").read_text(encoding="utf-8")
CONTROLLER = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
VIEWER = (ROOT / "backend/server/static/scene_viewer.js").read_text(encoding="utf-8")


def test_white_model_exposes_walk_and_furniture_edit_modes() -> None:
    assert 'data-white-interaction="walk"' in HTML
    assert 'data-white-interaction="edit"' in HTML
    assert 'id="white-walk-room"' in HTML
    assert "setInteractionMode" in CONTROLLER


def test_walk_mode_moves_and_blocks_walls_and_large_furniture() -> None:
    assert 'interactionMode !== "walk"' in VIEWER
    assert "walkPositionInsideFloor(clamped)" in VIEWER
    assert "walkPositionBlocked(clamped)" in VIEWER
    assert "walkPositionBlockedByFurniture(clamped)" in VIEWER
    assert "insideDoorOpening" in VIEWER
    assert "door_openings" in VIEWER
    assert 'walkKeys.has("w")' in VIEWER


def test_walk_mode_hides_door_leaves_and_cannot_select_furniture() -> None:
    assert "function configureOpeningsForView(mode)" in VIEWER
    assert 'object.userData.roompilotArchitecturalDetail === "door"' in VIEWER
    assert 'object.visible = mode !== "walk"' in VIEWER
    assert "object.userData.roompilotNumberMarker" in VIEWER
    assert 'if (interactionMode === "walk") {' in VIEWER
    assert "selectWrapper(null);" in VIEWER
    assert "function setWalkRoom(room" in VIEWER
    assert "if (!lastSceneData) return false;" in VIEWER
    assert "if (!spawn) {" in VIEWER
    assert "找不到可安全站立的位置" in VIEWER
    assert "if (!whiteViewer.setWalkRoom(room))" in CONTROLLER


def test_walk_room_uses_the_rendered_floorplan_region_matched_by_room_id() -> None:
    walk_room = VIEWER.split("function setWalkRoom(room", 1)[1].split(
        "function findWalkLookTarget", 1
    )[0]

    assert "floorplan?.room_regions" in walk_room
    assert "region.room_id" in walk_room
    assert "activeRoom.label" in walk_room
    assert "resolvedRegion.exterior" in walk_room


def test_edit_mode_is_required_before_dragging_furniture() -> None:
    assert 'interactionMode !== "edit"' in VIEWER
    assert "cameraLocked = true" in VIEWER
    assert "controls.enableRotate = false" in VIEWER
    assert "validatePlacement(item, newPositionCm, newRotationDeg)" in VIEWER


def test_catalog_results_are_opened_on_demand_instead_of_living_in_sidebar() -> None:
    assert 'id="open-furniture-catalog"' in HTML
    assert 'id="furniture-catalog-drawer"' in HTML
    sidebar = HTML.split('<aside class="rp-control-pane rp-3d-sidebar">', 1)[1].split(
        "</aside>",
        1,
    )[0]
    assert 'id="glb-search-results"' not in sidebar
