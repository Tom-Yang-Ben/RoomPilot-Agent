# 需求決策紀錄 (Requirement Decision Record) - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 01_requirements/requirement_decision_record.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v1.0 | **更新:** 2026-08-04 | **狀態:** 草稿（回溯導入，待 owner 逐列補簽）

這份文件是**需求決策的權威來源**，由產品 owner 填寫，AI 不得代為拍板。它是 `/intake → /specify` 之間那條硬邊界的檢查對象：**在此表把需求決策標為「已核准」並簽名之前，`/specify` 不得把該項需求工程化。**

導入註記（RoomPilot 現況）：

- 本 repo 於 2026-08-04 工作樹中，`.claude/skills/` 下確有 `intake`、`specify`、`deliver`、`verify` 四支流程 skill，但**皆為未追蹤檔案**（`git ls-files .claude/skills/` 只列出 roompilot-budget／furniture-query／proposal／security 四支共 14 個檔案）；`/specify` 硬閘目前**未被任何 CI 或 hook 強制**。實際發揮硬閘作用的是根目錄 `AGENTS.md` 的「動手前必做 6 步」與 11 條不可違反契約（AGENTS.md:5-12、:50-60）。
- 本文件為**回溯導入**：下列 DEC 均為已實作、已進 commit 的既成決策，依程式碼、`docs/contracts/` 與 commit 紀錄整理；正式簽核紀錄 repo 內查無，「決策者」依 `docs/TEAM_AI_OWNERSHIP.md` 的目錄責任表回推（該檔 :3 明示 Git author 不能單獨視為 owner），待各 owner 補認。
- 模板原文對照的 `docs/document-system/architecture.md`（Excel B 區）在本 repo 不存在：**(未查證：來源不在 repo)**。語域規則檔 `.claude/rules/language-register.md` 與 `.claude/rules/thinking-boundary.md` 存在於工作樹（未進版控，`.gitignore` 的 `.claude/*` 僅豁免 `skills/`）。

---

## 1. 決策邊界：誰決定什麼

| 決策類型 | 誰拍板 | 內容 | 落在哪 |
| :--- | :--- | :--- | :--- |
| **需求決策** | 產品 owner（人；RoomPilot 為 7 人團隊各目錄 owner，見 `docs/TEAM_AI_OWNERSHIP.md:7-15`） | 優先序、範圍納入/排除、里程碑、Gate 核准、業務驗收、商業例外 | 本表 |
| **工程決策** | 工程 + AI 協作 | FR/NFR 措辭、架構、元件映射、API/資料契約、測試設計 | `docs/contracts/`（22 個檔案：17 .md + 1 .yaml + 3 .schema.json + 1 example.json）、`tests/`（99 支 test_*.py）、各目錄 `AGENTS.md` |

鐵律：**需求決策不可由規則或 AI 自動衍生**。若某欄目前是系統自動推斷（例如以關鍵字判優先序），必須由 owner 覆寫或明確接受，才算數。

RoomPilot 的 owner 對照（`docs/TEAM_AI_OWNERSHIP.md:19-34` 目錄責任表）：

| Owner | 需求決策範圍（主責目錄） |
| :--- | :--- |
| Bella | `backend/server/`（八步 FastAPI 工作流、正式 UI）、`docs/contracts/` 整合、工程文件 MVP |
| Cody | `backend/floorplan/`、`backend/upgrade3d/`（辨識與升維） |
| Django | `backend/spatial_data/`（含 rag/ 家具 RAG runtime） |
| Kai | `backend/catalog/`（官方型錄、PostgreSQL 五階段） |
| Yen | `backend/agent/`（選件與擺位紀律） |
| Ancai | `backend/engine/`（幾何合法性唯一裁決者，`docs/TEAM_AI_OWNERSHIP.md:53`） |
| Ben | 辨識 QA／evaluation |

---

## 2. 需求決策主表

每一列是一個需求項的 owner 決策。程式碼、`docs/contracts/` 與 `tests/` 側**無 `FR-*`/`NFR-*` 編號系統**（唯一出現 `FR-*` 的地方是 VibeCoding 導入文件自編的序號：舊版 `docs/vibecoding/05_architecture_and_design_document.md:465` 起 11 處、本 v5 版 `03_architecture/architecture_and_design.md`，兩者都未回寫程式碼或契約，不構成可追溯 ID 系統）；「對應工程ID」欄改以工程側契約檔與守約測試作為追溯橋。

