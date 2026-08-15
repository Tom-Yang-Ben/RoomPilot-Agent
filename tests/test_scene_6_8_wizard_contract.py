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
    # 預覽改走離屏縮圖 viewer 拍照（拍完卸載），前景 whiteViewer 場景與相機不動。
    assert "glbThumbnailViewer.capturePng()" in source


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


def test_step_six_surface_controls_live_in_the_white_model_sidebar_tab() -> None:
    # bella-new 架構：材質微調不再彈任務對話框（open-surface-adjustment /
    # surface-adjustment-dialog / openStepSixTaskDialog 皆已拆除），改為第 6 步
    # 白模側欄三分頁的「牆面與地面」分頁（white-model-surface-entry），並以
    # confirmStepSixRoomSurfaces / unlockStepSixRoomSurfaces 提供逐房草稿→鎖定
    # 的生命週期。此測試釘住新結構，避免退回舊的任務對話框設計。
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    # 舊的任務對話框設計必須維持已拆除。
    assert 'id="surface-adjustment-dialog"' not in html
    assert 'id="lighting-adjustment-dialog"' not in html
    assert "openStepSixTaskDialog" not in source

    # 材質面板嵌在白模側欄的第三個分頁（surfaces），而非彈窗。
    assert 'data-scene-sidebar-tab="surfaces">牆面與地面</button>' in html
    assert 'id="white-model-surface-entry"' in html
    assert 'data-scene-sidebar-panel="surfaces"' in html
    # 牆面與地面各自為表面子分頁。
    assert 'data-step-six-surface-kind="wall"' in html
    assert 'data-step-six-surface-kind="floor"' in html

    # 逐房草稿→鎖定生命週期：確認/解鎖按鈕、鎖定狀態與進度。
    assert 'id="confirm-room-surfaces"' in html
    assert 'id="unlock-room-surfaces"' in html
    assert 'id="surface-room-lock-state"' in html
    assert 'id="surface-room-progress"' in html
    assert "async function confirmStepSixRoomSurfaces()" in source
    assert "function unlockStepSixRoomSurfaces()" in source
    assert "stepSixSurfaceConfirmed: true" in source
    # 確認鈕確實接上逐房確認生命週期。
    assert "void confirmStepSixRoomSurfaces()" in source
    assert 'button.addEventListener("click", unlockStepSixRoomSurfaces)' in source


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
