# Output Styles 導入指南(RoomPilot-Agent)

> 本文件由 VibeCoding 模板 output_style.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

一句話結論:**把「需求→設計→行為→單元」用可切換的 Claude Code Output Styles 固化成標準作業:SDD/DDD 定義邊界,BDD/TDD 驅動正確性,前後端與跨系統各就各位——RoomPilot 的 `.claude/output-styles/` 已內建 15 個樣式檔,本文件是機制說明、模板正本與 RoomPilot 語境對照。**

---

## 如何在本 repo 使用(先讀這節)

### 放置位置與現況

| 項目 | 內容 | 依據 |
| :--- | :--- | :--- |
| 專案層樣式目錄 | `.claude/output-styles/`,**已存在** 15 個樣式檔 + `README.md` | 2026-07-26 `ls` 實測 |
| 用戶層樣式目錄 | `~/.claude/output-styles/`(跨專案共用,本 repo 未使用) | 官方文件([docs.claude.com][1]) |
| 樣式檔格式 | YAML Front-Matter(`name`/`description`,repo 版另有 `stage`/`template_ref`)+ 指令內文 | 實測 `06-tdd-unit-spec.md` 檔頭 |
| 切換指令 | `/output-style <樣式名>`;恢復預設 `/output-style default` | 官方文件([docs.claude.com][1]) |
| 切換紀錄 | 官方文件稱記錄於 `.claude/settings.local.json`;本 repo 目前無此檔(實測),切換後行為未實際驗證(未查證) | 官方文件([docs.claude.com][1]) |

### 版控注意事項

- `.gitignore` 第 54 行忽略整個 `.claude/`,且 `git ls-files .claude` 為空(實測)——**現有 15 個樣式檔只存在本機,不會隨 git push 分享給組員**。
- 若要團隊共享,需修改 `.gitignore` 豁免 `.claude/output-styles/`,或另闢版控目錄存放正本。此為裁決事項,待補。
- 樣式檔內的 `README.md`(`.claude/output-styles/README.md`)有完整的樣式選用指南與 mermaid 流程圖,內容以通用預約系統為範例語境,尚未 RoomPilot 化(實測讀檔)。

### 本 repo 既有 15 個樣式檔 × 本文件第 2 節模板對照

樣式名 = 檔名(front-matter `name` 與檔名一致;`15-Vision-output.md` 例外,front-matter 無 `name` 欄位,實測)。

| repo 樣式檔(可直接 `/output-style` 切換) | 對應本文件模板 | 開發階段 |
| :--- | :--- | :--- |
| `01-prd-product-spec` | (無;PRD 屬 `docs/vibecoding/02_project_brief_and_prd.md` 範疇) | 規劃 |
| `02-bdd-scenario-spec` | §2.6 BDD 可執行規格 | 規劃 |
| `03-architecture-design-doc` | §2.1 SDD 系統設計說明 | 架構 |
| `04-ddd-aggregate-spec` | §2.2 DDD 聚合與界限脈絡 | 架構 |
| `05-api-contract-spec` | §2.5 API First 合約 | 架構 |
| `06-tdd-unit-spec` | §2.7 TDD 函式級單元 | 開發 |
| `07-code-review-checklist` | §2.11 架構/程式碼審查守門 | 品質 |
| `08-security-checklist` | (無;安全清單屬 `docs/vibecoding/13_security_and_readiness_checklists.md` 範疇) | 上線 |
| `09-database-schema-spec` | §2.3 資料庫綱要 | 架構 |
| `10-backend-python-impl` | §2.4 後端實作 Python/FastAPI | 開發 |
| `11-frontend-component-bdd` | §2.8 前端元件 | 開發 |
| `12-integration-contract-suite` | §2.9 跨系統整合 | 整合 |
| `13-data-contract-evolution` | §2.10 數據契約與演進 | 整合 |
| `14-ci-quality-gates` | §2.12 CI/CD 品質柵欄 | 品質 |
| `15-Vision-output` | (無;視覺化優先解釋模式,repo 自加) | 輔助 |

### RoomPilot 常用驗證指令(樣式產出後的證據來源)

```bash
uv sync --extra server                                    # 安裝後端依賴(pyproject.toml)
uv run uvicorn backend.server.main:app --port 8002        # 啟動(README.md「使用 uv」一節)
uv run pytest tests/ -q                                   # 全測試(47 個測試檔、392 tests collected,實測 --collect-only;通過率本次未執行,未查證)
```

---

# 系統化總覽(教科書式)

## 0. 為何用 Output Styles 來落地流程

Claude Code 的 **Output Styles** 允許你用 `/output-style <name>` 一鍵切換「產物格式與觀點」,等同把「團隊最佳實踐」寫成模板檔,放在 `~/.claude/output-styles`(用戶層)或專案內的 `.claude/output-styles/`(專案層)持續重用;切換會被記錄在 `.claude/settings.local.json`。此機制是**修改系統提示**而非一般提示文,還能與 subagents、hooks 串起自動化流程。([docs.claude.com][1])
若需把「一定要做」變成可重複的自動動作(如格式化、保護敏感檔、測試前置),可用 **Hooks** 在 Claude Code 生命週期各點執行 shell 指令,作為流程觸發器。([docs.claude.com][2])RoomPilot 的 `.claude/hooks/` 已有 `post-write.sh`、`pre-tool-use.sh` 等 7 支腳本 + `README.md`(實測 `ls`),同樣不在版控內。

