# 工程知識資料字典

## WorkItem

| 欄位 | 說明 |
|---|---|
| work_item_code | 穩定且唯一的工項代碼 |
| trade | 工種 |
| name | 顯示名稱 |
| unit | m2、m、point、unit 等 |
| quantity_key | 從 Quantity／RAG 哪個欄位取得數量 |
| default_for_room | 是否每房間自動加入 |
| professional_confirmation_required | 是否必須專業確認 |
| source_id | 來源 ID |
| confidence | low／medium／high／contractor_confirmed |

## MaterialWorkMapping

| 欄位 | 說明 |
|---|---|
| keywords | 材料名稱命中詞 |
| part | floor／wall／ceiling／other |
| work_item_codes | 觸發工項 |

## EquipmentMEPMapping

| 欄位 | 說明 |
|---|---|
| categories | 家具／設備 category 精確值或同義值 |
| required_systems | power、lighting、data、cold_water、hot_water、drain、hvac |
| direct_work_items | 直接觸發的安裝工項 |
| reason | 推薦理由 |

## PriceRecord

數字只由 Cost Service 使用；LLM 不得改寫或補值。

## ProductivityRecord

數字只由 Schedule Service 使用；LLM 不得改寫或補值。

## ConstructionKnowledge

文字型 RAG 文件。每筆必須有 id、title、content、source_id、confidence 與 professional_confirmation_required。
