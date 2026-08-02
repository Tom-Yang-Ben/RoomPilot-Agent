"""截圖出口接線契約（2026-07 盤點第 9 項修復）。

盤點結論：鎖定視角與 capturePng 機制完整、後端 browser_capture 入庫端點
經測試覆蓋（tests/test_project_store_hardening.py），但前端對 /renders、
下載函式全部零命中——使用者示範完視角鎖定後拿不出任何一張圖。

本檔鎖住接線本身：第 7 步（方案視角）與第 8 步（渲染視角）都要有
「下載 PNG」與「保存到專案」出口，保存走既有 POST /renders 樂觀鎖契約，
成果清單用後端附的 download_url。
"""
from __future__ import annotations

from backend.paths import STATIC_DIR


def _html() -> str:
    return (STATIC_DIR / "scene.html").read_text(encoding="utf-8")


def _source() -> str:
    return (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")


def test_both_steps_expose_download_and_save_buttons() -> None:
    html = _html()
    for element_id in (
        "download-proposal-view",
        "save-proposal-view-png",
        "download-render-view",
        "save-render-view-png",
        "saved-renders-list",
    ):
        assert f'id="{element_id}"' in html, f"scene.html 缺 {element_id}"


def test_save_uses_the_hardened_renders_endpoint_with_optimistic_lock() -> None:
    source = _source()

    assert "async function saveViewerPngToProject(" in source
    assert "/renders`" in source, "必須打 POST /api/projects/{id}/renders"
    assert 'form.append("expected_revision"' in source, "樂觀鎖欄位不可省略"
    assert "state.project = result.project" in source, "保存後必須更新 revision，否則第二張必 409"


def test_saved_renders_list_uses_backend_download_url() -> None:
    source = _source()

    assert "async function refreshSavedRenders(" in source
    assert "record.download_url" in source
    assert "refreshSavedRenders();" in source.split("async function prepareAiRender()", 1)[1].split(
        "function renderRequestPayload", 1
    )[0], "進入第 8 步時必須載入已保存清單"


def test_download_works_without_any_remote_provider() -> None:
    source = _source()

    assert "function downloadViewerPng(" in source
    assert "capturePng()" in source
    # 下載出口不得依賴遠端渲染設定——503 情境下仍要有本地成果。
    handler_block = source.split("function downloadViewerPng(", 1)[1].split("async function saveViewerPngToProject", 1)[0]
    assert "render-provider" not in handler_block
    assert "render_provider" not in handler_block
