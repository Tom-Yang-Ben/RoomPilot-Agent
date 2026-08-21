# `_unused/` — 移出主線的檔案與理由

這裡是**封存**不是垃圾桶。每一項都寫清楚「為什麼不需要」與「什麼情況下要拿回去」。
判定標準只有一條：**跑得起正式產品（`backend.server.main:app`）與 `pytest -q` 都不需要它**。

判定方法：對每個路徑字串 grep 全 repo 的 `.py` / `.js` / `.json` / `.md` / `.yml`
（排除 `.venv/`、`graphify-out/`、`.git/`），確認沒有任何 runtime、測試或建置引用。

要拿回去：`git mv _unused/<名字> ./<名字>`。歷史沒斷，`git log --follow` 查得到。

---

## 已移入

| 路徑 | 大小 | 不需要的理由 |
|---|---|---|
| `manual_test_kit/` | 0.7 MB | 手動測「最後一步」（生圖 + 設計手冊 PDF）的獨立小工具，含一份已產出的 `output/design_manual.pdf`。只有自己的 README 提到自己，`tests/`、`backend/`、`scripts/` 全部零引用；同樣的路徑現在由 `tests/test_design_manual_api.py`、`tests/test_delivery_proposal_api.py` 自動覆蓋。 |
| `install.txt` | 1 行 | 內容只有 `.venv\Scripts\playwright.exe install chromium` 一行便條。這條指令已經寫在 `README.md` 的第 8 步安裝段與 `requirements-delivery.txt` 的註解裡，重複第三份只會漂移。 |

---

## 已直接刪除的（不搬進來，但理由記在這）

這幾項在 `6edbd666`（2026-08-15，`docs:some trash file delete`）就已從版控移除，早於本資料夾成立。既然工作區裡已經沒有它們，就不為了「搬進 `_unused/`」把位元組復活——留理由在這裡，要取回走 git：`git checkout 6edbd666^ -- <路徑>`。

| 路徑 | 原大小 | 不需要的理由 |
|---|---|---|
| `genpic_result/` | 9.4 MB | 第 8 步 AI 生圖的**人工試跑輸出**（`result1.png`、`test2/test1~5.png`）。全 repo 零引用，不是測試 fixture、不是 UI 素材。生圖結果現在寫進 `.runtime/renders/`，這裡是早期手動存檔的殘留。 |
| `fix/` | 7 個 .md | 2026-08-02～08-04 的**單次修復筆記**（地板破口、家具朝向、逐房問卷死結、躺椅搶位…）。當時的除錯過程紀錄，對應修改都已進 code 與 commit message，沒有任何檔案連到它們。歷史價值走 `git log` 查更準。 |
| `feedback.png` | 276 KB | 同一個 commit 一併掃掉。**它不是零引用**：`backend/agent/knowledge.py:119`、`backend/server/scene_service.py:1685/1693/2947`、`backend/server/static/scene_architecture.js:153` 五處註解指名它解釋那幾段擺位防呆的由來。刪除後那些引用是斷鏈，但註解本身仍讀得懂（「曾有這個回報案例」），所以維持刪除；要看圖走 `git show 4dc30331:feedback.png`。 |

---

## 查過但**決定留下**的

清單裡曾被當成候選，實際查證後有引用或有作用，留在原位：

| 路徑 | 為什麼留 |
|---|---|
| `backend/skills/` | `roompilot-llm/SKILL.md` 是對話式 intake／風格推薦的**行為契約**，`docs/01_專題進度/RoomPilot_現行版本總覽.md:205` 明確登記它「未接程式」。未接 ≠ 作廢，它是規格不是產物。 |
| `examples/` | `demo_agent_flow.py` 被 `backend/engine/README.md:25` 與 `docs/資料夾功能總覽.md:28` 指定為 Agent ↔ 引擎介面的**活文件**。 |
| `RoomPilot_Docs/` | 60 份正式工程文件（BRD／PRD／SRS／ADR／runbook），本身就是交付物。 |
| `VibeCoding_Workflow_Templates/` | 34 份文件模板，被 `.claude/CLAUDE.md` 當作文件系統的模板來源引用，搬走會斷掉 skill 路由。 |
| `data/`、`JSON/`、`knowledge/` | 分別是測資與 GLB／BGE-M3 向量與 manifest／`ROOMPILOT_KNOWLEDGE_DIR` 的預設值（`backend/engineering/config.py:38`）。全部是執行期或測試期真實資料。 |
| `frontend/` | React/R3F 原型雖非正式流程，但 `tests/test_team_ai_guidance.py:82` 會檢查它的 `package-lock.json`，而且 `docker compose --profile frontend` 會用它。 |

---

## 不搬進來的東西

`.venv/`、`.runtime/`、`.pytest_cache/`、`__pycache__/`、`graphify-out/` **不屬於封存範圍**。

它們是**本機執行狀態**，已經被 `.gitignore` 擋在版控之外，搬進一個納入版控的資料夾反而
會把它們推上去。特別是 `.runtime/`（約 430 MB）裝的是**你目前 8002 上所有專案的實際資料**
——專案 DB、上傳的平面圖、算好的算圖。刪掉或搬走會讓專案清單整個歸零。

要清掉這類快取用 `git clean -Xn` 先看、再 `-Xf` 執行，不要靠搬資料夾。
