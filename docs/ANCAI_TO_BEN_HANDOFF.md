# Ancai → Ben：功能如何合併進 `ben` 分支

> **一句話**：以 `origin/ben` 為產品主幹，把 Ancai（`ancai` @ `5f564dfa`）的引擎／擺位／旋轉／消失案／選件對齊**分批移植進去**；**禁止** `git merge ancai` 整包合入。  
> **對象**：Ben 與 Ben 的 AI（執行合併的一方）  
> **基準日**：2026-08-04  
> **來源 tip**：`ancai` = `5f564dfa`　**目標 tip**：`origin/ben` = `ee2cdd3d`　**共同祖先**：`5986f659`

規格細節查 `docs/owners/ANCAI.md`；本檔只回答「東西怎麼進 ben」。

---

## 0. 合併策略（先讀這段）

```text
正確：checkout ben → 開整合分支 → 按批次拷貝／改寫 Ancai 功能島 → 每批測試
錯誤：git merge ancai   或   用 ancai 的 backend/server/static 整夾蓋掉 frontend/
```

| 規則 | 說明 |
|---|---|
| 主幹 | 一律留在 `ben`（auth、router 工廠、`frontend/`、shortlist 候選集都保留） |
| Ancai 帶來的 | 策略層引擎、第 6 步接線、Agent 對齊、前端行為修補、稽核腳本與對應測試 |
| 路徑 | Ancai 的 UI 在 `backend/server/static/`；ben 的 UI 在 `frontend/`——**移植時改路徑，不要還原 static 主線** |
| 衝突裁法 | 產品殼／帳號／路由拆檔 → **留 ben**；幾何／合法性／TV-first／旋轉／床消失 → **採 Ancai** |
| 選件入口 | **檢索短名單留 ben shortlist**；**放不下換小採 Ancai 階梯邏輯，候選改吃 shortlist**（見 §3） |

---

## 1. Ancai 這包「有什麼要進 ben」

### 1.1 必進（沒有＝第 6 步擺位回退）

| 功能島 | Ancai 為何要帶 | ben tip 現況 |
|---|---|---|
| 擺放策略層 | `layout_strategy.py`、`layout_room.py`、`clearance_defaults.py`、`room_strategy/` | **檔案不存在** |
| 瀏覽器路徑接策略層 | `scene_service._strategy_placement`、`ROOMPILOT_LAYOUT_STRATEGY` | **無** `_strategy_placement`／無 layout_strategy import |
| TV-first／companion／opposite | 客廳對牆、配套淨空豁免 | 隨策略層一起缺 |
| 窗帶看窗台高 | `window_clearance_zones` 分級 | 需對照後移植，勿用 Ancai 整檔蓋 ben |
| 床消失雙修 | `catalog_furniture_id` 對型錄、中文語意認床 | 行為要進 `scene_service` |
| `model_orientation_deg` | 輸出白名單＋前端渲染欄位；**不動擺位 rotation** | 需接進 ben 的 scene payload／viewer |
| 旋轉修補 | 離牆再轉、15° 不被 90° snap 吃掉、夾位邊距 6→9 | 在 `scene_layout2d.js`／`scene_viewer.js` |
| 種子／SPACE_DEFAULTS v1 | 死鍵拔除、衣櫃、留空房 | `SPACE_DEFAULTS` ben 有舊表 → **用 Ancai 語意覆寫內容，保留 ben 呼叫點** |
| Agent 對齊 | 配套池、床頭櫃 ×2、階梯換小、knowledge v1 | 與 ben shortlist **銜接**，不要砍 shortlist API |
| 測試 | `test_layout_strategy`、`test_layout_tv_first`、`test_scene_seed_dead_keys`、`test_agent_addon_pool`、`test_scene_window_bands` | ben 無這些檔 → **新增** |

### 1.2 應進（工具／回歸）

- `scripts/audit_furniture_vanish.py`
- `scripts/audit_room_programs.py`
- `scripts/floor04_layout_preview.py`
- （可選）`scripts/build_rag_offer_cache.py`——若 §3 拍板「shortlist 為主」，此腳本降為備援，勿取代 shortlist

### 1.3 不要整包帶進 ben

| 不要帶 | 原因 |
|---|---|
| `git merge` 整支 `ancai` | 會打爆 `frontend/` 搬家、auth、佇列 7 拆檔 |
| 把 UI 搬回 `backend/server/static/` | ben 已定 `frontend/` 為主線 |
| `frontend3d/`、`docs/vibecoding/` 殘件、本機 `VibeCoding_*`、`.env*` | 非正式／密鑰／未版控自用 |
| Ancai 的 `scripts/sql/*10550*` 大包（除非 Kai／Ben 另開資料任務） | 非第 6 步擺位合併範圍 |
| `notes/` 工作總帳 | 可選附錄；不是 runtime |

