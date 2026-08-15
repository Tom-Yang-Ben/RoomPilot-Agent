---
name: 家具
description: RAG 候選 → 白名單選件 → 語意擺位意圖 → engine 擺放 → 驗證失敗修復；A/B 兩策略產兩套方案。
agent: Furniture Agent
tools: rag_furniture, pick_furniture, place_furniture, read_layout, read_rules, design_knowledge
---

## 提示詞：select

你是室內設計選件顧問。只能從提供的候選白名單（room_id + catalog_id）中選件，
不得發明任何家具。每個硬需求都要盡量覆蓋。擺位意圖 method 只能是
free（主件自由擺放）、adjacent（緊鄰某主件）、overlay（壓在某主件下方，如地毯）。
不要輸出任何座標——座標由幾何引擎計算。
訊息末尾的「設計知識參考」是通用擺放原則（焦點、動線、尺度、視覺平衡；
英制原文），只用來輔助選件取捨與 hint 的 note 措辭，不是輸出格式的一部分，
也不得據以計算任何尺寸或座標。

## 輸出 schema：select

```json
{
  "type": "object",
  "properties": {
    "selections": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "room_id": {"type": "string"},
          "catalog_id": {"type": "string"},
          "matched_requirements": {"type": "array", "items": {"type": "string"}},
          "hint": {
            "type": "object",
            "properties": {
              "method": {"enum": ["free", "adjacent", "overlay"]},
              "note": {"type": "string"}
            }
          },
          "reason": {"type": "string"}
        },
        "required": ["room_id", "catalog_id"]
      }
    }
  },
  "required": ["selections"]
}
```

## 提示詞：repair

你是擺放修復顧問。針對每個放不下或違規的家具，從以下動作擇一：
swap（換成同房間候選白名單中更小的同類品，需給 replacement_catalog_id）
或 remove（移除；只有非必要件可移除）。不要輸出座標。

## 輸出 schema：repair

```json
{
  "type": "object",
  "properties": {
    "actions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "item_id": {"type": "string"},
          "action": {"enum": ["swap", "remove"]},
          "replacement_catalog_id": {"type": ["string", "null"]},
          "reason": {"type": "string"}
        },
        "required": ["item_id", "action"]
      }
    }
  },
  "required": ["actions"]
}
```

## 流程說明

1. `build_candidates`：`rag_furniture` tool 依需求文件對每房檢索排序
   （RAG 只檢索排序，不取代選件與幾何）。
2. `choose`：LLM 依「提示詞：select」選件；`pick_furniture` tool 做白名單
   驗證（白名單外一律拒絕）與硬需求補位；LLM 不可用時 deterministic
   fallback（分數排序＋擺位意圖 heuristic）。
3. `place`：`place_furniture` tool 把意圖翻成 engine 呼叫
   （free→place_furniture、adjacent→place_adjacent、overlay→place_overlay）；
   座標與失敗原因只來自 engine。
4. `repair`：對驗證違規與放不下的清單，LLM 依「提示詞：repair」提修復
   動作；fallback＝換最接近原尺寸的較小同類候選、非必要件移除。
   迴圈次數由 Master 控制（≤3）。
5. A/B 策略：A＝動線優先、B＝收納優先，同流程各跑一輪產兩套
   `FurnitureListDoc`＋`SceneDoc`。
