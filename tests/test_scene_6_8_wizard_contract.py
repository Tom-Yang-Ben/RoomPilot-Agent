from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_step_six_keeps_legacy_ab_data_out_of_the_user_workflow() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    start = source.index("function roomSchemeSelectionRequired()")
    assert "return false;" in source[start : start + 500]
    assert 'id="room-scheme-gate" class="rp-editor-box" aria-labelledby="room-scheme-gate-title" hidden' in html
    assert "async function prepareProposalReview()" in source
    assert "function allStepSixRoomSurfacesConfirmed()" in source


def test_step_seven_locks_every_room_view_before_color_card_selection() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "第 7 步：逐房生圖視角" in source
    assert "先選好每個房間的視角" in source
    assert "確認視角並進入代表房色卡比較" in source
    assert "function proposalRoomCameraCandidates(room)" in source
    assert "function confirmProposalRoomViews()" in source
    assert "function renderProposalStyleStage()" in source
    assert "proposal-confirm-render-palette" in source
    assert "confirmedStyleCardId" in source


def test_step_eight_submits_each_room_with_a_confirmed_view_and_user_brief() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="render-brief-dialog"' in html
    assert 'id="render-brief-confirm"' in html
    assert "function openRenderBriefDialog(" in source
    assert 'renderRequestPayload("room_final"' in source
    assert "spatial_override_warning" in source
    assert 'state.workflow.complete("ai_render"' in source
    assert "function aiRenderSubmissionPayload(" in source
    submission = source.split("function aiRenderSubmissionPayload(", 1)[1].split(
        "async function submitRoomRenders", 1
    )[0]
    assert "lockedConfigurationSnapshot()" in submission
    assert "refreshConfigurationSnapshot()" not in submission
    assert "configuration_snapshot: configuration" in submission
    assert "room_surface_assignments:" not in submission


def test_step_six_surface_confirmation_refreshes_the_shared_snapshot() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    confirmation = source.split("async function confirmStepSixRoomSurfaces()", 1)[1].split(
        "function unlockStepSixRoomSurfaces", 1
    )[0]

    assert "refreshConfigurationSnapshot();" in confirmation
    assert confirmation.index("requirement.surfaces =") < confirmation.index(
        "refreshConfigurationSnapshot();"
    )


def test_step_six_exposes_room_surface_controls_without_a_lighting_editor() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    surface_panel = html.split('id="white-model-surface-entry"', 1)[1].split(
        'id="white-model-error"', 1
    )[0]

    assert 'class="rp-white-surface-entry"' in surface_panel
    assert 'data-scene-sidebar-panel="surfaces"' in surface_panel
    assert html.count('id="white-walk-room"') == 1
    for removed_element_id in (
        "continue-to-surface-adjustment",
        "open-surface-adjustment",
        "surface-adjustment-dialog",
        "surface-adjustment-content",
        "surface-room-selector",
    ):
        assert f'id="{removed_element_id}"' not in html
    assert 'id="open-lighting-adjustment"' not in html
    assert 'id="lighting-adjustment-dialog"' not in html
    assert "調整天花與照明" not in html


def test_step_six_inline_surface_editor_exposes_the_confirmed_controls() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    surface_panel = html.split('id="white-model-surface-entry"', 1)[1].split(
        'id="white-model-error"', 1
    )[0]

    for markup in (
        'data-step-six-surface-tab="wall"',
        'data-step-six-surface-tab="floor"',
        'data-surface-color-palette="wall"',
        'data-surface-color-palette="floor"',
        'id="wall-color"',
        'id="floor-color"',
        'id="wall-material-grouped"',
        'id="floor-material-grouped"',
        'data-open-material-catalog="wall"',
        'data-open-material-catalog="floor"',
        'id="surface-room-progress"',
        'id="confirm-room-surfaces"',
        'id="unlock-room-surfaces"',
        '<details id="material-boundary-advanced"',
    ):
        assert markup in surface_panel


def test_engineering_export_contains_configuration_room_context_and_cost_request() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    delivery = source.split("async function downloadEngineeringDelivery()", 1)[1].split(
        "function engineeringReportFilename", 1
    )[0]

    assert "async function downloadEngineeringDelivery()" in source
    assert "lockedConfigurationSnapshot()" in delivery
    assert "refreshConfigurationSnapshot()" not in delivery
    assert "configuration_snapshot: configuration" in delivery
    assert "engineering_brief" in delivery
    assert "/design-delivery`" in delivery
