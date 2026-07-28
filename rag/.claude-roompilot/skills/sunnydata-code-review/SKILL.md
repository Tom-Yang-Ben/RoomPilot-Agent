---
name: sunnydata-code-review
description: RoomPilot 檢索管線的完整程式碼審查生命週期 —— 宣稱完成前先驗證、請求結構化審查、以技術嚴謹度回應意見。完成任務時、提交／交付前、收到審查意見時使用。
---

> **繁體中文說明**：此技能整合三個階段的完整程式碼審查流程：驗證完成前的正確性 (Verify) → 請求結構化審查 (Request) → 以技術嚴謹度回應審查意見 (Receive)。順序固定，不可跳過。
> 本專案（RoomPilot 家具風格檢索系統）的審查另有兩個必檢維度：**六個坑**與**資料契約**，見下方〈RoomPilot 專屬審查維度〉。

# Code Review

## Overview

Three phases, fixed order. The sequence is mandatory — not optional.

```
Verify → Request → Receive → Verify again → Done
```

**Why this order eliminates ambiguity:**
- You cannot claim completion without verification (Phase 1).
- You cannot request review of unverified work (Phase 2 depends on Phase 1).
- You cannot process feedback without first verifying your current state (Phase 3 loops back to Phase 1).

**Core principles across all phases:**
- Evidence before claims, always.（本專案的「證據」＝ `.venv-rag/bin/python` 實跑後的輸出）
- Review early, review often.
- Technical correctness over social comfort.
- 規格衝突時**以 SSOT 文件為準**（`docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、`rag_pipeline/README.md`、`taxonomy_v2.json`、`category_groups.json`、`json_adjustment/RAGSQL.md`）。

---

## Phase 1: Verify Before Completion

### The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

如果你沒有在這一則訊息裡實際跑過驗證指令，就不能宣稱它通過。

**違反這條規則的字面，就是違反這條規則的精神。**

### The Gate Function

```
在宣稱任何狀態或表達滿意之前：

1. IDENTIFY: 哪一條指令能證明這個宣稱？（本專案一律 .venv-rag/bin/python …）
2. RUN:      執行「完整」指令（重新跑、跑完整）
3. READ:     讀完整輸出，看 exit code，數失敗數
4. VERIFY:   輸出真的支持這個宣稱嗎？
   - 若否：帶著證據陳述真實狀態
   - 若是：帶著證據做出宣稱
5. ONLY THEN: 才可以宣稱

跳過任何一步 = 說謊，不是驗證
```

### Common Failures Table

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| 測試通過 | `.venv-rag/bin/python -m pytest` 輸出：0 failures（測試套件尚未建置時，以下列 CLI 實跑替代） | 上一次的執行結果、「應該會過」 |
| 語法／匯入乾淨 | `.venv-rag/bin/python -m compileall -q rag_pipeline` 加 `import` 實測：0 errors | 只看了 diff、憑推論 |
| 檢索跑得起來 | `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"`：exit 0 且有結果 | 「語法沒錯」（語法正確不代表 `where` 不會命中 0 筆） |
| 索引可重建 | `.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50`：exit 0 | 只改了程式沒跑過 |
| UI 正常 | `.venv-rag/bin/python rag_pipeline/app.py` 啟動後開 `127.0.0.1:7860` 實送一條需求、卡片有圖有價 | 「Gradio 沒報錯」 |
| Bug 修好了 | 用原始症狀的需求語句重跑：通過 | 改了程式、假設修好了 |
| 迴歸測試有效 | Red-green 循環已驗證 | 測試只跑過一次就過 |
| Agent 完成了 | 實際讀檔／`diff` 看到變更（**專案尚未 git init**，無法用 `git diff`） | Agent 回報 "success" |
| 需求達成 | 逐條對照 SSOT 文件的 checklist | 測試通過 |

### Rationalization Prevention Table

