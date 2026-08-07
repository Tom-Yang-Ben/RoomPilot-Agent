# 文件索引 (Document Index) - RoomPilot VibeCoding Pilot 導入

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 待審閱
> **Owner:** Ben（docs support，暫代——正式文件 owner 指派見 §6 待確認 B-2）
> **語域:** L2（橋接；索引本身不承載工程或業務主張）
> **定位:** 本檔回答「docs/vibecoding-pilot/ 有哪些文件、每份做什麼、哪些事項待人工確認」。文件內容各歸其檔；流程唯一權威在 [.claude/WORKFLOW.md](../../.claude/WORKFLOW.md)，模板標準在 [template_standard.md](../../VibeCoding_Workflow_Templates/_meta/template_standard.md)。
> **實例:** 單例（整個資料夾一份）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/INDEX.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

## 目錄

- [1. 生成憑證](#1-生成憑證)
- [2. 六階段文件清單](#2-六階段文件清單)
- [3. 與舊版 docs/vibecoding/ 的關係](#3-與舊版-docsvibecoding-的關係)
- [4. 追蹤簿（tracker xlsx）不實例化](#4-追蹤簿tracker-xlsx不實例化)
- [5. diagrams/ 工具包](#5-diagrams-工具包)
- [6. 待人工確認清單](#6-待人工確認清單)
- [7. 追溯](#7-追溯)

## 1. 生成憑證

| 項目 | 值 |
|---|---|
| 基準 | branch `docs/vibecoding-restructure` @ commit `1268b2b4` |
| 生成日 | 2026-08-07（平行文件 agent 產出 → 一致性稽核修正 25 項 → 本索引收尾） |
| 模板來源 | [VibeCoding_Workflow_Templates/](../../VibeCoding_Workflow_Templates/)（2026-07-27 重整後的 Pilot 核心模板組） |
| 產出規模 | 29 份 Markdown ＋ 1 份 OpenAPI YAML，六階段目錄鏡射模板結構 |
| 連結驗證 | 2026-08-07 全資料夾相對連結掃描 0 斷鏈（各 agent 先前標註的「平行產出連結待核」已全數可達） |

事實紀律：每份文件均對 1268b2b4 現行程式碼複核後才寫；無法複核的內容標「（未查證）」「待補」「TO-BE」，未編造任何數字或決策。全量 pytest 於 2026-08-07 由 test_plan 產出過程實跑一輪：1,043 通過／10 跳過／0 失敗（詳見 [test_plan.md](05_qa/test_plan.md)）。

## 2. 六階段文件清單

### 2.1 01_requirements（需求）

| 文件 | 用途 |
|---|---|
| [brd.md](01_requirements/brd.md) | 商業需求：L1 語域、BR-001~012 可查證業務規則；商業背景因來源匱乏大量標未查證 |
| [prd.md](01_requirements/prd.md) | 產品需求：14 條使用者故事（US/SCN-\<AREA\>-NN）、Given/When/Then 允收；SCN 編號權威 |
| [srs.md](01_requirements/srs.md) | 軟體需求：AGENTS.md 契約正式化為 24 FR＋8 NFR＋26 ACPT；FR/NFR 編號權威 |

### 2.2 02_ux_ui（體驗與介面）

| 文件 | 用途 |
|---|---|
| [ux_research_and_journey.md](02_ux_ui/ux_research_and_journey.md) | 使用者旅程：現行 8 步 UI 實況旅程；研究與 Persona 段誠實標 TO-BE/假設 |
| [information_architecture.md](02_ux_ui/information_architecture.md) | 資訊架構：8 個頁面路由／77 條總路由、導航與跨頁交接（含兩條已知交接斷裂） |
| [ui_spec-scene.md](02_ux_ui/ui_spec-scene.md) | 八步工作流主頁（/scene）規格：8 顆 UI 按鈕對 11 內部步驟，欄位與文案附行號 |
| [ui_spec-login.md](02_ux_ui/ui_spec-login.md) | 登入頁（/login）規格：欄位、驗證與錯誤狀態 |
| [ui_spec-projects.md](02_ux_ui/ui_spec-projects.md) | 我的專案頁（/projects）規格：清單、建立與權限可見性 |

### 2.3 03_architecture（架構）

| 文件 | 用途 |
|---|---|
| [sad.md](03_architecture/sad.md) | 系統架構：C4 L1–L3、DDD Context Map、3 張核心 sequence、ER 與部署視圖（9 張 mermaid） |
| [ADR-001-unified-backend-package.md](03_architecture/ADR-001-unified-backend-package.md) | 決策：單一 backend 套件、FastAPI 路由拆 APIRouter |
| [ADR-002-centimeter-contract.md](03_architecture/ADR-002-centimeter-contract.md) | 決策：跨模組幾何公分制（`_cm`/`_m2`）契約 |
| [ADR-003-cloudfront-glb-delivery.md](03_architecture/ADR-003-cloudfront-glb-delivery.md) | 決策：家具 GLB 走 CloudFront 交付 |
| [ADR-004-official-catalog-master-set.md](03_architecture/ADR-004-official-catalog-master-set.md) | 決策：官方型錄母集合（9,350→8,557 收斂沿革） |
| [ADR-005-catalog-import-hardening.md](03_architecture/ADR-005-catalog-import-hardening.md) | 決策：型錄匯入硬化機制 |
| [ADR-006-postgres-single-source-five-phases.md](03_architecture/ADR-006-postgres-single-source-five-phases.md) | 決策：PostgreSQL 五階段單一真相源（strict provider，無自動 JSON 回退） |
| [ADR-007-lighting-separate-table.md](03_architecture/ADR-007-lighting-separate-table.md) | 決策：燈具獨立表（793/637/156，偏離契約原文待四人確認） |
| [ADR-008-site-css-no-split.md](03_architecture/ADR-008-site-css-no-split.md) | 決策：site.css 不按頁拆（repo 外記錄回溯，全文待 Ben 確認） |
| [ADR-009-docker-removal.md](03_architecture/ADR-009-docker-removal.md) | 決策：Docker 整套移除、回歸本機 uvicorn（09891216） |

### 2.4 04_design（設計）

| 文件 | 用途 |
|---|---|
| [api_spec.md](04_design/api_spec.md) | API 設計約定：錯誤語意、公分制例外、JWT 守衛對照（404-not-403）、77 條路由總表 |
| [openapi-roompilot-v1.yaml](04_design/openapi-roompilot-v1.yaml) | OpenAPI 快照：實跑 `app.openapi()` 匯出，70 paths／77 operations |
| [db_design.md](04_design/db_design.md) | 資料庫設計：`roompilot.furniture_catalog_current` read model、ERD、索引與保留政策；筆數經 live 直查（7,958 可選） |
| [lld.md](04_design/lld.md) | 低階設計：模組結構與依賴邊、四個 Aggregate 狀態機契約 |

### 2.5 05_qa（品質）

| 文件 | 用途 |
|---|---|
| [test_plan.md](05_qa/test_plan.md) | 測試計畫：26 條 TC 對應 SCN、conftest 隔離與 opt-in 開關；實跑 1,043/10/0（460.18s） |
| [uat_plan.md](05_qa/uat_plan.md) | UAT 計畫：11 個情境對應現行八步旅程，全標「未執行」，輪次 UAT_RoomPilot_Pilot_20260820 |

### 2.6 06_ops（維運）

| 文件 | 用途 |
|---|---|
| [deployment_and_operations.md](06_ops/deployment_and_operations.md) | 部署與維運：本機 uvicorn 8002＋PostgreSQL 17.10 現況、環境變數表逐鍵複核、CI/備援照實標無 |
| [runbook-postgres-catalog-unavailable.md](06_ops/runbook-postgres-catalog-unavailable.md) | 症狀：PostgreSQL 不可用 → 503 顯式受阻＋人工切換 provider（無自動 JSON 回退） |
| [runbook-provider-env-shadow.md](06_ops/runbook-provider-env-shadow.md) | 症狀：終端 `ROOMPILOT_*_PROVIDER` 環境變數蓋過 .env |
| [runbook-port-8002-in-use.md](06_ops/runbook-port-8002-in-use.md) | 症狀：port 8002 被佔用 |
| [runbook-furniture-glb-missing.md](06_ops/runbook-furniture-glb-missing.md) | 症狀：家具 GLB 缺檔顯示琥珀色替代方塊（skip＋decor_summary.skipped） |
| [runbook-cold-start-first-scene.md](06_ops/runbook-cold-start-first-scene.md) | 症狀：第 6 步冷啟約 33 秒——shader 綁定的已知特性，非故障 |

## 3. 與舊版 docs/vibecoding/ 的關係

一句話：**本資料夾是新模板組（2026-07-27 重整後 Pilot 核心）的導入版；[docs/vibecoding/](../vibecoding/) 是 2026-07-26 舊模板（01–17 編號、基準 bella-local-20260726）的導入版，僅供參考、不是事實權威。**

- 舊版事實已過時 12 天；本輪逐項對 1268b2b4 複核，多項已翻案（路由 44→77、型錄 9,350→8,557/7,958、unpkg CDN→vendored three.js、十步/四頁 IA→八步/8 頁、44 條無認證→77 條 JWT）。細節見各文件內「過時口徑」標註。
- 舊版仍引用時一律標「沿用 2026-07-26 版未複核」。
- **舊資料夾去留待 Ben 裁決**（保留為沿革、或標記封存、或移除）；本輪未動 docs/vibecoding/ 任何檔案。

## 4. 追蹤簿（tracker xlsx）不實例化

三本 `*_tracker.xlsx` 本輪**刻意不實例化**：需求決策、Gate 簽核與執行證據由 owner 親自拍板填寫，AI 不得代填——規則見 [workflow_manual.md §7–8](../../VibeCoding_Workflow_Templates/_meta/workflow_manual.md#7-追蹤簿與欄位所有權)。

## 5. diagrams/ 工具包

`VibeCoding_Workflow_Templates/03_architecture/diagrams/` 的 drawio 工具包本輪未產圖；架構圖以 [sad.md](03_architecture/sad.md) 內嵌 mermaid（9 張）承載。需要對外溝通級大圖時再啟用 drawio 工具包。

## 6. 待人工確認清單

各文件 agent 回報項已去重、按主題分組；一致性稽核已於本輪修正 25 項（穩定 ID 對線、SCN/NFR 編號收斂、「自動 JSON 回退」錯誤敘述統一改為「503 顯式受阻＋人工切換」、數字口徑與交叉引用），下列為**修正後仍需人工**的殘餘項。

### A. 版控阻斷（最高優先，擋 commit）

| # | 事項 | 待誰 |
|---|---|---|
| A-1 | `.gitignore` 的 `docs/*` 規則原本吞掉整個 docs/vibecoding-pilot/；`!docs/vibecoding-pilot/`＋`!docs/vibecoding-pilot/**` negation 已補進工作樹（2026-08-07 `git check-ignore` 複驗資料夾已不被忽略），但該 `.gitignore` 修改**尚未 commit**，須與本資料夾一併提交 | orchestrator／人工 |

### B. 業務決策與 owner 拍板

| # | 事項 | 待誰 |
|---|---|---|
| B-1 | 2026-08-20 發表日僅團隊口述、repo 無紀錄（brd/prd/uat/deployment 均標未查證）；發表當日環境形態（本機 demo／雲端）與多人跨機驗收方式未定 | Ben／全隊 |
| B-2 | BRD Owner 暫填 Ben；repo 內無業務代表／需求決策 owner 的正式指派紀錄 | 全隊 |
| B-3 | BR-001~012 已在系統行為生效但未經 owner 於 requirements_tracker ①需求決策核准（追蹤簿依 §4 未實例化）；UAT 簽核人、起訖日、REQ/DEC ID 回填同此 | Ben（owner） |
| B-4 | 目標用戶「屋主自助」vs「設計師帶客戶用」兩說並存未拍板；預期效益完全未量化（無現行流程耗時基線） | Ben／訪談 |
| B-5 | NFR 效能門檻（API p95、3D 首次載入）無量測基準標 TO-BE；資料保留政策全數未定義（srs §3、db_design §5 同口徑） | Ben／團隊 |
| B-6 | ADR「決策者」欄多依 commit 作者回推（CLAUDE.md 明訂責任不可只依 git author 推論）；ADR-008 全文待 Ben 確認（.out-of-scope/ 實查無 site.css 紀錄，屬 repo 外回溯）；ADR-009「達到目標狀態」驗收條件無紀錄 | Ben／全隊 |
| B-7 | sad §9 演進路線（IKEA 地端備援、燈具分流、容器化重建）為現況整理，非已裁決 roadmap | Ben |
| B-8 | 舊資料夾 docs/vibecoding/ 去留（見 §3） | Ben |
| B-9 | 「僅桌面瀏覽器」為 uat_plan 假設，README 未宣稱支援範圍 | Ben |
| B-10 | 平面圖辨識 KPI 待重新指定（舊 floor04 基準已從 README 移除）；樑柱手繪標定屬設計決策但無獨立決策文件，待補 ADR | Cody、Ben |

### C. 型錄數量多來源不一致

| # | 事項 | 待誰 |
|---|---|---|
| C-1 | 9,349/9,350（Phase1／embeddings 契約、JSON 檔名、rag.html:32）vs 現況 8,557 母集合／7,958 可選；差額歸因燈具分表（793）為算術推測，未逐筆對帳；契約檔待補記 | Kai、Django |
| C-2 | 599 筆停用家具中 347 筆 DB 內查無停用原因；停用決策位於 Kai 匯入層來源檔未查證 | Kai |
| C-3 | furniture_categories schema 註解 64 類 vs 實測 55 類 active，註解待更正 | Kai |
| C-4 | 燈具 156 筆待分流之進度未複核（沿 2026-08-02 紀錄）；ADR-007 分表偏離 LIGHTING_CEILING_CATALOG_CONTRACT.md 原文，契約仍標草案 | Kai/Django/Bella/Ancai |

### D. README 與既有文件陳舊口徑

| # | 事項 | 待誰 |
|---|---|---|
| D-1 | 根 README「JSON 為預設來源／DB 不可連自動 JSON 備援」與現行 strict postgres＋503 程式碼矛盾（已寫入 ADR-006 後果段） | Bella、Kai |
| D-2 | README 套件基線（FastAPI 0.140.0／uvicorn 0.51.0／Python 3.12.13）vs .venv 實測（0.139.0／0.50.0／3.12.10），權威待對齊 | Ben、Bella |
| D-3 | index.html:62「12 種風格」「5 步流程卡」舊口徑待更新為 6 風格 18 色卡與八步；library.html:19「風格模型」字樣待統一為「風格類型」；README.md:134 第 5 步描述與現行初回面談 UI 口徑差 | Bella、Ben |

### E. 資安與授權缺口

| # | 事項 | 待誰 |
|---|---|---|
| E-1 | GET /api/v1/engineering/health 無守衛 vs AGENTS.md「/api/v1/* 全掛守衛」——是否豁免待裁決 | Bella、Ben |
| E-2 | 孤兒文件下載跳過專案授權（engineering/api.py:387-389） | 資安確認 |
| E-3 | 免登入計算端點群（/api/scene/*、/api/agent/furniture/select、/api/floorplan/*、/api/upload）：區網 demo 定位下未收斂，對外部署前必須裁決 | Bella、Ben |
| E-4 | Codex 2026-08-04 稽核仍開放：shortlist 捷徑後門、首帳號自動 admin（BR-008 例外欄已註記；/api/rag 守衛已確認補上） | Bella |
| E-5 | 錯誤 detail 三形狀並存（code／error_code／純字串）無統一計畫 | Bella |

### F. UX／IA 裂縫

| # | 事項 | 待誰 |
|---|---|---|
| F-1 | library→scene 方案清單交接無消費端（scene_v2.js 不讀 roompilot:sceneProposal）——修復或移除寫入端 | Bella |
| F-2 | styles→scene 儲存備援錯接：styles.js 寫 sessionStorage、scene_v2.js 讀 localStorage 同名 key（query 通道正常） | Bella |
| F-3 | /scene 步驟切換只用 history.replaceState，瀏覽器 back 直接離開工作流；首頁 CTA 指 /projects 而 styles/library CTA 指 /scene 的動線不一致；無自訂 404 頁 | Bella（裁決） |
| F-4 | 無正式使用者研究：Persona、旅程情緒欄、預測卡點全為假設；a11y（鍵盤、對比、螢幕閱讀器）未系統性驗證；非成員 404 前端文案未逐一查證 | Pilot 階段排入 |

### G. 測試與驗證缺口

| # | 事項 | 待誰 |
|---|---|---|
| G-1 | 全量 pytest 已於 2026-08-07 實跑全綠（1,043/10/0）；但 10 個跳過原因未逐項盤點（需 pytest -rs 一輪） | Django |
| G-2 | postgres opt-in 路徑（ROOMPILOT_TEST_POSTGRES_* 四開關）未執行，發表前需一輪實連 | Django |
| G-3 | SCN-FP-03（第 4 步人工校正／樑柱手繪）與第 8 步生圖→報告端到端無自動化，瀏覽器 QA 待排；UAT 11 情境全數未執行（UAT-005 牆體目視即正式驗收場合；UAT-008 外部生圖服務可達性需執行前人工確認） | Django／全隊 |
| G-4 | SCN-LAYOUT-01 自動化對應（候選 test_floorplan_room_evaluation.py）與 TC-AUTH-03 對 test_auth_lifecycle.py 的對應未逐函式複核 | Django |
| G-5 | 缺陷登錄／UAT 問題單通道未定（repo 內無 issue tracker 慣例）；暫記執行紀錄檔後由 owner 移入 qa_tracker ②執行證據 | Ben（owner） |
| G-6 | 依賴方向（領域模組不得 import backend.server）無 CI 自動守門，待補 import-linter 類檢查 | Ancai／Bella |

### H. 其他工程待辦

| # | 事項 | 待誰 |
|---|---|---|
| H-1 | engine/adjustment.py 與 engine/schema.py tool 常數為死碼候選（server 零呼叫點已複核），去留待裁決 | Ancai |
| H-2 | @app.on_event → lifespan 遷移未裁決（main.py:1401-1414 仍在用） | Bella |
| H-3 | .env.example 缺 ROOMPILOT_AUTH_SECRET/_ACCESS_TTL/_REFRESH_TTL/_DISABLE_FIRST_ADMIN 四鍵（README 有設定要求），是否補進範本待定 | Bella |
| H-4 | PostgreSQL 正式專案資料無任何備份機制；pg_dump 僅 TO-BE 建議、repo 無現成腳本 | Kai、Ben |
| H-5 | 伺服器端「只驗步驟名不驗順序」沿用 2026-07-26 版描述未複核 main.py 該段（ui_spec-scene §7、prd Q-006 同項） | Bella |
| H-6 | ADR-003 local 模式 DATASET_DIR 缺陷為舊版實測記載未複核（README 已明文禁止啟用本機模式） | — |
| H-7 | openapi 快照無 servers/securitySchemes（FastAPI 產生器限制，檔頭已註記）；瀏覽器端實際帶 token 行為未實測 | Bella |
| H-8 | runbook agent 遺留背景 psql 任務（bcooko1oq）可能仍掛起，唯讀無害，見到請終止；PostgreSQL 17.10／pgvector 0.8.2 版本號沿用 2026-08-05 NEW_MACHINE_SETUP 實測，本輪僅驗 service Running | 本機清理 |
| H-9 | 冷啟 33 秒與三條已排除優化路出自 2026-08-01 團隊 QA 工作紀錄（未入版控），文件內已如實標注 | — |

## 7. 追溯

- 上游：[VibeCoding_Workflow_Templates/INDEX.md](../../VibeCoding_Workflow_Templates/INDEX.md)（模板組與實例化規則）、[template_standard.md](../../VibeCoding_Workflow_Templates/_meta/template_standard.md)（六要素）、[AGENTS.md](../../AGENTS.md)（目錄責任與不可違反契約）、基準 commit `1268b2b4`
- 下游：§2 全部 30 份文件；追溯 ID 主鏈唯一權威在 [docs/document-system/architecture.md §7.1](../document-system/architecture.md)；穩定 ID 編號權威——FR/NFR/ACPT 在 [srs.md](01_requirements/srs.md)、SCN 在 [prd.md](01_requirements/prd.md)、TC 在 [test_plan.md](05_qa/test_plan.md)、ADR 在 03_architecture/ 各檔
- 待確認清單（§6）之來源：各文件 agent openItems 回報＋一致性稽核修正報告（2026-08-07），去重後殘餘項；逐項證據座標見各文件追溯段
