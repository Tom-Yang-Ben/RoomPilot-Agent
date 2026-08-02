from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_step_six_requires_every_room_to_choose_a_scheme_before_micro_adjustment() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-scheme-selection-dialog"' in html
    assert 'id="room-scheme-complete"' in html
    assert "function composeSelectedRoomFurniture()" in source
    assert "allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)" in source
    assert "await confirmLayout2d({ allowPendingFurniture: true })" in source
    assert "configuration_scene_generation_failed" in source
    assert "function ensureRoomScheme3dPreviews()" in source
    assert "roomSchemePreviewCache" in source
    assert "whiteViewer.capturePng()" in source


def test_render_submission_requires_a_user_visible_render_brief() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="render-brief-dialog"' in html
    assert 'id="render-brief-confirm"' in html
    assert "function openRenderBriefDialog(" in source
    assert "function confirmRenderBriefAndSubmit()" in source
    assert "render_brief: renderBrief" in source
    assert "room_scheme_selections" in source
    assert "configuration_snapshot" in source


def test_step_six_moves_existing_material_and_lighting_controls_into_task_dialogs() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="open-surface-adjustment"' in html
    assert 'id="open-lighting-adjustment"' in html
    assert 'id="surface-adjustment-dialog"' in html
    assert 'id="lighting-adjustment-dialog"' in html
    assert 'id="surface-editor"' in html
    assert 'id="lighting-editor"' in html
    assert "function openStepSixTaskDialog(kind)" in source
    assert "function restoreStepSixTaskControls()" in source
    assert 'openStepSixTaskDialog("surface")' in source
    assert 'openStepSixTaskDialog("lighting")' in source


def test_configuration_generation_explains_catalog_unavailability_before_starting() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="requirements-generation-help"' in html
    assert 'id="retry-configuration-catalog-check"' in html
    assert 'id="return-to-room-requirements"' in html
    assert "async function configurationCatalogReadiness()" in source
    assert 'await api("/api/catalog/status")' in source
    assert "showRequirementsGenerationHelp(" in source
    assert "Kai 家具型錄尚未就緒" in source