| Excuse | Reality |
|--------|---------|
| 「現在應該可以了」 | 去 RUN 一次驗證 |
| 「我很有把握」 | 把握不是證據 |
| 「就這一次」 | 沒有例外 |
| 「語法檢查過了」 | 語法正確不等於檢索得出結果（`where` 寫錯照樣 import 成功） |
| 「Agent 說成功了」 | 自己獨立驗證 |
| 「我累了」 | 疲勞不是理由 |
| 「部分檢查就夠了」 | 部分證明不了任何事 |
| 「模型載入太慢，先跳過實跑」 | 慢不是跳過的理由；預熱一次約 1–2 分鐘，比錯誤交付便宜 |
| 「換個說法規則就不適用」 | 精神重於字面 |

### Red Flags — STOP Immediately

- 使用「應該」「大概」「看起來」
- 驗證前就表達滿意（「太好了！」「完美！」「完成！」）
- 即將交付／提交而尚未驗證
- 相信 agent 的成功回報卻沒自己看過檔案變更
- 依賴部分驗證
- 心裡想「就這一次」
- 改了排序權重或 `where` 條件卻沒實跑一條需求
- 任何未經實跑就暗示成功的措辭

### Key Verification Patterns

**Tests：**
```
CORRECT:   [跑 .venv-rag/bin/python -m pytest] → [看到：34/34 pass] → 「全部測試通過」
INCORRECT: 「現在應該會過」／「看起來對」
（測試套件尚未建置期間：以 CLI 實跑輸出作為等效證據，並註明「pytest 尚未建置」）
```

**Regression tests (TDD Red-Green cycle — mandatory)：**
```
CORRECT:   寫測試 → 跑（過）→ 還原修正 → 跑（必須失敗）→ 復原 → 跑（過）
INCORRECT: 「我寫了迴歸測試」（沒完成紅綠循環）
```

**Runtime（本專案沒有編譯步驟，實跑取代 build）：**
```
CORRECT:   [跑 .venv-rag/bin/python rag_pipeline/retriever.py "日式客廳 預算三萬"] → [exit 0 且有結果] → 「檢索可用」
INCORRECT: 「compileall 過了」（語法檢查不會告訴你 where 命中 0 筆）
```

**索引一致性：**
```
CORRECT:   [跑 embed_v3.py --limit 50] → [Chroma 筆數與 rag_export jsonl 筆數一致] → 「索引流程正常」
INCORRECT: 「只改了文字組裝，索引不用重跑」（text_hash 一變就影響 --only-changed）
```

**Requirements：**
```
CORRECT:   重讀 SSOT 文件 → 建 checklist → 逐項驗證 → 回報落差或完成
INCORRECT: 「測試過了，這階段完成」
```

**Agent delegation：**
```
CORRECT:   Agent 回報成功 → 實際讀檔／比對檔案內容 → 確認變更存在 → 回報真實狀態
INCORRECT: 照單全收 agent 的回報
（**專案尚未 git init**，無 `git diff` 可用；改以 Read 檔案 + 目錄時間戳比對）
```

### When Phase 1 Applies

**以下情況前一律適用：**
- 任何形式的成功或完成宣稱
- 任何表達滿意的說法
- 交付、寫入 SSOT 文件、任務完成（專案尚未 git init，commit／PR 目前不適用）
- 進入下一個任務
- 把工作派給 subagent
- 開跑高成本批次（`embed_v3.py` 全量約 27 分鐘、全量風格判定約 US$7）

這條規則適用於精確措辭、換句話說、同義詞，以及任何暗示成功的表達。

---

## Phase 2: Request Review

### When to Request

**Mandatory:**
- subagent 驅動開發中，每完成一個任務後
- 完成一個主要功能後（新增檢索階段、改排序權重、改解析 schema）
- 交付前（本專案尚未 git init，「merge to main」＝把變更視為定案交付）

**Optional but valuable:**
- 卡住時（換個視角）
- 重構前（先建立基準）
- 修完複雜 bug 後（例如檢索突然變 0 筆）

### How to Request

**Step 1 — 取得變更範圍：**
```bash
# 本專案尚未 git init，沒有 SHA 可取。改用「檔案 + 時間窗」界定範圍：
ls -lT rag_pipeline/*.py json_adjustment/*.py vlm_annotation/*.py

# 待專案 git init 後，恢復標準做法：
# BASE_SHA=$(git rev-parse HEAD~1)   # 或以 origin/main 為 base
# HEAD_SHA=$(git rev-parse HEAD)
```

**Step 2 — Dispatch code-reviewer subagent:**

