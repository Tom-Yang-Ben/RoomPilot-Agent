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

- [x] 第 0 步:契約文件入庫(本 commit)
- [ ] 第 1 步:生圖交付檔 `build_agent_generation_handoff()`(自 `13a8e193` 移植)
- [ ] 第 2 步:`furniture_id` / `catalog_furniture_id` 拆分
- [ ] 第 3 步:RAG 工作契約(`questionnaire_version`+雜湊去重、五終態、輪詢收斂、撤回自動套用)
- [ ] 第 4 步:第 5 步問卷 UI 一包(`fd0cee11` 起五連)+方案 A/B 卡與逐房 3D 預覽+家具編號開關+wizard 契約測試

移植機制:全程人工移植、按 bella-test1 時間序,不 cherry-pick(`backend/server/static/` → `frontend/` 搬家,路徑必撞)。
