---
name: sunnydata-testing
description: RoomPilot 家具檢索管線的測試驅動開發工作流，涵蓋單元、整合、端到端三層測試。Red-Green-Refactor 循環、80%+ 覆蓋率目標、pytest（本專案尚未建置）、CLI 端到端 + Gradio 冒煙。撰寫功能、修 bug、建立測試基礎設施時使用。
origin: merged(tdd-workflow + e2e-testing)
---

<!-- 繁中摘要：此技能整合了 TDD 工作流程與 RoomPilot 端到端測試模式。涵蓋單元、整合、E2E 三層測試，紅綠重構循環，80% 覆蓋率要求，及本機 runbook 整合（本專案無 CI、無 Docker）。 -->

# Testing

> 最低覆蓋率要求見 `.claude-roompilot/rules/testing.md`。
>
> **現況聲明**：本專案**目前無正式測試套件**（`tests/` 尚未建立、pytest 尚未安裝）。
> 以下所有範例以 **pytest** 為預設建議框架，**尚未建置**；執行方式一律 `.venv-rag/bin/python -m pytest`。
> 落地第一步是 `.venv-rag/bin/python -m pip install pytest pytest-cov` 並建立 `tests/`。

## Overview

所有功能都用 TDD 開發：先寫會失敗的測試，實作到通過，再重構。三層測試合力達成 80%+ 覆蓋率：

- **Unit tests 單元測試** — 個別函式與純邏輯（`style_score()`、`mood_score()`、`allocate_budget()`、`build_where()`）
- **Integration tests 整合測試** — Chroma `furniture_v3` 查詢、bge-m3 編碼、reranker 打分、`retrieve()` 全鏈路
- **E2E tests 端到端測試** — 關鍵使用者旅程：`retriever.py "<需求>"` CLI 端到端 + `app.py` Gradio 冒煙

## TDD Workflow (Red-Green-Refactor)

### When to Apply

- 撰寫新功能（新增檢索維度、新增受控詞彙、新增 Gradio 卡片欄位）
- 修 bug（先寫一支重現 bug 的測試，例如「`rag_indexable` 寫進 `where` 導致 0 筆」）
- 重構既有程式（拆 `search_item()`、抽出排序權重）
- 新增解析 schema 欄位或新的管線階段

### The 7-Step Cycle

**Step 1: Write User Journey**
```
As a [role], I want to [action], so that [benefit]

範例：
身為想佈置客廳的使用者，我想用「日式無印風、預算三萬、要有沙發和茶几」這種
自然語言描述需求，這樣我不必記得任何家具型號或關鍵字就能找到合適的物件。
```

**Step 2: Derive Test Cases**
```python
# tests/unit/test_retriever_scoring.py（尚未建置）
class TestStyleScore:
    def test_returns_1_for_exact_style_match(self): ...
    def test_falls_back_to_compat_matrix(self): ...   # japanese↔scandinavian = 0.9
    def test_handles_empty_style_list(self): ...       # 空風格需求不應炸掉
    def test_never_exceeds_1_or_drops_below_0(self): ...
```

**Step 3: Run Tests (RED — they must fail)**
```bash
.venv-rag/bin/python -m pytest tests/unit/test_retriever_scoring.py
# 預期：測試失敗 — 實作還不存在
```

**Step 4: Implement Minimal Code**
```python
# 只寫剛好能讓測試通過的程式碼
def style_score(meta: dict, styles: list, compat: dict) -> float:
    # minimal implementation
    ...
```

**Step 5: Run Tests (GREEN — they must pass)**
```bash
.venv-rag/bin/python -m pytest tests/unit/test_retriever_scoring.py
# 預期：全部通過
```

**Step 6: Refactor**
- 移除重複（`retriever.py` 與 `app.py` 各自的房型中文對照）
- 改善命名與可讀性
- 優化效能（避免每次查詢重載 taxonomy，用 `lru_cache`）
- 全程保持測試綠燈

