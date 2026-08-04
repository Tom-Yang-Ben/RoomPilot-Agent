import re

from backend.paths import STATIC_DIR


HTML = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
CONTROLLER = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
VIEWER = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")


def aside_blocks(html: str, class_name: str) -> list[str]:
    """取出 class 含 class_name 的每個 <aside> 內容。

    比對 class 而不是整個開頭標籤，否則面板多一個屬性（例如
    `data-scene-sidebar-mode`）就會讓斷言失效。
    """
    blocks: list[str] = []
    for opening in re.finditer(r"<aside\b([^>]*)>", html):
        classes = re.search(r'class="([^"]*)"', opening.group(1))
        if not classes or class_name not in classes.group(1).split():
            continue
        blocks.append(html[opening.end() :].split("</aside>", 1)[0])
    return blocks


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


def test_walk_mode_bridges_doorways_between_room_polygons() -> None:
    # 相鄰房間多邊形之間隔一個牆厚；門洞要同時通過地板判定與牆碰撞，
    # 否則人會被擋在門口（移植自 bella-test1 的 walkDoorwayConnectsRooms）。
    assert "function walkDoorwayConnectsRooms(position" in VIEWER
    assert "roomFloorContainsPoint(position) || walkDoorwayConnectsRooms(position)" in VIEWER
    assert "if (walkDoorwayConnectsRooms(position)) return false;" in VIEWER
    assert "roomFloorContainsPoint(leftSide) && roomFloorContainsPoint(rightSide)" in VIEWER


def test_walk_door_openings_use_the_closed_leaf_not_the_opened_one() -> None:
    # 牆洞是 closed_segment（鉸鏈→swing_end）；拿打開的 start→end 當開口
    # 會把走廊開在隔壁那面牆上（門座標語意，backlog 已記）。
    assert "function walkDoorOpenings()" in VIEWER
    assert "const closed = door?.closed_segment;" in VIEWER
    assert "if (closed?.start && closed?.end) openings.push({ ...door, ...closed });" in VIEWER


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


def test_edit_mode_is_required_before_dragging_furniture() -> None:
    assert 'interactionMode !== "edit"' in VIEWER
    assert "cameraLocked = true" in VIEWER
    assert "controls.enableRotate = false" in VIEWER
    assert "validatePlacement(item, newPositionCm, newRotationDeg)" in VIEWER


def test_catalog_results_are_opened_on_demand_instead_of_living_in_sidebar() -> None:
    assert 'id="open-furniture-catalog"' in HTML
    assert 'id="furniture-catalog-drawer"' in HTML
    sidebars = aside_blocks(HTML, "rp-3d-sidebar")
    assert sidebars, "scene.html 找不到 rp-3d-sidebar 面板"
    for sidebar in sidebars:
        assert 'id="glb-search-results"' not in sidebar
