# Ancai × Ben 分支整合指南

> **對象**：Ancai（你）要如何與目前的 `origin/ben` 整合  
> **基準日**：2026-08-04  
> **原則**：依 `AGENTS.md`——**禁止整包 merge**；只檢視後移植最小且相容的功能。

---

## 0. 一句話結論

把 **`origin/ben` 當產品主幹**（auth、路由工廠化、前端已搬到 `frontend/`），把 **Ancai 的引擎／擺位／旋轉／消失案修補** 當必須移植的功能島。  
用 **獨立 worktree + 分批 cherry-pick／手工移植**，不要 `git merge origin/ben` 進 `ancai`，也不要反向整包蓋過去。

---

## 1. 目前分叉快照（本機已有的 tip）

| 項目 | 值 |
|---|---|
| 你的分支 | `ancai` @ `5f564dfa`（2026-08-03 晚） |
| Ben tip | `origin/ben` @ `ee2cdd3d`（2026-08-03 午） |
| 共同祖先 | `5986f659`（2026-07-31） |
| 你有、Ben 沒有 | **56** commits |
| Ben 有、你沒有 | **71** commits |
| 與 Bella | `origin/bella` **是** `origin/ben` 的祖先（Ben 已吃進 Bella） |

上次整包式合併：`890a0c4e Merge origin/ben into ancai`（08-01，為解第 6 步阻斷）。  
那之後兩邊又各自往前衝——舊結論「已追上 Ben」**已過期**。

核對指令：

```bash
git fetch origin ben
git rev-parse --short ancai origin/ben
git merge-base ancai origin/ben
git rev-list --count origin/ben..ancai   # 你超前 Ben
git rev-list --count ancai..origin/ben   # Ben 超前你
```

---

## 2. 兩邊各自獨有什麼（整合優先序的依據）

### 2.1 Ben 獨有（產品／平台，你應視為「地基」）

| 主題 | 代表 commit／跡象 | 對你的意涵 |
|---|---|---|
| 前端目錄搬家 | `ca051dbc`：`backend/server/static` → repo 根 `frontend/` | 你在 `static/` 的所有修補都要**改路徑再移植** |
| 路由工廠化（佇列 7） | `0745dad8`…`0c3681f4`：`scene_api`／`projects_api`／問卷與候選集拆檔 | 不要再改巨大的 `main.py` 舊結構當主戰場 |
| Auth／JWT／專案角色 | `f904b36f`、`295fc447`、`79362558` | API 與截圖 blob 多半要帶身分；移植時注意 401 |
| 問卷→逐房候選集 | `061d2299`、`7589b2ec` | 第 6 步不再預設全庫掃；與你的 RAG 離線快取路線要對齊語意 |
| 辨識複核閘 | `e6279a24` | 第 3→4 步產品行為，整合時別踩掉 |
| 檯面小物宿主 | `332d619a`、`68ddc2cc` | 與碰撞／離地高度有關，移植引擎時一併看 |
| 一鍵啟動 | `ee2cdd3d` `dev.ps1` | 環境入口可能已變 |

### 2.2 Ancai 獨有（幾何／第 6 步正確性，Ben tip **沒有**）

| 主題 | 代表 | 風險若沒移植 |
|---|---|---|
| **擺放策略層整包** | `layout_strategy.py`、`layout_room.py`、`room_strategy/`、`clearance_defaults.py` | Ben tip 的 `backend/engine/` **沒有這些檔**——整包以 Ben 為底卻忘記帶回來＝策略層蒸發 |
| TV-first／companion／對面牆 | `c1ffbe9a`、`b05b59e0`、`3b2073ef` | 客廳同牆怪局、觀影距離回退 |
| 旋轉五層修補 | `0891d25d`…`6587dec9` | 「轉不動／被 90° snap 吃掉」回歸 |
| `model_orientation_deg` 白名單 | `908f86bd`、`f79cf30b` | 3D 反向案 |
| 床消失／假家具／死鍵 | `6b23213c`、`e4199f3f`、`b16f8801`、`9d7191fa` | 家具無聲消失 |
| RAG 離線快取＋階梯換小 | `555fce9f`、`bc383ce6` | 與 Ben「問卷候選集」是**兩條選件路徑**，需對齊誰優先 |
| 五表對齊／種子／問卷預設 | `e34997ad`、`0ba0aee2`、`5d354b84` | 房型策略 v1 前端不一致 |
| 稽核工具 | `4bd50243`、`63fe1c84` | 整合後失去回歸雷達 |