**Step 7: Verify Coverage**
```bash
.venv-rag/bin/python -m pytest --cov=rag_pipeline --cov-report=term-missing
# 目標：branches / functions / lines / statements 都 80%+
```

### Coverage Thresholds (pytest 設定，尚未建置)
```ini
# pytest.ini — 建議內容，本專案尚未建立此檔
[pytest]
testpaths = tests
addopts =
    --cov=rag_pipeline
    --cov=json_adjustment
    --cov-branch
    --cov-fail-under=80
    --cov-report=term-missing
markers =
    slow: 需載入 bge-m3／reranker（約 4.6 GB 常駐）
    costly: 會呼叫 Anthropic API 或跑全量批次，預設不執行
```

### Watch Mode and Pre-Commit Hook
```bash
# 開發中重跑上次失敗的（需 pytest-xdist / pytest-watch，尚未安裝）
.venv-rag/bin/python -m pytest --lf -x

# Pre-commit 檢查（專案尚未 git init，git hook 目前無法註冊；先當成手動 checklist）
.venv-rag/bin/python -m pytest -m "not slow and not costly" && \
  .venv-rag/bin/python -m compileall -q rag_pipeline json_adjustment
```

---

## Unit Tests

### Pattern (pytest，純函式優先)
```python
# tests/unit/test_card_html.py（尚未建置）
import pytest
from rag_pipeline.app import card_html

class TestCardHtml:
    def test_renders_item_name(self):
        html = card_html({"name": "橡木餐椅", "price": 3200}, images={})
        assert "橡木餐椅" in html

    def test_escapes_user_supplied_text(self):
        html = card_html({"name": "<script>x</script>", "price": 100}, images={})
        assert "<script>" not in html          # 必須經過 html.escape

    def test_renders_placeholder_when_image_missing(self):
        html = card_html({"name": "無圖沙發", "price": 8800}, images={})
        assert "data:image" not in html        # 沒有渲染圖就不塞 base64
```

### Mocking External Services

**ChromaDB（`furniture_v3` collection）**
```python
# 不碰 chroma_db/，用假 collection 驗證 where 條件與結果組裝
@pytest.fixture
def fake_collection(monkeypatch):
    class FakeCollection:
        def __init__(self):
            self.last_kwargs = None
        def query(self, **kwargs):
            self.last_kwargs = kwargs          # 之後可斷言 where 沒混進 rag_indexable
            return {
                "ids": [["abo_0001"]],
                "metadatas": [[{"style_primary": "japanese", "price": 3200}]],
                "distances": [[0.18]],
                "documents": [["日式橡木餐椅…"]],
            }
    col = FakeCollection()
    monkeypatch.setattr("rag_pipeline.retriever.load_collection", lambda: col)
    return col
```

**Reranker（`BAAI/bge-reranker-v2-m3`）**
```python
# CrossEncoder 已內建 sigmoid，mock 必須直接回 0–1，不可再套一層
@pytest.fixture
def fake_reranker(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, **_):
            return [0.92, 0.71, 0.05][: len(pairs)]
    monkeypatch.setattr(
        "rag_pipeline.retriever.load_models",
        lambda: (object(), FakeCrossEncoder()),
    )
```

**Anthropic Haiku 需求解析（`claude-haiku-4-5`）**
```python
# 不真的呼叫 API（每次約 US$0.005），直接回一份符合 schema 的 parsed dict
@pytest.fixture
def fake_parse_query(monkeypatch):
    parsed = {
        "room_type": "living_room",
        "styles": ["japanese", "scandinavian"],
        "moods": ["溫暖", "自然"],
        "budget_total": 30000,
        "items": [{"group": "sofa", "qty": 1, "semantic_query": "淺色布沙發 原木腳"}],
        "confidence": 0.86,
    }
    monkeypatch.setattr("rag_pipeline.query_parser.parse_query", lambda *_, **__: parsed)
    return parsed
```