> 開發「聖經」對應:
>
> * **SDD** 依據 IEEE Std 1016 規範「設計描述內容與結構」。([IEEE Standards Association][3])
> * **DDD**(Evans)落實聚合、界限脈絡、領域事件與不變量。([Domain Language][4])
> * **TDD**(Kent Beck/M. Fowler)「Red → Green → Refactor」的最小步驟與測試清單。([martinfowler.com][5])
> * **BDD/Gherkin** 用 Given/When/Then 的可執行規格;Cucumber 做為事實標準。([cucumber.io][6])
> * **前端元件測試**:Storybook 的互動/元件測試讓 UI 規格可視化。([Storybook][7])RoomPilot 的 `frontend3d/` 尚未安裝 Storybook(`package.json` devDependencies 僅 `vite` 與 `@vitejs/plugin-react`,實測),互動測試工具待補。
> * **Claude Code 實務**:官方最佳實踐與樣式切換說明。([anthropic.com][8])

---

## 1. 角色 × 用途 × 對應樣式(總覽表)

RoomPilot 採目錄負責人制(`README.md` 團隊目錄表,實測):Cody=`backend/floorplan/`+`backend/upgrade3d/`、Kai=`backend/catalog/`、Django=`backend/spatial_data/`、Yen=`backend/agent/`、AN=`backend/engine/`、Bella=`backend/server/`+`frontend3d/`。下表最右欄把模板角色接到 RoomPilot 的實際落點。

| 角色/層面 | 主要目的 | 推薦 Output Style(repo 既有樣式名) | 產物重點 | RoomPilot 落點 |
| --------------- | ----------- | ---------------------------- | -------------------------------------------- | --- |
| 系統架構(SA/SD) | 輸出設計說明(SDD) | `03-architecture-design-doc` | 背景、品質屬性、視圖(C4/流程/資料)、介面契約、ADR | `docs/RoomPilot_現行版本總覽.md` + `docs/contracts/`(6 份,實測 `ls`) |
| 後端領域(DDD) | 定義語境與不變量 | `04-ddd-aggregate-spec` | 界限脈絡、聚合根、不變量、領域事件、倉儲介面 | `backend/agent/`(選件決策)×`backend/engine/`(幾何) |
| API/合約 | 穩定對外交付 | `05-api-contract-spec` | OpenAPI/JSON Schema、錯誤語意、版本策略 | `backend/server/main.py` 44 條路由(grep 實測) |
| BDD 規格 | 行為驅動與跨職能對齊 | `02-bdd-scenario-spec` | Feature/Scenario/Examples、步驟骨架 | 十一步內部工作流(`scene_workflow.js`) |
| TDD(函式級) | 單元可靠性 | `06-tdd-unit-spec` | 測試清單、紅綠重構、特例/邊界 | `backend/engine/` 幾何函式 + `tests/` |
| 前端元件 | 元件驅動 | `11-frontend-component-bdd` | 行為案例、互動測試、可存取性 | `frontend3d/`(React Three Fiber)+ `backend/server/static/` |
| 跨系統整合 | 合約穩定與測試 | `12-integration-contract-suite` | 同步/非同步合約測試、mock/fixture | 遠端渲染、OpenRouter、CloudFront 三條外部邊界 |
| 數據契約/演進 | 模式治理 | `13-data-contract-evolution` | Schema 演進策略、稽核、漂移偵測 | 9,350 件雲端型錄 + manifest 一對一契約 |
| 稽核/Review | 守門與拉齊 | `07-code-review-checklist` | 走查清單、錯誤類型庫、風險提示 | 公分制/座標轉換/agent-engine 分界 |
| CI/CD 品質柵欄 | 自動強制規範 | `14-ci-quality-gates` | 覆蓋率/靜態分析閥值、hooks 指令 | 現況無 CI(repo 無 `.github/`,實測);gate=本機 pytest |

> 放置方式:每個樣式存一檔(`.md`),檔名即樣式名,存於 `~/.claude/output-styles` 或 `.claude/output-styles/`,以 `/output-style <樣式名>` 切換。([docs.claude.com][1])

---

# 2. 可直接複製的 Output Style 模板(YAML Front-Matter + 指示)

> **使用法**:把下列每一段**整段**另存為一個檔案,例如 `.claude/output-styles/sdd-system-1016.md`,然後在專案內輸入 `/output-style sdd-system-1016` 切換。([docs.claude.com][1])
> **RoomPilot 注意**:本 repo 的 `.claude/output-styles/` 已有對應實作檔(見開頭對照表),**不需重複建檔**;以下模板保留原骨架、範例語境換成 RoomPilot 技術棧(FastAPI/pytest/uv/Vite/three.js),供修訂既有樣式或新增樣式時當底稿。每節末的「RoomPilot 套用」列出已查證的真實落點。

### 2.1 SDD(IEEE 1016)— 系統設計說明

