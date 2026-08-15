# Bella AI 責任說明

## 任務

把團隊模組整合成唯一、可恢復的八步產品，不能複製其他 owner 的核心演算法。Bella 維護 `backend/server/`、正式靜態前端、專案保存、API 邊界與發布驗證。

## 整合流程

```text
各 owner 模組 -> FastAPI adapter -> project/workflow state
               -> 正式 HTML/CSS/JS/Three.js
               -> 保存 layout_json / requirements_json / scene_json
```

`backend/server/static/` 是唯一正式 frontend；公開 repository 不包含第二套 React/R3F 原型。

第 6 步使用 Kai PostgreSQL catalog 優先。第 5 步家電需求必須保存給 AI 生圖，但不得變成 2D/3D 自動擺設。第 6 步位置、碰撞與淨空仍由 Ancai 引擎決定。

## 修改前

1. 閱讀所有受影響 payload 的 `docs/contracts/`。
2. 找出領域 owner，保持其演算法在原目錄。
3. 檢查專案恢復、舊資料相容與前端 cache key。
4. 規劃 API/契約測試與實際瀏覽器驗證。

## 跨目錄規則

- 平面圖行為需要 Cody/Django review。
- catalog/SQL 行為需要 Kai review。
- 選件說明需要 Yen review。
- 配置合法性需要 Ancai review。
- 不得整包 merge 成員分支，也不得新增第二套 production app。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
```
