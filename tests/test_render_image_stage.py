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

import hashlib

from test_scene_workflow import ROOT


STATIC = ROOT / "backend" / "server" / "static"


def _html() -> str:
    return (STATIC / "scene.html").read_text(encoding="utf-8")


def _js() -> str:
    return (STATIC / "scene_v2.js").read_text(encoding="utf-8")


def _css() -> str:
    return (STATIC / "site.css").read_text(encoding="utf-8")


def test_overlay_dom_exposes_caption_gallery_close_and_present_button() -> None:
    html = _html()
    # 放大疊層:單張圖 + 房名/色卡標籤 + 圖片牆 + 切回 3D 關閉鈕。
    assert 'id="ai-render-image-stage"' in html
    assert 'id="ai-render-image-caption"' in html
    assert 'id="ai-render-gallery"' in html
    assert 'id="ai-render-stage-close"' in html
    # 第 8 步缺的「呈現已獲取圖片」按鈕。
    assert 'id="ai-openrouter-gallery"' in html
    assert "查看已生成圖片" in html
    # 關閉鈕文案要讓使用者知道能切回 3D。
    assert "切回 3D" in html


def test_js_exposes_enlarge_gallery_and_close_helpers() -> None:
    js = _js()
    assert "let renderStageView" in js
    assert "function completedOpenrouterRows" in js
    assert "function showRenderImageEnlarged" in js
    assert "function showRenderGallery" in js
    assert "function closeRenderImageStage" in js
    # 疊層元素都註冊到 element registry。
    for ref in (
        'aiRenderImageCaption: $("#ai-render-image-caption")',
        'aiRenderGallery: $("#ai-render-gallery")',
        'aiRenderStageClose: $("#ai-render-stage-close")',
        'aiOpenrouterGallery: $("#ai-openrouter-gallery")',
    ):
        assert ref in js, ref


def test_js_wires_thumbnail_clicks_and_present_button() -> None:
    js = _js()
    # 第 7 步色卡縮圖點擊 → 放大。
    assert 'element.paletteRenderResults?.addEventListener("click"' in js
    # 第 8 步全房縮圖點擊 → 放大(依 room 卡片 dataset)。
    assert 'element.aiOpenrouterResults?.addEventListener("click"' in js
    assert "card.dataset.roomId" in js
    # 呈現按鈕開圖片牆;關閉鈕/圖片牆磚塊接線。
    assert "element.aiOpenrouterGallery?.addEventListener" in js
    assert "element.aiRenderStageClose?.addEventListener" in js
    assert "data-gallery-room" in js


def test_gallery_and_caption_have_styles() -> None:
    css = _css()
    assert ".rp-render-gallery {" in css
    assert ".rp-render-gallery-item" in css
    assert ".rp-render-image-caption {" in css
    assert ".rp-render-stage-close {" in css


def test_entrypoint_cache_keys_are_fresh_after_this_change() -> None:
    """本變更改了 scene_v2.js 與 site.css → scene.html 的 sha256 cache key 必須同步更新。"""
    html = _html()
    bundle = (STATIC / "scene_v2.js").read_bytes()
    css = (STATIC / "site.css").read_bytes()
    expected_bundle = hashlib.sha256(bundle).hexdigest()[:12]
    expected_css = hashlib.sha256(css).hexdigest()[:12]
    assert f'src="/static/scene_v2.js?v=sha256-{expected_bundle}"' in html
    assert f'href="/static/site.css?v=sha256-{expected_css}"' in html
