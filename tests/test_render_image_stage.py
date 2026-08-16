"""第 7/8 步生圖「放大到 3D 區呈現」契約測試。

scene_v2.js 於載入時就會接觸 THREE 與 DOM,無法在 node 單獨匯入執行,
因此沿用本檔庫既有慣例(見 test_scene_v2_contract.py):以文字契約斷言
DOM id、函式與事件接線都在,任何一處被改壞測試就會紅燈。

驗證使用者需求:
- 第 7 步三張色卡、第 8 步全房生圖的縮圖都能點擊放大到左側 3D 疊層;
- 疊層隨時可用關閉鈕/點空白切回 3D;
- 放大與圖片牆都標明「是哪一個房間/色卡」;
- 第 8 步新增「查看已生成圖片」呈現按鈕(圖片牆)。
"""
from __future__ import annotations

import re

from scripts.update_static_hashes import static_content_digest
from test_scene_workflow import ROOT


STATIC = ROOT / "backend" / "server" / "static"


def _html() -> str:
    return (STATIC / "scene.html").read_text(encoding="utf-8")


def _js() -> str:
    return (STATIC / "scene_v2.js").read_text(encoding="utf-8")


def _css() -> str:
    return "\n".join(
        (STATIC / name).read_text(encoding="utf-8")
        for name in ("site.css", "scene.css")
    )


def test_overlay_dom_exposes_empty_gallery_without_claiming_generated_images() -> None:
    html = _html()
    # 放大疊層:單張圖 + 房名/色卡標籤 + 圖片牆 + 切回 3D 關閉鈕。
    assert 'id="ai-render-image-stage"' in html
    assert 'id="ai-render-image-caption"' in html
    assert 'id="ai-render-gallery"' in html
    assert 'id="ai-render-stage-close"' in html
    assert 'id="ai-render-image-toggle"' in html
    assert "尚未連接遠端渲染服務" in html
    assert 'id="ai-openrouter-gallery"' not in html
    # 關閉鈕文案要讓使用者知道能切回 3D。
    assert "切回 3D" in html


def test_js_exposes_enlarge_and_close_helpers_without_fake_gallery_action() -> None:
    js = _js()
    assert "let renderStageView" in js
    assert "function completedOpenrouterRows" in js
    assert "function showRenderImageEnlarged" in js
    assert "function showRenderGallery" not in js
    assert "function closeRenderImageStage" in js
    # 疊層元素都註冊到 element registry。
    for ref in (
        'aiRenderImageCaption: $("#ai-render-image-caption")',
        'aiRenderGallery: $("#ai-render-gallery")',
        'aiRenderStageClose: $("#ai-render-stage-close")',
    ):
        assert ref in js, ref


def test_js_wires_only_real_completed_rows_and_close_actions() -> None:
    js = _js()
    # 第 7 步色卡縮圖點擊 → 放大。
    assert 'element.paletteRenderResults?.addEventListener("click"' in js
    assert "completedOpenrouterRows().find" in js
    assert "tile.dataset.galleryRoom" in js
    assert "element.aiRenderStageClose?.addEventListener" in js
    assert "data-gallery-room" in js


def test_gallery_and_caption_have_styles() -> None:
    css = _css()
    assert ".rp-render-gallery {" in css
    assert ".rp-render-gallery-item" in css
    assert ".rp-render-image-caption {" in css
    assert ".rp-render-stage-close {" in css