```md
---
name: sdd-system-1016
description: "IEEE 1016 風格的系統設計說明(SDD)模板;輸出可審查、可追蹤的設計描述。"
---
# 指令(你是系統設計顧問)
以 IEEE 1016 的資訊結構輸出 SDD;必要時反問以補足缺失。避免空話,所有主張需可驗證。優先清楚描述「設計決策與取捨」。

## 交付結構
1. **背景與目標**:問題定義、範圍、非目標
2. **利害關係人與品質屬性**:Availability、Latency、Throughput、Security、Cost、Operability(用 ATAM 式權衡)
3. **脈絡與視圖**:
   - C4:Context→Container→Component(若需 Code 片段)
     (RoomPilot Container 例:backend/server FastAPI 應用、backend/floorplan+upgrade3d 平面圖辨識、
      backend/engine 幾何擺位、backend/agent 選件決策、backend/catalog 型錄、frontend3d Vite/R3F 子專案)
   - 流程圖(關鍵交易/風險流程;RoomPilot 例:POST /api/scene/generate 的場景生成管線)
   - 資料視圖(核心資料模型、事件流;RoomPilot 例:.runtime/projects.sqlite3 專案存檔與場景 payload)
4. **介面契約**:同步(REST)與非同步的規格、版本策略、錯誤語意(RoomPilot 正本在 docs/contracts/)
5. **運維與彈性**:部署拓撲、可觀測性、備援/降級策略(RoomPilot 例:OpenRouter 失效必須本地 fallback)
6. **風險與假設**:已知風險、緩解計畫、開放議題
7. **架構決策紀錄(ADR)**:決策→選項→取捨→依據→狀態
8. **驗證計畫**:合約測試、容量與故障演練、回歸矩陣(RoomPilot 例:uv run pytest tests/ -q)

## 蘇格拉底檢核
- 若某品質屬性衝突,誰優先?為何?證據?
- 若單一依賴失效,系統如何退化仍滿足業務最小價值?
- 哪些假設若被推翻,設計需如何重構?
```

(依據 IEEE 1016 的 SDD 內容組織。([IEEE Standards Association][3]))

**RoomPilot 套用**:repo 既有樣式 `03-architecture-design-doc`。提示語範例:「以 SDD 描述 `POST /api/scene/generate` 場景生成管線,介面契約以 `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md` 為準」。已查證落點:FastAPI app 定義於 `backend/server/main.py:144`;路由共 44 條全在 `main.py`、無 APIRouter 拆分(grep 實測);正式契約 6 份在 `docs/contracts/`(實測 `ls`)。

---

### 2.2 DDD — 聚合與界限脈絡

```md
---
name: ddd-backend-aggregate
description: "Eric Evans DDD 風格的後端設計輸出;聚合、不變量、事件與倉儲。"
---
# 指令(你是領域建模教練)
輸出以 DDD 為核心的設計產物;明確「語境(Ubiquitous Language)」、聚合邊界與不變量,避免貧血模型。

## 交付結構
1. **界限脈絡**:名稱、目標、與其他脈絡的關係(Context Map)
   (RoomPilot 例:選件決策=backend/agent、幾何擺位=backend/engine、型錄=backend/catalog;
    agent 只決定選品與修復策略、絕不算座標,座標一律由 engine 產生)
2. **語彙表**:核心名詞與定義、反例澄清
   (RoomPilot 例:族系 family、主件/副件 companion、淨空 clearance、公分制 cm)
3. **聚合**(每個):
   - 聚合根、成員實體/值物件
   - **不變量**與交易邊界(需可測試)
     (RoomPilot 例:副件不得脫離主件 COMPANION_OF;每房最多 8 種 MAX_ITEMS_PER_ROOM;
      單品數量夾在 1..6 COUNT_MAX;必要族系 REQUIRED_FAMILIES_BY_ROOM——bedroom 必有 bed、
      living_room 必有 sofa、dining_room 必有 dining-table+dining-chair)
   - 允許操作(命令)與觸發之**領域事件**
   - 倉儲介面(擷取、儲存)
4. **應用服務**:用例流程、跨聚合協作
5. **反腐層(ACL)**:與外部/舊系統的轉換策略
6. **測試策略**:以事件與不變量為核心的單元/整合測試(RoomPilot 例:tests/test_agent_select.py 17 個測試)

## 蘇格拉底檢核
- 此聚合的**唯一交易邊界**是什麼?違反時會出現什麼不一致?
- 事件命名是否貼合業務語彙?是否描述過去已發生的事?
- 哪個規則是**不變量**而非流程慣例?如何破壞性驗證?
```

(聚合與交易邊界定義根據 Evans 參考手冊。([Domain Language][4]))

**RoomPilot 套用**:repo 既有樣式 `04-ddd-aggregate-spec`。已查證落點:宣告式知識單一事實來源在 `backend/agent/knowledge.py`(`FAMILY_OF`/`COMPANION_OF`/`ROOM_AFFINITY`/`ANCHOR_FAMILIES`/`GROUP_OF`,實測讀檔);不變量常數在 `backend/agent/select.py:25-27`(`MAX_ITEMS_PER_ROOM = 8`、`COUNT_MAX = 6`、`REQUIRED_FAMILIES_BY_ROOM`);測試數以 `grep -c "def test_"` 實測(select 17、placement 18、clearance 10)。

---

### 2.3 資料庫綱要 — 實體設計與演進

