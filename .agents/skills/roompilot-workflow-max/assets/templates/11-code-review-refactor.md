# 11 程式碼審查與重構：［變更名稱］

## 審查資料

| 項目 | 內容 |
|---|---|
| 主要 owner／審查 owner | ［owner］／［owner、Bella 整合］ |
| 輸入 | ［diff、PRD、ADR、contract、test logs］ |
| 預期輸出 | ［findings、修正、驗證結論］ |
| 影響路徑／保存 | ［路徑］／［保存邊界］ |

## 變更摘要

- 行為改變：［內容］
- 資料契約改變：［內容／無］
- 未改變的 owner 邊界：［內容］
- 已存在的工作樹變更：［需保留的檔案］

## 審查 Gate

### 正確性與契約

- [ ] 輸入、輸出、錯誤、schema version 與單位一致。
- [ ] `layout_json`／`scene_json` 邊界沒有混用。
- [ ] RAG 不裁決幾何，Engine 不被 UI/Agent fallback 取代。
- [ ] PostgreSQL active、inactive、quarantine、家電界線正確。
- [ ] 保存、revision、reload 與舊資料相容已驗證。

### Owner 與結構

- [ ] 核心邏輯位於正確 owner 目錄。
- [ ] 跨資料夾原因與 producer/consumer tests 已記錄。
- [ ] 未建立第二套 FastAPI、catalog、layout、scene 或 production frontend。
- [ ] `scripts/` 未混入歷史、備份或帶版本尾碼實作。

### 安全與品質

- [ ] 無 secret、`.env`、cert、runtime、cache、模型權重或大型資產。
- [ ] 錯誤不洩露 `raw_data`、credential 或內部路徑。
- [ ] 變更最小、命名一致、邊界條件與失敗路徑有測試。

## Findings

| 嚴重度 | 檔案／位置 | 證據 | 風險 | 最小修正 |
|---|---|---|---|---|
| ［P0–P3］ | ［位置］ | ［可重現證據］ | ［影響］ | ［建議］ |

## 重構計畫

| 步驟 | 行為保持證據 | 修改範圍 | 驗證 |
|---|---|---|---|
| ［步驟］ | ［既有／新增測試］ | ［檔案］ | ［命令］ |

## 驗證結論

- Owner tests：［命令與結果］
- Producer／consumer tests：［命令與結果］
- API／browser／SQL：［命令與結果］
- `git diff --check`：［結果］
- 未驗證項目：［原因］