### 2.3 結構地雷（一定要先認清）

```text
ancai tip:
  backend/server/static/*.js     ← 你最近的 UI 修補都在這
  backend/engine/layout_strategy.py 等 ← Ben tip 沒有

ben tip:
  frontend/*.js                  ← 正式前端在這
  backend/server/static/         ← 幾乎清空／不再是主線
  backend/engine/                ← 只有基礎 placement/clearance，無策略層
```

`git diff --name-status ancai origin/ben -- backend/engine/` 會看到 Ben 側把策略層標成 **D（刪除）**——那是「相對 ancai 工作樹」的 diff 視角；意思是：**若以 Ben 為 checkout 基準，那些檔本來就不存在，必須由你主動加回。**

---

## 3. 正確做法 vs 禁止做法

### 禁止

- `git merge origin/ben` 進現行 `ancai`（預期大量衝突：`static`↔`frontend`、`main.py` 拆檔、engine 刪檔）
- `git merge ancai` 進 Ben 工作複本後不看 diff 整包推（違反團隊守則，且會蓋掉 Ben 的 auth／工廠化）
- 把 `frontend3d/` 或第二套 FastAPI 當整合載體
- 假設「engine `.py` 零衝突＝整庫安全」（08-01 經驗：engine 安靜、全庫仍可爆出數十個衝突）

### 建議流程（推薦）

```text
1. 保留 ancai 本機未提交變更（先 stash / 另開 worktree）
2. 從 origin/ben 開乾淨 worktree：ancai-port-on-ben
3. 分批移植 Ancai 功能島（先 engine，再 server adapter，再 frontend 對應檔）
4. 每批跑對應 pytest + 必要的瀏覽器 QA
5. 與 Ben 對過「誰推哪個分支／誰開 PR」後再合入 origin/ben 或 bella-test*
```

---

## 4. 建議操作步驟（可照抄）

### 4.1 開工前

```bash
git status --short          # 保留他人／自己未提交檔（目前有 notes、uv.lock、VibeCoding_* 等）
git fetch origin ben bella
```

讀完：

1. `AGENTS.md`、`docs/TEAM_AI_OWNERSHIP.md`
2. `docs/owners/ANCAI.md`、`docs/owners/BEN.md`
3. 本檔 + `backend/engine/notes/engine工作總帳.md` 明日優先序

### 4.2 開隔離 worktree（不要弄髒現行 `ancai`）

```bash
git worktree add ../RoomPilot-Agent-ben-port origin/ben
cd ../RoomPilot-Agent-ben-port
git switch -c ancai/port-engine-to-ben
```

本機 `.env` 若仍要跑第 6 步，依參考手冊確認（Ben 預設偏 postgres 嚴格時）：

```bash
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json
ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite
```

### 4.3 分批移植順序（由內而外）

每一批開始前在聊天／PR 寫清楚跨資料夾格式（見 §7）。