```md
---
name: database-physical-schema
description: "資料庫實體綱要設計;輸出 ERD、DDL、索引策略與查詢模式。"
---
# 指令(你是經驗豐富的資料庫管理員)
以 DDD 聚合為基礎,輸出具體的資料庫實體設計。優先考量資料完整性、查詢效能與未來演進的彈性。

## 交付結構
1. **邏輯模型對應**:說明 DDD 聚合/實體如何映射至資料表。
2. **實體關係圖 (ERD)**:使用 Mermaid 語法描述資料表關聯。
3. **資料表定義 (DDL)**:提供 PostgreSQL 的 `CREATE TABLE` 語法,包含欄位、型別、約束(主/外鍵、唯一、非空)。
   (RoomPilot 現行三張表:catalog_items、glb_assets、catalog_import_batches)
4. **索引策略**:基於主要查詢模式,提供 `CREATE INDEX` 語法並解釋其取捨。
5. **查詢模式與優化**:列出關鍵查詢的 SQL 範例,並說明綱要如何支援其效能。
   (RoomPilot 例:view official_furniture_with_glb 以 JOIN + upload_status 白名單過濾,匯入後驗證 count 必須 = 9350)
6. **資料演進計畫**:描述綱要變更的遷移腳本策略。
   (RoomPilot 現行:importer 單一交易 UPSERT,--dry-run 只驗證不連庫、--prune-extra 才清除官方集合外資料、預設非破壞)

## 蘇格拉底檢核
- 此綱要正規化程度為何?在什麼情境下會考慮反正規化?
- 索引是否會過度影響寫入效能?是否有更合適的索引類型?
- 如何處理大規模資料的清除或封存?
```

**RoomPilot 套用**:repo 既有樣式 `09-database-schema-spec`。已查證落點:`scripts/sql/roompilot_postgresql_schema.sql` 有 3 張表、9 個索引、1 個 view(grep 實測);importer 為 `scripts/sql/import_official_catalog_to_postgres.py`,dry-run 期望診斷值在 `scripts/sql/README.md:25-29`。注意:PostgreSQL 目前只到 importer 階段,伺服器執行期不連 Postgres,另有兩個執行期 SQLite——專案存檔 `.runtime/projects.sqlite3`(`backend/server/project_store.py`)與問卷視覺索引(`backend/server/questionnaire_visuals.py`);Postgres 接上 API 的後續計畫未在程式中見到(未查證)。

---

### 2.4 後端實作 — Python/FastAPI 程式碼生成

````md
---
name: backend-impl-python
description: "基於 DDD 與資料庫綱要設計,生成 Python/FastAPI 實作程式碼骨架。"
---
# 指令(你是資深 Python 後端架構師)
讀取 `ddd-backend-aggregate` 與 `database-physical-schema` 的產出,生成符合本專案分層紀律的
Python/FastAPI 程式碼骨架。程式碼需包含型別提示,長度單位一律公分,並將職責清晰分離。

## 交付結構(RoomPilot 實際包結構;模板原版的 Clean Architecture 目錄為理想型,本專案以下列現況為準)
```
backend/
├── server/      # FastAPI 入口(main.py 單檔 44 條路由,無 APIRouter)+ static/ 前端頁
├── agent/       # 選件與擺位修復決策(純 stdlib,不算座標、不碰網路、不依賴 server)
├── engine/      # 幾何、碰撞、淨空(shapely;dataclass 公分制,原點=平面圖左下角)
├── floorplan/   # PNG 辨識(vision/)與 PNG→DXF(floorplan2dxf.py)
├── upgrade3d/   # DXF 解析(dxf_parser.py)
└── catalog/     # 型錄載入與引擎轉接層(style_db.py、cloud_catalog.py)
```

## 生成內容
1. **決策層(backend/agent)**:只輸出選品、順序與修復策略;LLM 呼叫器以 callable 注入,
   失敗拋例外讓呼叫端降級本地規則,絕不在此層算座標。
2. **幾何層(backend/engine)**:dataclass 模型(models.py)+ Shapely 碰撞(geometry.py)+
   淨空(clearance.py);對外序列化含 schema_version 與 coordinate_unit='cm'(schema.py)。
3. **持久層(backend/server/project_store.py)**:SQLite + 樂觀鎖 revision,衝突回 409。
4. **展示層(backend/server/main.py)**:FastAPI 路由,錯誤語意沿用既有詞彙
   (409/413/415/422/410),回應附既有欄位形狀。
5. **依賴宣告**:新依賴進 pyproject.toml 對應 extra(server/vision/ocr/catalog),用 uv sync 安裝。

## 蘇格拉底檢核
- 是否遵守依賴反轉:agent 層是否仍不依賴 server 與網路?engine 是否仍不知道 HTTP?
- 領域模型是否保持純淨,不含任何資料庫或框架相關的程式碼?
- 錯誤處理是否清楚區分業務規則錯誤(如 SelectionParseError)與基礎設施錯誤
  (如 SelectionUnavailableError → 降級本地規則)?
````

**RoomPilot 套用**:repo 既有樣式 `10-backend-python-impl`。已查證落點:`backend/agent/__init__.py` docstring 宣告「座標一律由 backend.engine 計算」;`SelectionParseError`/`SelectionUnavailableError` 定義於 `backend/agent/select.py:34,38`;`backend/engine/schema.py:21-22` 輸出 `schema_version: "2.0"`、`coordinate_unit: "cm"`;pyproject extras(server/vision/ocr/catalog)與 dev 群組 `pytest>=9.1.1` 實測讀檔。

---

### 2.5 API First — 合約即真相

