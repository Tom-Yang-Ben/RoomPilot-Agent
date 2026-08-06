# Django AI 責任與交接說明

文件版本：2026-08-06。Django 擁有辨識後的空間語意、layout evaluation 與家具 RAG 檢索證據；正式程式主要位於 `backend/spatial_data/`。

## AI 快速結論

Django 提供「空間關係與可追溯證據」，不輸出家具合法座標，也不直接管理正式家具、價格、前端或 OpenRouter。遠端 Django-Skill 的三項能力已拆成跨 owner 目標，但並非三項都已接入正式八步 runtime；不可在 `backend/spatial_data/` 再建立一套 FastAPI、報告服務或 catalog。

## 角色與範圍

Django 負責辨識完成後的空間語意：房間尺寸、面積、相鄰關係、門窗與房間關聯、家具符號證據，以及格局評估。正式程式位置為 `backend/spatial_data/`；可重用的視覺推論 helper 可在 `backend/floorplan/vision/`，但須由 Cody 審核。

## 資料流

```text
Cody 輸出 layout_json（牆、房間、門、窗、信心度）
  -> Django 正規化房間、開口與相鄰關係
  -> 面積、動線、採光面、可用牆面、家具可放置區評估
  -> enrichment / layout evaluation report
  -> Ancai 決定幾何合法性；Kai 提供可推薦 catalog；Bella 儲存並呈現
```

## 遠端 Django-Skill 三項能力的現行落點

| 遠端能力 | 現行實作責任 | Django 提供內容 |
|---|---|---|
| 問卷以專業室內設計語言整理後送入 RAG | **待整合**：Yen `RequirementSkill` + Bella Step 5 adapter；家具 RAG jobs 本身已接線 | 房間類型、空間限制、關係 evidence、家具 RAG query／rerank 證據 |
| 最終資安工程審核 | **部分實作**：Bella `/design-delivery` 目前只做敏感欄位名稱 denylist 移除 | 只提供可公開的空間 evaluation；不得輸出 token、連線字串或原始個資。完整 schema allowlist、權限與稽核仍待補 |
| 工程報告與預算報告 | **部分實作**：Bella deterministic builder 已有 Web/JSON；Yen `ReportAgent` 尚未接入 | 牆門窗樑柱數量、房間與限制摘要、layout evaluation reason code |

上述三項是跨 owner pipeline，不是 Django 單一模組包辦。AI 修改時必須在資料生產者處改資料，在 Bella adapter 處改交付，不得因 skill、class 或單元測試存在就把「待整合」改成「已完成」。

## 八步流程中的位置

- 第 4 步：在 Cody 草稿與使用者校正之間提供房間、開口、相鄰與信心度 evidence。
- 第 5 步：提供可供問卷與 RAG 使用的空間類型、用途限制與關係證據。
- 第 6 步：提供 layout evaluation；實際家具合法性仍由 Ancai 決定。
- 第 7 步：全室視角可讀取房間 polygon、門窗與主要家具關係；camera 必須綁定 `room_id` 且位於該房，不能因此修改或平移結構。
- 第 8 步：只把可公開空間摘要送入 prompt 與成果包；生圖、修圖、資安組稿由 Yen／Bella 負責。

## Django 必須提供的關係

- `room_id`、面積（m2）、尺寸（cm）、房間類型與信心度。
- `host_wall_id`、門窗類型、中心點、寬度、門鉸鏈與開啟方向證據。
- 窗戶淨空區、門扇掃掠區、可貼牆區、主要動線區。
- 家具候選的可放置／不可放置理由，例如超出房間、遮擋窗戶、侵入門扇、動線不足或朝向不合理。

這些是「觀測或推論結果」，不是家具資料。家具 ID、GLB URL、圖片、授權與尺寸主檔永遠以 Kai catalog 為準。

## 天花板與 HVAC 的邊界

Django 僅提供天花板／冷氣所需的空間條件：房高、樑柱、房間 polygon、可用天花區域與衝突。Django 不管理天花板材質、燈具 GLB 或冷氣資產。

全屋天花板、照明與冷氣預設由 Bella 建立；Django 只在個別房間因房高、樑柱、門窗或可用區域產生衝突時，回傳可覆寫的限制與原因。

- 天花板結構與材質選擇由 Bella 的 `scene_json.surface_overrides` 保存。
- 燈具資料由 Kai 的 `lighting_fixture` catalog 提供。
- 冷氣第一階段是 `wall-split`、`ceiling-cassette`、`ducted` 的定位 placeholder；Django 僅回報是否與樑、樑下高度、窗或門衝突。

