---
name: roompilot-security
description: RoomPilot 專屬資安工程 skill — 自我確認、補充、加強。掃描 RoomPilot 實際攻擊面（FastAPI 八步工作流、專案保存、SSRF、家具模型交付、PostgreSQL catalog），對照已知風險基線，產出可修的補強。當觸碰 backend/server、新增端點、處理上傳/URL 抓取/DB 查詢/秘密，或使用者要求資安審查時使用。
origin: RoomPilot-Agent 專案原生
---

<!-- 繁中：本 skill 是 RoomPilot 目前唯一的資安工程邏輯來源。泛用 OWASP 知識載入 sunnydata-security；本檔提供貼合本 repo 實際程式碼的攻擊面地圖、已知風險基線、自我稽核腳本與本技術棧修補範式。 -->

# RoomPilot Security

> 基線規則：`.claude/rules/security.md`（每次 commit 前必檢）
> 泛用 OWASP 分類與跨語言清單：載入 `sunnydata-security`
> 本 skill 專責：**RoomPilot 這個 repo 的實際攻擊面**與可執行的補強

## 這個 skill 存在的理由

RoomPilot 目前 **沒有任何內建資安工程邏輯**：全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線。本 skill 把資安變成 repo 的一等公民：

- **自我確認**：`audit.sh` 靜態掃描實際程式碼型態，抓回歸與新風險。
- **補充**：把缺的防護（授權依賴、SSRF allowlist、rate limit、安全標頭）以本技術棧的具體程式碼補上。
- **加強**：對照「已知風險基線」，逐項收斂 CRITICAL → HIGH → MEDIUM。

## 何時啟動

- 動到 `backend/server/`（main.py、project_store、render/cloud service、postgres_catalog、rag_api）
- 新增或修改 FastAPI 端點、上傳處理、檔案/URL 抓取、DB 查詢
- 處理秘密、憑證、`.env`、CloudFront/render provider token
- 使用者要求資安審查、威脅建模、上線前檢查
- 準備 commit/PR 前的最後一道靜態關卡

---

## 鐵律：先讀邊界，尊重 owner

RoomPilot 是多 owner 協作 repo。動手前先讀 `AGENTS.md` 與 `docs/TEAM_AI_OWNERSHIP.md`。資安修補**不能**繞過所有權：

| 攻擊面所在 | Owner | 資安修補方式 |
| :--- | :--- | :--- |
| `backend/server/`（端點、保存、交付） | Bella | 授權依賴、SSRF、rate limit、標頭在此加 |
| `backend/catalog/`、`scripts/sql/`、`postgres_catalog.py` DB 存取 | Kai | SQL 參數化、sslmode、憑證處理需與 Kai 確認 |
| `backend/floorplan/` 影像/DXF 解析 | Cody | 解析器資源上限、惡意檔防護 |
| `backend/engine/` 幾何合法性 | Ancai | 不在資安範圍，勿改領域邏輯 |
| `backend/agent/` LLM 意圖 | Yen | prompt injection、輸出信任邊界 |

跨 owner 的資安修補，用 `AGENTS.md` 的「跨資料夾修改」格式記錄，兩端測試都要過。**不得**把幾何/合法性判定移到別處，也不得以前端 fallback 悄悄取代後端演算法。

---

## RoomPilot 信任邊界與攻擊面地圖

```
[瀏覽器 static/*.js]  ──HTTP/JSON、multipart──▶  [FastAPI main.py :8000]  (信任邊界①：無認證)
                                                      │
        ┌─────────────────────────────────────────────┼──────────────────────────────┐
        ▼                         ▼                    ▼                              ▼
 [project_store 檔案系統]   [postgres_catalog]   [render_service httpx]      [家具模型交付]
  uploads/{project_id}/     roompilot view       ROOMPILOT_RENDER_*          urllib.urlopen(model_url)
  (信任邊界②：路徑)         (信任邊界③：SQL)     (外部 render provider)      (信任邊界④：SSRF/LFI)
        │                                                                          │
        └── LLM: OpenRouter / OpenAI（intake_service, scene_service）──────────────┘
             (信任邊界⑤：外送 payload + prompt injection)
```