**bge-m3 向量（1024 維、normalized）**
```python
# 索引測試不載入 2 GB 模型，用固定假向量
@pytest.fixture
def fake_embedder(monkeypatch):
    import numpy as np
    vec = np.full(1024, 1.0 / 32.0, dtype="float32")   # L2 norm = 1
    monkeypatch.setattr(
        "rag_pipeline.embed_v3.encode_batch",
        lambda texts, **__: [vec.tolist() for _ in texts],
    )
```

---

## Integration Tests

### 檢索管線整合 Pattern（`retrieve()` 對真實 Chroma）
```python
# tests/integration/test_retrieve_pipeline.py（尚未建置）
import pytest
from rag_pipeline.retriever import retrieve

pytestmark = pytest.mark.slow          # 會載入 bge-m3 + reranker，約 4.6 GB

class TestRetrievePipeline:
    def test_returns_final_top_k_at_most(self, parsed_living_room):
        result = retrieve(parsed_living_room)
        assert len(result["items"][0]["hits"]) <= 8          # FINAL_TOP_K

    def test_hard_filter_respects_room_and_price(self, parsed_living_room):
        result = retrieve(parsed_living_room)
        for hit in result["items"][0]["hits"]:
            assert hit["meta"]["price"] <= 30000 * 1.3       # BUDGET_SLACK

    def test_never_returns_zero_hits_for_common_request(self, parsed_living_room):
        # 迴歸守門：where 混進 rag_indexable 會讓這條變 0 筆
        result = retrieve(parsed_living_room)
        assert sum(len(i["hits"]) for i in result["items"]) > 0

    def test_degrades_gracefully_when_collection_missing(self, monkeypatch):
        # mock Chroma 開啟失敗，驗證錯誤訊息可讀、不是裸 traceback
        ...
```

### 需求解析整合 Pattern（`parse_query()` 對真實 schema）
```python
# tests/integration/test_query_parser_contract.py（尚未建置）
import pytest
from rag_pipeline.query_parser import build_schema, load_vocab

class TestParserContract:
    def test_nullable_enum_uses_anyOf(self):
        styles, groups = load_vocab()
        # load_vocab() 回傳 (tax["styles"], 整份 category_groups.json)，
        # 後者頂層是 version / note / groups / room_default_sets —— 群組表在 groups["groups"]。
        # 這行必須與 rag_pipeline/query_parser.py:214 的真實呼叫一致，否則測的是假 schema。
        schema = build_schema(list(styles), list(groups["groups"]))
        room = schema["properties"]["room_type"]
        assert "anyOf" in room            # 寫成 type 陣列會被 API 回 400

    def test_style_enum_is_exactly_six(self):
        styles, _ = load_vocab()
        assert len(styles) == 6           # 六風格 taxonomy，多一個就是詞表漂移

    def test_group_enum_matches_category_groups_json(self):
        _, groups = load_vocab()
        # 陷阱：len(groups) 是 4（整份 JSON 的頂層鍵數），不是群組數，斷言要往裡一層。
        assert len(groups["groups"]) == 19       # category_groups.json 現有 19 個檢索群組
        # 群組刻意允許重疊（兒童桌同屬 desk 與 kids、電視櫃同屬 storage 與 media），
        # 所以「細類數 × 群組數」不會相等，別拿細類總數回推群組數。
```

---

## E2E Tests（CLI 端到端 + Gradio 冒煙）

本專案沒有瀏覽器自動化框架（**Playwright 未安裝，列為可選方案**，見本節末）。
端到端＝**用真實指令跑完整條管線**：`query_parser.py` → `retriever.py` → `app.py`。