里程碑註記：repo 內查無正式里程碑編號；唯一已知里程碑為成果發表（日期 repo 內無紀錄，(未查證)），下表以 `M-發表` 代稱。

| 決策ID | 需求/VOC（業務語言） | 優先序 | 範圍 | 里程碑 | 業務驗收條件 | 商業例外/限制 | 決策狀態 | 決策者 | 日期 | 對應工程ID（契約/測試） |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| DEC-001 | 屋主上傳平面圖後，在**單一網頁八步流程**內走完「建專案 → 上傳 → 確定尺寸 → 空間結構 → 需求問卷 → 配置預覽 → 方案鎖定 → AI 渲染」，不需要學會多套工具 | P0 | 納入 | M-發表 | `/scene` 頁一次操作可從空專案走到成果包；重新整理後進度可恢復 | 正式產品只有這一套 FastAPI 與前端，不建第二套（專案 CLAUDE.md 禁止事項） | 已核准（回溯） | Bella + 全隊 | 2026-07-24 前後（commit b04833c 整合，(未查證：口頭拍板時間)） | `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md`；scene.html:25-32（8 顆步驟按鈕）、scene_workflow.js:4-16（11 內部步驟）；tests/test_scene_workflow.py |
| DEC-002 | 網站、選件與 3D 只能出現**保證有 3D 模型的官方家具**；正式母集合固定 8,557 件，每件具已驗證 CloudFront GLB，不符即拒絕載入 | P0 | 納入 | M-發表 | 家具頁與 3D 場景不出現缺模型家具；載入期件數不符直接啟動失敗而非靜默缺圖 | 未對應的舊型錄資料只進 quarantine，不得作為正式家具（CLAUDE.md 禁止事項） | 已核准（回溯） | Kai | 2026-07-26 首版（9,350 件，commit 83b3c8a5）；2026-07-30 改 8,557 件（commit f5fc0995「切換 Kai 官方家具資料與交付契約」） | `backend/catalog/cloud_catalog.py:15`（`OFFICIAL_CATALOG_COUNT = 8_557`）；`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`；tests/test_official_cloud_catalog.py、test_cloud_quarantine.py |
| DEC-003 | 家具「放不放得下、合不合法」只由**幾何引擎**判定；LLM 與前端都不能自己算座標或碰撞 | P0 | 納入 | M-發表 | 任何擺放結果都通過引擎的碰撞/淨空/邊界檢查；LLM 只選件不給座標 | 幾何決策不得移到 Graph RAG、瀏覽器或 LLM（CLAUDE.md 禁止事項；`docs/TEAM_AI_OWNERSHIP.md:53`） | 已核准（回溯） | Ancai + 全隊 | 2026-07-23~24（公分制 commit 鏈期間，(未查證：口頭拍板時間)） | `backend/engine/schema.py`（介面 v0.1）；`backend/agent/select.py` docstring（LLM 不輸出座標）；tests/test_placement.py、test_clearance.py、test_agent_place.py |
| DEC-004 | 跨模組幾何資料**一律公分**，新欄位命名 `_cm`、面積 `_m2`，避免單位換算錯誤毀掉擺放結果 | P0 | 納入 | M-發表 | 改動公分制 payload 必須同步更新兩端測試（CLAUDE.md 禁止事項反面） | 內部模組（DXF/視覺管線）可保留公尺，但只允許單點邊界轉換 | 已核准（回溯） | 全隊 | 2026-07-23~24（commits d97f95c→714722f→b04833c） | AGENTS.md:50；`backend/engine/schema.py`（單位契約）；tests/test_dxf_room_units.py |
| DEC-005 | 風格提案固定**六風格 × 3 色卡 = 18 組**台灣生活色卡，讓屋主在有限選項內快速比較 | P1 | 納入 | M-發表 | `/styles` 頁完整呈現 6 風格 18 色卡；3D 場景可切換 | 色碼/材質參數以程式資料為準，不得由 LLM 生成 | 已核准（回溯） | 全隊 | (未查證) | `backend/catalog/data/taiwan_style_cards.json`（實測 styles=6、cards 合計 18）；`docs/contracts/STYLEPACK_RENDERING_CONTRACT.md` |
| DEC-006 | 家具資料庫走 **PostgreSQL 五階段**上線：第 6 步家具資料以 view `roompilot.furniture_catalog_current` 優先，只有資料庫暫時不可用才用已驗證 JSON | P0 | 納入 | M-發表 | 型錄查詢/分頁/facet 由 DB 承擔（`POSTGRESQL_CATALOG_READ_PHASE1.md:54` 定 repository「執行 parameterized SQL，處理 filter/count/facet/pagination」，同檔 :60 定 FastAPI「只接收 HTTP query、呼叫 repository」「不在 FastAPI 內複製 SQL 或 catalog 演算法」）；strict 模式下 DB 失效不得靜默回退掃 JSON | `docs/TEAM_AI_OWNERSHIP.md:57` 註明 JSON 目前仍是第 6 步預設來源、DB 需環境變數啟用——與 CLAUDE.md「PostgreSQL 優先」表述存在張力，待 owner 對齊 | 已核准（回溯） | Kai（Phase 1/2/5）、Bella（Phase 3/4 對接） | Phase 1/2/3/5 契約標頭「更新日期：2026-07-27」；Phase 4 契約標頭無日期欄 (未查證) | `docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md`～`POSTGRESQL_SINGLE_SOURCE_PHASE5.md`（5 份）；`backend/catalog/postgres_repository.py`（891 行）、`postgres_admin_repository.py`、`runtime_catalog_repository.py`；`scripts/sql/`、`scripts/project_store/`、`scripts/runtime_catalog/` |
| DEC-007 | 設計師**鎖定方案後**，系統自動產出工程文件包（估價、排程、施工建議），鎖定前不得產出，避免對未定案方案報價 | P0 | 納入 | M-發表 | snapshot → lock → packages → jobs → documents 五段流程可走通；未鎖定（`approval_status != "designer_confirmed"`）請求產包被拒（409 REVISION_NOT_LOCKED） | 文件下載僅限 `.runtime/engineering` 之下實檔（路徑逃逸防護） | 已核准（回溯） | Bella（協作 Kai/Django/Ancai） | 2026-07-29（契約更新日期） | `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`、`engineering_openapi.yaml`、3 份 .schema.json；`backend/server/engineering/api.py`（8 條 /api/v1 路由；:191 鎖定檢查）；tests/ engineering_* 7 支 |
| DEC-008 | 屋主可用**日常口語**描述想要的家具，由家具 RAG 轉成受控詞彙檢索（六風格、24 氛圍詞、19 家具群組），從官方型錄撈出對的東西 | P1 | 納入 | M-發表 | `/rag` 測試台可示範口語 → 檢索結果；embedding 表無資料或模型快取缺失時就緒檢查要亮 blocker，不得假成功 | RAG 只做檢索與重排，不做幾何、不改擺位 | 已核准（回溯） | Django（協作 Kai、Bella） | 2026-07-29（契約更新日期） | `docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`、`POSTGRESQL_FURNITURE_EMBEDDINGS.md`；`backend/spatial_data/rag/`（11 個 .py 檔 1,234 行，另 `rag/data/` 2 份 JSON）＋ `backend/server/rag_api.py`（共 5 條路由 = `/api/rag/*` 4 條 ＋ `/rag` 測試台頁 1 條）；tests/test_rag_api.py、test_rag_domain.py、test_rag_frontend.py |
| DEC-009 | 寫實 AI 渲染**只走遠端供應商**（render-jobs），本機不做寫實渲染；供應商未設定回 503，不得假成功；送出前剝除姓名、電話、Email 等私人欄位 | P0 | 納入 | M-發表 | 第 8 步送單回 202 並可輪詢；未設供應商時明確報 503 | 個資剝除是紅線（`render_service.py:12-22` PRIVATE_KEYS 為 9 個私人欄位名的**排除名單**，`:51-60` `_strip_private_fields()` 遞迴剝除） | 已核准（回溯） | Bella | (未查證) | `docs/contracts/REMOTE_RENDER_CONTRACT.md`；main.py:2270（POST render-jobs, 202）；tests/test_remote_render_workflow.py |
| DEC-010 | 家電需求**留在問卷與生圖脈絡**（`scene_json.render_context`）協助第 8 步生圖，不列入 2D/3D 擺設，避免家電進幾何引擎 | P1 | 納入 | M-發表 | 問卷可表達家電需求；2D/3D 場景不出現家電擺件 | 專案 CLAUDE.md 明文邊界 | 已核准（回溯） | 全隊 | (未查證) | 專案 CLAUDE.md「目前產品邊界」節；`backend/server/questionnaire_visuals.py`（問卷視覺載入與驗證，250 行）；題庫本體在 `backend/server/data/questionnaire_visual_catalog.json`（實測 questions=55、options=110） |
| DEC-011 | 工程報告要能一鍵轉成**給屋主的提案簡報**與**給廠商的預算書**，且數字一律取自 ReportPayload、禁止編造 | P1 | 納入 | M-發表 | 提案/預算文件經核對腳本（verify_numbers.py / verify_budget.py）比對通過才算交付 | 文件內數字零 LLM 生成；skill 不碰 `backend/server/engineering/` 程式 | 已核准（回溯） | Django（skill 作者）＋ Bella（payload owner） | 2026-08-04（commits 3b2438dd、a2179f7e） | `.claude/skills/roompilot-proposal/`、`roompilot-budget/`（含 roompilot-security、roompilot-furniture-query 共 4 支入版控，14 個追蹤檔案） |
| DEC-012 | quarantine 隔離資料（sf3d_legacy、unmatched_cloud_furniture）**排除**於正式產品之外，只留檔供核對，不刪 | P0 | 排除（tombstone） | — | 隔離 ID 不得出現在網頁、Agent 與 3D 場景 | CLAUDE.md 禁止事項：不得將 quarantine 資料視為正式家具 | 已核准（回溯） | Kai | 2026-07-26（隨母集合決策） | `backend/catalog/data/quarantine/`；tests/test_cloud_quarantine.py |
| DEC-013 | `frontend3d/`（R3F 原型）**排除**於正式產品，僅作次要原型保留；不投入正式化 | P1 | 排除（tombstone） | — | 正式 UI 只有 `backend/server/static/`；原型驗證門檻僅 `npm ci && npm run build` | 不得新建正式前端（CLAUDE.md 禁止事項） | 已核准（回溯） | Bella | (未查證) | `frontend3d/AGENTS.md`（明定 secondary prototype） |

