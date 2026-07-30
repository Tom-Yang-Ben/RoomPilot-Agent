# Engine 工作筆記（非正式 SSOT）

這裡放 Ancai 討論／實驗筆記，**不是**正式契約。

| 正式文件（請以此為準） | 路徑 |
|---|---|
| 引擎使用與驗證順序 | [`../README.md`](../README.md) |
| 房型策略表（人讀規格） | [`../room_strategy/README.md`](../room_strategy/README.md) |
| Agent 機器可讀規則 | [`../../agent/knowledge.py`](../../agent/knowledge.py) |

## 本目錄檔案

| 檔案 | 說明 | 可否當正式規格 |
|---|---|---|
| `engine淨空定義_2026-07-29.md` | 淨空欄位與類型對照討論稿 | 否；已落地部分見引擎碼與 `../README.md` |
| `engine規則討論紀錄_2026-07-29.md` | 進度總帳與交接討論 | 否；完成狀態以 git／測試為準 |

## 維護規則

1. 拍板結果要寫進 `room_strategy/README.md` 或引擎 README，不要只留在筆記。
2. 筆記可保留歷史討論，但標題須標「非正式」。
3. 預設**不強制 commit**；若提交，勿覆蓋正式 README 的結論。
