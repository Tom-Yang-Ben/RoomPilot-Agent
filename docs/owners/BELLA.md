# Bella AI 責任與交接說明

文件版本：2026-08-06。Bella 是正式產品整合 owner，維護唯一的 FastAPI／HTML／CSS／JavaScript／Three.js 八步流程。

## AI 快速結論

正式入口只有 `/scene`，正式前端只有 `backend/server/static/`。`frontend3d/`、各成員 demo 與遠端分支只能作能力來源，不能成為第二套 production app。

## 主要責任

- 維護 `backend/server/`、`backend/server/static/`、專案保存、API adapter、舊資料相容與發布驗證。
- 把 Cody、Django、Kai、Yen、Ancai 的公開契約接進同一份 workflow；不複製其他 owner 的核心演算法。
- 確保直接開啟或重新整理任一步驟都能恢復，包括第 7 步 Yen 視角與第 8 步成果包。
- 前端修改後同步更新靜態資源 SHA-256 cache key，並做桌面與手機瀏覽器 QA。

## 現行第 6 至 8 步

```text
第 6 步：單一配置與逐房牆面／地面預覽，保存 configuration_snapshot
  -> 第 7 步：每房三個綁定 room_id 的全室視角候選，逐房鎖定，再確認代表房全屋色卡
  -> 第 8 步：問卷／RAG 大致詞彙確認，全屋初稿完成後，每張房間圖最多一次修圖
  -> design-delivery：逐房簡報、工程報告、資安基線、家具與裝潢預算
```

- 第 6 步不得再顯示 A/B；舊 `designSchemes` 僅供歷史資料讀取。
- 第 6 步 surface override 以 `room_id` 保存；房間、地面與家具保留平面圖全域座標，不得在切換房間時重新置中。
- 第 6 步家具替換結果必須顯示 Kai catalog 的實物照片；圖片失效時顯示清楚空狀態，不能留下看似還在載入的空白區。
- 公開步驟是八步；內部 `proposal_review`、`ai_render` 是保存 key，不是額外步驟。
- 第 7 步視角由鎖定的第 6 步場景產生，不消耗 AI 生圖額度；相機必須位於對應房間並呈現全室。
- 第 8 步只透過後端呼叫 Yen／OpenRouter，瀏覽器不得取得 token。

## Agent 實際接線

| 元件 | 狀態 | Bella adapter |
|---|---|---|
| 家具 RAG jobs | 已實作 | Step 5 前端呼叫 `/api/rag/search/jobs` |
| Yen `GenPicAgent` | 已實作 | `backend/server/ai_render_service.py` 直接呼叫 |
| Yen `RequirementSkill`／`MasterAgent` | 待整合 | `backend/server/` 目前沒有呼叫 `build_master()` 或 `RequirementSkill` |
| Yen `ReportAgent` | 待整合 | `/design-delivery` 目前沒有呼叫 Report Agent |
| 成果包 | 已實作 | Bella deterministic builder 回傳 Web/JSON |

## 現行第 8 步 API

| API | 用途 |
|---|---|
| `GET /api/ai-render/status` | 回報 provider、主模型與 fallback；不回傳金鑰 |
| `POST /api/projects/{project_id}/ai-renders` | 逐房首次生圖 |
| `POST /api/projects/{project_id}/ai-renders/{room_id}/edit` | 每房唯一一次修圖，額度由後端保存狀態強制 |
| `POST /api/projects/{project_id}/design-delivery` | 建立逐房 Web 簡報、工程、資安與預算成果包 |

舊 `/render-jobs` 僅供相容舊資料與舊 provider，不是現行第 8 步主要路徑。

現行 `/ai-renders`／`/edit` 只有在 `OPENROUTER_API_KEY` 非空時啟用；legacy
`/render-jobs` 則以 `ROOMPILOT_RENDER_PROVIDER_URL` 非空為啟用條件，兩者互不替代。
現行主程式沒有 `/api/health`。

## 成果包真實性與資安

- 設計師觀點只能寫「方法論參照」，並明示不代表設計師參與或背書。
- 目標契約要求家具同時有 `price_twd`／`price_source` 才可列參考價；現行 builder 只檢查正數價格，尚未強制來源，正式報價前必須補強。缺價家具與裝潢工程一律「待報價」。
- 後端目前依固定敏感欄位名稱 denylist 遞迴移除 token、cookie、password、secret 等資料；不得稱為完整欄位 whitelist 或最終專業資安審查。
- Web 成果包與 JSON 已完成；PDF／PPTX 不是目前必要 runtime 交付。

## 跨 owner 邊界

- 平面圖與 `layout_json`：Cody／Django。
- catalog、價格與資產：Kai。
- 問卷專業化、RAG 意圖、生圖／修圖語意：Yen。
- 家具座標、碰撞與淨空：Ancai。
- API、保存、UI、資安組稿與端到端驗證：Bella。

## 最低驗證

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check backend/server/static/scene_v2.js
$env:ROOMPILOT_RUNTIME_DIR = (Join-Path (Get-Location) '.runtime-test-integration')
.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_v2_contract.py tests/test_scene_6_8_wizard_contract.py tests/test_ai_render_openrouter.py tests/test_remote_render_workflow.py tests/test_scene_delivery.py tests/test_scene_pricing.py
git diff --check
```
