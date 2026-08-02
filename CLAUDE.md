# RoomPilot 協作指引

修改前先閱讀 `AGENTS.md`。它定義必要的閱讀順序、跨資料夾修改規則與驗證門檻。

接著依序閱讀：

1. `README.md`
2. `docs/TEAM_AI_OWNERSHIP.md`
3. 對應的 `docs/owners/<OWNER>.md`
4. 目標路徑最近的 `AGENTS.md`
5. 相關 `docs/contracts/`

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

第 6 步家具資料以 Kai PostgreSQL view `roompilot.furniture_catalog_current` 優先；只有資料庫暫時不可用才使用已驗證 JSON。家電需求留在問卷與 `scene_json.render_context` 協助第 8 步生圖，不列入 2D/3D 擺設。

責任、遠端分支與整合證據以 `docs/TEAM_AI_OWNERSHIP.md` 為準，不可只依 Git author 推論。