**欄位說明：**

- **優先序**：owner 依商業價值定，不是由 ID 前綴或關鍵字自動判。上表 P0/P1 為依「發表能否成立」回溯排定，須由 owner 明確接受。
- **範圍**：本次發布**納入**或**排除**。排除項（DEC-012、DEC-013）留著（tombstone），不刪。
- **里程碑**：repo 內無正式里程碑編號，統一以 `M-發表` 代稱（發表日期未查證）。
- **業務驗收條件**：用 owner 聽得懂的話寫「怎樣算通過」，不是工程測試步驟。
- **決策狀態**：全表為「已核准（回溯）」——決策已實作進 commit，但正式簽核 repo 內查無；owner 補簽前，本表對新工作的放行力以 `AGENTS.md` 為準。
- **對應工程ID**：本 repo 無 FR-*/NFR-* 系統，以契約檔＋守約測試作追溯橋，形成 `DEC → docs/contracts/ → tests/` 鏈。

### 2.1 決策理由（思考軌跡）

記「為什麼」，不只結果。以下理由整理自舊導入版 ADR（`docs/vibecoding/04_architecture_decision_record_template.md`，2026-07-26 對舊分支查證）與現行契約檔；「考慮過的選項」多為依 commit 前後狀態回推，未必是當時實際討論方案。

