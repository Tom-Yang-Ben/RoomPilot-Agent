---
name: 14-ci-quality-gates
description: "RoomPilot 本機品質門檻 - 解析冒煙、檢索冒煙、索引覆蓋率、資料筆數與重複 ID 驗證（本專案無 CI）"
stage: "Local Quality Gates & Operations"
template_ref: "14_deployment_and_operations_guide.md"
---

# 指令 (你是本機交付把關者)

輸出**本機品質門檻**階段與通過標準,對未達標的情境提供修正建議。
將品質要求變成「提交前一定跑一遍」的固定動作,確保改動與交付的穩定性。

> ⚠️ **本專案無 CI、無 Docker、無容器化部署**,也**尚未 git init**。
> 沒有任何 workflow 檔存在,所有門檻都在**本機 macOS(Apple Silicon)**用 `.venv-rag/bin/python` 執行。
> 「阻止合併 / 阻止部署」在本專案的實際意義是:**不得把改動留在工作區、不得把 `rag_export/` 交出去**。

## 交付結構

### 1. 本機品質門檻流程

```bash
#!/usr/bin/env bash
# scripts/local_gates.sh（建議樣板，尚未建置；本專案無 CI）
set -euo pipefail
PY=.venv-rag/bin/python

echo "=== Gate 0: 環境自檢（門檻: Python 3.11、.venv-rag 存在） ==="
test -x "$PY" || { echo "缺 .venv-rag，先重建環境"; exit 1; }
$PY -c "import sys; assert sys.version_info[:2] == (3, 11), sys.version; print(sys.version)"

echo "=== Gate 1: 語法與匯入（門檻: 全部可編譯、可 import） ==="
$PY -m compileall -q rag_pipeline json_adjustment vlm_annotation
$PY -c "import sys; sys.path.insert(0, 'rag_pipeline'); import query_parser, retriever; print('import ok')"

echo "=== Gate 2: 需求解析冒煙（門檻: 回傳合法 JSON、風格值屬六風格） ==="
$PY rag_pipeline/query_parser.py "想找日式風格的木質餐桌，預算一萬以內"

echo "=== Gate 3: 檢索冒煙（門檻: 回 8 筆、無例外、主導風格收斂） ==="
$PY rag_pipeline/retriever.py "北歐風小客廳，想要淺色木頭沙發跟茶几"

echo "=== Gate 4: 索引覆蓋率（門檻: coverage_percent == 100.0、無重複 ID） ==="
$PY - <<'PYEOF'
import json, sys
r = json.load(open("rag_export/embedding_validation_report.json"))
bad = []
if r["coverage_percent"] != 100.0:        bad.append(f"覆蓋率 {r['coverage_percent']}")
if r["duplicate_furniture_ids"] != 0:     bad.append(f"重複 ID {r['duplicate_furniture_ids']}")
if r["missing_furniture_ids"] != 0:       bad.append(f"缺漏 {r['missing_furniture_ids']}")
if r["invalid_vector_count"] != 0:        bad.append(f"非法向量 {r['invalid_vector_count']}")
if list(r["dimension_distribution"]) != ["1024"]: bad.append(f"維度異常 {r['dimension_distribution']}")
print("索引驗證:", "PASS" if not bad else "FAIL " + "；".join(bad))
sys.exit(1 if bad else 0)
PYEOF

echo "=== Gate 5: 資料檔筆數與重複 ID（門檻: 9,349 筆、0 重複、風格值合法） ==="
$PY - <<'PYEOF'
import json, sys
d = json.load(open("rag_dataset/furniture_enriched_v3.json"))
items = d["items"]; ids = [i["id"] for i in items]
six = {"scandinavian","japanese","modern_minimal","cream","industrial","american"}
illegal = {s for s in (i.get("style_primary") for i in items) if s not in six}
bad = []
if len(items) != d["indexable_count"]: bad.append(f"筆數 {len(items)} != 宣告 {d['indexable_count']}")
if len(ids) != len(set(ids)):          bad.append(f"重複 ID {len(ids)-len(set(ids))}")
if illegal:                            bad.append(f"非法風格 {illegal}")
if any(not i.get("text_hash") for i in items): bad.append("有 item 缺 text_hash")
print("資料驗證:", "PASS" if not bad else "FAIL " + "；".join(bad))
sys.exit(1 if bad else 0)
PYEOF

echo "=== Gate 6: 金鑰外洩掃描（門檻: 0 命中） ==="
! grep -rn --exclude-dir=.venv-rag --exclude-dir=chroma_db --exclude=".anthropic_key" \
      -E "sk-ant-[A-Za-z0-9_-]{10,}" . || { echo "偵測到疑似金鑰！"; exit 1; }

echo "=== Gate 7: 單元測試（門檻: pytest 全綠、覆蓋率 ≥ 80%） ==="
echo "⚠️ 本專案尚無正式測試套件（pytest 尚未建置），此關暫時 SKIP。"
# 建置後改為：
# $PY -m pytest -q --cov=rag_pipeline --cov-fail-under=80

echo "全部門檻通過。"
```