**進入點（49 條路由）**，安全敏感者：
- `POST /api/projects/{project_id}/floorplan` — DXF/PNG/JPG 上傳（main.py:1783）
- `POST /api/projects/{project_id}/renders` — PNG 上傳，20MB 上限 + magic bytes（main.py:1850）
- `POST /api/projects/{project_id}/render-jobs` — 提交外部 render（main.py:1946）
- `POST /api/upload`、`POST /api/floorplan/analyze` — DXF/影像 + OCR（main.py:2925/2955）
- `GET /api/furniture/{id}/model|model.gltf|buffer.bin|images/{i}` — 模型/貼圖交付（main.py:2861+）
- `POST /api/rag/search[/jobs]` — RAG 檢索（rag_api.py:169+）

---

## 已知風險基線（RoomPilot 目前狀態快照）

> 這是稽核的對照基準。每次審查先確認這些是否被處理或惡化；`audit.sh` 會自動覆蓋大部分。
> 檔案行號可能隨開發位移，發現不符時以實際程式碼為準並更新本表。

| # | 風險 | 位置 | OWASP | 嚴重度 | 現況 |
| :-- | :--- | :--- | :--- | :--- | :--- |
| R1 | **全端點無認證/授權**，任何人可讀寫任一 `project_id`（IDOR） | main.py 所有 `/api/projects/*` | A01/A07 | **CRITICAL** | 未處理 |
| R2 | **SSRF/LFI**：`_remote_glb_response` 用 `urllib.urlopen(model_url)` 無 scheme allowlist；urllib 會解析 `file://` | main.py:1019-1036 | A10 | **HIGH** | 未處理 |
| R3 | **DB 明文連線**：`DB_SSLMODE` 預設 `"disable"` | postgres_catalog.py:96 | A02/A05 | HIGH | 未處理 |
| R4 | **無 rate limiting / CORS 政策**，上傳與 LLM 端點可被濫用 | main.py:168 | A04 | MEDIUM | 未處理 |
| R5 | **例外文字回傳 client**：`detail=f"...{exc}"` | main.py:1031 等 | A09 | MEDIUM | 未處理 |
| R6 | **`/docs`、`/openapi.json` 預設公開**（無 auth 下曝露完整攻擊面） | main.py:168 | A05 | MEDIUM | 未處理 |
| R7 | **`ROOMPILOT_CATALOG_ADMIN_TOKEN`** 宣告於 .env.example 但 backend 未強制（死設定或漏驗證） | .env.example | A05 | MEDIUM | 待確認 |
| R8 | f-string SQL 型態（目前 view 為 hardcoded，**安全**，但屬易被複製的危險範式） | postgres_catalog.py:215 | A03 | LOW | 監控回歸 |

**已達標、須維持的良好基線（不要弄壞）：**
- 上傳檔名用 `Path(...).name` 取 basename、副檔名白名單、size 上限、PNG magic bytes（main.py:1790+）。
- `project_id` 為 UUID，路徑組裝安全（project_store.py）。
- SQL 皆參數化或 hardcoded view，無注入。
- 無 `pickle`/`eval`/`exec`/`os.system`/`subprocess`（零基線）。
- 秘密皆由 `os.getenv` / `.env` 讀取，無硬編碼；`.env` 已 gitignore。

---

## 自我確認工作流（每次審查跑這個）

### 1. 執行靜態自我稽核

```bash
bash .claude/skills/roompilot-security/audit.sh            # 全 backend 掃描
bash .claude/skills/roompilot-security/audit.sh --staged   # 只掃 staged 差異（commit 前）
```