| 決策ID | 理由 | 考慮過的選項 | 拒絕的替代與原因 | 當時的不確定 |
| :--- | :--- | :--- | :--- | :--- |
| DEC-002 | 「每件對外家具必有模型」從執行期判斷升級為載入期硬驗證，壞資料直接讓啟動失敗而非靜默缺圖 | A. 沿用舊 10,550 件型錄、缺模型者標記不可 3D／B. 雲端已驗證集合為母集合、舊型錄降級 enrichment、無法映射者隔離 | 拒 A：母集合含千餘件無模型項目，「有沒有模型」變執行期判斷、測試無法立契約 | 首版定 9,350 件，其後母集合改為 8,557 件（現行 `cloud_catalog.py:15`），變更決策紀錄見第 4 節 CR-001 |
| DEC-003/004 | 家具擺放與碰撞對單位錯誤零容忍；把裁決權收斂到單一引擎＋公分契約，換算錯誤才能在邊界測試攔截 | A. 全面公尺／B. 對外公分、內部各自保留、邊界單點轉換 | 拒 A：家具型錄與台灣室內設計慣例都是公分，UI 全小數不可用 | 內部公尺表示仍存在，繞過邊界模組會拿到公尺 |
| DEC-006 | 型錄規模達萬件級（Phase 契約成文的 2026-07-27 當時母集合為 9,350 件，2026-07-30 起為 8,557 件），逐次掃 JSON 做 filter/count/facet 不可持續；分五階段上線可讓每階段有獨立契約與回退 | A. 一次性切換 PostgreSQL／B. 五階段（Read → 管理 CRUD → 專案保存 → runtime catalog → 單一事實來源） | 拒 A：五個資料域（catalog/admin/project/runtime/embeddings）風險面不同，一次切換無法隔離失敗 | JSON 與 DB 何時完成主從交接：TEAM_AI_OWNERSHIP 與 CLAUDE.md 表述尚未對齊（見 DEC-006 例外欄） |
| DEC-007 | 報價與排程一旦產出就會被拿去溝通，必須綁在「設計師已確認」的 snapshot 上，否則對浮動方案報價會造成商業誤導 | A. 任何 revision 都可產包／B. 鎖定（designer_confirmed）後才可產包 | 拒 A：未定案方案的估價無法承諾，且 revision 前進後舊包無從對賬 | XLSX 產出依賴 Node adapter（workbook_builder.mjs），環境缺 node 時的降級體驗 |
| DEC-009 | 寫實渲染算力與模型不在本機；假成功比失敗更傷信任，所以未設供應商一律 503；個資在離開系統前剝除 | A. 本機渲染／B. 遠端供應商代理＋503 明確失敗 | 拒 A：本機無 GPU 渲染能力，且供應商可替換 | 供應商 SLA 與費用 (未查證) |
| DEC-011 | 提案與預算文件會直接面對屋主/廠商，LLM 編造數字是不可接受的商業風險；用核對腳本把「文案自由、數字鎖死」變成可驗證的機制 | A. LLM 直接生成整份文件／B. 文案由 agent 寫、數字由腳本從 payload 取＋核對腳本擋編造 | 拒 A：無法保證數字與 ReportPayload 一致 | skill 為本機 `.claude/skills/`，團隊其他成員環境是否啟用 (未查證) |