### Directory Structure
```
tests/                       # 尚未建置，以下為建議佈局
├── conftest.py              # 共用 fixture（parsed 樣本、假 collection、CLI runner）
├── unit/
│   ├── test_retriever_scoring.py
│   └── test_card_html.py
├── integration/
│   ├── test_retrieve_pipeline.py
│   └── test_query_parser_contract.py
└── e2e/
    ├── cli/
    │   ├── test_query_parser_cli.py    # $PY rag_pipeline/query_parser.py "<需求>"
    │   ├── test_retriever_cli.py       # $PY rag_pipeline/retriever.py "<需求>"
    │   └── test_embed_smoke.py         # $PY rag_pipeline/embed_v3.py --limit 50
    └── ui/
        └── test_gradio_smoke.py        # 啟動 app.py，打 127.0.0.1:7860
fixtures/
├── queries.json             # 代表性需求語句（六風格 × 9 房型）
└── expectations.json        # 每條需求的最低允收條件
pytest.ini
```

### CLI Runner 物件（Page Object Model 的本專案對應物）
```python
# tests/e2e/cli/runner.py（尚未建置）
import json
import subprocess
from pathlib import Path

PROJ = Path(__file__).resolve().parents[3]
PY = PROJ / ".venv-rag" / "bin" / "python"

class RetrieverCli:
    """把 CLI 呼叫封裝成物件 —— 測試只描述意圖，不重複拼指令字串。"""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.proc = None

    def search(self, query: str) -> "RetrieverCli":
        self.proc = subprocess.run(
            [str(PY), str(PROJ / "rag_pipeline" / "retriever.py"), query],
            capture_output=True, text=True, timeout=self.timeout,
        )
        return self

    @property
    def ok(self) -> bool:
        return self.proc.returncode == 0

    def hits(self) -> list:
        """從 stdout 抓出結果列（CLI 目前輸出人類可讀文字＋JSON 區塊）。"""
        start = self.proc.stdout.find("{")
        return json.loads(self.proc.stdout[start:])["items"] if start >= 0 else []

    def hit_count(self) -> int:
        return sum(len(i.get("hits", [])) for i in self.hits())
```

### Test Structure with CLI Runner
```python
# tests/e2e/cli/test_retriever_cli.py（尚未建置）
import pytest
from .runner import RetrieverCli

pytestmark = pytest.mark.slow

class TestRetrieverCli:
    @pytest.fixture
    def cli(self):
        return RetrieverCli()

    def test_should_search_by_natural_language(self, cli, tmp_path):
        cli.search("日式無印風客廳，預算三萬，要沙發和茶几")

        assert cli.ok
        assert cli.hit_count() > 0
        assert cli.hit_count() <= 8 * 2               # FINAL_TOP_K × 品項數
        (tmp_path / "search-results.json").write_text(cli.proc.stdout)

    def test_should_handle_no_results_gracefully(self, cli):
        cli.search("太空站用的反重力衣櫃，預算三塊錢")

        assert cli.ok                                  # 查無結果不是錯誤
        assert "找不到" in cli.proc.stdout or cli.hit_count() == 0
```

### 端到端執行設定（本機 runbook，取代 playwright.config）
```python
# tests/conftest.py（尚未建置）
import os
import pytest

# 六個坑 #4：HF Hub 未登入被限流會卡數分鐘 —— 測試環境同樣要離線
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:7860")   # Gradio 預設位址

def pytest_addoption(parser):
    parser.addoption("--run-costly", action="store_true",
                     help="開啟會呼叫 Anthropic API／跑全量批次的測試")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-costly"):
        return
    skip = pytest.mark.skip(reason="需 --run-costly（會產生 API 費用）")
    for item in items:
        if "costly" in item.keywords:
            item.add_marker(skip)

@pytest.fixture(scope="session")
def gradio_server():
    """啟動 app.py，等 7860 就緒後交給測試；結束時關閉。"""
    import subprocess, socket, time
    proc = subprocess.Popen([".venv-rag/bin/python", "rag_pipeline/app.py"])
    deadline = time.time() + 180        # 預熱 bge-m3 + reranker 可能要 1–2 分鐘
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", 7860)) == 0:
                break
        time.sleep(1)
    else:
        proc.terminate()
        pytest.fail("Gradio 未在 180 秒內就緒")
    yield BASE_URL
    proc.terminate()
```