輸出 PASS / WARN / FAIL：
- **FAIL** → 提交前必修（新增 f-string SQL、危險呼叫、硬編碼秘密、`.env` 被追蹤）。退出碼 1。
- **WARN** → 逐項判讀，對照上方基線；若是已知未處理項，在 PR 說明處置或建立追蹤 issue。

### 2. 手動審查（audit.sh 補不到的語意層）

- [ ] 新端點是否需要授權？有無 IDOR（用別人的 `project_id`）？→ 見 R1、remediation「端點授權」
- [ ] 新的外部抓取，URL 來源可信嗎？只允許 https？擋掉 file/ftp/內網？→ R2、remediation「SSRF/LFI」
- [ ] 動到 `scene_json`/`layout_json` 契約時，公分制 payload 兩端測試是否同步（AGENTS.md 契約）
- [ ] LLM 送出的 payload 是否夾帶未清理的使用者輸入？回應是否被當可信資料直接執行？→ 信任邊界⑤
- [ ] 錯誤訊息是否洩漏內部路徑、SQL、堆疊？→ R5

### 3. 分層修補（補充 / 加強）

依序處理，一次一個 finding，改完立刻驗證不要回歸：
1. **Classify** — 對照基線給 R# 或新編號 + OWASP + 嚴重度。
2. **Fix** — 載入 `references/remediation.md` 取本技術棧安全範式，最小差異修補。
3. **Verify** — 跑對應 pytest + 重跑 `audit.sh`，確認 finding 消失且無新 WARN/FAIL。

---

## 修補範式索引

具體可貼上的 RoomPilot 技術棧安全程式碼在 `references/remediation.md`：

| 主題 | 對應風險 |
| :--- | :--- |
| 端點授權依賴（`require_project_access`）與 IDOR 防護 | R1 |
| SSRF/LFI 防護（urllib scheme + 內網 IP allowlist） | R2 |
| DB sslmode 與憑證衛生（需與 Kai 協作） | R3 |
| Rate limiting（slowapi）與安全回應標頭 | R4 |
| 安全錯誤處理（generic client 訊息 + server 詳記） | R5 |
| 生產環境關閉 `/docs`、`/openapi.json` | R6 |
| LLM prompt injection / 輸出信任邊界 | 信任邊界⑤ |

---

## 運作模式

| 模式 | 時機 | 動作 |
| :--- | :--- | :--- |
| **Secure-by-default** | 在 backend/server 寫新程式 | 主動套用 remediation 範式（授權依賴、SSRF allowlist、參數化 SQL） |
| **Passive self-check** | 動到既有程式 | 跑 `audit.sh`；FAIL 阻擋提交，WARN 對照基線判讀 |
| **Full report** | 使用者要求資安審查 | 跑 audit → 對照基線 → 依嚴重度排序報告 → 逐項提議修補 |

## 報告輸出

Full report 依 `.claude/rules/subagent-context.md`，若由 security-infrastructure-auditor 產出則寫入 `.claude/context/security/`。結構：
- 執行摘要（2-3 句：整體姿態 + 最高風險）
- 依嚴重度分組（Critical → High → Medium → Low），每項：R# / OWASP / 一句影響 / `file:line` / 建議修補
- 對照基線標示「新風險 / 惡化 / 維持 / 已改善」
- 從最高嚴重度開始逐一提議修補

## 驗證與退出標準

依 `AGENTS.md` 驗證矩陣。資安變更最低門檻：

```bash
bash .claude/skills/roompilot-security/audit.sh   # FAIL=0
python -m pytest -q                                # 對應模組測試綠燈
git diff --check                                   # 無空白/衝突殘留
```

- 涉及授權/端點 → 補測試：無憑證回 401、錯身分回 403、惡意輸入回 400/422。
- 涉及公分制契約 → 生產端與消費端測試都要過（AGENTS.md 鐵律）。
- 若某 WARN 為已知且本次不修，於 PR 明確記錄理由與追蹤項，不得靜默略過。
