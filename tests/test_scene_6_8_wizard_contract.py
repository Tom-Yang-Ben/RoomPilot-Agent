from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_step_six_requires_room_ab_selection_before_entering_the_editor() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    start = source.index("function roomSchemeSelectionRequired()")
    assert "return Boolean(state.rooms?.length && state.designSchemes?.schemes?.A);" in source[start : start + 500]
    assert "async function prepareProposalReview()" in source
    assert "function openStepSixTaskDialog(kind)" in source


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


def test_step_six_keeps_material_and_lighting_controls_in_closable_task_dialogs() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    for element_id in (
        "open-surface-adjustment",
        "open-lighting-adjustment",
        "surface-adjustment-dialog",
        "lighting-adjustment-dialog",
        "surface-editor",
        "lighting-editor",
    ):
        assert f'id="{element_id}"' in html
    assert 'openStepSixTaskDialog("surface")' in source
    assert 'openStepSixTaskDialog("lighting")' in source


def test_engineering_export_contains_configuration_room_context_and_cost_request() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "async function downloadEngineeringDelivery()" in source
    assert "configuration_snapshot: configuration" in source
    assert "engineering_brief" in source
    assert 'api("/api/cost/estimate"' in source