### Gradio 冒煙測試
```python
# tests/e2e/ui/test_gradio_smoke.py（尚未建置）
import urllib.request
import pytest

pytestmark = pytest.mark.slow

def test_ui_serves_root(gradio_server):
    with urllib.request.urlopen(gradio_server, timeout=30) as resp:
        assert resp.status == 200

def test_ui_search_returns_cards(gradio_server):
    """走 Gradio 的 /gradio_api/call 介面送一條需求，驗證回傳含卡片 HTML。"""
    ...   # 斷言回應含 <div class="card"> 與至少一個價格欄位

def test_ui_clarify_buttons_present(gradio_server):
    """追問按鈕最多 MAX_CLARIFY=4 個，不可超出。"""
    ...
```

### Playwright（可選方案，本專案未安裝）
> 若日後要對 Gradio 卡片做視覺驗證，可額外導入 Playwright 的 Python 綁定與 Page Object Model。
> **現階段不採用**：本專案只有 Python 3.11 環境（`.venv-rag/`），沒有前端建置鏈，
> 且 Gradio 卡片由 `card_html()` 產生 —— 直接對該函式做單元測試的成本遠低於瀏覽器自動化。
> 有需求時的替代路徑：`.venv-rag/bin/python -m pip install playwright` + `playwright install chromium`，
> 以 `sync_playwright()` 對 `http://127.0.0.1:7860` 截圖比對。導入前須先寫 ADR。

### Flaky Test Diagnosis and Isolation

**Quarantine a flaky test**
```python
@pytest.mark.xfail(reason="LLM 解析偶發把「三萬」讀成 3 —— 追蹤於 docs/query_parser_spec.md", strict=False)
def test_budget_parsing_chinese_numeral():
    ...

@pytest.mark.skipif(
    not (PROJ / ".anthropic_key").exists(),
    reason="無金鑰時跳過；需求解析走真實 API",
)
def test_parse_query_live():
    ...
```

**Reproduce flakiness locally**
```bash
# 重複跑同一支（需 pytest-repeat，尚未安裝）
.venv-rag/bin/python -m pytest tests/e2e/cli/test_retriever_cli.py --count=10

# 不裝套件的做法：純 shell 重跑
for i in $(seq 1 10); do .venv-rag/bin/python -m pytest tests/e2e/cli -q || break; done
```

**Race conditions（模型載入）**
```python
# Bad：假設 bge-m3 / reranker 已就緒就直接查
result = retrieve(parsed)

# Good：測試前顯式預熱一次，讓載入成本不落在第一條斷言上
load_models()          # session fixture 內做，之後 lru_cache 命中
result = retrieve(parsed)
```

**Network timing（HF Hub 與 Anthropic）**
```python
# Bad：讓測試在無網路時默默去 HF Hub 拉權重，卡數分鐘後才 timeout
# Good：離線化 + 明確標記需要外網的測試
os.environ.setdefault("HF_HUB_OFFLINE", "1")     # 六個坑 #4，勿移除

@pytest.mark.costly                               # 預設不執行，需 --run-costly
def test_haiku_returns_valid_schema():
    ...
```

**啟動時序（Gradio 預熱）**
```python
# Bad：睡固定秒數就假設 UI 起來了
time.sleep(5)

# Good：輪詢真實就緒條件（連得上 7860 才往下走）
while time.time() < deadline:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 7860)) == 0:
            break
    time.sleep(1)
```

### Artifact Management