---

## 3. Gate 決策紀錄

里程碑與階段放行由 owner 在此簽核。**現況：repo 內查無任何人為 Gate 簽核紀錄**——下表第一列為待補的正式 Gate；其後列出的是**程式內建的機器閘**（runtime gate），它們是既成需求決策的執行機制，不能替代 owner 簽核。

| Gate ID | Gate 名稱 | 對應里程碑 | 前置條件（範圍/驗收） | 決策 | 決策者 | 日期 | 備註 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| GATE-001 | 成果發表放行 | M-發表 | DEC-001～DEC-011 全數驗收；`pytest -q` 綠燈（AGENTS.md:76-80 最終整合指令） | （待簽） | （待補） | （待補） | 發表日期 (未查證) |
| （機器閘）G-M1 | 工程文件鎖定閘 | — | snapshot `approval_status == "designer_confirmed"`，否則 409 REVISION_NOT_LOCKED | 程式強制 | — | — | `backend/server/engineering/api.py:191` |
| （機器閘）G-M2 | 平面圖確認閘 | — | 未確認圖檔內容前呼叫 analyze 回 409 `floorplan_confirmation_required` | 程式強制 | — | — | `backend/server/main.py:2323` |
| （機器閘）G-M3 | 型錄啟用閘 | — | 家具管理寫入須通過 activation gate／參照驗證／樂觀併發檢查 | 程式強制 | — | — | `backend/catalog/postgres_admin_repository.py`（:406 `_activation_gaps`） |
| （機器閘）G-M4 | RAG 就緒閘 | — | embedding 模型快取缺失或 pgvector 表無資料即 blocker | 程式強制 | — | — | `backend/spatial_data/rag/service.py:82-90` |
| （機器閘）G-M5 | 母集合完整性閘 | — | 官方型錄載入件數 ≠ 8,557 即 raise，啟動失敗 | 程式強制 | — | — | `backend/catalog/cloud_catalog.py:96-103` |