用 Task tool 派給 code-reviewer，填寫本 skill 目錄下的 `code-reviewer.md` 範本。

Placeholders to fill:
- `{WHAT_WAS_IMPLEMENTED}` — 你剛做了什麼
- `{PLAN_OR_REQUIREMENTS}` — 它應該做什麼（計畫或 SSOT 文件的引用）
- `{BASE_SHA}` — 起始 commit SHA（尚未 git init 時填 `N/A — 檔案清單見下`）
- `{HEAD_SHA}` — 結束 commit SHA（同上）
- `{DESCRIPTION}` — 變更摘要

**Step 3 — Act on feedback (see Phase 3 below for full handling):**
- Critical 立即修，修完才能做下一步
- Important 在進下一個任務前修掉
- Minor 記下來，有機會順手處理

### RoomPilot 專屬審查維度（必檢，兩者都不可略過）

**A. 六個坑 —— 逐條確認，任何一條踩到就是 Critical：**

| # | 坑 | 審查時怎麼看 |
| :--- | :--- | :--- |
| 1 | `rag_indexable` 不能寫進 Chroma `where` | 讀 `build_where()` 回傳的 key 集合；它是頂層欄位、不在 `chroma_metadata`，寫了會命中 0 筆 |
| 2 | rerank 分數不可再套 sigmoid | 搜 diff 有沒有 `1/(1+exp(...))`；`bge-reranker-v2-m3` 經 CrossEncoder 已輸出 0–1 |
| 3 | structured outputs 可為 null 的 enum 要用 `anyOf` | 看 `build_schema()`／`nullable()`；直接寫 type 陣列會 400 |
| 4 | `HF_HUB_OFFLINE` 的 `setdefault` 不可移除 | 搜 diff 有無刪除該行；未登入被限流會卡數分鐘 |
| 5 | 尺寸是硬過濾，LLM 不得用常識推測 | 看 system prompt 有沒有鼓勵推測尺寸；猜錯會直接濾掉正確結果 |
| 6 | 勿把 reranker 換成 ms-marco MiniLM | 看 `RERANK_MODEL` 常數；英文模型會讓中文查詢劣化 |

**B. 資料契約 —— 改動只要碰到欄位、詞彙或交付檔，全部要對齊：**

| 契約 | SSOT | 審查問題 |
| :--- | :--- | :--- |
| 六風格詞表 + 6×6 相容矩陣 | `vlm_annotation/taxonomy_v2.json` | 新增／改名風格有無同步矩陣？`style_score()` 查不到 key 時的退路是什麼？ |
| 64 細類 → 19 檢索群組、房型典型組合 | `rag_pipeline/category_groups.json` | 新增細類有無歸進群組？群組數還是 19 嗎？ |
| 解析輸出 schema（受控詞彙、可為 null 欄位） | `docs/query_parser_spec.md` | schema 改了，文件跟著改了嗎？`retrieve()` 讀得到新欄位嗎？ |
| 硬過濾 vs 軟加權界線 | `docs/RAG檢索系統說明.md` | 房型／類別／價格／尺寸＝硬過濾；風格／氛圍＝軟加權；顏色／材質**只進 `semantic_query`**。有沒有把軟的做成硬的？ |
| Chroma metadata 欄位集合 | `rag_pipeline/embed_v3.py` | 新增 `where` 條件用到的欄位，索引時真的寫進 `chroma_metadata` 了嗎？ |
| SQL 端交付檔（向量 jsonl / metadata / 失敗清單 / 驗證報告） | `json_adjustment/RAGSQL.md`、`i_need_rag.md` | `rag_export/` 四個檔的欄位與筆數有無隨改動失準？ |
| 排序權重（0.60 rerank / 0.20 style_compat / 0.10 mood / 0.10 confidence） | `rag_pipeline/retriever.py:47` | 權重改了有無記 ADR？加總還是 1.0 嗎？ |
| 資料量與 collection 名 | 9,349 筆、`furniture_v3` | 筆數對得上嗎？有沒有誤寫成舊 collection？ |

**規格衝突時以文件為準**；若判定文件才是錯的，先改文件再改程式，不可只改程式。

### Example Dispatch

