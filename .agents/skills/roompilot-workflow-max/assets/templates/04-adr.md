# ADR-［編號］：［決策標題］

> 狀態：［提議／接受／取代／棄用］｜日期：［YYYY-MM-DD］

## 責任與範圍

| 項目 | 內容 |
|---|---|
| 主要 owner | ［owner］ |
| 受影響 owner／審核者 | ［producer、consumer、Bella 整合］ |
| 影響路徑 | ［檔案／目錄］ |
| 影響契約 | ［`docs/contracts/...`／無］ |

## 輸入與期望輸出

- 決策輸入：［現況證據、需求、限制、測試結果］
- 預期輸出：［選定行為、schema、adapter 或運維方式］
- 不變邊界：［owner 核心演算法、正式資料來源、production frontend］

## 背景與問題

- 現況：［可驗證描述］
- 問題：［具體失敗或限制］
- 驅動因素：［相容性、正確性、成本、維運］
- 必守限制：［cm、layout/scene、RAG/Engine、catalog、保存］

## 選項

| 選項 | 作法 | 優點 | 缺點／風險 | Owner 影響 |
|---|---|---|---|---|
| A | ［作法］ | ［優點］ | ［風險］ | ［影響］ |
| B | ［作法］ | ［優點］ | ［風險］ | ［影響］ |

## 決策

- 選擇：［選項］
- 理由與證據：［為何符合現行 RoomPilot］
- 明確不選：［選項與理由］
- 重新評估觸發：［schema、規模、依賴或產品條件］

## 契約與保存影響

- 輸入／輸出 schema：［變更或不變］
- 單位：［cm／`_cm`／`_m2`／不適用］
- 保存／revision／reload：［影響］
- RAG／Engine 邊界：［影響或不適用］
- PostgreSQL／JSON／quarantine：［影響或不適用］
- API／production frontend：［影響或不適用］

## 執行與驗證

1. ［producer 變更］
2. ［consumer adapter 變更］
3. ［保存／UI 變更］

- Producer 測試：［命令］
- Consumer 測試：［命令］
- 回歸／手動驗收：［命令或流程］

