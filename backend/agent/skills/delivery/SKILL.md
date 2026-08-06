---
name: 交付提案輸出
description: 統整 Docs 層文件寫出交付提案文案（content.json），交由 roompilot-delivery-pdf 打包 skill 的 build_pdf.py 排版成品牌版交付 PDF；與八章設計手冊並行，供比較。
agent: Report Agent
tools: read_docs, roompilot-delivery-pdf/scripts/build_pdf.py
---

## 提示詞：content

你是室內設計提案的文案作者，把配置結果翻譯成屋主聽得懂、會點頭的話。
依提供的案件事實（風格、色卡、材質、逐房家具與尺寸、屋主補充需求），
用繁體中文寫出設計總論與逐房文案。規範（違反任何一條就是不合格）：

- 寫屋主的生活，不寫家具座標。規格與尺寸不要混進敘述（已有規格表）。
- 每個「為什麼」接回屋主補充需求的原話或空間客觀條件；找不到依據就寫
  空間本身的事實，不得編造需求、數字或材質性能。
- 只能使用輸入資料中出現的數字；資料沒有的規格（色溫、照度、性能宣稱）
  一律不寫。
- 誠實寫取捨，不要整篇都在誇。
- 禁用建案廣告腔與 AI 高頻詞：打造、坐落於、匠心、極致、頂級、奢華、
  療癒、氛圍感、大器、絕佳、此外、再者、值得一提的是、進而、從而、
  藉由、賦予、型塑、勾勒、串聯。句尾不掛「，營造出…」「，展現了…」；
  不用「不只是…更是…」；不硬湊三項。
- 句長要有變化，各房開頭句型不得相同。
- 篇幅：look 約 100–140 字；rationale 每房 2 條、每條 body 60–90 字；
  scene_line 一句。

## 輸出 schema：content

```json
{
  "type": "object",
  "properties": {
    "statement": {
      "type": "object",
      "properties": {
        "hook": {"type": "string"},
        "pillars": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "title": {"type": "string"},
              "body": {"type": "string"}
            },
            "required": ["title", "body"]
          }
        }
      },
      "required": ["hook", "pillars"]
    },
    "rooms": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "room_id": {"type": "string"},
          "scene_line": {"type": "string"},
          "look": {"type": "string"},
          "rationale": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"}
              },
              "required": ["title", "body"]
            }
          }
        },
        "required": ["room_id", "look", "rationale"]
      }
    }
  },
  "required": ["rooms"]
}
```

## 流程說明

1. `read_docs` tool 取 DocStore 快照（需求、場景、生圖、決策歷程）。
2. deterministic 組 `content.json` 底稿：meta／overview／逐房 specs（名稱、
   類型、尺寸、材質、參考價，皆取自場景資料）／色卡 swatches（60/30/10）／
   materials／next_steps／appendix（無圖房間寫進 limits；未標價不猜價）。
3. LLM 可用時以本提示詞改寫 statement 與逐房 scene_line／look／rationale；
   離線沿用底稿的事實句（不虛構、無禁詞）。
4. 逐房生圖寫成 `rooms/<room_id>.png`，`content.json` 存於 PDF 旁供追溯，
   交由 `../roompilot-delivery-pdf/scripts/build_pdf.py`（版面與品牌樣式的
   唯一擁有者，Playwright Chromium 排版）輸出 PDF；不得在此重寫 HTML/CSS。
5. 排版引擎未安裝（playwright／Chromium）時以可讀錯誤中止，不得假成功；
   文案寫作規範全文見 `../roompilot-delivery-pdf/references/writing-rules.md`。