**檢索結果快照（取代 screenshots）**
```python
# 把 CLI 輸出留檔，回歸時做 diff —— 這是本專案的「截圖」
(ART / "search-japanese-living-room.json").write_text(cli.proc.stdout, encoding="utf-8")
(ART / "parsed-japanese-living-room.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
(ART / "top1-card.html").write_text(card_html(result["items"][0]["hits"][0], images), encoding="utf-8")
```

**Trace（取代 Playwright trace）**
```python
# retriever 各階段筆數與耗時就是 trace：候選 50 → rerank 20 → 收斂 8
trace = {
    "vec_top_k": 50, "rerank_top_k": 20, "final_top_k": 8,
    "where": where, "elapsed_s": round(t1 - t0, 2),
}
(ART / "retrieve-trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2))
```

**UI 產出物（取代 video）**
```python
# 沒有錄影機制；改為失敗時保留 Gradio 進程的 stdout/stderr 與最後一次回應 HTML
ART = PROJ / "artifacts"        # 建議加入 .gitignore
(ART / "gradio-stdout.log").write_bytes(proc.stdout.read())
(ART / "last-response.html").write_text(last_html, encoding="utf-8")
```

### 本機執行 Runbook（**本專案無 CI、無 Docker**）
```bash
# 取代 CI pipeline —— 交付前依序手動執行，每步都要看到綠燈才往下
PY=.venv-rag/bin/python

# 1. 快測：不載模型、不呼叫 API
$PY -m pytest -m "not slow and not costly" -q

# 2. 索引冒煙：只跑 50 筆，確認 embed 流程沒壞
$PY rag_pipeline/embed_v3.py --limit 50

# 3. CLI 端到端：解析 + 檢索各一條代表性需求
$PY rag_pipeline/query_parser.py "日式無印風客廳，預算三萬"
$PY rag_pipeline/retriever.py   "日式無印風客廳，預算三萬，要沙發和茶几"

# 4. UI 冒煙：啟動後手動打開 http://127.0.0.1:7860 送一條需求、確認卡片有圖有價
$PY rag_pipeline/app.py
```

### 覆蓋率報告（本機產出，無上傳服務）
```bash
# 取代 CI 的 coverage 上傳 —— 產出本機 HTML 報告後自行檢閱
.venv-rag/bin/python -m pytest --cov=rag_pipeline --cov=json_adjustment \
  --cov-report=html:artifacts/coverage --cov-report=term-missing
open artifacts/coverage/index.html
```

### 外部服務整合測試（Anthropic / Ollama）
```python
# 外部依賴不是瀏覽器錢包，而是 LLM 供應商；測試要能在「無金鑰／無 Ollama」時明確跳過
@pytest.mark.costly
def test_haiku_structured_output_contract():
    key = (PROJ / ".anthropic_key")
    if not (key.exists() or os.environ.get("ANTHROPIC_API_KEY")):
        pytest.skip("無 Anthropic 金鑰")           # 絕不回顯金鑰內容
    parsed = parse_query("北歐風臥室，兩萬以內")
    assert set(parsed) >= {"room_type", "styles", "items", "confidence"}

@pytest.mark.costly
def test_ollama_qwen3_reachable():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
    except OSError:
        pytest.skip("本機 Ollama 未啟動")            # 批次風格判定才需要
```

### 高成本／高風險流程測試（批次作業）
```python
# 對應「金流測試」的位置 —— 本專案的真金白銀是 API 額度與 27 分鐘的全量重建
@pytest.mark.costly
def test_full_reindex_is_never_run_by_accident(monkeypatch):
    """全量建索引約 27 分鐘、全量風格判定約 US$7 —— 測試只驗證守門，不真的跑。"""
    calls = []
    monkeypatch.setattr("rag_pipeline.embed_v3.encode_batch", lambda t, **k: calls.append(len(t)) or [])

    rc = embed_main(["--limit", "50"])             # 冒煙路徑
    assert rc == 0
    assert sum(calls) <= 50                        # 絕不可整批 9,349 筆被觸發

@pytest.mark.costly
def test_only_changed_reuses_existing_vectors():
    """--only-changed 依 text_hash 比對，646 筆約 1.5 分鐘；重算全量就是回歸。"""
    ...
```

