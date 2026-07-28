---
name: sunnydata-branch-lifecycle
description: Git 分支生命週期管理 — 為功能工作建立隔離的 worktree，完成後以結構化的 merge/PR/清理選項收尾。當要開始需要隔離的功能工作，或實作完成準備整合時使用。注意：RoomPilot 專案尚未 git init，流程照走但指令目前無法執行。
---

> **⚠️ RoomPilot 現況：專案尚未 `git init`。**
> 本技能的流程仍是團隊標準，**收尾與交付時照這套走**；但在本專案初始化版本控制之前，
> 下列所有 `git` / `gh` 指令都無法執行。第一次使用前請先確認：
>
> ```bash
> git rev-parse --is-inside-work-tree 2>/dev/null || echo "尚未 git init"
> ```
>
> 若輸出「尚未 git init」，請先與使用者確認是否要初始化（並確保 `.anthropic_key`、
> `chroma_db/`、`.venv-rag/`、`rendering/output/` 已列入 `.gitignore`）再繼續。

> **繁體中文說明**：本技能整合了 `sp-using-git-worktrees` 與 `sp-finishing-a-development-branch` 兩個技能，涵蓋分支從建立、隔離工作到完成整合的完整生命週期。

# 分支生命週期

## 總覽

一個技能涵蓋完整分支生命週期：**建立 → 工作 → 收尾**

- **Phase 1** 建立隔離的 git worktree，讓你可以在不干擾目前工作區的狀況下開發。
- **Phase 2** 驗證完成度、提出結構化的整合選項，並清理。

**核心原則：** 一開始就系統性隔離 + 結束時經過驗證的收尾 = 不會遺失工作、不會污染分支。

**Phase 1 開始時宣告：**「我正在使用 branch-lifecycle skill 建立隔離工作區。」
**Phase 2 開始時宣告：**「我正在使用 branch-lifecycle skill 收尾這份工作。」

---

## Phase 1：建立 Worktree

### 目錄選擇

嚴格依此優先序：

**Step 1 — 檢查既有目錄：**

```bash
ls -d .worktrees 2>/dev/null   # 偏好（隱藏目錄）
ls -d worktrees 2>/dev/null    # 替代方案
```

找到就用該目錄。兩者都存在時，`.worktrees` 勝出。

**Step 2 — 檢查 CLAUDE.md：**

```bash
grep -i "worktree.*director" CLAUDE.md 2>/dev/null
```

若有指定偏好，直接採用、不用問。

**Step 3 — 詢問使用者（僅在沒有目錄也沒有 CLAUDE.md 偏好時）：**

```
找不到 worktree 目錄。要把 worktree 建在哪裡？

1. .worktrees/（專案內、隱藏）
2. ~/.config/superpowers/worktrees/<project-name>/（全域位置）

你偏好哪一個？
```

### 安全性驗證

**專案內目錄（`.worktrees` 或 `worktrees`）— 必須確認已被 ignore：**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

若**未被** ignore：
1. 在 `.gitignore` 加上對應那一行
2. 提交這次變更
3. 才繼續

這可避免 worktree 內容被誤提交進 repo。RoomPilot 另外必須確保 `.gitignore` 已含
`.anthropic_key`、`.venv-rag/`、`chroma_db/`、`rendering/output/`——這些檔案體積大或含金鑰。

**全域目錄（`~/.config/superpowers/worktrees`）：** 不需檢查 `.gitignore` — 它完全在專案外。

### 建立步驟

**1. 偵測專案名稱：**

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
```

**2. 用新分支建立 worktree：**

```bash
# 專案內
git worktree add .worktrees/<branch-name> -b <branch-name>

# 全域
git worktree add ~/.config/superpowers/worktrees/$project/<branch-name> -b <branch-name>

