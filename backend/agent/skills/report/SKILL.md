---
name: 報告整理輸出
description: 統整 Docs 層全部文件，組稿七章設計手冊並輸出 PDF；工程預算沿用工程文件 MVP 併章。
agent: Report Agent
tools: read_docs, render_pdf
---

## 提示詞：intro

你是室內設計手冊撰寫者。根據需求摘要與方案概況，
用兩三句繁體中文寫一段給屋主看的前言。語氣專業溫暖，不誇大。

## 輸出 schema：intro

```json
{
  "type": "object",
  "properties": {"intro": {"type": "string"}},
  "required": ["intro"]
}
```

## 流程說明

1. `read_docs` tool 取 DocStore 快照（需求、清單、場景、驗證、生圖、
   使用者決策歷程）。
2. 七章 deterministic 組稿：
   一、專案與需求摘要（LLM 前言可選，離線用模板）
   二、空間與平面配置（engine 座標翻成位置措辭）
   三、家具清單與預算參考（未標價品項不猜價）
   四、材質與色卡（標記使用者選定色卡）
   五、驗證與調整紀錄（含修復輪次與未解決裁決、改圖紀錄）
   六、渲染成果（每房最新 edit／full_render 圖）
   七、工程與預算章節（併工程文件 MVP ReportPayload 輸出；缺價保留
   pending_quote，不自行補猜）
3. `render_pdf` tool 以 Pillow 排版輸出多頁 PDF（A4；中文字型自動尋找，
   `ROOMPILOT_PDF_FONT` 可覆蓋）。
4. 輸出 `DesignManualDoc`（含 pdf_path），寫入 DocStore `manual` 鍵。
