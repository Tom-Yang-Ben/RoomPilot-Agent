---
description: 儲存當前 RoomPilot 檢索工作的 session 狀態到檔案，讓下次 session 可以完整恢復上下文。
---

# 儲存 Session 指令

擷取本次 session 中發生的所有事 -- 建構了什麼、什麼有效、什麼失敗、還剩什麼 -- 寫入有日期的檔案，讓下次 session 可以從中斷處繼續。

本專案特別需要保存的高成本上下文：索引重建進度（`embed_v3.py` 全量約 27 分鐘）、
批次工作已燒的額度（六風格全量判定約 US$7）、以及調權重時試過哪些組合。

## 使用時機

- 工作 session 結束前，關閉 Claude Code 之前
- 接近 context 限制前（先執行此指令，再開新 session）
- 解決複雜問題後想記住的時候
- 需要將上下文傳遞給未來 session 的任何時候
- **跑長時間批次前後**（全量建索引、六風格重判定、VLM 標註）

## 流程

### 步驟 1: 收集上下文

寫入檔案前收集：
- 讀取本次 session 修改的所有檔案（**專案尚未 git init，無法用 `git diff`**，改用回憶對話 + 直接讀檔比對）
- 審查討論、嘗試和決定的內容
- 記錄遇到的錯誤及解決方式
- 檢查當前檢索管線可用狀態（**本專案無建置步驟、pytest 尚未建置**），改用冒煙檢查：
  ```bash
  PY=.venv-rag/bin/python
  $PY rag_pipeline/query_parser.py "北歐風小坪數客廳"   # 解析是否正常
  $PY rag_pipeline/retriever.py   "北歐風小坪數客廳"   # 檢索是否回得出 8 筆
  ```
- 確認 `chroma_db/` 的 `furniture_v3` 是否為最新（有無跑過 `--only-changed`）

### 步驟 2: 建立 sessions 資料夾

```bash
mkdir -p .claude-roompilot/sessions
```

### 步驟 3: 寫入 session 檔案

建立 `.claude-roompilot/sessions/YYYY-MM-DD-<short-id>-session.tmp`

### 步驟 4: 填入所有區段

誠實地寫每個區段。不跳過區段 -- 如果某區段真的沒內容就寫「無」。

### 步驟 5: 向使用者展示

```
Session 已儲存至 [實際檔案路徑]

這看起來正確嗎？關閉前有什麼要修正或補充的嗎？
```

## Session 檔案格式

```markdown
# Session: YYYY-MM-DD

**開始時間:** [大約時間]
**最後更新:** [當前時間]
**專案:** RoomPilot 家具風格檢索系統（`.../final_term/Demo2/RAG`）
**主題:** [一行摘要]

---

## 我們在建構什麼
[1-3 段描述功能、bug 修復或任務]

> 範例：調整 `retriever.py:47` 的排序權重，讓「日式」查詢不再被 cream 風格洗版。
> 把 `style_compat` 從 0.20 提到 0.25、`rerank` 從 0.60 降到 0.55，用 12 組查詢做人工比對。

---

## 確認有效的部分（含證據）
- **[有效的事項]** -- 確認方式: [具體證據]

> 範例：**新增「侘寂自然」色卡到 `taxonomy_v2.json`** -- 確認方式:
> `.venv-rag/bin/python rag_pipeline/query_parser.py "想要侘寂感的臥室"`
> 回傳的 `style` 已從 null 變成 `japanese`，`mood` 含「侘寂」。

---

## 未成功的部分（及原因）
- **[嘗試的方法]** -- 失敗原因: [確切原因/錯誤訊息]

> 範例：**用 `where={"rag_indexable": True}` 過濾** -- 失敗原因:
> 命中 0 筆；`rag_indexable` 是頂層欄位、不在 `chroma_metadata` 內（見 CLAUDE.md 六個坑 #1）。

---

## 尚未嘗試的方法
- [方法/想法]

> 範例：把 `VEC_TOP_K` 從 50 拉到 80 觀察 rerank 後的召回變化（尚未跑，怕拖慢 UI 回應）。

---

## 檔案當前狀態

| 檔案 | 狀態 | 備註 |
|------|------|------|
| `rag_pipeline/retriever.py` | 完成 | 權重已改為 0.55/0.25/0.10/0.10 |
| `rag_pipeline/query_parser.py` | 進行中 | 受控詞彙已擴充，structured outputs schema 待補 `anyOf` |
| `vlm_annotation/taxonomy_v2.json` | 壞掉 | 新增色卡後 6×6 相容矩陣列數不一致，載入會 KeyError |

---

## 索引與資料狀態

| 項目 | 狀態 |
|------|------|
| `chroma_db/` collection `furniture_v3` | [最新 / 落後（待跑 `--only-changed`）/ 需全量重建] |
| `rag_dataset/furniture_enriched_v3.json` | [筆數／是否重跑過 `build_rag_v3.py`] |
| `rag_export/` 四個交付檔 | [是否與現行索引同批產出] |
| 本次批次花費 | [約 US$X；需求解析每次約 US$0.005] |

---

## 已做的決策
- **[決策]** -- 原因: [選擇此方案而非替代方案的理由]

> 範例：**維持 `bge-reranker-v2-m3` 不換 ms-marco MiniLM** -- 原因:
> MiniLM 是英文模型，中文查詢會劣化（CLAUDE.md 六個坑 #6）。

---

## 阻礙與待解決問題
- [阻礙/待解決問題]

> 範例：`rendering/` 與 `vlm_annotation/` 腳本目前無可用環境（舊 `.venv/` 已不存在），重跑前需先重建。

---

## 確切的下一步
[恢復時要做的第一件事]

> 範例：先修 `taxonomy_v2.json` 的相容矩陣，再跑
> `.venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed`，最後開 `app.py` 目視 8 張卡片。
```

## 注意事項

- 每個 session 有自己的檔案 -- 絕不附加到之前 session 的檔案
- 「未成功的部分」最關鍵 -- 沒有它未來 session 會盲目重試失敗方法
- 此檔案設計為在下次 session 開始時由 Claude 讀取
- **絕不把 `.anthropic_key` 內容或任何金鑰寫進 session 檔案**
- 索引／資料狀態一定要寫 -- 重建成本 27 分鐘，未來 session 沒這段就會盲目重跑