```md
---
name: api-first-contract
description: "API 合約輸出;OpenAPI/JSON Schema、錯誤語意、版本與相容性準則。"
---
# 指令(你是 API 契約設計師)
以契約為中心輸出:OpenAPI(sync)或事件 Schema(async);標示錯誤碼與語意、相容性規則(Backward/Forward)。

## 交付結構
- **OpenAPI**:路由、模型、狀態碼與錯誤語意、範例
- **錯誤策略**:可重試與不可重試分類、冪等性說明
  (RoomPilot 既有詞彙:409 project_revision_conflict 樂觀鎖衝突、409 floorplan_confirmation_required、
   413 workflow_too_large(2MB 上限)、415 unsupported_floorplan_type、422 驗證失敗、
   410 = cloudfront 模式下本機 glTF 拆解端點已停用、502/503 = 渲染供應商拒絕/未設定;
   冪等:渲染工作 POST 附 Idempotency-Key 標頭)
- **版本策略**:URL/標頭/Schema 版本、棄用流程(RoomPilot 慣例:payload 帶 schema_version 欄位)
- **合約測試**:提供 Provider/Consumer 驗證腳本骨架
  (RoomPilot 例:tests/test_project_workflow_api.py、tests/test_floorplan_vision_api.py、
   tests/test_remote_render_workflow.py)
- **安全**:身分、授權、稽核欄位;對外送出前剝除私人欄位(who/when/why)

## 蘇格拉底檢核(補)
- 新錯誤碼是否重用既有詞彙?前端是否已有對應處理?
- 欄位變更是否同步 docs/contracts/ 對應契約?
```

**RoomPilot 套用**:repo 既有樣式 `05-api-contract-spec`。已查證落點:`floorplan_confirmation_required` 在 `backend/server/main.py:1805`;`Idempotency-Key` 在 `backend/server/render_service.py:133`;渲染供應商未設定拋 `render_provider_not_configured`(`render_service.py:128`),503/502 語意見 `docs/contracts/REMOTE_RENDER_CONTRACT.md`;三個 API 測試檔名以 `ls tests/` 實測。FastAPI 內建 OpenAPI 文件頁(`/docs`)是否可正常瀏覽,本次未啟動伺服器驗證(未查證)。

---

### 2.6 BDD — 可執行規格(Gherkin)

```md
---
name: bdd-feature-spec
description: "Gherkin 可執行規格模板;Given/When/Then + 參數化範例與步驟骨架。"
---
# 指令(你是 BDD 引導者)
產出 Feature 檔與步驟綁定骨架;所有句子以業務語彙撰寫,避免 UI 細節綁定。

## 交付結構
**Feature:** <名稱>
**Background:**(必要時)
**Scenario Outline:** <行為>
  Given <前置條件>
  When <觸發>
  Then <可驗收結果>
**Examples:**(表格)

## RoomPilot 範例(平面圖辨識)
**Feature:** 平面圖辨識
**Scenario:** 已確認上傳圖後才能辨識
  Given 專案已建立且已上傳 DXF 平面圖
  And workflow.floorplan_confirmation.confirmed 為 true
  When POST /api/projects/{id}/floorplan/analyze
  Then 回應 200,analysis 帶 geometry_engine="dxf"
**Scenario:** 未確認前禁止辨識
  Given 專案已上傳平面圖但尚未確認
  When POST /api/projects/{id}/floorplan/analyze
  Then 回應 409 且 code 為 "floorplan_confirmation_required"

## 步驟骨架
- `Given …`(建資料/狀態)
- `When …`(觸發行為)
- `Then …`(驗證可觀測結果與不變量)

## 蘇格拉底檢核
- 這是**業務語言**還是實作細節?
- 結果是否可觀測、可重現?資料驅動是否覆蓋反例?
```

(Gherkin 關鍵詞與結構依 Cucumber 官方文檔。([cucumber.io][6]))

**RoomPilot 套用**:repo 既有樣式 `02-bdd-scenario-spec`。寫主流程場景時,步驟順序一律以程式碼為準——`backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS` 共 11 個有序內部步驟(實測讀檔):`project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render`(recognition 與 calibration 共用同一 scale 面板,UI 顯示 10 顆步驟按鈕)。不要沿用任何舊文件的步驟順序。

---

### 2.7 TDD — 函式級單元(Red→Green→Refactor)