```
[剛完成任務 2：把配件品項的 rerank 候選數降到 RERANK_TOP_K_LIGHT]

# 專案尚未 git init：以檔案清單界定範圍
CHANGED="rag_pipeline/retriever.py"

[Dispatch code-reviewer subagent]
  WHAT_WAS_IMPLEMENTED: 配件品項（is_inferred / accent）的 rerank 候選數獨立為 RERANK_TOP_K_LIGHT=12
  PLAN_OR_REQUIREMENTS: docs/RAG檢索系統說明.md「Re-ranking 階段」段落
  BASE_SHA: N/A — 專案尚未 git init
  HEAD_SHA: N/A — 變更檔案：rag_pipeline/retriever.py:44, 222-280
  DESCRIPTION: 降低配件品項的 cross-encoder 呼叫量以縮短延遲；仍 > FINAL_TOP_K，去重後夠取

[Subagent returns]:
  Strengths: 常數集中在檔頭、註解說明了為何仍大於 FINAL_TOP_K
  Issues:
    Important: 未在 docs/RAG檢索系統說明.md 標註新常數（資料契約未同步）
    Minor: 12 這個魔術數字沒說明推導依據
  Assessment: Ready to proceed

[修掉 Important → 回 Phase 1 重新驗證 → 繼續任務 3]
```

### Integration by Workflow Type

| Workflow | Review Cadence |
|----------|---------------|
| Subagent 驅動開發 | 每個任務後都審 —— 趁問題還沒疊起來 |
| 執行既定計畫 | 每約 3 個任務一批 |
| 臨時性開發 | 交付前；或卡住時 |
| 批次資料重建（embed_v3 / reclassify_styles） | **開跑前**先審 —— 全量重建 27 分鐘、全量風格判定約 US$7，跑完才發現錯就來不及 |

### Red Flags for Phase 2

Never:
- 因為「這很簡單」就跳過審查
- 無視 Critical 就繼續往下
- 帶著沒修的 Important 進下一個任務
- 沒有技術性反論就跟正確的意見爭辯
- 動了 `retriever.py` 的權重或 `where` 卻沒對照六個坑

If the reviewer is wrong: 用技術理由反駁，拿實跑輸出或程式碼佐證，並要求澄清。

See reviewer template at: `code-reviewer.md`（本 skill 目錄下）

---

## Phase 3: Receive and Respond to Feedback

### The Response Pattern

```
收到 code review 意見時：

1. READ:       完整讀完，先不反應
2. UNDERSTAND: 用自己的話重述需求 —— 或直接問
3. VERIFY:     對照程式庫的實際狀況查證
4. EVALUATE:   對「這個」程式庫來說技術上成立嗎？
5. RESPOND:    技術性確認，或有理據的反駁
6. IMPLEMENT:  一次一項，每項都驗證
```

### Forbidden Response Phrases

**NEVER say:**
- 「你完全正確！」（明確違規）
- 「好觀點！」／「很棒的回饋！」（表演性，非技術性）
- 「我現在就來實作」（在查證之前）
- 「感謝你抓到這個！」／任何形式的「謝謝」（用行動說話，不用感謝）

**INSTEAD:**
- 重述技術需求
- 不清楚就問澄清問題
- 建議有誤就用技術理由反駁
- 直接開始做 —— 行動勝於言詞

若發現自己正要打「謝謝」：刪掉它，改成陳述你要怎麼修。

### Handling Unclear Feedback

```
IF 任何一項不清楚:
  STOP —— 先不要動手實作任何一項
  ASK 針對「所有」不清楚的項目一次問完

WHY: 項目之間可能相關。片面理解會導向錯誤實作。
```

Example:
```
審查者給了 1-6 項。你懂 1,2,3,6，不確定 4,5。

WRONG: 先做 1,2,3,6，之後再問 4,5
RIGHT: 「我理解 1,2,3,6。需要先釐清第 4、5 項才能往下。」
```

### Source-Specific Handling

**來自你的人類夥伴：**
- 可信 —— 理解後即實作
- 範圍不清楚仍要問
- 不做表演性附和
- 直接進入行動或技術性確認