def test_module_state_assignments_are_all_declared() -> None:
    """函式內賦值的模組層狀態一定要有宣告，否則整條看圖路徑會 ReferenceError。

    886b7f7f 帶狀拼接時把 ``let aiRenderImageVisible = false;`` 整行刪掉，留下
    5 處使用、0 處宣告。scene_v2.js 以 ``type="module"`` 載入（嚴格模式），
    這種漏宣告一執行就 ReferenceError：進第 8 步時 prepareAiRender 中斷、
    一鍵全房生圖走進 catch（連 scheduleSave 都沒跑到，生圖結果不落地）、
    縮圖點了沒反應。``node --check`` 與字串契約測試都驗不到——語法合法、
    字串也還在——所以這裡改用「宣告是否存在」當守門。

    範圍（刻意保守，只漏報不誤報）：只看縮排、以 ``;`` 收尾、且名稱含大寫的
    賦值。樣板字串裡的 HTML／SVG 屬性（``class=``、``stroke=``）與跨行參數
    預設值因此都不會誤入。要精準判別得做完整 JS 詞法分析（本檔有 ``/[&<>"']/g``
    這種帶引號的正則字面量，逐字掃描一樣會咬錯邊界），代價不值得。
    """
    js = _js()
    declared: set[str] = set()
    for pattern in (
        r"\b(?:let|const|var)\s+([A-Za-z_$][\w$]*)",
        r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)",
        r"\bclass\s+([A-Za-z_$][\w$]*)",
    ):
        declared.update(match.group(1) for match in re.finditer(pattern, js))

    undeclared: dict[str, int] = {}
    for lineno, line in enumerate(js.splitlines(), 1):
        match = re.match(r"\s+([A-Za-z_$][\w$]*)\s*=(?!=)[^;]*;\s*$", line)
        if not match:
            continue
        name = match.group(1)
        if name.lower() == name or name in declared:
            continue
        undeclared.setdefault(name, lineno)

    assert not undeclared, (
        "scene_v2.js 有賦值但沒宣告的識別字（嚴格模式下一執行就 ReferenceError）："
        + "、".join(f"{name}（第 {line} 行）" for name, line in sorted(undeclared.items()))
    )


def test_step8_render_state_variables_are_declared() -> None:
    """疊層的兩個模組層狀態要成對存在；少一個就等於整個看圖路徑沒接上。"""
    js = _js()
    assert "let renderStageView" in js
    assert "let aiRenderImageVisible" in js


def test_report_payload_carries_the_living_room_night_image() -> None:
    """夜間圖要跟著報告 payload 送出，否則後端圖庫建不出 full_render_night。"""
    js = _js()
    payload = js[js.index("function deliveryRoomsPayload"):]
    payload = payload[: payload.index("\n}\n")]
    assert "night_image_data_url: finalRoom?.night_image_data_url" in payload
    assert "night_model: finalRoom?.night_model" in payload
    # 生圖回應的 night_model 也要存進 finalRooms，逐房與一鍵全房兩條路徑都要。
    assert "night_model: renderResult.night_model" in js
    assert "night_model: row.night_model" in js


def test_representative_room_still_gets_a_night_render() -> None:
    """代表房沿用色卡圖當日光初稿後，夜間圖仍要有觸發點。

    色卡比較的代表房通常就是客廳（實測專案 `palette_render.room_id = room-6`
    ＝客廳）。`seedRepresentativeRoomRenderFromPalette()` 把色卡圖塞進
    `finalRooms` 並設 `submitted_at`，該房因此被一鍵生圖的 pending 過濾排除，
    `full_render_night` 從來不會被請求 —— 前端沒有夜間縮圖、報告也沒有夜間圖。
    """
    js = _js()
    assert "function roomsMissingNightRender" in js
    assert "function isLivingRoomForRender" in js
    # 補生的房間以 night_only 併進同一次請求（只生夜間那張，不重生日光初稿）。
    assert "night_only: true" in js
    # night_only 結果不得覆蓋既有日光初稿與 submitted_at。
    flow = js[js.index("async function submitAllRoomRenders"):]
    flow = flow[: flow.index("\n}\n")]
    assert "if (row.night_only)" in flow
    assert "nightPending" in flow
    # 全部初稿完成、只剩夜間圖時，一鍵按鈕仍要出現（否則沒有任何觸發點）。
    panel = js[js.index("function renderFinalRoomWorkflow"):]
    panel = panel[: panel.index("\n}\n")]
    assert "anyPending || nightPendingCount" in panel


def test_entrypoint_cache_keys_are_fresh_after_this_change() -> None:
    """本變更改了 scene_v2.js 與 site.css → scene.html 的 sha256 cache key 必須同步更新。"""
    html = _html()
    expected_bundle = static_content_digest(STATIC / "scene_v2.js", 12)
    expected_site_css = static_content_digest(STATIC / "site.css", 12)
    expected_scene_css = static_content_digest(STATIC / "scene.css", 12)
    assert f'src="/static/scene_v2.js?v=sha256-{expected_bundle}"' in html
    assert f'href="/static/site.css?v=sha256-{expected_site_css}"' in html
    assert f'href="/static/scene.css?v=sha256-{expected_scene_css}"' in html