```md
---
name: tdd-unit-function
description: "以 TDD 最小步驟落地單一函式;先測試清單,再紅綠重構,含邊界與性質測試。"
---
# 指令(你是 TDD 導師)
輸出【測試清單】→【最小紅】→【最小綠】→【重構】的循環;每步驟都最小化修改面積。

## 交付結構
1. **測試清單**:正常例、邊界例、錯誤例、隨機性/性質測試(若適用)
   (RoomPilot 例——擺位驗證:出界、撞牆、撞家具、淨空區撞他人本體、我方本體壓他人淨空)
2. **第一個測試(紅)**:最小可失敗測試
3. **最小實作(綠)**:僅滿足當前測試
4. **重構**:提煉命名、去重、純化副作用;保留綠色
5. **循環**:挑下一測試;直至涵蓋清單

## 函式契約(RoomPilot 真實範例)
- 簽名:`check_placement_with_clearance(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`
  (backend/engine/clearance.py;回傳 None = 合法,否則為繁中拒絕原因字串)
- 前置/後置條件:輸入輸出一律公分、原點=平面圖左下角、rotation 為逆時針度數
- 跑法:`uv run pytest tests/test_clearance.py -q`(10 個測試)、`uv run pytest tests/test_placement.py -q`(18 個測試)

## 蘇格拉底檢核
- 這個測試是否**唯一**驅動了設計?
- 是否有更小步驟能失敗?是否太貪心?
- 重構是否改善設計而未更動行為?
```

(循環與原則依 TDD 經典流程。([martinfowler.com][5]))

**RoomPilot 套用**:repo 既有樣式 `06-tdd-unit-spec`。已查證落點:函式定義於 `backend/engine/clearance.py:89`,docstring 自述「本體碰撞 + 淨空檢查的總入口」;座標契約(公分、左下原點、逆時針)出自 `backend/engine/models.py`;測試數以 `grep -c "def test_"` 實測。

---

### 2.8 前端元件 — 行為優先 + 互動測試

```md
---
name: frontend-component-bdd
description: "以行為描述元件;輸出 Stories(案例)、互動/可近用測試骨架。"
---
# 指令(你是前端資深工程師)
以「使用者行為」描述元件;輸出行為案例與互動測試,避免過早耦合實作細節。

## 交付結構
1. **元件說明**:目的、可視狀態、不可視狀態、Props/Events
2. **行為案例(Stories)**:主要流程、例外流程、邊界(空資料/Loading/Error)
   (RoomPilot 真實範例——frontend3d 家具擺放層 Furniture.jsx:
    點擊放置 ghost 家具、Shift+點擊連續放置、R 旋轉 90 度、Delete/Backspace 刪除、Esc 取消)
3. **互動測試**:點擊/輸入/快捷鍵;可近用檢查(Role/Name/State)
4. **可測性設計**:把純邏輯抽離渲染層
   (RoomPilot 範例:snap.js 吸附幾何刻意不 import three,以便在純 node 環境單測——檔頭註解明言)

> 技術棧(frontend3d,package.json 實測):React 18.3 + @react-three/fiber 8 + @react-three/drei 9
> + three 0.160.1 + Vite 8;dev server 以 vite.config.js 把 /api 代理到 http://localhost:8002。
> Storybook 未安裝,互動測試工具待補。
```

(對應 Storybook 的互動/元件測試能力。([Storybook][7]))

**RoomPilot 套用**:repo 既有樣式 `11-frontend-component-bdd`。已查證落點:快捷鍵行為在 `frontend3d/src/Furniture.jsx:187-202`(Escape/R/Delete/Backspace)與 `:253`(shiftKey 連續放置);`snap.js` 檔頭註解「no three.js import so it can be unit-tested in plain node」。注意雙前端現況:現行主前端是 `backend/server/static/` 的無框架靜態頁(`scene_v2.js` 8,544 行,`wc -l` 實測),`frontend3d/` 是獨立 Vite 子專案;新元件要先確認落在哪一邊。

---

### 2.9 跨系統整合 — 同/非同步契約與合約測試

```md
---
name: integration-contract-suite
description: "整合測試視角;同步 REST 與外部供應商契約、Provider/Consumer 驗證與失效注入。"
---
# 指令(你是整合測試設計者)
產出跨系統合約的規格與測試骨架;為每個介面提供 provider/consumer 測試與失效注入案例。

## 交付結構
- **合約索引**:端點/事件 → 版本 → 擁有者
  (RoomPilot 三條外部邊界:
   1. 遠端渲染供應商 — docs/contracts/REMOTE_RENDER_CONTRACT.md;
   2. OpenRouter LLM — 需求 intake 與場景規劃兩個獨立開關;
   3. CloudFront GLB 交付 — docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)
- **REST**:規格 + 範例請求/回應 + 錯誤語意
- **合約測試**:Provider/Consumer 測試腳本骨架與流水線步驟
- **Failover 案例**:超時、降級、冪等重做
  (RoomPilot 實例:渲染供應商未設定回 503、拒絕回 502、timeout 由
   ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS 控制(預設 60 秒);
   LLM 未設定或失敗必須降級本地規則,回應標明 fallback 來源;
   cloudfront 模式下本機 glTF 拆解端點一律 410)

## 環境變數(RoomPilot 實例)
- 渲染:ROOMPILOT_RENDER_PROVIDER_URL / _TOKEN / _NAME / _TIMEOUT_SECONDS
- LLM:OPENROUTER_API_KEY + OPENROUTER_INTAKE_ENABLED=1(intake)、OPENROUTER_SCENE_PLANNING_ENABLED=1(場景規劃)
- GLB:ROOMPILOT_MODEL_DELIVERY_MODE(預設 cloudfront)、ROOMPILOT_CLOUDFRONT_BASE_URL、ROOMPILOT_GLB_MANIFEST_PATH
```

**RoomPilot 套用**:repo 既有樣式 `12-integration-contract-suite`。已查證落點:渲染 env 讀取在 `backend/server/render_service.py:34,42-44`,私人欄位剝除清單 `PRIVATE_KEYS` 亦在該檔;`OPENROUTER_INTAKE_ENABLED` 在 `backend/server/intake_service.py:138`(預設模型 `qwen/qwen3-32b:free`);`OPENROUTER_SCENE_PLANNING_ENABLED` 在 `backend/server/scene_service.py:80,87,264`;CloudFront 預設 base URL 與模式在 `backend/server/services/cloud_models.py`。整合測試範例:`tests/test_remote_render_workflow.py`、`tests/test_cloud_models.py`(檔名 `ls` 實測)。

---

### 2.10 數據契約與演進

```md
---
name: data-contract-evolution
description: "資料模式治理;Schema 演進策略、相容性矩陣、稽核與漂移偵測。"
---
# 指令(你是數據架構師)
輸出 Schema 與演進規則;提供稽核欄位、漂移告警與測試資料集生成指南。

## 交付結構
- **Schema vN**:欄位語意、單位、缺漏值策略
  (RoomPilot 實例:雲端型錄 furniture_catalog_cloud_9350.json schema_version "2.0"、count 9350;
   場景物件序列化 schema_version "2.0" + coordinate_unit "cm";全系統長度單位=公分)
- **演進策略**:向後/向前相容性、棄用/移除流程
  (RoomPilot 實例:正式家具集合由雲端 JSON + manifest CSV 一對一決定,
   數必須恰為 9,350、ID 集合完全一致、upload_status 走白名單,否則載入即 raise ValueError;
   舊六風格型錄只能補 enrichment(9,021 件),不能新增家具;無法映射的 1,514 筆進隔離區,
   網頁/Agent/3D 不得直接讀取隔離目錄)
- **稽核/可觀測性**:who/when/lineage、抽樣比對與容忍度
  (RoomPilot 實例:GET /api/catalog/status 回報 manifest 健康度與 verified_model_count)
- **測試資料**:合成/脫敏規範、極端值集
```

**RoomPilot 套用**:repo 既有樣式 `13-data-contract-evolution`。已查證落點:`schema_version "2.0"`/`count 9350` 在 `backend/catalog/data/furniture_catalog_cloud_9350.json` 檔頭(實測);強制驗證邏輯在 `backend/catalog/cloud_catalog.py`(`OFFICIAL_CATALOG_COUNT = 9_350`);9,350/9,021/329/1,514 數字組在 `scripts/sql/README.md:25-29`(實測);隔離守門測試 `tests/test_cloud_quarantine.py`;引擎序列化在 `backend/engine/schema.py:21-22`。

---

### 2.11 架構/程式碼審查守門

```md
---
name: reviewer-architect-guard
description: "架構與程式碼走查清單;聚焦複雜度、邊界、回歸風險與安全。"
---
# 指令(你是嚴格但友善的 Reviewer)
逐條產出結論/風險/修正建議,鏈接到 SDD/DDD/合約或測試證據。

## 走查清單(RoomPilot 化節錄)
- 邊界是否清晰?agent 層是否越界計算座標(紀律:座標一律 backend.engine)?
- 單位是否公分?單位轉換是否只發生在既定邊界
  (DXF 公尺→公分:backend/engine/dxf_room.py;PNG 管線:canonicalize_analysis_cm)?
- 不變量是否由測試守護?例外是否可觀測?
- 合約是否可版本化?欄位/行為變更是否同步 docs/contracts/ 對應契約?
- 錯誤語意是否沿用既有詞彙(409/410/413/415/422/502/503)而非自創?
- 測試證據:uv run pytest 是否綠燈?新行為有無對應測試?
- LLM 相關:失敗是否降級本地規則而非硬失敗?回應是否標明來源(openrouter/local_rules)?
```

**RoomPilot 套用**:repo 既有樣式 `07-code-review-checklist`。已查證落點:單位邊界 `backend/engine/dxf_room.py`(×100)與 `backend/floorplan/vision/units.py` 的 `canonicalize_analysis_cm`;選件來源標記 `openrouter`/`local_rules`/`local_rules_unvalidated` 出自 `POST /api/agent/furniture/select`(`backend/server/main.py:2220` 起)。

---

### 2.12 CI/CD 品質柵欄(搭配 Hooks)

```md
---
name: ci-quality-gates
description: "把品質門檻寫進流水線;覆蓋率、靜態分析、合約與 E2E 必通。"
---
# 指令(你是 DevEx 工程師)
輸出 CI 階段與條件;對未達標的情境提供自動化修正建議/指令。

## 交付結構
- **Stages**:Lint → Unit → Contract → Integration → E2E → Perf/Chaos
- **門檻**:Coverage、Lint/Type Check、Contract Tests 全通、金路徑 E2E
- **Artifacts**:合約報告、基準數據、回歸矩陣
- **Hook 範例**:提交後自動格式化/阻擋敏感檔變更/通知

## RoomPilot 現況(2026-07-26 實測)
- repo 無 .github/、無任何 CI 流水線;品質柵欄 = 本機 `uv run pytest tests/`
  (47 個測試檔、392 tests collected;通過率本次未執行,未查證)。
- .claude/hooks/ 已有 post-write.sh、pre-tool-use.sh、session-start.sh 等腳本,但 .claude/ 不入版控。
- Lint/型別檢查工具(ruff/mypy 等)未列於 pyproject.toml,未導入。
- 待補:CI 平台選型、覆蓋率門檻數值、合約測試在流水線的強制點。
```

(將不可或缺的動作用 hooks 自動化以「保證」執行。([docs.claude.com][2]))

**RoomPilot 套用**:repo 既有樣式 `14-ci-quality-gates`。已查證落點:`.github/` 不存在、`.claude/hooks/` 內容、`pytest --collect-only -q` 回報 392 tests,均為 2026-07-26 實測。

---

## 3. 前/後端與跨系統的「風格建議」(RoomPilot 版)

* **設計與實作流程**:建議採 `03-architecture-design-doc` → `04-ddd-aggregate-spec` → `09-database-schema-spec` → `10-backend-python-impl` → `05-api-contract-spec` 的順序,由宏觀到微觀;RoomPilot 的既有邊界(agent 決策/engine 幾何/公分制)是每一步的硬約束,不因樣式切換而放寬。
* **前端開發**:以 `11-frontend-component-bdd` 為核心,用行為案例描述元件;先分清目標是 `backend/server/static/` 靜態頁還是 `frontend3d/` Vite 子專案。互動測試工具(Storybook 等)待補。([Storybook][7])
* **後端開發**:以 `06-tdd-unit-spec` 實踐紅綠重構;幾何與擺位函式(`backend/engine/`)是最高價值的 TDD 對象,證據一律 `uv run pytest`。
* **整合與演進**:使用 `12-integration-contract-suite` 與 `13-data-contract-evolution` 守護三條外部邊界(遠端渲染/OpenRouter/CloudFront)與 9,350 件型錄契約。
* **品質保證**:透過 `07-code-review-checklist` 進行人工審查;`14-ci-quality-gates` 目前只能描述目標狀態,因 repo 尚無 CI(實測)。
* **Claude Code 操作**:`/output-style` 切換樣式;`/hooks` 建立格式化/檔案保護/通知。([docs.claude.com][1])

---

## 4. 最小可行落地(RoomPilot 版)

1. **樣式已就位,不需重建**:`.claude/output-styles/` 已有 15 個樣式檔(實測);要修訂或新增時以本文件第 2 節模板為底稿。
2. `/output-style 03-architecture-design-doc`,先把場景生成管線(`POST /api/scene/generate` → `build_scene_payload`)「說清楚」,生成第一版 SDD。
3. 換 `/output-style 04-ddd-aggregate-spec`,對照 `backend/agent/knowledge.py` 與 `select.py` 的既有不變量,把選件聚合拉齊。
4. 再用 `/output-style 09-database-schema-spec`,對照 `scripts/sql/roompilot_postgresql_schema.sql` 檢視三張表與 view 的演進計畫。
5. 接著用 `/output-style 10-backend-python-impl`,生成骨架時遵守 agent/engine 分界與公分制。
6. 最後 `/output-style 06-tdd-unit-spec`,挑一個高風險函式(例:`check_placement_with_clearance`),用紅綠重構把不變量守起來。([martinfowler.com][5])
7. Hooks:`.claude/hooks/post-write.sh` 已存在;把樣式與 hooks 納入版控供團隊共享,屬 `.gitignore` 裁決事項,待補。([docs.claude.com][2])

---

## 5. 參考來源(精選)

* Claude Code 官方:**Output Styles** 說明與檔案位置、`/output-style` 指令。([docs.claude.com][1])
* Claude 工程部落格:**最佳實務與工作流**。([anthropic.com][8])
* IEEE Std 1016:**SDD 結構與資訊內容**。([IEEE Standards Association][3])
* DDD:Evans **Reference**(聚合、不變量、界限脈絡)。([Domain Language][4])
* TDD:Fowler **Red-Green-Refactor**。([martinfowler.com][5])
* BDD/Gherkin:Cucumber 官方文件。([cucumber.io][6])
* 前端測試:Storybook 元件/互動測試。([Storybook][7])
* RoomPilot 內部正本:`docs/contracts/`(6 份契約)、`docs/RoomPilot_現行版本總覽.md`、`.claude/output-styles/README.md`(樣式選用指南)。

---

# 心法內化(像 5 歲小孩也懂)

把蓋房子想成三件事:**先畫藍圖(SDD)**,**再決定每個房間的規則(DDD)**,**最後拿尺量一量做對了沒(BDD/TDD)**;每次動工前,**換一種帽子(Output Style)**,就會說出正確的話、做對的事。RoomPilot 剛好就是在幫使用者「蓋房間」——樣式切換的每一步,都對應平面圖→規則→驗證的同一套思路。

# 口訣記憶(3 點)

1. **先邊界,後行為,再函式**(SDD/DDD → BDD → TDD)
2. **樣式即流程**(`/output-style` 固化觀點,`/hooks` 強制執行)
3. **證據說話**(合約在 `docs/contracts/`、測試用 `uv run pytest`,避免口號)

[1]: https://docs.claude.com/en/docs/claude-code/output-styles "Output styles - Claude Docs"
[2]: https://docs.claude.com/en/docs/claude-code/hooks-guide "Get started with Claude Code hooks - Claude Docs"
[3]: https://standards.ieee.org/ieee/1016/4502/ "IEEE 1016-2009 - Systems Design"
[4]: https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf "Domain-Driven Design Reference"
[5]: https://martinfowler.com/bliki/TestDrivenDevelopment.html "Test Driven Development"
[6]: https://cucumber.io/docs/gherkin/reference/ "Reference"
[7]: https://storybook.js.org/docs/8/writing-tests/component-testing "Component tests | Storybook docs - JS.ORG"
[8]: https://www.anthropic.com/engineering/claude-code-best-practices "Claude Code: Best practices for agentic coding"