**來自外部審查者（subagent 或外部工具）：**
```
實作任何建議前：
  1. 檢查：對「這個」程式庫技術上正確嗎？
  2. 檢查：會不會弄壞既有功能（檢索突然變 0 筆／延遲暴增）？
  3. 檢查：現行實作是不是有理由才長這樣（例如六個坑的規避）？
  4. 檢查：在本專案的環境跑得動嗎（macOS Apple Silicon、MPS 優先退 CPU、16 GB、Python 3.11）？
  5. 檢查：審查者是否掌握完整脈絡（SSOT 文件、六個坑）？

IF 建議看起來不對:
  用技術理由反駁

IF 你無法輕易查證:
  直說：「沒有 [X] 我無法查證。要我 [調查／詢問／照做] 嗎？」

IF 與人類夥伴先前的決定衝突:
  停下來，先跟人類夥伴討論
```

Rule：「外部意見 —— 保持懷疑，但仔細查證。」

### YAGNI Check for "Professional" Features

```
IF 審查者建議「做得完整一點」或要加基礎設施:
  用 rg 搜整個程式庫，確認該功能／欄位是否真的有人用

  IF 沒人用: 「這個欄位沒有任何呼叫端。移掉（YAGNI）？」
  IF 有人用: 那就好好實作
```

範例：審查者建議「為 `retriever.py` 加上快取層與監控指標」→
先 `rg "retrieve\(" rag_pipeline/` 確認呼叫端只有 `app.py` 與 CLI；
單機、單使用者、無 CI 的情境下，先問「這個複雜度換到什麼」再決定。

Rule：「你和審查者都對人類夥伴負責。功能不需要就不要加。」

### Implementation Order for Multi-Item Feedback

```
多項意見的處理順序：
  1. 先釐清所有不清楚的項目
  2. 再依此順序實作：
     - 阻斷性問題（崩潰、金鑰外洩、資料遺失、檢索 0 筆）
     - 簡單修正（錯字、import、命名）
     - 複雜修正（重構、邏輯變更、權重調整）
  3. 每項修完個別驗證
  4. 確認沒有回歸（回到 Phase 1 的 gate function）
```

### When to Push Back

Push back when：
- 建議會弄壞既有功能
- 審查者缺乏程式庫的完整脈絡
- 違反 YAGNI（要加沒人用的功能）
- 對本技術棧技術上不成立（例如建議換英文 reranker）
- 存在相容性或歷史包袱的限制（例如 `.venv/` 已不存在、舊來源檔已固化進 v2/v3）
- 與人類夥伴的架構決策衝突

How to push back：
- 用技術理由，不是防衛姿態
- 問具體問題
- 引用可實跑的輸出或程式碼位置
- 若屬架構層級，拉人類夥伴進來

**Disagreement signal:** 如果你不方便直接反駁，就寫下這句暗號：「Strange things are afoot at the Circle K」—— 這是在告訴人類夥伴：你有沒說出口的異議。

### Acknowledging Correct Feedback

```
CORRECT:   「已修。[一句話說明改了什麼]」
CORRECT:   「抓得好 —— [具體問題]。已在 [位置] 修正。」
CORRECT:   [直接修好，讓程式碼說話]

INCORRECT: 「你完全正確！」
INCORRECT: 「好觀點！」
INCORRECT: 任何感謝用語
```

### Correcting Your Own Pushback

反駁之後發現自己錯了：
```
CORRECT:   「你是對的 —— 我查了 [X]，它確實 [Y]。現在實作。」
CORRECT:   「查證過，你正確。我原本的理解錯在 [原因]。修正中。」

INCORRECT: 長篇道歉
INCORRECT: 辯解自己當初為何反駁
INCORRECT: 過度解釋
```

事實性地陳述更正，然後往前走。

### Common Mistakes Table

| Mistake | Fix |
|---------|-----|
| 表演性附和 | 陳述需求，或直接動手 |
| 盲目照做 | 先對照程式庫查證 |
| 一次全改不驗證 | 一次一項，每項驗證 |
| 預設審查者一定對 | 檢查會不會弄壞東西 |
| 迴避反駁 | 技術正確優於社交舒適 |
| 只做一半 | 先把所有項目問清楚 |
| 無法查證卻照樣往前 | 說明限制，請求指示 |
| 拿模型行為當藉口 | 「LLM 就是不穩」不是理由 —— 給出 schema 或 prompt 層級的具體對策 |