cd <worktree-path>
```

**3. 自動偵測並安裝相依：**（RoomPilot 只有 Python 3.11 一種環境）

```bash
if [ ! -d .venv-rag ];      then python3.11 -m venv .venv-rag; fi
if [ -f requirements.txt ]; then .venv-rag/bin/pip install -r requirements.txt; fi
if [ -f pyproject.toml ];   then .venv-rag/bin/pip install -e .; fi
if [ ! -d chroma_db ];      then echo "缺索引：稍後需跑 .venv-rag/bin/python rag_pipeline/embed_v3.py"; fi
if [ ! -f .anthropic_key ]; then echo "缺金鑰：需設定 ANTHROPIC_API_KEY 或建立 .anthropic_key"; fi
```

> worktree 不會複製 `.venv-rag/`、`chroma_db/`、`rendering/output/`（皆已 ignore）。
> 重建索引要 27 分鐘，實務上建議直接沿用主工作區的 `chroma_db/`（唯讀查詢）或以
> `--limit 50` 建冒煙用小索引。

**4. 驗證乾淨基準** — 跑專案測試：

```bash
.venv-rag/bin/python -m pytest        # 專案尚未建置測試套件，預期 no tests ran
# 冒煙替代方案（目前唯一可信的基準驗證）
.venv-rag/bin/python rag_pipeline/query_parser.py "北歐風客廳沙發，預算三萬"
.venv-rag/bin/python rag_pipeline/retriever.py   "北歐風客廳沙發，預算三萬"
```

- 冒煙通過：回報就緒。
- 冒煙失敗：回報失敗內容，詢問要繼續還是先調查。不可默默繼續。

**5. 回報位置：**

```
Worktree 已就緒：<full-path>
冒煙檢索通過（回傳 8 筆，主導風格 scandinavian）
可以開始實作 <feature-name>
```

### Phase 1 速查

| 情況 | 動作 |
|-----------|--------|
| `.worktrees/` 存在 | 用它（確認已 ignore） |
| `worktrees/` 存在 | 用它（確認已 ignore） |
| 兩者都存在 | 用 `.worktrees/` |
| 都不存在 | 查 CLAUDE.md → 問使用者 |
| 目錄未被 ignore | 加進 `.gitignore` 並提交 |
| 基準冒煙失敗 | 回報失敗 + 詢問 |
| 找不到相依清單檔 | 跳過安裝，沿用 `.venv-rag/` |

---

## Phase 2：收尾分支

### Step 1：驗證測試（強制前置條件）

```bash
.venv-rag/bin/python -m pytest        # 尚未建置：改以下列冒煙為準
.venv-rag/bin/python rag_pipeline/retriever.py "日式臥室，預算五萬，要溫暖一點"
.venv-rag/bin/python rag_pipeline/app.py       # 手動確認 http://127.0.0.1:7860 卡片正常
```

測試／冒煙失敗：停下。在通過之前不要提出選項。

### Step 2：稽核 commit 歷史（強制前置條件）

提出選項前，先審視 commit log 的品質：

```bash
git log --oneline <base-branch>..HEAD
```

**逐一對照 `.claude-roompilot/rules/git-workflow.md` 檢查：**

| 檢查項 | 未通過時的動作 |
|-------|-------------|
| Subject > 72 字元或含糊（"fix"、"update"、"misc"） | 標記給使用者，建議 reword |
| 缺 body（WHY/WHAT/IMPACT） | 標記給使用者，建議 amend 或 squash |
| 單一 commit 動到 10+ 個不相關檔案 | 建議拆成多個邏輯 commit |
| 多個 commit 在做同一件事 | 建議 squash |

**把稽核摘要呈現給使用者：**

```
Commit 歷史審視（N 個 commit）：
✓ <sha> <subject>  — OK
✗ <sha> <subject>  — body 缺 WHY
✗ <sha> <subject>  — subject 太含糊

建議：合併前先 squash/reword？
```

使用者可以選擇維持原樣或修正。不要卡住流程 — 這是建議而非閘門。但一定要把稽核結果講出來。

### Step 3：確定 base 分支

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

或直接跟使用者確認：「這個分支是從 main 切出來的，對嗎？」

### Step 4：提出正好 4 個選項

```
實作完成。你想怎麼做？

1. 在本機 merge 回 <base-branch>
2. Push 並建立 Pull Request
3. 分支維持現狀（我之後再處理）
4. 丟棄這份工作

選哪一個？
```

不要加解釋 — 選項保持精簡。

### Step 5：執行選擇

#### 選項 1 — 本機 Merge

```bash
git checkout <base-branch>
git pull
git merge <feature-branch>
.venv-rag/bin/python rag_pipeline/retriever.py "北歐風客廳沙發"   # 驗證 merge 後結果
git branch -d <feature-branch>
```

接著：進行 Step 6（清理 worktree）。

#### 選項 2 — Push 並建立 PR

**起飛前檢查（強制 — 執行前呈現給使用者）：**

```
PR 起飛前檢查：
✓/✗ 冒煙檢索全部通過（pytest 尚未建置）
✓/✗ Commit 歷史已稽核（Step 2）
✓/✗ 已自我 review 完整 diff
✓/✗ 無除錯殘留（暫時的 print()、註解掉的程式碼、寫死的測試查詢）
✓/✗ 無金鑰外洩（`.anthropic_key` 內容絕不可出現在 diff）
✓/✗ PR 大小合理（< 400 行 diff、< 10 個檔案）
```

若 PR 超過大小限制，建議拆分：
```
這個 PR 動到 <N> 個檔案、<M> 行變更。
建議拆成更小、更聚焦的 PR：
1. <建議拆法 1>
2. <建議拆法 2>

