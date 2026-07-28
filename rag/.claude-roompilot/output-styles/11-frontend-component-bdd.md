---
name: 11-frontend-component-bdd
description: "Gradio UI 元件 BDD 設計 - 情境樣本、互動測試、可存取性"
stage: "Development"
template_ref: "12_frontend_architecture_specification.md"
---

# 指令 (你是資深 Gradio 介面工程師)

以「使用者行為」描述 UI 元件,輸出情境樣本 (Scenario Fixtures) 與互動測試,避免過早耦合實作細節。

本專案前端**只有 Gradio 6.20.0**（`rag_pipeline/app.py`,`http://127.0.0.1:7860`）,
卡片以 Python f-string 組出 HTML 字串再交給 `gr.HTML()` 呈現,不使用任何 JS 前端框架。

> ⚠️ **測試框架現況**:本專案**目前無正式測試套件**。以下 `pytest` 程式碼為建議骨架,
> **尚未建置**。落地時放在 `tests/ui/`,執行方式一律 `.venv-rag/bin/python -m pytest tests/ui -q`。

## 交付結構

### 1. 元件規格說明

```markdown
## 元件名稱: FurnitureResultCard  (實作於 rag_pipeline/app.py:card_html)

### 職責 (Responsibility)
顯示單件家具的檢索結果摘要,包含正面渲染縮圖、中文名稱、細類、風格標籤、氛圍詞、
三軸尺寸、台幣價格與四項評分 (綜合／相關／風格／氛圍),讓使用者一眼判斷是否符合需求。

### 使用場景 (Use Cases)
- 檢索結果頁的品項區塊,每個 block 最多 FINAL_TOP_K = 8 張卡片
- 整組搭配 (is_set = true) 時,每個 item 一列卡片牆 (沙發／茶几／單椅…)
- 使用者點擊追問選項按鈕後,以 refine() 重新檢索並重繪整片結果

### 參數 (Parameters)
| 名稱 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| row["meta"] | dict | ✅ | - | Chroma metadata（name_zh、category、style_primary、moods_flat、price_twd、尺寸） |
| row["score_final"] | float | ✅ | - | 綜合分 = 0.60×rerank + 0.20×style + 0.10×mood + 0.10×confidence |
| row["score_rerank"] / ["score_style"] / ["score_mood"] | float | ✅ | - | 三項分解分數,顯示於卡片底部灰字 |
| images | dict[str, str] | ✅ | - | furniture_id → `rendering/output/…/正面(abo\|ikea)/*.png` 路徑 |
| THUMB | int | ❌ | 240 | PIL 縮圖邊長,轉 base64 data URI 內嵌 |

### 事件 (Events)
- `search`: 使用者按「檢索」按鈕 (`go.click`) 或在輸入框按 Enter (`query.submit`)
- `refine`: 使用者點擊追問選項按鈕 (`opt_buttons[i].click` → `refine(query, option)`)
- `example_select`: 使用者點擊 `gr.Examples` 的五句範例需求,自動填入輸入框

### 狀態變化 (States)
- **正常**: 顯示「解析出的條件」摘要 + 主導風格／預算列 + 各品項卡片牆
- **載入中**: Gradio 按鈕內建進度指示;啟動時已 `load_models()` 預熱 bge-m3 + reranker,
  避免第一次查詢乾等一分鐘 (常駐約 4.6 GB)
- **需追問**: `needs_clarification = true` → 顯示追問訊息與最多 MAX_CLARIFY = 4 顆選項按鈕,
  下方結果先依目前理解呈現
- **空結果**: 該 block 的 hits 為空 → 紅字「這個條件下沒有符合的物件,請放寬預算或尺寸限制。」
- **空狀態**: 輸入空字串 → 條件摘要、追問列、結果全部清空並隱藏
```

### 2. 情境樣本 (Scenario Fixtures)

Gradio 沒有元件目錄伺服器,情境樣本以兩種形式落地:
**(a)** `gr.Examples` 的五句真實需求,啟動 UI 就能點;
**(b)** `tests/ui/fixtures_cards.py` 的 Python dict,供 pytest 直接餵給 `card_html()` / `results_html()`。

#### 2.1 主要流程情境

```python
# tests/ui/fixtures_cards.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/ui -q

BASE_META = {
    "furniture_id": "abo_sofa_0001",
    "name_zh": "米色亞麻三人座沙發",
    "category": "沙發",
    "style_primary": "japanese",
    "style_secondary": "scandinavian",
    "moods_flat": "寧靜|自然|溫潤",
    "width_cm": 198.0, "depth_cm": 88.0, "height_cm": 72.0,
    "price_twd": 18500,
    "confidence": 0.82,
    "category_conflict": False,
    "duplicate_group": "",
}


def meta(**over) -> dict:
    """永遠回傳新 dict,不修改 BASE_META（不可變性）。"""
    return {**BASE_META, **over}


def row(meta_over=None, **over) -> dict:
    base = {
        "id": BASE_META["furniture_id"],
        "meta": meta(**(meta_over or {})),
        "document": "名稱：米色亞麻三人座沙發。類別：沙發。…",
        "score_final": 0.8123, "score_rerank": 0.91,
        "score_style": 1.00, "score_mood": 0.67,
    }
    return {**base, **over}


# 情境 1: 日式侘寂沙發（單物件,預算兩萬內）
SCENARIO_JAPANESE_SOFA = {
    "query": "想要日式侘寂感、預算兩萬內的客廳沙發",
    "parsed": {
        "room_type": "living_room", "styles": ["japanese"],
        "moods": ["寧靜", "自然"], "budget_total": 20000, "price_level": None,
        "is_set": False, "confidence": 0.86, "needs_clarification": False,
        "items": [{"item_id": "main_sofa", "label_zh": "主沙發",
                   "category_group": "sofa", "quantity": 1, "role": "anchor",
                   "is_inferred": False, "styles": ["japanese"],
                   "semantic_query": "名稱：…。類別：沙發。風格：日式(japanese)。…"}],
    },
    "expect_dominant_style": "japanese",
}

# 情境 2: 北歐整組客廳（is_set,預算十萬,含推論品項）
SCENARIO_SCANDINAVIAN_SET = {
    "query": "北歐風溫馨感的客廳,幫我配一整組,預算十萬",
    "parsed_overrides": {
        "styles": ["scandinavian"], "moods": ["溫馨", "明亮"],
        "budget_total": 100000, "is_set": True,
    },
    "expect_blocks": ["主沙發", "茶几", "單椅", "邊桌"],
    "expect_inferred_badge": True,   # 推論品項顯示藍色「建議加入」標籤
}

# 情境 3: 只給風格、不給類別（category_group = null → 全庫語意檢索）
SCENARIO_INDUSTRIAL_ROOM = {
    "query": "臥室想弄成 loft 那種調調,牆面深色水泥",
    "parsed_overrides": {
        "room_type": "bedroom", "styles": ["industrial"],
        "color_hint": "深灰、水泥色", "material_hint": "水泥、黑鐵",
    },
    "expect_where_has_no_category": True,
}

# 情境 4: 餐桌配四張餐椅（quantity > 1,分配預算）
SCENARIO_DINING_SET = {
    "query": "餐廳要一張餐桌配四張餐椅,中古世紀現代風",
    "parsed_overrides": {"room_type": "dining_room", "styles": ["american"], "is_set": True},
    "expect_quantity_suffix": "×4",     # 卡片區塊標題顯示「餐椅 ×4」
}

# 情境 5: 模糊需求觸發追問（四顆選項按鈕）
SCENARIO_VAGUE_CHAIR = {
    "query": "想找便宜一點的椅子",
    "parsed_overrides": {
        "price_level": "budget", "budget_total": None,
        "needs_clarification": True,
        "clarify_question": "這張椅子要放在哪個空間？",
        "clarify_options": ["客廳", "書房", "餐廳", "臥室"],
    },
    "expect_visible_buttons": 4,
}
```

#### 2.2 邊界條件情境

```python
# 情境 6: 預熱中／首次載入（載入指示狀態）
SCENARIO_PREHEATING = {
    "query": "北歐風單椅",
    "state": "loading",
    "note": "app.py __main__ 先 load_models() 預熱,避免首查乾等；"
            "測試時 monkeypatch load_models 讓它停在載入態",
}

# 情境 7: 極小金額（NT$ 1,千分位格式與版面不可破）
SCENARIO_MINIMAL_PRICE = row({"price_twd": 1, "name_zh": "極簡木夾"})

# 情境 8: 極大金額 + 極大尺寸（NT$ 999,999 / 400×200×250 cm）
SCENARIO_MAXIMAL_PRICE = row({
    "price_twd": 999999, "name_zh": "大器實木長桌",
    "width_cm": 400.0, "depth_cm": 200.0, "height_cm": 250.0,
})

# 情境 9: 超長名稱（card_html 以 name_zh[:40] 截斷,容器 height:36px overflow:hidden）
SCENARIO_LONG_NAME = row({
    "name_zh": "北歐風原木色可延伸多功能餐邊櫃附抽屜與玻璃門片組合款超長名稱測試用例",
})

# 情境 10: 缺渲染圖（降級為灰底佔位方塊,不可讓版面塌陷）
SCENARIO_NO_RENDER_IMAGE = {
    "row": row(),
    "images": {},                    # render_index() 查不到此 id
    "expect_placeholder_div": True,  # <div style="height:150px;background:#f0f0f0…">
}
```

### 3. 互動測試 (Interaction Tests)

#### 3.0 BDD 場景 (Gherkin — 使用者操作 UI 的流程)

```gherkin
功能: RoomPilot 家具檢索介面

  場景: 輸入需求後看到符合風格的卡片
    假設 使用者開啟 http://127.0.0.1:7860 且模型已預熱完成
    當 使用者在「你想要什麼樣的家具？」輸入「想要日式侘寂感、預算兩萬內的客廳沙發」
    並且 點擊「檢索」按鈕
    那麼 畫面上方顯示解析出的條件:房型客廳、風格日式(japanese)、總預算 20,000
    並且 結果區出現主導風格「日式(japanese)」與首選組合總價
    並且 每張卡片顯示縮圖、名稱、細類、風格標籤、尺寸與 NT$ 價格

  場景: 需求模糊時以追問按鈕收斂
    假設 使用者輸入「想找便宜一點的椅子」
    當 系統判定 needs_clarification 為真
    那麼 顯示追問訊息與最多 4 顆選項按鈕
    並且 下方仍先依目前理解呈現結果
    當 使用者點擊選項「書房」
    那麼 系統以「想找便宜一點的椅子,書房」重新檢索並重繪卡片

  場景: 條件過嚴時給出可行動的錯誤訊息
    假設 使用者輸入「預算三千的實木餐桌」
    當 硬過濾後該品項沒有任何命中
    那麼 該區塊顯示紅字「這個條件下沒有符合的物件,請放寬預算或尺寸限制。」
    並且 其他品項的卡片仍正常呈現

  場景: 清空輸入後介面回到初始狀態
    假設 畫面上已有一批檢索結果
    當 使用者清空輸入框並按 Enter
    那麼 條件摘要、追問列與結果區全部清空且追問按鈕隱藏
```

#### 3.1 互動測試骨架

```python
# tests/ui/test_interactions.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/ui/test_interactions.py -q
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rag_pipeline"))
import app as ui  # noqa: E402
from fixtures_cards import SCENARIO_JAPANESE_SOFA, SCENARIO_VAGUE_CHAIR, row  # noqa: E402


@pytest.fixture
def stub_pipeline(monkeypatch):
    """把 parse_query / retrieve 換成 stub,UI 測試不打 Anthropic API、不載模型。"""
    calls = {"parse": [], "retrieve": []}

    def fake_parse(text, client=None):
        calls["parse"].append(text)
        return {**SCENARIO_JAPANESE_SOFA["parsed"]}

    def fake_retrieve(parsed, top_k=8):
        calls["retrieve"].append(parsed)
        return {"dominant_style": "japanese", "style_zh": "日式",
                "budget_total": 20000, "estimated_total": 18500,
                "blocks": [{"item_id": "main_sofa", "label_zh": "主沙發",
                            "category_group": "sofa", "quantity": 1,
                            "is_inferred": False, "price_cap": 20000,
                            "where": None, "hits": [row()]}]}

    monkeypatch.setattr(ui, "parse_query", fake_parse)
    monkeypatch.setattr(ui, "retrieve", fake_retrieve)
    monkeypatch.setattr(ui, "render_index", lambda: {})
    return calls


# 互動測試 1: 點擊「檢索」按鈕 → 條件摘要與卡片牆同時更新
def test_click_search_renders_condition_and_cards(stub_pipeline):
    condition, clarify, clarify_row, *rest = ui.search("想要日式侘寂感、預算兩萬內的客廳沙發")
    results_html = rest[-1]

    # 1. 需求被原文送進解析器
    assert stub_pipeline["parse"] == ["想要日式侘寂感、預算兩萬內的客廳沙發"]

    # 2. 條件摘要含房型／風格／預算
    assert "客廳" in condition and "日式" in condition and "20,000" in condition

    # 3. 沒有追問 → 追問列隱藏、訊息為空
    assert clarify == ""
    assert clarify_row["visible"] is False

    # 4. 卡片牆含名稱、價格與綜合分
    assert "米色亞麻三人座沙發" in results_html
    assert "NT$ 18,500" in results_html
    assert "綜合 0.812" in results_html


# 互動測試 2: 點擊追問選項按鈕 → 以「原句,選項」重新檢索
def test_click_clarify_option_triggers_refine(monkeypatch, stub_pipeline):
    monkeypatch.setattr(ui, "parse_query",
                        lambda text, client=None: {**SCENARIO_JAPANESE_SOFA["parsed"],
                                                   **SCENARIO_VAGUE_CHAIR["parsed_overrides"]})

    # 1. 第一次檢索出現追問列與 4 顆選項按鈕
    _, clarify, clarify_row, *btns_and_html = ui.search("想找便宜一點的椅子")
    btns = btns_and_html[:ui.MAX_CLARIFY]
    assert "需要確認" in clarify
    assert clarify_row["visible"] is True
    assert [b["value"] for b in btns] == ["客廳", "書房", "餐廳", "臥室"]
    assert all(b["visible"] for b in btns)

    # 2. 點擊「書房」→ refine 把選項接在原句之後
    ui.refine("想找便宜一點的椅子", "書房")
    assert stub_pipeline["parse"][-1] == "想找便宜一點的椅子,書房"


# 互動測試 3: 空輸入 → 全部清空、追問按鈕全部隱藏（等同載入前的靜止態）
def test_empty_query_clears_everything(stub_pipeline):
    condition, clarify, clarify_row, *rest = ui.search("   ")
    btns, results_html = rest[:ui.MAX_CLARIFY], rest[-1]

    assert condition == "" and clarify == "" and results_html == ""
    assert clarify_row["visible"] is False
    for btn in btns:
        assert btn["visible"] is False
    # 空輸入不應該打 API,省成本（需求解析每次約 US$0.005）
    assert stub_pipeline["parse"] == []


# 互動測試 4: 鍵盤操作 —— 輸入框按 Enter 等同點擊「檢索」
def test_keyboard_submit_is_bound_to_same_handler():
    demo = ui.build_ui()
    handlers = [(dep["targets"], dep["fn"]) for dep in demo.config["dependencies"]]

    # 1. go.click 與 query.submit 綁的是同一個 search 函式
    search_bindings = [t for t, fn in handlers if getattr(fn, "__name__", "") == "search"]
    assert len(search_bindings) >= 2, "Enter 送出未綁定,鍵盤使用者無法操作"

    # 2. 兩者輸出的元件清單一致,避免只有滑鼠路徑會更新畫面
    outs = {tuple(dep["outputs"]) for dep in demo.config["dependencies"]
            if getattr(dep["fn"], "__name__", "") == "search"}
    assert len(outs) == 1
```

### 4. 可存取性測試 (Accessibility Tests)

Gradio 版面本身由框架產生 (label、按鈕語意皆已具備),
**風險集中在 `card_html()` 手寫的 HTML 字串**——這段是我們自己的責任。

```python
# tests/ui/test_a11y.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/ui/test_a11y.py -q
import re

from fixtures_cards import row
import app as ui


def test_thumbnail_has_alt_text():
    """縮圖必須有 alt,螢幕閱讀器才知道這是哪件家具。

    現況缺口：app.py:card_html 的 <img> 尚未帶 alt —— 這是待修項,測試先紅著。
    """
    html_out = ui.card_html(row(), {"abo_sofa_0001": "/tmp/fake.png"})
    assert re.search(r'<img[^>]+alt="[^"]+"', html_out), "縮圖缺 alt 屬性"


def test_card_has_semantic_landmark_and_labels():
    """卡片應為可被輔助技術辨識的區塊,價格與評分要有可讀標籤。"""
    html_out = ui.card_html(row(), {})

    # 驗證語意角色（建議把最外層 <div> 改成 <article role="article">）
    assert 'role="article"' in html_out or "<article" in html_out

    # 驗證關鍵欄位有可存取名稱,而不是只有視覺樣式
    assert 'aria-label="價格' in html_out
    assert 'aria-label="綜合評分' in html_out


def test_text_contrast_meets_wcag_aa():
    """卡片文字對比需達 WCAG AA 4.5:1（正文）／3:1（大字）。

    已知：價格 #b45309 於白底約 4.9:1（通過）；
    id 灰字 #bbb 於白底約 1.9:1（不通過）—— 建議改為 #6b7280（約 4.8:1）。
    """
    html_out = ui.card_html(row(), {})
    assert "color:#bbb" not in html_out, "灰字對比不足 4.5:1"


def test_empty_block_message_is_announced():
    """無命中訊息要進 live region,而不是只有紅字視覺提示。"""
    result = {"dominant_style": "japanese", "style_zh": "日式",
              "budget_total": None, "estimated_total": 0,
              "blocks": [{"item_id": "x", "label_zh": "餐桌", "category_group": "table",
                          "quantity": 1, "is_inferred": False, "price_cap": None,
                          "where": None, "hits": []}]}
    html_out = ui.results_html(result)

    assert "沒有符合的物件" in html_out
    assert 'role="status"' in html_out or 'aria-live="polite"' in html_out
```

### 5. 響應式設計測試

卡片牆用 `display:flex;flex-wrap:wrap;gap:12px`,單卡固定 `width:220px`——
換行行為由瀏覽器負責,測試重點是**版面規則沒有被改壞**,以及不同視窗寬度下的手動檢查。

```python
# tests/ui/test_responsive.py（pytest 骨架,尚未建置）
import app as ui
from fixtures_cards import row

CARDS = [row(), row({"furniture_id": "ikea_chair_0002", "name_zh": "淺木單椅"})]
RESULT = {"dominant_style": "scandinavian", "style_zh": "北歐", "budget_total": None,
          "estimated_total": 0,
          "blocks": [{"item_id": "s", "label_zh": "主沙發", "category_group": "sofa",
                      "quantity": 1, "is_inferred": False, "price_cap": None,
                      "where": None, "hits": CARDS}]}


# 視窗 1: 窄視窗（約 375px）—— 單欄,卡片不得被壓縮到破版
def test_narrow_viewport_single_column_rules():
    html_out = ui.results_html(RESULT)
    assert "flex-wrap:wrap" in html_out          # 允許換行 → 窄視窗自然單欄
    assert "width:220px" in html_out             # 卡片寬度固定,不隨視窗縮到不可讀


# 視窗 2: 中視窗（約 768px）—— 三欄,圖片維持等比不裁切
def test_medium_viewport_image_fit():
    html_out = ui.results_html(RESULT)
    assert "object-fit:contain" in html_out      # 家具外觀不可被裁切
    assert "height:150px" in html_out            # 圖高一致,卡片頂線對齊


# 視窗 3: 寬視窗（約 1280px）—— 多欄,名稱區高度固定避免高低不齊
def test_wide_viewport_row_alignment():
    html_out = ui.results_html(RESULT)
    assert "height:36px" in html_out             # 名稱兩行高固定
    assert "overflow:hidden" in html_out
```

> 手動檢查清單:啟動 `.venv-rag/bin/python rag_pipeline/app.py` 後,
> 把瀏覽器視窗依序拉到約 375 / 768 / 1280 px,確認卡片牆換行正常、無水平捲軸。

### 6. 視覺回歸測試 (Visual Regression)

沒有截圖比對服務可用（本專案無 CI、無 Docker）,改用**HTML 快照回歸**:
把 `card_html()` 的輸出存成基準檔,改動樣式時 diff 一眼看出破壞範圍。

```python
# tests/ui/test_snapshot.py（pytest 骨架,尚未建置）
# 更新基準：.venv-rag/bin/python -m pytest tests/ui/test_snapshot.py --snapshot-update
from pathlib import Path

import app as ui
from fixtures_cards import (SCENARIO_LONG_NAME, SCENARIO_MAXIMAL_PRICE,
                            SCENARIO_MINIMAL_PRICE, row)

BASELINE = Path(__file__).parent / "snapshots"


# 快照 1: 五種代表狀態的卡片 HTML 基準
def test_card_html_snapshots():
    cases = {
        "normal": row(),
        "minimal_price": SCENARIO_MINIMAL_PRICE,
        "maximal_price": SCENARIO_MAXIMAL_PRICE,
        "long_name": SCENARIO_LONG_NAME,
        "category_conflict": row({"category_conflict": True}),
    }
    for name, case in cases.items():
        actual = ui.card_html(case, {})
        expected = (BASELINE / f"card_{name}.html").read_text(encoding="utf-8")
        assert actual.strip() == expected.strip(), f"卡片版面變動：{name}"


# 快照 2: 主題設定 —— Gradio 6 的 theme 在 launch() 傳,不在 Blocks()
def test_theme_is_passed_at_launch_not_blocks():
    source = (Path(ui.__file__)).read_text(encoding="utf-8")
    assert "gr.Blocks(title=" in source
    assert "theme=gr.themes.Soft()" in source
    # Gradio 6 若把 theme 塞進 Blocks(),UI 會以預設主題渲染,視覺整片走樣
    assert "gr.Blocks(theme=" not in source
```

### 7. 元件測試腳本 (Component Tests)

```python
# tests/ui/test_card_html.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/ui/test_card_html.py -q
import app as ui
from fixtures_cards import (SCENARIO_LONG_NAME, SCENARIO_MAXIMAL_PRICE,
                            SCENARIO_MINIMAL_PRICE, SCENARIO_NO_RENDER_IMAGE, row)


def test_should_render_furniture_information_correctly():
    html_out = ui.card_html(row(), {})

    assert "米色亞麻三人座沙發" in html_out
    assert "沙發" in html_out                 # 細類
    assert "日式" in html_out                 # style_primary 轉中文
    assert "寧靜、自然、溫潤" in html_out       # moods_flat 的 | 轉頓號
    assert "198×88×72 cm" in html_out


def test_should_format_price_with_thousand_separator():
    assert "NT$ 18,500" in ui.card_html(row(), {})
    assert "NT$ 1</b>" in ui.card_html(SCENARIO_MINIMAL_PRICE, {})      # 無千分位
    assert "NT$ 999,999" in ui.card_html(SCENARIO_MAXIMAL_PRICE, {})


def test_should_show_conflict_badge_only_when_category_corrected():
    # category_conflict = True → 顯示黃底「分類已修正」
    assert "分類已修正" in ui.card_html(row({"category_conflict": True}), {})
    # 預設 False → 不顯示
    assert "分類已修正" not in ui.card_html(row(), {})


def test_should_fallback_to_placeholder_when_render_image_missing():
    case = SCENARIO_NO_RENDER_IMAGE
    html_out = ui.card_html(case["row"], case["images"])

    assert "<img" not in html_out
    assert "background:#f0f0f0" in html_out    # 灰底佔位,版面不塌陷


def test_should_escape_user_visible_text_to_prevent_injection():
    """name_zh 來自資料集,仍必須 html.escape —— 邊界一律不信任外部資料。"""
    html_out = ui.card_html(row({"name_zh": '<script>alert("x")</script>沙發'}), {})

    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_should_truncate_over_long_name_without_breaking_layout():
    html_out = ui.card_html(SCENARIO_LONG_NAME, {})

    assert SCENARIO_LONG_NAME["meta"]["name_zh"][:40] in html_out
    assert SCENARIO_LONG_NAME["meta"]["name_zh"] not in html_out   # 超過 40 字被截斷
    assert "height:36px" in html_out and "overflow:hidden" in html_out
```

### 8. 可觀測性 (Observability)

本專案沒有前端分析服務,埋點以 **stdout 結構化日誌**落地——
啟動 UI 的終端機就是觀測面板,重點盯**延遲**（rerank 是主因）與**成本**（Haiku token）。

```python
# rag_pipeline/app.py（建議加在 search() 內）
import logging
import time

log = logging.getLogger("roompilot.ui")


def search(query: str):
    query = (query or "").strip()
    if not query:
        return ("", "", gr.update(visible=False), *[gr.update(visible=False)] * MAX_CLARIFY, "")

    t0 = time.perf_counter()
    parsed = parse_query(query)
    t_parse = time.perf_counter() - t0

    # 解析埋點：token 用量直接對應成本（每次約 US$0.005,cache_read 命中會顯著降低）
    usage = parsed.get("_usage", {})
    log.info(
        "ui.search.parsed query_len=%d styles=%s room=%s items=%d clarify=%s "
        "conf=%.2f in_tok=%d out_tok=%d cache_read=%d elapsed=%.2fs",
        len(query), parsed.get("styles"), parsed.get("room_type"),
        len(parsed.get("items") or []), parsed.get("needs_clarification"),
        parsed.get("confidence", 0),
        usage.get("input_tokens", 0), usage.get("output_tokens", 0),
        usage.get("cache_read", 0), t_parse,
    )

    t1 = time.perf_counter()
    result = retrieve(parsed)
    t_retrieve = time.perf_counter() - t1

    # 檢索埋點：零命中的品項要留下來,它直接對應使用者看到的紅字錯誤
    empty = [b["label_zh"] for b in result["blocks"] if not b["hits"]]
    log.info(
        "ui.search.retrieved dominant=%s blocks=%d empty=%s est_total=%d elapsed=%.2fs",
        result.get("dominant_style"), len(result["blocks"]), empty,
        result.get("estimated_total", 0), t_retrieve,
    )

    # …（維持原本的追問按鈕與 HTML 組裝邏輯）


def refine(query: str, option: str):
    # 追問埋點：追問被點擊的比率,反映需求解析的模糊程度
    log.info("ui.refine.clicked option=%s", option)
    return search(f"{query},{option}")
```

## 蘇格拉底檢核

1. **業務語言 vs 實作細節**:
   - 情境命名是否使用業務語彙? (✅ "SCENARIO_JAPANESE_SOFA" vs ❌ "CardBorderRadius10")
   - 測試是否關注行為而非實作? (✅ "should render furniture information" vs ❌ "should return f-string")

2. **可測試性**:
   - `card_html()` / `results_html()` 是否為純函式,只吃 dict 不碰全域狀態?
   - `search()` 的外部依賴 (`parse_query` / `retrieve` / `render_index`) 是否可被 monkeypatch,
     讓 UI 測試不打 Anthropic API、不載 4.6 GB 模型?

3. **可存取性**:
   - 縮圖是否有 alt? 價格與評分是否有 aria-label?
   - 是否可純鍵盤操作 (Enter 送出、追問按鈕 Tab 可達)?
   - 空結果訊息是否能被螢幕閱讀器讀出 (live region)?

4. **邊界條件覆蓋**:
   - 是否測試極小/極大價格、超長名稱、缺渲染圖?
   - 是否測試預熱中/零命中/需追問狀態?
   - 是否測試空輸入 (不得白打 API 燒額度)?

5. **視覺一致性**:
   - 是否在約 375 / 768 / 1280 px 三種視窗寬度下檢查過?
   - 主題是否確認在 `launch()` 傳 (Gradio 6 規則)?
   - 是否有 HTML 快照回歸保護樣式改動?

## 輸出格式

- 情境樣本使用 Python dict + `gr.Examples`,一律可由 `.venv-rag/bin/python` 直接執行
- 測試使用 pytest + monkeypatch（**本專案尚未建置測試套件**,以上為建議骨架）
- 遵循 Gradio 6.20.0 官方 API（Blocks / Row / Markdown / HTML / Examples;theme 在 `launch()` 傳）

## 審查清單

- [ ] 所有主要流程有對應情境樣本 (五句 `gr.Examples` 皆可跑通)
- [ ] 所有邊界條件有對應情境樣本 (極值/超長/缺圖/零命中/需追問)
- [ ] 互動測試涵蓋主要使用者操作 (檢索、追問、清空、Enter 送出)
- [ ] 縮圖有 alt、關鍵欄位有 aria-label
- [ ] 可純鍵盤導航 (Enter 送出與滑鼠點擊綁同一個 handler)
- [ ] 文字對比達 WCAG AA (灰字 #bbb 已列為待修)
- [ ] 測試使用語義化斷言 (斷內容與角色,不斷 CSS 位元組)
- [ ] 預熱中與零命中狀態有對應情境樣本
- [ ] 三種視窗寬度的版面規則有測試或手動檢查紀錄
- [ ] 有可觀測性埋點 (解析耗時、token 用量、零命中品項、追問點擊)

## 關聯文件

- **API 設計**: 05-api-contract-spec.md (`query_parser` structured outputs schema 為資料結構依據)
- **測試規範**: 06-tdd-unit-spec.md (測試原則)
- **前端架構**: VibeCoding_Workflow_Templates/12_frontend_architecture_specification.md
- **專案 SSOT**: `docs/RAG檢索系統說明.md`、`rag_pipeline/README.md`

---

**記住**: Gradio UI 測試應關注使用者行為而非實作細節。用情境樣本讓需求與介面並行驗證,
用互動測試保證 `search` / `refine` 的行為正確,用可存取性測試確保包容性。
本專案卡片 HTML 是手寫字串——框架幫不了你的部分,正是最需要測試的部分。
