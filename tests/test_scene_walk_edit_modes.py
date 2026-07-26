from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "backend/server/static/scene.html").read_text(encoding="utf-8")
CONTROLLER = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
VIEWER = (ROOT / "backend/server/static/scene_viewer.js").read_text(encoding="utf-8")


def test_white_model_exposes_walk_and_furniture_edit_modes() -> None:
    assert 'data-white-interaction="walk"' in HTML
    assert 'data-white-interaction="edit"' in HTML
    assert "setInteractionMode" in CONTROLLER


def test_walk_mode_moves_and_blocks_walls_and_large_furniture() -> None:
    assert 'interactionMode !== "walk"' in VIEWER
    assert "walkPositionInsideFloor(clamped)" in VIEWER
    assert "walkPositionBlocked(clamped)" in VIEWER
    assert "walkPositionBlockedByFurniture(clamped)" in VIEWER
    assert "insideDoorOpening" in VIEWER
    assert "door_openings" in VIEWER
    assert 'walkKeys.has("w")' in VIEWER


def test_edit_mode_is_required_before_dragging_furniture() -> None:
    assert 'interactionMode !== "edit"' in VIEWER
    assert "cameraLocked = true" in VIEWER
    assert "controls.enableRotate = false" in VIEWER
    assert "validatePlacement(item, newPositionCm, newRotationDeg)" in VIEWER