---

## 2. 建議合併步驟（Ben AI 照做）

### 2.1 開分支（在 ben 上）

```bash
git fetch origin ben ancai
git switch -c integrate/ancai-engine-into-ben origin/ben
# 建議另開 worktree，勿弄髒正在跑的 ben 工作區
```

核對 tip：

```bash
git rev-parse --short HEAD          # 應接近 ee2cdd3d
git rev-parse --short origin/ancai  # 或 ancai：5f564dfa
```

### 2.2 分批移植（順序固定）

#### Batch A — 引擎（先做，風險最低）

從 `ancai` **新增／覆寫**到 ben 同路徑：

```text
backend/engine/layout_strategy.py          # 新增
backend/engine/layout_room.py              # 新增
backend/engine/clearance_defaults.py       # 新增
backend/engine/room_strategy/README.md     # 新增
backend/engine/room_strategy/samples/      # 新增
backend/engine/clearance.py                # 取 ancai 差分（勿盲蓋前先 diff）
backend/engine/placement.py
backend/engine/models.py
backend/engine/schema.py
backend/engine/README.md
backend/engine/AGENTS.md
tests/test_layout_strategy.py             # 新增
tests/test_layout_tv_first.py             # 新增
```

```bash
# 例：直接检出 ancai 版新檔
git checkout origin/ancai -- \
  backend/engine/layout_strategy.py \
  backend/engine/layout_room.py \
  backend/engine/clearance_defaults.py \
  backend/engine/room_strategy \
  tests/test_layout_strategy.py \
  tests/test_layout_tv_first.py
```

對已存在檔（`clearance.py` 等）先：

```bash
git diff origin/ben origin/ancai -- backend/engine/clearance.py
```

只合併與策略／淨空相關的 hunk，保留 ben 若有的其他修正。

驗證：

```bash
.venv/bin/python -m pytest -q \
  tests/test_layout_strategy.py \
  tests/test_layout_tv_first.py \
  tests/test_clearance.py \
  tests/test_placement.py
```

#### Batch B — `scene_service` 接線（最痛，禁止整檔覆寫）

**以 ben 的 `backend/server/scene_service.py` 為底**，從 ancai 移植這些行為（用 `git show origin/ancai:backend/server/scene_service.py` 對函式抄）：

| 必帶行為 | Ancai 線索 |
|---|---|
| import `layout_strategy` 原語／`ROOM_RULES`／`family` 對接 | 檔頭 import；`_strategy_placement` |
| `_strategy_placement` + `ROOMPILOT_LAYOUT_STRATEGY` 開關 | ~L1435–1550 |
| layout 流程依錨點 `order` 呼叫策略層 | ~L1819–1913 |
| `SPACE_DEFAULTS` 內容對齊 room_strategy v1 | ~L124 起（覆寫**內容**） |
| `window_clearance_zones` 窗台高度豁免 | ~L1119 |
| companion_pairs 含「others 彼此」 | 單件驗證路徑；commit `3b2073ef` |
| 選件合併用 `catalog_furniture_id` | ~L665–670 |
| 床語意防呆（中文描述） | `catalog_item_matches_type_semantics` |
| payload 輸出 `model_orientation_deg` | ~L2120 |
| 一鍵止血 | `ROOMPILOT_LAYOUT_STRATEGY=0`、`ROOMPILOT_WINDOW_BAND_FLAT=1` |

若 ben 已拆 `scene_api.py`：路由掛載留 ben；**邏輯仍改 `scene_service.py`**。

驗證：

```bash
.venv/bin/python -m pytest -q \
  tests/test_scene_layout_regions.py \
  tests/test_scene_window_bands.py \
  tests/test_scene_v2_contract.py
```

（`test_scene_window_bands.py` 若尚無：`git checkout origin/ancai -- tests/test_scene_window_bands.py`）

#### Batch C — Agent（銜接 shortlist，不取代）

```text
backend/agent/knowledge.py
backend/agent/select.py
backend/agent/place.py
tests/test_agent_addon_pool.py
tests/test_agent_select.py   # 跑回歸，勿無故刪 ben 既有斷言
tests/test_agent_place.py
```

合併前確認 §3：換小／補件的**輸入列表**改呼叫 ben shortlist（`shortlist_api`／`scene_furniture_offers`），不要默默改回全庫或只吃 Ancai RAG cache。

