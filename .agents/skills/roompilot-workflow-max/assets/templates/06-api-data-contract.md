# 06 API 與資料契約：［端點／資料名稱］

## 契約識別

| 項目 | 內容 |
|---|---|
| Domain producer owner | ［owner］ |
| FastAPI／保存 owner | Bella |
| Consumer owner | ［owner／production frontend］ |
| 路徑與方法 | ［現有 route；不要自行預設 `/v1`］ |
| Schema version | ［版本］ |
| 正式契約 | ［`docs/contracts/...`］ |

## 輸入

| 欄位 | 型別 | 必填 | 單位／語意 | 驗證與來源 |
|---|---|---|---|---|
| ［欄位］ | ［型別］ | ［是／否］ | ［`_cm`／`_m2`／enum］ | ［規則／producer］ |

## 輸出

| 欄位 | 型別 | 單位／版本 | Consumer 用途 | 可為空條件 |
|---|---|---|---|---|
| ［欄位］ | ［型別］ | ［單位／schema］ | ［用途］ | ［條件］ |

若沿用 `width`、`depth`、`pos_x`、`pos_y`，必須同時輸出 `coordinate_unit: "cm"` 與 schema version。

## 行為與錯誤

| 條件 | HTTP／reason code | 可重試 | 保存是否改變 | UI 行為 |
|---|---|---|---|---|
| 無效輸入 | 400／［code］ | 否 | 否 | ［提示］ |
| 資源不存在 | 404／［code］ | 否 | 否 | ［提示］ |
| revision 衝突 | 409／［code］ | 重新載入後 | 否 | ［提示］ |
| 正式 PostgreSQL 不可用 | 503／［code］ | 是 | 否 | 不得靜默 JSON fallback |

## 領域與資料來源 Gate

- [ ] `layout_json`／`scene_json` 名稱、生命週期與 consumer 沒有混用。
- [ ] RAG 回應是候選與證據；Engine 結果才可聲明幾何合法。
- [ ] Catalog API 只公開 active 正式家具；inactive、quarantine、未匹配與家電被排除。
- [ ] 管理刪除採 `is_active=false`；不提供破壞性 hard delete。
- [ ] 認證沿用現行端點需求；只有管理 API 需要時才使用既有 Bearer 邊界，不虛構 OAuth。

## 保存與相容性

- 持久化位置／transaction：［PostgreSQL table/view、project JSONB、無］
- revision／audit：［欄位與衝突行為］
- backward／forward compatibility：［規則］
- cache／hot refresh：［現行行為，不新增隱藏 process cache］

## 驗證

| 類型 | Producer／Consumer | 測試檔／命令 | 驗證重點 |
|---|---|---|---|
| Schema | ［owner］ | ［命令］ | 型別、版本、單位 |
| API | Bella | ［命令］ | status、error、auth |
| 保存／reload | Bella | ［命令］ | revision、相容性 |
| UI | Bella | ［命令／手動步驟］ | 空、錯誤、成功狀態 |

