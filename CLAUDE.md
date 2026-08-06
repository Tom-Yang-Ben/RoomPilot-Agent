# RoomPilot 協作指引

修改前先閱讀 `AGENTS.md`。它定義必要的閱讀順序、跨資料夾修改規則與驗證門檻。

接著依序閱讀：

1. `README.md`
2. `docs/RoomPilot_現行版本總覽.md`
3. `docs/使用者流程與系統架構圖.md`
4. `docs/TEAM_AI_OWNERSHIP.md`
5. 對應的 `docs/owners/<OWNER>.md`
6. 目標路徑最近的 `AGENTS.md`
7. 相關 `docs/contracts/`

## 修改前

說明目標 owner、修改檔案、輸入/輸出契約與測試。跨多個 owner 目錄時，使用 `AGENTS.md` 的跨資料夾修改格式。

禁止：

- 未檢視差異就整包合併成員分支。
- 新建第二套 FastAPI 或正式前端。
- 將幾何決策移到 Graph RAG、瀏覽器或 LLM。
- 未更新兩端測試就改動公分制 payload。
- 將 quarantine 資料視為正式家具。
- 覆蓋他人未提交的本機變更。

## 目前產品邊界

正式產品是 `backend/server/` 與 `backend/server/static/` 的八步 FastAPI/Three.js 工作流：辨識止於 `layout_json`，方案與編輯使用 `scene_json`，家具合法性由 `backend/engine/` 計算。

第 6 步只交付單一 `configuration_snapshot`，不公開 A／B 方案；牆面與地面材質以
`room_id` 逐房保存，房間與地面沿用確認版平面圖座標，不可為預覽重新置中。家具資料預設讀
Kai PostgreSQL view `roompilot.furniture_catalog_current`；strict postgres 不可用時回傳
503，只有明確指定 JSON 離線模式才可讀已驗證備援。家電需求留在問卷與
`scene_json.render_context` 協助第 8 步生圖，不列入 2D/3D 擺設。

第 7 步使用逐房三視角候選；每個相機必須綁定正確 `room_id`、位於該房並能呈現全室。
第 8 步先確認依問卷與 RAG 組成的大致生圖詞彙，再完成全屋初稿，之後每個房間的
初稿圖片只允許一次成功修圖。全部確認後由 Bella
`/design-delivery` 輸出逐房簡報、工程報告、資安審核與家具／裝潢預算；缺價必須
標記「待報價」，設計師名稱只能是方法論參照且不得暗示本人背書。

接線狀態必須如實描述：正式 Step 5 已呼叫家具 RAG jobs，Step 8 已透過
`ai_render_service.py` 使用 Yen `GenPicAgent`；但 `RequirementSkill`、`MasterAgent`、
`ReportAgent` 尚未由正式 FastAPI 八步流程呼叫。`/design-delivery` 目前是 Bella 的
deterministic Web/JSON 組稿；資安基線是敏感欄位名稱 denylist 移除，不是完整欄位
whitelist，也不能等同最終專業資安審查。

目前主程式實際使用 SQLite `ProjectStore`。`.env.example` 的 PostgreSQL project-store
設定是尚未接線的遷移目標；legacy `/render-jobs` 也不是現行第 8 步主要入口。

`frontend3d/` 是次要原型。責任、遠端分支與整合證據以 `docs/TEAM_AI_OWNERSHIP.md` 為準，不可只依 Git author 推論。