### 2. 品質門檻

| 階段 | 門檻 | 不通過處理 |
|------|------|------------|
| 環境自檢 | Python 3.11.15、`.venv-rag/` 存在 | 停止,先重建環境 |
| 語法與匯入 | `compileall` 0 錯、模組可 import | 停止,先修語法 |
| 需求解析冒煙 | 回傳合法 JSON、風格值 ∈ 六風格 | 停止,先修 `query_parser.py` schema |
| 檢索冒煙 | 回 `FINAL_TOP_K=8` 筆、無例外 | 停止,先修 `retriever.py` |
| 索引覆蓋率 | `coverage_percent == 100.0` | 停止,重跑 `embed_v3.py` |
| 資料筆數與重複 ID | 9,349 筆、`duplicate_furniture_ids == 0` | 停止,回頭查 v2→v3 加工 |
| 金鑰外洩掃描 | 0 命中(`sk-ant-*`) | 停止,立刻輪換金鑰 |
| 單元測試 | 覆蓋率 ≥ 80% | **尚未建置**,建置後才啟用 |
| 交付檔完整性 | `rag_export/` 4 個檔齊全 | 不得交付給 SQL 端 |

### 3. Pre-commit 檢查

本專案**尚未 git init**,因此沒有 `.git/hooks/`,無法安裝真正的 pre-commit hook。
流程照走,但目前靠**手動執行**這份「輕量關卡」(重的 Gate 4/5 留給交付前):

```bash
# scripts/pre-commit.sh（建議樣板；專案尚未 git init，目前手動執行）
PY=.venv-rag/bin/python

$PY -m compileall -q rag_pipeline                       # 語法檢查
$PY rag_pipeline/query_parser.py "日式木質餐桌"          # 解析冒煙（約 2 秒、US$0.005）
grep -rn "sk-ant-" --exclude=".anthropic_key" rag_pipeline json_adjustment && exit 1  # 金鑰檢查
# $PY -m pytest -q tests/ -k "not slow"                 # 待 pytest 建置後啟用
```

**⚠️ 提交前必檢**:`.anthropic_key`、`chroma_db/`、`rag_dataset/*.json`(合計數十 MB)、
`rag_export/furniture_embeddings_bge_m3.jsonl`(**111 MB**)一律不得進版控,
git init 時第一件事就是把它們寫進 `.gitignore`。

### 4. 自動修復建議

```bash
PY=.venv-rag/bin/python

# 索引與資料集不同步（筆數對不上／text_hash 漂移）
$PY rag_pipeline/embed_v3.py --only-changed   # 增量重算（646 筆約 1.5 分鐘）
$PY rag_pipeline/embed_v3.py                  # 全量重建（約 27 分鐘）

# 只想先確認管線能跑通，不想等 27 分鐘
$PY rag_pipeline/embed_v3.py --limit 50       # 冒煙建索引

# v2→v3 加工結果怪怪的：先看統計，不落檔
python3 json_adjustment/build_rag_v3.py --dry-run

# 風格判定疑似漂移：抽 30 筆比對 v1/v2 一致率
$PY json_adjustment/reclassify_styles.py --compare 30

# 檢索結果不合理：開 UI 用眼睛看卡片
$PY rag_pipeline/app.py                       # → http://127.0.0.1:7860
```

