---
name: 報告整理輸出
description: 統整 Docs 層全部文件，組稿九章設計手冊並輸出 PDF；含每房設計理念與選件理由，金額只出現在末章報價單，工程預算沿用工程文件 MVP 併章。
agent: Report Agent
tools: read_docs, render_pdf
---

## 提示詞：intro

你是室內設計手冊撰寫者。根據需求摘要與方案概況，
用兩三句繁體中文寫一段給屋主看的前言。語氣專業溫暖、能打動屋主，
但只依既有成果陳述，不誇大不實、不杜撰未提供的資訊。

## 輸出 schema：intro

```json
{
  "type": "object",
  "properties": {"intro": {"type": "string"}},
  "required": ["intro"]
}
```

## 提示詞：rationale

你是室內設計手冊撰寫者。根據每個空間的選件理由與通用設計原則
（焦點、動線、尺度、視覺平衡），為每間房寫一段繁體中文設計理念，
說明為什麼這樣配置、如何呼應屋主的風格與需求，語氣專業且能打動屋主。
每段兩到四句；只依提供的選件理由發揮，不杜撰未提供的家具或數據，
也不得計算任何尺寸或座標。

## 輸出 schema：rationale

```json
{
  "type": "object",
  "properties": {
    "rooms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "text": {"type": "string"}
        },
        "required": ["name", "text"]
      }
    }
  },
  "required": ["rooms"]
}
```

## 流程說明

1. `read_docs` tool 取 DocStore 快照（需求、清單、場景、驗證、生圖、
   使用者決策歷程）。
2. 九章 deterministic 組稿。**金額只准出現在第九章**：其餘章節（含餵給
   LLM 的 payload）不帶單價、小計與預算，避免潤稿把價格寫進敘述。
   一、專案與需求摘要（LLM 前言可選，離線用模板；不含預算金額）
   二、設計理念與亮點（每房選件理由＋擺放通則 → LLM 敘事；離線用理由
   直接組稿。理由來源＝家具文件 reason／hint.note，經 place_furniture
   附進 placed row）
   三、空間與平面配置（engine 座標翻成位置措辭）
   四、家具清單（品名、尺寸與選件理由；不帶金額）
   五、材質與色卡（標記使用者選定色卡）
   六、驗證與調整紀錄（含修復輪次與未解決裁決、改圖紀錄）
   七、渲染成果（每房最新 edit／full_render 圖）
   八、工程與預算章節（併工程文件 MVP ReportPayload 輸出；缺價保留
   pending_quote，不自行補猜）
   九、報價單（`backend/agent/quote` 彙整：同款同尺寸併列＋數量、單價、
   小計；缺價標「待報價」且不計入合計，不用中位數或預算回推補猜）
3. `render_pdf` tool 以 Pillow 排版輸出多頁 PDF（A4；中文字型自動尋找，
   `ROOMPILOT_PDF_FONT` 可覆蓋）。
4. 輸出 `DesignManualDoc`（含 pdf_path），寫入 DocStore `manual` 鍵。
