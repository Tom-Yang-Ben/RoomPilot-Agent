# BEN 第 5/6 步規格整合 log(ben-local,2026-08-03)

`docs/BEN_第5第6步整合規格_中文.md` 與四份問卷契約自 `origin/bella-test1`(`23de9dda`)原文搬入,契約 owner 為 Bella,本檔只記 ben-local 落地時的落差與決策,不改契約原文。

## 搬入時已滿足的條文(無需實作)

- 鎖定兩類 `position_locked` / `appearance_locked`(`main.py`、`scene_api.py`、`scene_service.py`、`scene_v2.js`)。
- `room_fit_checked` 可行性旗標與提示文案(`frontend/scene_furniture_offers.js:828,937`)。
- 結構風險提示——拆牆/打通關鍵字攔截(`frontend/scene_v2.js`)。
- 廚浴陽台家電走 `questionnaire.appliance_requirements` 與 `scene_json.render_context`,不進 2D/3D 配置。
- `room_type` CamelCase 詞彙:cody-dev 合入(`a0c46975`)後辨識端已輸出十類 CamelCase,與本規格一致。

## 落地決策

1. **id 拆分(規格「3D 預覽資料要求」)**:採規格 schema——`furniture_id` 為配置實例 id、`catalog_furniture_id` 為型錄 id。Ancai 分支 `e4199f3f` 亦收斂到 `catalog_furniture_id`,日後合流沿用同名。
2. **房型詞彙正規化點**:問卷 payload 依規格攜帶 CamelCase `room_type`;伺服器 API 邊界統一經 `CODY_ROOM_TYPE_MAP` 正規化為既有小寫契約鍵,內部程式不直接比對 CamelCase。
3. **12 空間房型鍵**(`FURNITURE_ENGINE_12_SPACE_KINDS.md` vs 本機 `SPACE_DEFAULTS` 的 `workspace`/`dining_room`/`studio`):契約先入庫供參,鍵值對齊**暫緩**,與 Ancai `0ba0aee2`(SPACE_DEFAULTS 臥室補衣櫃)在同一次三方(Ben×Bella×Ancai)決策處理。
4. **方案 B 生成來源**:規格未定義。第 4 步先落 UI 與 payload 契約,方案 B 缺席時走規格明定的「顯示原因、預設 A」;生成器待 Ancai `layout_strategy` 合入後再接。

## 實作進度

- [x] 第 0 步:契約文件入庫(`ad136bff`)
- [x] 第 1 步:生圖交付檔 `build_agent_generation_handoff()`(`1404cefe`,自 `13a8e193` 移植;`1a87b56f` 補讀 `test2_questionnaire` 巢狀來源)
- [x] 第 2 步:`furniture_id` / `catalog_furniture_id` 拆分(`70d2b85f`)
- [x] 第 3 步:RAG 工作契約(`1a87b56f`——問卷版本進指紋、逐房終態 completed/unavailable、`rag_jobs` 隨問卷入 scene_json、過期自動套用撤回)
- [x] 第 4 步:第 5 步問卷 UI 一包(`fd0cee11`→`25b83f95`)+方案 A/B 卡與逐房 3D 預覽+家具編號開關(`23de9dda` UI 部分)+wizard 契約測試

移植機制:全程人工移植、按 bella-test1 時間序,不 cherry-pick(`backend/server/static/` → `frontend/` 搬家,路徑必撞)。

## 第 4 步落地註記(2026-08-04)

- 驗收清單第 4、5、6 條完整可用:逐房方案 A/B 卡(2D SVG+可旋轉 3D 預覽)、A/B 同結構(兩方案共用方案 A baseScene 裁切)、家具編號僅第 6 步(`showFurnitureNumberMarkers` 預設關,第 7 步無編號)。
- **已知落差**:材質配對卡、牆/地生圖偏好欄與型錄空間分組掛在 legacy 逐房問卷路徑,而目前第 5 步可見 UI 是初回面談(first-meeting),legacy 區塊 `hidden`——契約與程式就緒,但使用者暫看不到;待初回面談延伸到逐房階段或恢復 legacy 問卷時啟用。
- 材質配對推薦改用本機 `STYLE_MATERIAL_OPTIONS` 精選集計分(bella 依賴的 `/api/scene/bootstrap` surface catalog 本機沒有)。
- 方案 B 由 `ensureSchemeB` 自動 relayout 產生;失敗標 stale、預設選 A,不卡流程。`confirmWhiteModel` 現在要求逐房選擇完成,實走動線多一步「完成選擇並開始微調」。
- 天花照片流程(`593047c0`/`fb008d31`)與 009b7020 的任務彈窗/catalog readiness 不在本輪範圍;72.9MB 風格卡/天花參考圖未搬。