**常見失敗與對應修法**:

| 症狀 | 最可能原因 | 修法 |
| :--- | :--- | :--- |
| 檢索命中 0 筆 | `rag_indexable` 被寫進 Chroma `where` | 從 `where` 拿掉;它是頂層欄位 |
| rerank 分數全部擠在 0.5 附近 | 對 CrossEncoder 輸出又套了一次 sigmoid | 移除多餘 sigmoid,`bge-reranker-v2-m3` 已輸出 0–1 |
| 解析呼叫回 400 | 可為 null 的 enum 直接寫 type 陣列 | 改用 `anyOf` |
| 模型載入卡數分鐘 | HF Hub 未登入被限流 | 確認 `HF_HUB_OFFLINE=1` 的 `setdefault` 還在,勿移除 |
| 正確結果被濾掉 | LLM 用常識推測尺寸 | 尺寸是硬過濾,未明說就不要填 |
| 中文查詢品質下降 | reranker 被換成 ms-marco MiniLM | 換回 `BAAI/bge-reranker-v2-m3` |

### 5. 未來若導入 CI,可對應的 job

**本專案目前無 CI,以下僅為對應關係表,`.github/` 目錄不存在、也不應憑空建立。**
導入前必須先完成兩件事:**git init** 與 **pytest 套件建置**。

| 本機門檻 | 未來可對應的 CI job | 導入前提 | 備註 |
| :--- | :--- | :--- | :--- |
| Gate 0 環境自檢 | `setup-python` | 無 | 需鎖 Python 3.11 |
| Gate 1 語法與匯入 | `lint` | 無 | 可加 ruff |
| Gate 2 解析冒煙 | `parser-smoke` | 需 CI 端持有 `ANTHROPIC_API_KEY` secret | 會產生費用,建議只在 PR 跑一次 |
| Gate 3 檢索冒煙 | `retrieval-smoke` | 需 `chroma_db/` 與模型快取 | 模型約 4.6 GB,CI 端成本高,建議改跑假向量 |
| Gate 4 索引覆蓋率 | `index-coverage` | 需 `rag_export/` artifact | 純讀 JSON,最容易搬上 CI |
| Gate 5 資料筆數與重複 ID | `dataset-validate` | 需 v3 資料集(49.9 MB) | 建議走 artifact 或抽樣檔 |
| Gate 6 金鑰掃描 | `secret-scan` | 無 | 最該優先導入的一關 |
| Gate 7 單元測試 | `unit-tests` + 覆蓋率門檻 | **pytest 尚未建置** | 目標 ≥ 80% |
| — | `deploy` | 無 | **本專案無 Docker、無容器部署**,不適用 |

### 6. 交付前 Runbook(取代原本的部署階段)

RoomPilot 沒有部署流水線,「上線」= **把 `rag_export/` 交給 SQL 端 + 本機把 Gradio 開起來**。

- [ ] `rag_export/` 四個檔齊全:`furniture_embeddings_bge_m3.jsonl`、`embedding_metadata.json`、
      `embedding_failures.jsonl`、`furniture_official_catagory.json`
- [ ] `embedding_metadata.json` 的 `embedding_dimension=1024`、`distance_metric=cosine`、`normalized=true`
- [ ] `embedding_validation_report.json` 的 `coverage_percent=100.0`
- [ ] `embed_v3.py` 是**同一次執行**同時寫 Chroma 與 `rag_export/`(否則 Demo 與 SQL 端會不一致)
- [ ] Gradio 能起、輸入三種代表性需求(有房型/無房型/只給風格)都回得出卡片
- [ ] 批次工作(全量建索引、風格全量判定)**不與 UI 同時跑** —— 16 GB 機器會被 4.6 GB 常駐模型擠爆
- [ ] `.anthropic_key` 沒有被複製進任何交付物

---

**記住**: 品質門檻是防止壞資料與壞改動流出的最後防線。
本專案沒有 CI 幫你把關——**這份清單就是 CI**,每次交付前用 `.venv-rag/bin/python` 從頭跑一遍,
失敗時明確告知是哪一關、哪個數字不對。