## 新增空間資料到資料庫：Django 作業手冊

Django 新增的是「可追溯的空間關係與評估結果」，不是 Kai 的家具 catalog。資料寫入前必須先把 producer 與 consumer schema 寫入契約，並保留來源 `layout_json` 版本與信心度。

### 目標持久化策略（非現行可直接執行的 migration）

`layout_json` 是唯一的原始格局來源。下列表格是團隊已定義的目標 schema；現行 repository 尚未提供完整 migration／重建工具，因此 AI 不得把這段文件當成已可直接執行的部署 runbook。實作前需與 Bella、Kai 更新契約與 migration。

- `layout_versions`：每次辨識或人工確認後新增版本，連回原始 `layout_json`。
- `spatial_rooms`：房間尺寸、面積、類型、信心度與 room polygon。
- `spatial_openings`：門窗類型、`host_wall_id`、鉸鏈、寬度與信心度。
- `spatial_clearance_zones`：門扇掃掠、窗前淨空、主要動線、可貼牆區與樑柱限制。
- `layout_evaluations`：家具放置、門窗與天花板/HVAC 的 reason code 與評估結果。

第 6 步直接查這些衍生表；Graph RAG 之後也讀相同關係，不另行搬遷或重算資料。

使用者於第 4 步確認新版本後，舊版第 6 步的 `scene_json` 與家具配置必須保留為可回復方案。新版本只重新驗證舊家具：合法者沿用座標；不合法者保留候選與原因，交由第 6 步提供移動、替換或移除選項。

1. 由 Cody 的 `layout_json` 讀取房間、牆、門窗與辨識信心度，不以畫面座標或手動名稱當主鍵。
2. 以 `project_id`、`layout_version`、`room_id`、`opening_id` 建立可回溯的關係資料。
3. 寫入房間尺寸、相鄰關係、`host_wall_id`、門窗淨空、窗戶淨空、樑柱與可用天花區域。
4. 對每一筆推論保留 `confidence`、`evidence_source`、`schema_version`；低信心資料須標記待第 4 步人工校正。
5. 透過 layout evaluation report 提供 Ancai 的 reason code 與 Bella 的 UI 提示，不直接修改家具座標。
6. 若需要新的 catalog 欄位，只在契約中提出需求並交由 Kai migration；Django 不可直接 UPSERT `furniture_catalog_current`。

建議空間關係的最小資料形狀：

```json
{
  "project_id": "...",
  "layout_version": 1,
  "room_id": "room-1",
  "opening_id": "door-1",
  "host_wall_id": "wall-3",
  "opening_type": "swing_door|sliding_door|window|floor_to_ceiling_window",
  "clearance_zones_cm": [],
  "confidence": 0.94,
  "evidence_source": "cody_adapter",
  "schema_version": "1.0"
}
```

資料表名稱、migration 與部署方式應與 Kai、Bella 共同確認；不可在 `backend/spatial_data/` 私自建立第二套 catalog 或繞過 `layout_versions`。

## Graph RAG 邊界

Graph RAG 只能檢索 Django 產生的房間、家具、材質與限制關係；它不能取代 Ancai 的碰撞檢查，也不能決定門洞、牆或家具的實際幾何座標。

## 跨資料夾改動規則

- 變更 `layout_json`：先與 Cody 更新 `LAYOUT_SCENE_BOUNDARY_CONTRACT.md`，並由 Bella 做 API 相容測試。
- 新增家具可放置規則：與 Ancai 共同定義評估 reason code，不可在 Django 自行改寫第 6 步擺放器。
- 需要 catalog 欄位時：寫入本文件與 `LIGHTING_CEILING_CATALOG_CONTRACT.md` 的需求，不直接修改 Kai 的 JSON／SQL。
- 任何門窗 host wall、窗戶淨空或房間 polygon 改動，需同時有 Cody producer 測試與 Bella/Ancai consumer 測試。

## 禁止事項

- 不在 RAG 中決定或改寫家具座標、碰撞結果與結構合法性。
- 不直接 UPSERT Kai 正式 catalog、價格、資產 URL 或 embedding。
- 不把 target PostgreSQL schema 說成目前已能從本 repository 一鍵部署。
- 不在 Django 模組持有 OpenRouter token、使用者 cookie 或成果包個資。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_room_inference.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_room_icons.py tests/test_floorplan_room_evaluation.py tests/test_rag_domain.py tests/test_rag_api.py
```