| 批次 | 帶什麼 | 來源（ancai） | 落到 Ben 樹的哪裡 | 最低驗證 |
|---|---|---|---|---|
| **A. 引擎核心** | `layout_strategy.py`、`layout_room.py`、`clearance_defaults.py`、`room_strategy/**`、相關 `placement.py`／`clearance.py`／`schema.py` 差分 | `backend/engine/` | 同路徑（Ben 缺檔＝新增） | `pytest -q tests/test_layout_strategy.py tests/test_placement.py tests/test_clearance.py` |
| **B. Server 適配** | `/api/scene/layout` 策略層接線、`model_orientation_deg` 白名單、companion 驗證、窗帶高度、SPACE_DEFAULTS／種子對齊 | `backend/server/scene_service.py` 等 | Ben 已拆成 `scene_api.py`／`scene_service.py`——**對函式移植，禁止整檔覆寫** | `pytest -q tests/test_scene_layout_regions.py tests/test_scene_v2_contract.py`（以 Ben 現有測試名為準） |
| **C. Agent／選件** | 配套池、床頭櫃 ×2、階梯換小、補件權、knowledge v1 對齊 | `backend/agent/` | 同路徑，與 Ben 的「問卷候選集」決定優先序後再合 | `pytest -q tests/test_agent_select.py tests/test_agent_place.py` |
| **D. 前端** | 旋轉離牆再轉、15° snap、2D 通用圖示、消失原因氣泡、種子死鍵、`model_orientation_deg` | `backend/server/static/*` | **對應改寫到 `frontend/*`**（檔名可能已拆：問卷→`scene_questionnaire_*.js`） | JS 語法／契約測試 + 瀏覽器第 6 步實操 |
| **E. 工具與文件** | `audit_furniture_vanish.py`、`audit_room_programs.py`、總帳必要段落 | `scripts/`、`notes/` | 同路徑；notes 可不進 Ben 主線 | 工具 dry-run |

Cherry-pick 可用，但遇路徑搬家（static→frontend）或 `main.py` 拆檔時，**預期會失敗——改為 `git show <sha> -- path` 手工移植**。

```bash
# 例：只看某 commit 對引擎的變更
git show c1ffbe9a -- backend/engine/

# 例：對照同一邏輯在兩邊前端的位置
git show ancai:backend/server/static/scene_v2.js | rg -n "model_orientation|snap|離牆"
rg -n "model_orientation|snap|離牆" frontend/scene_v2.js   # 在 ben-port worktree
```

### 4.4 與 Ben「候選集 RAG」的對齊決策（移植前先拍板）

兩邊都動了第 6 步選件入口，但路線不同：

| | Ancai | Ben |
|---|---|---|
| 路線 | 離線 RAG 快取 top-12 + 放不下階梯換小 | 問卷送出即建逐房候選集，避免全庫掃 |
| 風險 | 忽略 Ben 候選集＝白做 auth／shortlist API | 忽略 Ancai 策略層＝擺得醜／同牆怪局 |

**建議拍板（給 Ben 確認）**：

1. **檢索／短名單**：採 Ben 的 shortlist／候選集 API 為主。  
2. **幾何合法性與擺位**：一律 Ancai `layout_strategy` + engine。  
3. **放不下換小**：保留 Ancai 階梯換小，但輸入候選改吃 Ben shortlist。  
4. Graph／向量 RAG **不得**輸出座標。

---

## 5. 高衝突熱區清單（預先避雷）

| 路徑 | 為什麼痛 | 處理策略 |
|---|---|---|
| `backend/server/main.py` | Ben 大砍並拆 router | 只往 `scene_api.py`／`projects_api.py`／`catalog_payloads.py` 加最小接線 |
| `backend/server/scene_service.py` | 兩邊都大改（±1000 行級） | 以 Ben 檔為底，逐函式移植 Ancai 行為；每函式附測試 |
| `backend/server/static/**` vs `frontend/**` | 路徑與拆檔雙重分叉 | 永遠改 `frontend/`；把 ancai 的 diff 當補丁說明書 |
| `backend/engine/layout_strategy.py` 等 | Ben 無檔 | **新增**，並修 README／AGENTS 引用 |
| `backend/agent/knowledge.py` | 兩邊都對齊房型表 | 以 room_strategy v1 為 SSOT，再改 knowledge |
| `tests/test_scene_v2_contract.py` | Ben 大改契約測試 | 先讓 Ben 測試綠，再加你的新斷言 |
| Auth 相關 | Ben 新加 | 任何會打 API 的瀏覽器 QA 先登入；截圖 URL 要帶身分 |

---

## 6. 驗證門檻（每批結束、合進 Ben 前）

