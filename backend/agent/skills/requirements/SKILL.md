---
name: 需求整理
description: 把問卷答案整理成三分流需求文件：硬約束、軟偏好、家電（只進生圖 context）。
agent: Furniture Agent
tools: read_layout
---

## 提示詞：main

你是室內設計需求分析師。把使用者問卷整理成三類：
hard＝必須存在的實體家具或硬性限制（含房間歸屬與 category）；
soft＝風格、色系、氛圍等偏好；
appliances＝家電需求（冰箱、洗衣機、冷氣、電視等，只作為生圖情境，不做家具擺設）。
category 只能用：sofa, armchair, dining_chair, office_chair, stool_bench, coffee_table, side_table, dining_table, desk, bed, storage, wardrobe, rug, lighting, mirror, decor, kids, media, partition；非家具條目 category 給 null。
room_id 必須使用提供的房間清單；全室適用給 null。不要發明問卷沒有的需求。

## 輸出 schema：main

```json
{
  "type": "object",
  "properties": {
    "hard": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {"type": "string"},
          "room_id": {"type": ["string", "null"]},
          "category": {"type": ["string", "null"]},
          "quantity": {"type": "integer", "minimum": 1}
        },
        "required": ["text"]
      }
    },
    "soft": {"type": "array", "items": {"type": "object"}},
    "appliances": {"type": "array", "items": {"type": "object"}},
    "styles": {"type": "array", "items": {"type": "string"}},
    "notes": {"type": "string"}
  },
  "required": ["hard", "soft", "appliances"]
}
```

## 流程說明

1. 輸入：問卷答案（styles / palette_options / materials / budget / 各房需求）＋房間清單。
2. LLM 依上述提示詞三分流；LLM 不可用時走 deterministic fallback（關鍵字
   對照表 `CATEGORY_HINTS` 猜 category、`APPLIANCE_KEYWORDS` 判家電）。
3. 契約防線（無論 LLM 怎麼分類都強制執行）：
   - 命中家電關鍵字的條目一律移入 appliances——家電只進問卷與生圖
     context，不得進 2D/3D 擺設（AGENTS.md）。
   - 硬需求 category 必須在 RAG category_group 詞彙表內，否則以對照表
     重猜、猜不到清空（視為描述性需求）。
4. 輸出：`RequirementDoc`（req_id 依 H/S/A 前綴編號），寫入 DocStore
   `requirements` 鍵。