仍要以單一 PR 送出嗎？
```

**執行：**

```bash
git push -u origin <feature-branch>
```

撰寫 PR body 前先審視完整 diff：

```bash
git diff <base-branch>...HEAD
```

分析**所有** commit（不只最新那個）以寫出準確摘要：

```bash
git log --oneline <base-branch>..HEAD
```

依 `.claude-roompilot/rules/git-workflow.md` 的 PR 品質標準建立 PR：

```bash
gh pr create --title "<type>(<scope>): <subject>" --body "$(cat <<'EOF'
## Background
<這個 PR 為什麼存在 — 問題、觸發事件、動機>
<關聯 issue：#NNN>

## Changes
<關鍵決策與取捨 — 不是檔案清單>
<為何選方案 A 而非 B，例如：為何 rerank 權重從 0.55 調到 0.60>

## Impact
<破壞性變更、migration 步驟、受影響模組>
<若索引結構有變，必須註明需重跑 embed_v3.py（全量約 27 分鐘）>
<若無：「無破壞性變更。」>

## Test Plan
- [ ] `.venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"` 輸出符合 docs/query_parser_spec.md
- [ ] `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 回傳 8 筆且主導風格正確
EOF
)"
```

PR 建立後，呼叫 `sunnydata-code-review` skill 做結構化自我審查。

接著：進行 Step 6（清理 worktree）。

#### 選項 3 — 維持現狀

回報：「保留分支 `<name>`。Worktree 保留於 `<path>`。」

**不要**清理 worktree。

#### 選項 4 — 丟棄

先明確確認細節：

```
這會永久刪除：
- 分支 <name>
- 所有 commit：<commit-list>
- Worktree：<path>

輸入 'discard' 以確認。
```

等待使用者輸入完全一致的 `discard`。其他輸入一律不放行。

確認後：

```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

接著：進行 Step 6（清理 worktree）。

### Step 6：清理 Worktree

**選項 1、2、4** — 先確認有註冊 worktree，再移除：

```bash
git worktree list | grep $(git branch --show-current)
git worktree remove <worktree-path>
```

**選項 3** — 保留 worktree，什麼都不做。

### Phase 2 速查

| 選項 | Merge | Push | 保留 Worktree | 刪除分支 |
|--------|-------|------|---------------|---------------|
| 1. 本機 merge | yes | no | no | yes（soft） |
| 2. 建立 PR | no | yes | yes | no |
| 3. 維持現狀 | no | no | yes | no |
| 4. 丟棄 | no | no | no | yes（force） |

---

## 速查：何時用哪個 Phase

```
要開始隔離的功能工作？
  └─ 是 → Phase 1：建立 Worktree
       └─ 一路做到實作完成
            └─ 冒煙全通過？ → Phase 2：收尾分支

已經在一般分支上（沒有 worktree）？
  └─ 直接進 Phase 2（跳過 Phase 1）
       └─ Step 6 的 worktree 清理在沒有註冊 worktree 時會自動 no-op

工作做到一半被打斷？
  └─ Phase 2、選項 3（維持現狀）— 之後再回來
```

---

## 紅旗

**絕不：**
- 在未確認已被 ignore 的情況下建立專案內 worktree
- 跳過 Phase 1 的基準冒煙驗證
- 在冒煙失敗的情況下就進入 Phase 2 的選項
- 沒有使用者輸入 `discard` 就刪除工作（選項 4）
- 未經明確要求就 force push
- Merge 後（選項 1）帶著失敗的冒煙結果繼續
- 把 `.anthropic_key`、`chroma_db/`、`.venv-rag/` 提交進版本控制

**永遠：**
- 目錄優先序：既有 > CLAUDE.md > 詢問
- 依相依清單檔自動偵測環境（本專案唯一環境是 `.venv-rag/`）
- Phase 2 提出正好 4 個選項
- 只在選項 1、2、4 清理 worktree

---

## 整合

**被誰呼叫：**
- `sunnydata-design`（Phase 1）— 設計核可、要開始實作時**必要**
- `sunnydata-design`（Phase 3）— 執行任務批次前後**必要**
- `sp-subagent-driven-development` — 任務執行的頭尾**必要**

**搭配使用：**
- `sunnydata-code-review` skill — 在本技能 Phase 2 收尾前，先跑 sunnydata-code-review 的 Phase 1
- `.claude-roompilot/rules/git-workflow.md` — commit 與 PR 訊息格式的參考標準
