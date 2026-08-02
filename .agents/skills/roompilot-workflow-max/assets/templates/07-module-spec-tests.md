# 07 模組規格與測試：［模組／函式］

## 基本資料

| 項目 | 內容 |
|---|---|
| 主要 owner | ［owner］ |
| 協作 owner | ［owner／無］ |
| 程式路徑 | ［repo 相對路徑］ |
| 對應 BDD／API／契約 | ［連結］ |

## 輸入與輸出

| 類型 | 名稱／型別 | Producer／Consumer | 單位／schema |
|---|---|---|---|
| 輸入 | ［值］ | ［owner］ | ［cm／m2／version］ |
| 輸出 | ［值／error］ | ［owner］ | ［cm／m2／version］ |

## 契約式設計

| 類型 | 可測條件 |
|---|---|
| 前置條件 | ［輸入已確認、版本、必填欄位］ |
| 後置條件 | ［輸出、reason code、無副作用］ |
| 不變量 | ［owner 專屬規則］ |
| 失敗保證 | ［不保存半成品、不覆寫既有 revision］ |

## Owner 邊界

- Cody：保留原始辨識證據與 confidence，輸出 cm-normalized `layout_json`。
- Django：提供空間關係、evaluation 與 RAG 證據，不直接改家具座標。
- Kai：維護 catalog identity、資產 URL、active/quarantine 與 PostgreSQL/embedding。
- Yen：輸出結構化需求、選件與修復意圖，不產生合法座標。
- Ancai：以 deterministic 規則判定 placement、collision、clearance、legality。
- Bella：提供 adapter、保存與 UI，不複製上述核心演算法。

刪除不適用項，並把適用 owner 規則改寫為可執行 invariant。

## 保存與副作用

- 讀取：［repository／檔案／無］
- 寫入：［table/project state／無］
- transaction／revision：［行為］
- reload／相容性：［行為］
- 外部依賴與失敗：［明確錯誤；不得靜默替代］

## 測試案例

| ID | 類型 | Arrange | Act | Assert |
|---|---|---|---|---|
| TC-001 | 正常 | ［狀態］ | ［呼叫］ | ［輸出與保存］ |
| TC-002 | 邊界 | ［極值／空值］ | ［呼叫］ | ［結果］ |
| TC-003 | 無效 | ［錯誤 schema／單位］ | ［呼叫］ | ［error／無寫入］ |
| TC-004 | 領域規則 | ［碰撞／inactive／低 confidence 等］ | ［呼叫］ | ［reason code］ |
| TC-005 | reload | ［舊版本］ | ［重新載入］ | ［相容結果］ |

## 驗證命令

- 單元：［` .\.venv\Scripts\python.exe -m pytest -q tests/... `］
- Producer／consumer：［命令］
- API／UI：［命令或手動步驟］