```bash
# 領域（Ancai）
.venv/bin/python -m pytest -q \
  tests/test_placement.py \
  tests/test_clearance.py \
  tests/test_layout_strategy.py \
  tests/test_agent_select.py \
  tests/test_agent_place.py

# 整合／契約（隨 Ben 現有檔名調整）
.venv/bin/python -m pytest -q tests/test_scene_v2_contract.py tests/test_scene_layout_regions.py

# 全量（合入前）
.venv/bin/python -m pytest -q
git diff --check
git status --short
```

瀏覽器最少實操：

1. 登入（若 Ben auth 已強制）→ 建案 → 走到第 6 步。  
2. 客廳：電視櫃與沙發是否對牆／對望（TV-first）。  
3. 任選一件旋轉 15°／90°，確認不會被 snap 吃掉或卡死。  
4. 主臥床是否還在（消失案回歸）。  
5. 換小／候選集來源提示是否仍可見（Ben 的 shortlist 通知）。

---

## 7. 跨資料夾修改紀錄模板（開做前填）

```text
跨資料夾修改
- 主要 owner：Ancai
- 協作 owner：Ben（產品／frontend／auth）、必要時 Bella（API 契約）
- 修改檔案：
- 改變的資料契約或流程：
- 為何不能只在 backend/engine/ 完成：
- 兩端驗證測試：
```

---

## 8. 跟 Ben 對焦時要問／要講清楚的事

1. **合入載體**：PR 打進 `ben`、還是 `bella-test*`？誰負責最終 push？  
2. **前端路徑**：確認 `frontend/` 已是唯一正式 UI（`TEAM_AI_OWNERSHIP` 仍寫 `backend/server/static/`——整合後文件要一起改）。  
3. **選件優先序**：shortlist vs 離線 RAG 快取（見 §4.4）。  
4. **策略層檔案**：Ben tip 刪／未含 `layout_strategy`——合入後必須存在並有測試。  
5. **你本機未推送的東西**：`VibeCoding_RoomPilot/`、總帳未提交段落、`.env`——不要混進 PR。  
6. **大型資產**：surface 貼圖、moodboard、GLB 權重——維持不進版控／不整包搬。

---

## 9. 回滾與安全網

| 動作 | 指令／做法 |
|---|---|
| 保留現況 tip | 已有 `ancai`；必要時 `git branch backup/ancai-YYYYMMDD`（只本機） |
| 放棄 port 分支 | 刪 worktree：`git worktree remove ../RoomPilot-Agent-ben-port` |
| 單批失敗 | 該批 `git reset --hard` 到批次起點，改手工更小的 patch |
| 絕不使用 | `push --force` 到 `main`／`ben`（除非 Ben 明確要求且你了解後果） |

---

## 10. 完成定義（DoD）

- [ ] Worktree 基於 `origin/ben`，而非在舊 `static/` 樹上硬 merge  
- [ ] `backend/engine/layout_strategy.py` + `room_strategy/` 存在於整合結果  
- [ ] TV-first／companion／旋轉／orientation／床消失相關測試綠  
- [ ] 前端改動只落在 `frontend/`，且 cache key／契約測試通過  
- [ ] 選件路徑與 Ben shortlist 的優先序有書面拍板  
- [ ] `pytest -q` 全綠或僅有雙方同意的 skip  
- [ ] 與 Ben 確認合入分支與 PR；文件（本檔 §8.2 路徑、ownership）已更新或開 follow-up

---

## 11. 相關文件

- `AGENTS.md`（禁止整包合併、公分契約、驗證矩陣）  
- `docs/TEAM_AI_OWNERSHIP.md`、`docs/owners/ANCAI.md`、`docs/owners/BEN.md`  
- `backend/engine/notes/engine工作總帳.md`、`backend/engine/notes/engine參考手冊.md`  
- 歷史參考（情境不同、勿照抄結論）：根目錄 `MAIN_SYNC_TODO.md`（cody-dev↔ben）、`890a0c4e` 08-01 合併經驗

---

*本檔描述的是「Ancai 如何把自身成果安全接到 Ben 目前 tip」的作業說明；Ben 名義職責仍是辨識 QA／發布驗證，但 `origin/ben` 實際已承載產品整合主幹——整合時以 tip 內容為準，不以職稱簡表為準。*
