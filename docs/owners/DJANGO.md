# Django：空間關係與格局評估架構

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

### 已定案的持久化策略

`layout_json` 是唯一的原始格局來源；使用者在第 4 步確認後，Django 將衍生關係寫入 PostgreSQL 的 versioned tables。不要把衍生關係只塞回 JSON，也不要建立第二套獨立格局來源。

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

## 驗證

```powershell
python -m pytest -q tests/test_floorplan_room_inference.py
python -m pytest -q tests/test_floorplan_room_icons.py tests/test_floorplan_room_evaluation.py
```
