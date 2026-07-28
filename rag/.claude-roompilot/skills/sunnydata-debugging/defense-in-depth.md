# 縱深防禦式驗證

## 總覽

當你修好一個由無效資料造成的 bug，只在一個地方加驗證會讓人覺得夠了。
但那唯一一道檢查可能被別的程式路徑、重構或替身物件繞過
（例如 `retriever.py` 的 CLI 入口驗了、`app.py` 的 UI 入口卻沒驗）。

**核心原則：** 在資料經過的**每一層**都驗證。讓這個 bug 在結構上不可能發生。

## 為什麼要多層

單一驗證：「我們修好了這個 bug」
多層驗證：「我們讓這個 bug 不可能發生」

不同層抓到的是不同狀況：
- 入口驗證抓到大部分 bug
- 業務邏輯抓到邊界情況
- 環境守衛擋掉特定情境下的危險操作
- 除錯記錄在其他層都失守時幫你查案

## 四層

### 第 1 層：入口驗證
**目的：** 在邊界就擋掉明顯無效的輸入

```python
# rag_pipeline/query_parser.py — LLM 回傳的結構化條件進入系統的邊界
def validate_parsed(parsed: dict, style_keys: list[str], group_keys: list[str]) -> dict:
    if not isinstance(parsed, dict):
        raise ValueError("需求解析結果必須是 dict")

    for style in parsed.get("styles") or []:
        if style not in style_keys:
            raise ValueError(f"風格不在六風格受控詞彙內：{style}（合法值：{style_keys}）")

    for group in parsed.get("category_groups") or []:
        if group not in group_keys:
            raise ValueError(f"檢索群組不存在於 category_groups.json：{group}")

    budget = parsed.get("budget_total")
    if budget is not None and budget <= 0:
        raise ValueError(f"預算必須為正整數，收到：{budget}")

    return parsed
```

### 第 2 層：業務邏輯驗證
**目的：** 確保資料對這個操作而言是合理的

```python
# rag_pipeline/retriever.py — build_where() 只允許確實存在於 chroma_metadata 的 key
ALLOWED_WHERE_KEYS = {
    "category", "price_twd", "width_cm", "height_cm", "depth_cm",
    "role", "size_class", "style_primary",
}  # room_* 前綴另行放行；rag_indexable 是頂層欄位，永遠不在此清單


def assert_where_keys(where: dict | None) -> None:
    """寫進不存在的 metadata key 不會報錯，只會靜靜命中 0 筆——所以要主動擋。"""
    if not where:
        return

    for clause in where.get("$and", [where]):
        for key in clause:
            if key.startswith("room_") or key in ALLOWED_WHERE_KEYS:
                continue
            raise ValueError(
                f"where 條件用了不存在於 chroma_metadata 的欄位：{key}（會命中 0 筆）"
            )
```

### 第 3 層：環境守衛
**目的：** 防止在特定情境下做出危險操作

```python
# 批次工作（reclassify_styles.py / vlm_annotation/）啟動前的守衛
import os
import sys
from pathlib import Path


def guard_batch_run(estimated_items: int) -> None:
    # 1) 模型載入：未設離線會去問 HF Hub，被限流時乾等數分鐘
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # 2) 金鑰：只確認存在，絕不回顯內容
    has_key = Path(".anthropic_key").exists() or bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        raise RuntimeError("找不到 .anthropic_key 或 ANTHROPIC_API_KEY，批次工作中止")

    # 3) 成本：全量六風格判定約 US$7，超過門檻要人工確認
    if estimated_items > 1000 and os.environ.get("ROOMPILOT_BATCH_CONFIRM") != "1":
        raise RuntimeError(
            f"本次將處理 {estimated_items} 筆（預估成本可觀）。"
            "確認後請設 ROOMPILOT_BATCH_CONFIRM=1 再跑。"
        )

    # 4) 記憶體：UI 常駐約 4.6 GB，16 GB 機器不要同時跑批次
    if os.environ.get("ROOMPILOT_UI_RUNNING") == "1":
        print("警告：偵測到 UI 正在執行，批次可能造成 MPS 記憶體不足", file=sys.stderr)
```

### 第 4 層：除錯探針
**目的：** 留下可供查案的上下文

```python
# rag_pipeline/retriever.py — 在危險操作之前記錄
import json
import sys
import traceback


def log_before_query(where: dict | None, semantic_query: str) -> None:
    print("DEBUG chroma query:", json.dumps({
        "where": where,
        "semantic_query": semantic_query,
        "collection": "furniture_v3",
    }, ensure_ascii=False), file=sys.stderr)
    traceback.print_stack(file=sys.stderr)
```

## 套用這個模式

當你找到一個 bug：

1. **追資料流** — 壞值從哪來？在哪裡被用？
2. **列出所有檢查點** — 把資料經過的每個地方都列出來
3. **每一層都加驗證** — 入口、業務、環境、除錯
4. **逐層測試** — 試著繞過第 1 層，確認第 2 層真的擋得住

## 實際案例

Bug：`where` 混進 `rag_indexable`，導致檢索永遠回 0 筆

**資料流：**
1. 需求解析 → `parsed`（受控詞彙）
2. `build_where(item, parsed, allocated, data)` → 組出 `$and` clauses
3. `query_collection(..., where=where)` → Chroma 對不存在的 key 一律不匹配
4. `retrieve()` 回傳空清單 → Gradio 卡片全空

**加上的四層：**
- 第 1 層：`validate_parsed()` 確認風格／群組都在受控詞彙內
- 第 2 層：`assert_where_keys()` 只放行確實存在於 `chroma_metadata` 的 key
- 第 3 層：`guard_batch_run()` 擋掉離線設定缺失、無金鑰、超量與記憶體衝突
- 第 4 層：查詢前把 `where` 與呼叫堆疊印到 stderr

**結果：** 12 句回歸查詢全部回得出 8 張卡片，這個 bug 無法再重現

## 關鍵洞見

四層都是必要的。實際驗證時，每一層都抓到了其他層漏掉的問題：
- 不同的程式路徑會繞過入口驗證（CLI 走 `main()`、UI 走 `on_submit()`）
- 手動塞測試資料時會繞過業務邏輯檢查
- 不同執行環境（MPS vs CPU、有無金鑰）的邊界情況需要環境守衛
- 除錯記錄揭露了結構性誤用（把資料檔頂層欄位當成向量庫 metadata）

**不要只加一個驗證點。** 每一層都加。
