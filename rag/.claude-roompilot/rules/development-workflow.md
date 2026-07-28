# 開發工作流

## 鐵律：先開分支，再動程式碼

**任何修改程式碼的動作之前，必須確認在正確的工作分支上。**

收到開發任務時，第一步永遠是：

```bash
git branch --show-current
git status
```

| 當前狀態 | 行動 |
| :------- | :--- |
| 在 `main`/`master` 上 | **停止。** 詢問使用者：要建新分支還是切到既有分支？ |
| 在功能分支但有未提交變更 | **停止。** 詢問使用者：先 commit 還是放棄這些變更？ |
| 在功能分支且乾淨 | 確認分支名稱與任務匹配，繼續 |
| 使用者直接說「改這個」沒提分支 | **停止。** 詢問使用者分支策略 |
| **指令報 `not a git repository`** | 本專案**尚未 git init** → 改走下方「無 git 時的替代做法」 |

### 無 git 時的替代做法（現況適用）

專案尚未 `git init`，上面兩條指令目前會失敗。在 init 之前：

1. **先備份會被覆寫的資料檔**，再動程式碼：

```bash
cp rag_dataset/furniture_enriched_v3.json rag_dataset/furniture_enriched_v3.json.bak
cp -R rag_export rag_export.bak          # 建索引前必備份（embed_v3 會重寫四個交付檔）
cp -R chroma_db chroma_db.bak            # 重建索引前必備份（9,349 筆，重跑要 27 分鐘）
```

2. 程式碼改動前，把要改的檔案複製成 `<檔名>.bak`（如 `retriever.py.bak`）
3. 驗證通過後刪除 `.bak`；驗證失敗直接覆蓋還原
4. 建議儘早向使用者提議 `git init`，並在第一個 commit 前把
   `.anthropic_key`、`chroma_db/`、`rendering/output/`、`*.bak` 寫進 `.gitignore`

### 禁止行為

- 禁止在 `main`/`master` 上直接修改程式碼
- 禁止用 `git stash` 作為工作流（stash 是臨時工具，不是分支替代品）
- 禁止在一個功能分支上混做不相關的任務
- 禁止跳過分支直接開始寫程式碼（尚未 git init 時＝禁止跳過備份直接開始寫）
- 禁止未備份就執行 `embed_v3.py`（非 `--limit`）或 `build_rag_v3.py`（非 `--dry-run`）

### 詢問模板

當使用者要求修改但未指定分支時：

```
開始前需要確認分支策略：

目前在：<branch-name>（或：專案尚未 git init）
未提交變更：<有/無>

建議：
1. 建新分支 <type>/<suggested-name>（推薦）
2. 在目前分支繼續（僅限已在正確功能分支上）
3. 切到既有分支 ___
4. 先 git init 再開分支（尚未 init 時的推薦選項）
5. 暫不 init，先備份 <會被覆寫的資料檔> 再改

請選擇，或告訴我你偏好的分支名稱。
```

## 功能實作流程

分支確認完成後，依以下順序執行：

### 0. 研究與重用（任何新實作前必做）
- 先讀專案內既有實作與 SSOT 文件（`docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、
  `rag_pipeline/README.md`、`json_adjustment/RAGSQL.md`）
- 再查官方文檔確認 API 行為（Anthropic structured outputs、ChromaDB `where`、
  sentence-transformers `CrossEncoder`、Gradio 6 `launch()`）
- 搜套件庫（PyPI）與 HuggingFace Hub 找現成方案，勿自行造輪子
- 優先採用經驗證的方案而非全新撰寫

### 1. 先規劃
- 載入 sunnydata-design skill
- 探索意圖與需求 → 撰寫實作計畫 → 依檢查點執行
- 動到檢索行為前，先確認落在硬過濾／軟加權／`semantic_query` 三區的哪一區

### 2. TDD 方法
- 遵循 TDD 流程（詳見 testing.md；pytest 套件尚未建置，先用手動驗證指令替代）

### 3. 程式碼審查
- 寫完程式碼後載入 sunnydata-code-review skill
- 處理 CRITICAL 和 HIGH 問題
- 對照 CLAUDE.md「六個坑」逐條確認

### 4. 提交
- 遵循 git-workflow.md 的 WHY/WHAT/IMPACT 標準
- 一個 commit 做一件事
- 同步更新受影響的 SSOT 文件（文件為契約，衝突時以文件為準）
- 載入 sunnydata-branch-lifecycle skill 完成分支收尾
- 尚未 git init 時：以「驗證通過 → 刪除 `.bak` → 在 `docs/` 記錄改動」作為收尾