#### Batch D — 前端（路徑改寫）

| Ancai 來源 | 寫入 ben | 帶什麼 |
|---|---|---|
| `backend/server/static/scene_layout2d.js` | `frontend/scene_layout2d.js` | 旋轉離牆再轉、15° snap、夾位邊距 |
| `backend/server/static/scene_viewer.js` | `frontend/scene_viewer.js` | `modelOrientationDeg`、消失原因氣泡／清單 |
| `backend/server/static/scene_v2.js` | `frontend/scene_v2.js` | 種子死鍵、五表／問卷預設對齊（注意 ben 已拆問卷到下列檔） |
| （行為可能已搬家） | `frontend/scene_questionnaire_data.js`／`_flow.js` | 問卷預設與種子——**先搜再改，勿只改 v2** |
| 相關測試 | `tests/test_scene_seed_dead_keys.py` 等 | 新增；契約測試依 ben 的 cache key 規則重算 |

```bash
# 對照同一邏輯（在整合分支上）
git show origin/ancai:backend/server/static/scene_layout2d.js | rg -n "snap|離牆|margin"
rg -n "snap|離牆|margin" frontend/scene_layout2d.js
```

**禁止**：把整個 `static/` checkout 進 ben。

驗證：瀏覽器第 6 步（見 §4）+ ben 既有 frontend 契約／cache key 測試。

#### Batch E — 工具（可後做）

```bash
git checkout origin/ancai -- \
  scripts/audit_furniture_vanish.py \
  scripts/audit_room_programs.py \
  scripts/floor04_layout_preview.py
```

---

## 3. 合併前拍板（Ben 與 Ancai 各一句）

兩邊都動過「第 6 步家具從哪來」：

| | Ancai | Ben |
|---|---|---|
| 做法 | 離線 RAG offer cache + 階梯換小 | 問卷即建逐房 shortlist，避免全庫掃 |

**建議定案（寫進 PR 描述）**：

1. 短名單／檢索 → **ben shortlist**  
2. 擺哪、合不合法 → **Ancai layout_strategy + engine**  
3. 放不下換小 → **Ancai 階梯**，候選來自 shortlist  
4. RAG／LLM **永不輸出座標**

未拍板不要同時開兩條選件主路徑。

---

## 4. 完成定義（Ben 可勾選）

- [ ] 整合分支基於 `origin/ben`，沒有把 UI 搬回 `static/`  
- [ ] `backend/engine/layout_strategy.py` 與 `room_strategy/` 存在  
- [ ] `scene_service` 有 `_strategy_placement`，且可用 `ROOMPILOT_LAYOUT_STRATEGY=0` 關閉  
- [ ] Batch A–D 對應 pytest 綠  
- [ ] 瀏覽器：登入（若 auth 強制）→ 第 6 步 → 客廳 TV 與沙發對牆 → 旋轉 15°／90° → 主臥床還在 → shortlist 來源提示仍在  
- [ ] PR 說明列了 §3 選件定案與「未帶入」清單（§1.3）  
- [ ] 未提交 `.env`、本機 notes、大型資產

全庫閘門（合入前）：

```bash
.venv/bin/python -m pytest -q tests/
git diff --check
git status --short
```

---

## 5. 給 Ben AI 的最短指令卡

```text
你在 origin/ben 上開 integrate/ancai-engine-into-ben。
不要 merge ancai。依 docs/ANCAI_TO_BEN_HANDOFF.md 做 Batch A→B→C→D。
引擎新檔可 git checkout origin/ancai -- <paths>。
scene_service 與 frontend 只允許函式級／行為級移植；UI 路徑 static→frontend。
選件短名單保留 ben shortlist；幾何以 Ancai 為準。
每批跑文件內 pytest；最後跑瀏覽器第 6 步五條 DoD。
規格不確定時讀 docs/owners/ANCAI.md，不要猜座標規則。
```

---

## 6. 相關文件

- `docs/owners/ANCAI.md` — 引擎邊界與已定案規格（查「為什麼」）  
- `docs/ANCAI_BEN_INTEGRATION.md` — Ancai 自己去 ben 樹上移植的備忘（視角相反；執行合併以**本檔**為準）  
- `backend/engine/room_strategy/README.md` — 房型清單 SSOT  
- `AGENTS.md` — 禁止整包合併成員分支  

---

*交付意圖：讓 Ben 把 Ancai 目前功能島安全合併進 ben，而不是把 ben 重做成 ancai。*