---

## Common Mistakes

### Test behavior, not implementation details
```python
# Wrong：斷言內部中間狀態
assert retriever._last_where["style_primary"] == "japanese"

# Correct：斷言使用者看得到的結果
assert all(h["meta"]["style_primary"] in {"japanese", "scandinavian"}
           for h in result["items"][0]["hits"])
```

### Use stable selectors / 穩定的識別欄位
```python
# Wrong：拿易變的排序位置或中文顯示字串當識別
assert result["items"][0]["hits"][3]["name"] == "橡木餐椅"

# Correct：用穩定 id 與可驗證的屬性
ids = {h["id"] for h in result["items"][0]["hits"]}
assert "abo_0001" in ids
assert all(h["meta"]["category_group"] == "sofa" for h in result["items"][0]["hits"])
```

### Isolate every test
```python
# Wrong：測試之間共用同一個 parsed dict，前一支改了後一支就爆
parsed = load_sample()                    # 模組層級共用，且會被就地修改
def test_a(): parsed["budget_total"] = 1
def test_b(): assert parsed["budget_total"] == 30000   # 依賴執行順序

# Correct：每支測試自己造資料（且不可變 —— 產生新 dict 而非改舊的）
@pytest.fixture
def parsed_living_room():
    return {"room_type": "living_room", "styles": ["japanese"], "budget_total": 30000,
            "items": [{"group": "sofa", "qty": 1, "semantic_query": "淺色布沙發"}]}

def test_b(parsed_living_room):
    tighter = {**parsed_living_room, "budget_total": 15000}    # spread，不改原物件
```

### Never use arbitrary timeouts
```python
# Wrong
time.sleep(5)

# Correct：等待確定性條件
wait_until(lambda: socket_open("127.0.0.1", 7860), timeout=180)
assert (PROJ / "rag_export" / "furniture_embeddings_bge_m3.jsonl").exists()
```

### Test error paths, not just happy paths
```python
# 一定要涵蓋：空輸入、無結果、外部服務失效、邊界值
def test_handles_empty_query_gracefully(): ...        # 空字串需求
def test_returns_empty_not_crash_when_filter_matches_nothing(): ...
def test_raises_readable_error_when_chroma_dir_missing(): ...
def test_price_boundary_is_inclusive_at_budget_ceiling(): ...
```

### 別把六個坑寫成測試的前提
```python
# Wrong：測試跟著錯誤實作走，把 bug 固化成契約
def test_where_includes_rag_indexable():
    assert build_where(...)["rag_indexable"] is True       # 這樣會命中 0 筆

# Correct：測試守住正確行為
def test_where_never_contains_rag_indexable():
    assert "rag_indexable" not in build_where(item, parsed, allocated, data)

def test_rerank_score_is_not_sigmoided_twice():
    assert 0.0 <= score <= 1.0 and score == pytest.approx(raw_cross_encoder_score)
```

---

## Success Metrics

- 80%+ 覆蓋率（branches / functions / lines / statements），範圍至少涵蓋 `rag_pipeline/`
- 全部測試通過 —— 沒有無追蹤事由的 skip / xfail
- 單元測試總時間 < 30 秒；單支 < 50ms（載模型的一律標 `slow`，不算在內）
- 端到端測試涵蓋所有關鍵旅程：需求解析 → 檢索 → 卡片呈現 → 追問
- 沒有 flaky 測試（本專案無 CI，改以本機連跑 10 次驗證穩定度；隔離時必須寫明追蹤事由）
- 測試能在交付前擋下回歸 —— 尤其六個坑的每一條都有對應的守門測試
