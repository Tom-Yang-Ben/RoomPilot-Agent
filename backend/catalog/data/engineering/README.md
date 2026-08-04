# RoomPilot MVP 工程知識資料

這個資料夾同時包含：

```text
Structured Data：精確工項、單位、價格、工率與依賴
RAG Documents：工法說明、注意事項與專業責任文字
```

## 檔案用途

| 檔案 | 用途 | 查詢方式 |
|---|---|---|
| work_items.json | 工項主檔、單位、quantity_key | Structured |
| material_catalog.json | 材質主檔與 Demo 材料價 | UI／Structured；Cost Service 目前不直接加總此檔 |
| material_work_mappings.json | 材料／部位 → 工項 | Structured |
| equipment_mep_mappings.json | 設備 → 水電需求／安裝工項 | Structured |
| price_records.json | Demo 價格 | Cost Service |
| productivity_records.json | Demo 工率 | Schedule Service |
| task_dependencies.json | 工序依賴 | Schedule Service |
| construction_knowledge.jsonl | 工法、風險、注意事項 | Advanced RAG 種子；目前以 Structured fallback 讀取 |
| source_registry.json／csv | 官方／Demo 來源登錄 | Traceability；JSON 為 runtime 主檔，CSV 為交接鏡像 |
| production_templates/ | 正式材料、單價與工率待填模板 | Production onboarding；不可當作已確認數值 |
| DATA_DICTIONARY.md | 欄位定義 | 維護與資料匯入 |
| PRICE_AND_PRODUCTIVITY_POLICY.md | 價格／工率政策 | 正式化與審核 |

## 數量

本版含：

```text
29 個常用 MVP 工項
14 組材料對應
13 組設備／水電對應
12 筆 Demo 材質價格
29 筆 Demo 工項價格
29 筆 Demo 工率
45 筆工序依賴
10 篇 RAG 種子文件
```

## Demo 資料規則

`price_records.json` 與 `productivity_records.json` 的數字是合成示範資料，目的只有：

- 測試公式。
- 顯示專題畫面。
- 產生完整 HTML／XLSX。
- 驗證排程依賴。

共同標記：

```json
{
  "region": "DEMO_ONLY",
  "source_type": "synthetic_demo",
  "is_synthetic": true,
  "confidence": "low"
}
```

不得宣稱為新北市行情、正式估價或廠商報價。

## 正式化

1. 設定 `ROOMPILOT_DEMO_MODE=false`。
2. 從 `production_templates/` 建立新版本，或由正式資料 Provider Adapter 新增
   同地區、同單位、同日期且有 `source_id` 的報價／歷史案件；不得把 null pending
   模板當成已確認價格，也不覆寫本資料夾的 Demo seed。
3. 通過設計師或廠商確認後，更新 confidence 與 status。
4. 不要直接覆寫歷史紀錄；新增新 effective_date 的版本。

目前 `NoopEngineeringSemanticRetriever` 是明示的 Mock／Noop，並不會查詢真正的
Vector Index。正式接入時只替換 Semantic Retriever Adapter；精確數字仍須走
Structured Retrieval。

## 哪些資料放 Vector Index

只放：

- construction_knowledge.jsonl 的 title/content。
- 材料工法說明。
- 施工注意事項。
- 專業責任與風險說明。

不要把以下資料當成向量答案：

- 精確單價。
- 工率。
- 尺寸。
- 日期。
- 工程量。
- 工項代碼。

這些必須走結構化查詢。

## 材質價格與工項價格的差異

`material_catalog.json` 是材料選擇與 UI 參考；`price_records.json` 是 Cost Service 使用的工項單價，已拆成材料、人工與其他費用。MVP 不可同時把兩者重複加總。
