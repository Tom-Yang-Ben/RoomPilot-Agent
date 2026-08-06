from __future__ import annotations

import subprocess

from test_scene_workflow import ROOT


VIEWER = ROOT / "backend" / "server" / "static" / "scene_viewer.js"


def _viewer_source() -> str:
    return VIEWER.read_text(encoding="utf-8")


def _function_source(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_scene_viewer_module_remains_valid_javascript() -> None:
    completed = subprocess.run(
        ["node", "--check", str(VIEWER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_shared_wall_keeps_a_distinct_room_override_on_each_face() -> None:
    source = _viewer_source()
    resolver = _function_source(
        source,
        "function wallMaterialResolver",
        "function wallSegmentPoint",
    )
    exterior_detection = _function_source(
        source,
        "function isExteriorWallSegment",
        "function wallEndpointTouchesExteriorBounds",
    )

    assert "resolveWallMaterial.faceMaterials = (segment, exteriorSideSign = 0)" in resolver
    assert "const roomOverrideForWallSide = (side) =>" in resolver
    assert "const positiveRoom = roomOverrideForWallSide(1);" in resolver
    assert "const negativeRoom = roomOverrideForWallSide(-1);" in resolver
    assert "const positiveContainsRoom = Boolean(positiveRoom)" in resolver
    assert "const negativeContainsRoom = Boolean(negativeRoom)" in resolver
    assert (
        "if (exteriorSideSign > 0 && !positiveContainsRoom && negativeContainsRoom)"
        in resolver
    )
    assert (
        "if (exteriorSideSign < 0 && !negativeContainsRoom && positiveContainsRoom)"
        in resolver
    )
    assert "positiveSide.clone(), negativeSide.clone(), interior.clone()," in resolver
    assert "interior.clone(), positiveSide.clone(), negativeSide.clone()," in resolver
    assert "if (leftInside || rightInside) return leftInside !== rightInside;" in exterior_detection


def test_room_ceiling_preview_uses_one_height_and_one_light_questionnaire_color() -> None:
    source = _viewer_source()
    ceiling = _function_source(
        source,
        "function createRoomCeilingOverrides",
        "function wallMaterialResolver",
    )
    room = _function_source(source, "function createRoom(sceneData)", "function buildFloorPlanOverlay")

    assert "const previewColor = questionnaireCeilingPreviewColor(" in ceiling
    assert "const previewHeight = wallHeight - unifiedDropCm;" in ceiling
    assert "color: previewColor.clone()" in ceiling
    assert "panel.position.y = previewHeight;" in ceiling
    assert 'panel.userData.roompilotCeilingPreviewMode = "questionnaire-unified-cover"' in ceiling
    assert "panel.userData.ceilingRequestedStyle = styleId;" in ceiling
    assert "panel.userData.ceilingPreviewFallbackNote = fallbackNote;" in ceiling
    assert "dropByStyle" not in ceiling
    assert "index * 0.05" not in ceiling
    assert "hasRoomCeilingRegions" in room
    assert "createRoomCeilingOverrides(sceneData, wallHeight)" in room