### 審查意見的回覆位置（本專案）

**專案尚未 git init、沒有遠端 repo，因此沒有 PR inline comment 可回。**
現階段的做法：把逐條回覆寫在同一次對話回應中，格式為
`檔案:行號 — 意見摘要 — 處置（已修／反駁理由／延後與原因）`；
結論依 `subagent-context.md` 規則寫入 `.claude-roompilot/context/quality/`。

待專案 git init 且有 GitHub 遠端後，恢復標準做法 —— 回在 comment thread 裡，不要開新的頂層留言：

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies \
  -f body="你的回覆"
```

### Real Examples

**表演性附和（錯）：**
```
審查者：「把舊的 taxonomy_v1 相關程式移掉」
WRONG: 「你完全正確！我馬上移除……」
```

**技術性查證（對）：**
```
審查者：「把舊的 taxonomy_v1 相關程式移掉」
CORRECT: 「查了一下 —— vlm_annotation/taxonomy_v1.json 仍被 glb_annotation_pipeline.py 讀取，
          現役檢索走的是 taxonomy_v2.json。要移的話得先確認標註流程改指 v2；
          直接刪會讓 GLB 標註 pipeline 壞掉。先改指向再刪，還是這輪先留著？」
```

**YAGNI 檢查（對）：**
```
審查者：「幫檢索加上完整的指標追蹤：資料庫、日期篩選、CSV 匯出」
CORRECT: 「rg 過整個程式庫 —— 沒有任何呼叫端會讀這些指標，本專案也沒有 CI 或監控端。
          移掉（YAGNI）？還是有我沒看到的用途？」
```

**六個坑的反駁（對）：**
```
審查者：「rerank 分數應該過一層 sigmoid 正規化到 0–1」
CORRECT: 「bge-reranker-v2-m3 走 CrossEncoder 已內建 sigmoid，輸出即 0–1（六個坑 #2）。
          再套一層會把分數壓向 0.5，破壞 0.60×rerank 的權重意義。
          實跑證據：同一條需求 top1 由 0.92 變 0.71，排序翻轉。」
```

---

## Workflow Summary

```
START
  |
  v
[Phase 1: Verify]
  跑驗證指令（.venv-rag/bin/python …）→ 讀輸出
  |
  失敗？ → 修 → 再跑
  |
  通過？
  |
  v
[Phase 2: Request Review]
  界定變更範圍（尚未 git init：用檔案清單取代 BASE_SHA + HEAD_SHA）
  逐條過六個坑 + 資料契約
  用 code-reviewer.md 範本 dispatch subagent
  |
  v
[Phase 3: Receive Feedback]
  完整讀完 → 理解 → 在程式庫中查證 → 評估
  |
  Critical？   → 立刻修 → 回 Phase 1
  Important？  → 進下一個任務前修 → 回 Phase 1
  Minor？      → 記下或順手處理
  |
  意見不清楚？ → 動手前先問清楚全部
  意見有誤？   → 用技術理由反駁
  |
  v
[Phase 1: 所有修正完成後再驗證一次]
  |
  v
DONE —— 帶著證據宣稱完成
```

The cycle is: **Verify → Request → Receive → Verify → Done.**

沒有任何階段是可選的。沒有新鮮的驗證證據，任何完成宣稱都不成立。

### 交付前最終 checklist（RoomPilot）

- [ ] `.venv-rag/bin/python -m compileall -q rag_pipeline json_adjustment` 無錯
- [ ] `.venv-rag/bin/python rag_pipeline/query_parser.py "<代表性需求>"` 輸出符合 schema
- [ ] `.venv-rag/bin/python rag_pipeline/retriever.py "<代表性需求>"` 有結果且筆數 ≤ `FINAL_TOP_K`
- [ ] 若動到索引邏輯：`.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50` 通過
- [ ] `.venv-rag/bin/python rag_pipeline/app.py` 起得來，卡片有圖有價
- [ ] 六個坑逐條確認
- [ ] 受影響的 SSOT 文件已同步（文件與程式衝突時以文件為準）
- [ ] 沒有硬編碼金鑰、沒有回顯 `.anthropic_key` 內容
