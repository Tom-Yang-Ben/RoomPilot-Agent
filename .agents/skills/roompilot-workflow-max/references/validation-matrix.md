# 驗證矩陣

先以最近 `AGENTS.md`、owner profile、目標程式與現行測試檔為準。命令或檔案不存在
時要回報文件漂移，不得假裝執行成功。

| 變更類型 | 最低驗證候選 |
|---|---|
| Cody floorplan | `tests/test_floorplan_vision.py`、`test_floorplan_vision_api.py`、`test_floorplan_room_evaluation.py`、`test_cody_semantic_status.py`；必要時小型 `testdata/` fixture |
| Django spatial/evaluation | `test_floorplan_room_inference.py`、`test_floorplan_room_icons.py`、`test_floorplan_room_evaluation.py`；schema 變更另加 Cody producer 與 Ancai/Bella consumer |
| Yen agent | `test_agent_select.py`、`test_agent_place.py`、`test_scene_room_requirements.py`、`test_scene_furniture_retrieval.py` |
| Ancai engine | `test_placement.py`、`test_clearance.py`、`test_scene_visual_regressions.py` |
| Kai catalog/SQL | 目標 importer `--help`/`--dry-run`、`test_official_cloud_catalog.py`、`test_official_catalog_sql.py`、`test_image_manifest_contract.py`、`test_postgres_catalog_contract.py`；可用時檢查 live views |
| Embedding/RAG | embedding importer `--require-all --dry-run`、`test_rag_domain.py`、`test_rag_api.py`；核對 active/vector/orphan/stale |
| Bella FastAPI/save/workflow | `test_scene_workflow.py`、`test_project_workflow_api.py`、`test_scene_v2_contract.py` 加受影響 API tests |
| Production static frontend | `node --check` 受影響 JS、契約測試、實際瀏覽器 QA |
| `frontend3d/` 原型 | `npm.cmd ci`、`npm.cmd run build` |
| Upgrade3D | `test_cody4_3d_gate.py` 加 scene/visual consumer tests |
| StylePack | `test_taiwan_style_cards.py`、`test_scene_v2_contract.py`、`test_project_workflow_api.py` |
| Security/env | `test_env_example_contract.py`、secret/auth/raw-data/quarantine 檢查 |
| 文件/skill | UTF-8、相對連結、命令存在、來源 inventory、skill validator、`git diff --check` |
| 跨 owner | Producer 與 consumer 兩側測試；必要時 API/save/browser E2E |

## 測試選擇規則

1. 先跑修改模組的最小 targeted tests。
2. 變更公開 payload 時跑 provider 與 consumer contract/API tests。
3. 變更保存時跑 create/update/reload/revision/legacy data。
4. 變更 frontend 時跑 JS syntax、contract tests 與實際瀏覽器 QA。
5. 變更 SQL/importer 時先 `--help` 與 dry-run，再由具權限環境驗證 live view。
6. 修正失敗後重跑原失敗測試與相鄰回歸，不只跑新增測試。
7. 最後依任務範圍執行全套：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

## 證據格式

每個命令記錄：command、exit code、pass/fail/skip、重要計數、失敗原因、是否為既有
問題。需要外部服務、瀏覽器、PostgreSQL 或 approval 而未執行時，明列為 not verified。