---

## 4. 決策沿革

記錄範圍或優先序的變更，讓後續開發能回查「為什麼當初這樣定」。下列變更均以「舊導入版文件（2026-07-26 查證）vs 現行工作樹（2026-08-04 實查）」對比得出；變更的拍板過程 repo 內查無，決策者欄依目錄責任回推。

| 變更ID | 受影響決策ID | 原決策 → 新決策 | 原因 | 決策者 | 日期 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CR-001 | DEC-002 | 官方母集合 9,350 件 → **8,557 件**（`OFFICIAL_CATALOG_COUNT = 8_557`，schema_version `official-json-8557-v3`） | 資料集重整原因 (未查證)；8,557 現行兩處一致：`cloud_catalog.py:15`、`TEAM_AI_OWNERSHIP.md:57`。**三個數字不可混用**：8,557 = 官方母集合，來源檔是 `JSON/furniture/furniture_official_catagory.json`（頂層 count=8557，由 `main.py:137-139` OFFICIAL_FURNITURE_CATALOG_PATH → `CLOUD_CATALOG_PATH` 載入）；9,350 = 另一份舊來源檔 `backend/catalog/data/furniture_catalog_cloud_9350.json`（頂層 count=9350，`docs/owners/KAI.md:19` 定位為 PostgreSQL 不可用時的唯讀 fallback，**不是** 8,557 的正規化前身）；9,349 = `rag/` 獨立管線的向量索引筆數 | Kai | 2026-07-30（commit f5fc0995，`OFFICIAL_CATALOG_COUNT` 由 `9_350` 改為 `8_557`；首次引入 `9_350` 為 2026-07-26 commit 83b3c8a5） |
| CR-002 | DEC-001 | UI 十步（10 顆按鈕）→ **UI 八步（8 顆按鈕）**；內部 11 步狀態機不變（無獨立按鈕的是 3 步：`calibration`、`white_model_3d`、`realistic_3d`；三者各自併入 `WORKFLOW_PANEL_BY_STEP` 的 scale／white-model-3d／realistic-3d 面板，scene_workflow.js:18-30） | 收斂步驟按鈕、降低操作負擔 (未查證：拍板紀錄)；證據：舊 scene.html:23-32 為 10 顆（commit b04833ce，含 white_model_3d／realistic_3d 兩顆）vs 現行 scene.html:25-32 為 8 顆 | Bella | 2026-07-26（commit f085fc1e 移除該兩顆按鈕；拍板紀錄 (未查證)） |
| CR-003 | DEC-006 | PostgreSQL 僅到匯入工具（舊 Q-006 原文：「PostgreSQL 僅到 importer 階段（`scripts/sql/`），伺服器執行期型錄仍由 JSON + CSV 記憶體載入；是否接上執行期 API 待定」，`docs/vibecoding/02_project_brief_and_prd.md:114`）→ **執行期五階段全面接入**（Read/CRUD/專案保存/runtime catalog/單一事實來源） | 型錄規模與併發寫入需求；五份 Phase 契約與三組 scripts 子目錄落地 | Kai、Bella | Phase 1/2/3/5 契約標頭「更新日期：2026-07-27」；Phase 4 契約標頭無日期欄 (未查證) |
| CR-004 | DEC-008（新增） | `backend/spatial_data/` 僅 `.gitkeep` 佔位（舊版明載「尚未實作」）→ **家具 RAG runtime 成為該目錄主體**（rag/ 11 個 .py 檔 1,234 行＋ `/api/rag/*` 4 條路由＋ `/rag` 測試台 1 條，rag_api.py 合計 5 條） | Django 的 RAG 標註與檢索能力上線 | Django | 2026-07-29（契約更新日期） |
| CR-005 | DEC-007（新增） | 舊版無工程文件功能 → **新增工程文件 MVP**（`backend/server/engineering/` 8 條 /api/v1 路由、`/engineering` 頁） | 發表需要可交付的估價/排程文件 | Bella | 2026-07-29（契約更新日期） |
| CR-006 | DEC-001 | 前端 Three.js 由 unpkg CDN（three@0.165.0）→ **vendored `/static/vendor/three/`**，無 CDN 依賴 | 消除執行期外部依賴，離線 demo 可用 (未查證：拍板紀錄)；證據：現行 scene.html:1058-1065 importmap 指向 /static/vendor/three/；舊版 scene.html:784-791（commit 915cecf4）指向 `https://unpkg.com/three@0.165.0/` | Bella | 2026-07-30（commit 614ae3a4「完成初談問卷、渲染與離線展示流程」；拍板紀錄 (未查證)） |
| CR-007 | 第 1 節 owner 表 | 團隊 6 人 → **7 人**（新增 Ben：辨識 QA／evaluation） | 辨識品質需要獨立 QA 角色 (未查證：拍板紀錄)；證據：舊導入版記 6 人（`docs/vibecoding/04_architecture_decision_record_template.md:92`、:95、`05_architecture_and_design_document.md:337`）vs 現行 TEAM_AI_OWNERSHIP.md:7-15 為 7 列（Bella/Cody/Django/Kai/Yen/Ancai/Ben）。註：`docs/TEAM_AI_OWNERSHIP.md` 建檔於 2026-07-27（commit debb7c95），Ben 自建檔即在表內，故「6 → 7」是**文件版本間**的差異，非該檔內的一次增列 | 全隊 | (未查證) |
| CR-008 | DEC-011（新增） | 無專案 skill → **四支 roompilot-* skill 進版控**（security → furniture-query/proposal/budget） | 把資安稽核與文件產出流程固化為可重複執行的 skill | Django | 2026-08-04（commits 3b2438dd、a2179f7e） |

