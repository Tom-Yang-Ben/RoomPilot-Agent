# 組員分支合併指南

## 原則

不要把照片結構的分支直接執行一般 `git merge` 到 Bella。舊分支可能包含
`backend/`、`frontend/`、`data/` 的整份複本，會製造重複模組與單位衝突。

每位成員先提供：

- 分支名稱與起始 commit。
- 功能入口及輸出格式。
- 只屬於自己的檔案清單。
- 測試指令與測試資料。

## 建立整合分支

```powershell
git fetch origin
git switch bella
git switch -c integration/<name>-into-bella
git diff --name-status bella...origin/<member-branch>
```

先看差異，不要立刻合併。依 `TEAM_FOLDER_OWNERSHIP.md` 把實作移到指定落點，
並調整 import：

```text
backend.engine      -> roompilot.engine
backend.agent       -> roompilot.agent
backend.catalog     -> roompilot.catalog
backend.floorplan   -> roompilot.floorplan
backend.upgrade3d   -> roompilot.upgrade3d
backend.server      -> roompilot.server
```

## 各分支移植方式

### Cody

只移植辨識演算法與必要測試。輸出要轉成 Bella 現有 floorplan JSON，不要帶入
另一套 FastAPI 或前端。

### Kai

只移植 catalog pipeline、Manifest 與雲端模型解析。未安全對應資料放入
`roompilot/catalog/data/quarantine/`，不能直接進網站型錄。

### Django

不要整包搬入 `Final-Project_Version3`。將房間面積、比例與尺寸標註邏輯移到
`roompilot/spatial_data/`，由 Bella 在 Step 4 呼叫。

### Yen

選件規則放 `roompilot/agent/`。Agent 可以選家具與提出修復策略，不可產生家具
座標。

### AN

擺放、碰撞與淨空放 `roompilot/engine/`。輸入輸出維持公尺，並保留
`check_placement_with_clearance` 的合法性檢查。

### Bella

頁面、FastAPI routes 與專案流程留在 `roompilot/server/`；R3F 編輯器留在
`frontend3d/`。Bella 只負責呼叫其他模組，不複製其演算法。

## 合併前檢查

```powershell
uv run pytest tests/ -q
git diff --check
git status --short
```

確認沒有新增第二套 `backend/`、沒有把大模型加入 Git、沒有修改其他成員目錄，
再提交整合分支並合回 Bella。