---

## 5. `/specify` 放行檢查（硬閘）

`/specify` 啟動前，逐項確認（RoomPilot 現況：`/specify` skill 存在於工作樹但未進版控、未被 CI 強制；在流程 skill 正式化之前，等效硬閘為 `AGENTS.md` 的修改前流程——本節兩者並列）：

- [ ] 目標需求在**第 2 節**有對應列，且 `決策狀態 = 已核准`（回溯核准列須 owner 補簽後才算數）。
- [ ] 該列有**決策者**與**日期**（owner 簽核）。
- [ ] 優先序、範圍、里程碑非空，且不是未經接受的系統自動值（本表 P0/P1 為回溯排定，owner 須明確接受）。
- [ ] 若跨里程碑 Gate，**第 3 節**對應 Gate 為 `核准`（機器閘 G-M1～G-M5 由程式自動把關，不需人工勾稽，但不可拿來替代 GATE-001 簽核）。
- [ ] 商業例外/紅線已標記，工程契約需承接（例：個資剝除、quarantine 排除、幾何裁決權、公分制）。

RoomPilot 等效檢查（AGENTS.md，動手前必做）：

- [ ] 已讀 README → `docs/TEAM_AI_OWNERSHIP.md` ＋ owner profile → 最近的 `AGENTS.md` 與相關 `docs/contracts/`（AGENTS.md:5-12）。
- [ ] 跨資料夾修改已填 6 欄記錄（主要 owner／協作 owner／修改檔案／改變的契約或流程／為何不能單一目錄完成／兩端驗證測試，AGENTS.md:20-28）。
- [ ] 不違反 11 條不可違反契約（AGENTS.md:50-60），含公分制、engine 唯一裁決、`furniture_catalog_current` 優先、不提交 `.env`/權重/大型 GLB。
- [ ] 對應驗證矩陣類別的測試可過（AGENTS.md:64-72；最終整合 `pytest -q` ＋ `git diff --check` ＋ `git status --short`）。

任一項不成立：**停止，退回 owner 決策**，不得由 AI 代填後續。
