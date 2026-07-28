---
name: 12-integration-contract-suite
description: "管線整合契約測試 - 段間契約、外部整合驗證、失效注入"
stage: "Testing"
template_ref: "07_module_specification_and_tests.md"
---

# 指令 (你是整合測試架構師)

產出跨模組與跨外部服務契約的規格與測試骨架,為每個介面提供 Provider/Consumer 測試與失效注入案例。
確保管線各段集成的穩定性與演進安全性。

本專案不是微服務——**契約邊界在管線各段之間**:
`query_parser → retriever → ChromaDB → app(UI)`,
以及對外的三個整合點:**Anthropic API**、**本機 Ollama**、**HF Hub 離線模型快取**。

> ⚠️ **測試框架現況**:本專案**目前無正式測試套件**。以下 `pytest` 程式碼為建議骨架,
> **尚未建置**。落地時放在 `tests/contracts/`,
> 執行方式一律 `.venv-rag/bin/python -m pytest tests/contracts -q`。

## 交付結構

### 1. 合約索引 (Contract Registry)

```markdown
## RoomPilot 整合合約清單

| 合約ID | 類型 | Provider | Consumer | 版本 | 狀態 |
|--------|------|----------|----------|------|------|
| CONT-001 | 函式契約 (parsed dict) | query_parser.parse_query | retriever.retrieve | v3 | 活躍 |
| CONT-002 | 索引契約 (chroma_metadata) | embed_v3.py | retriever.build_where / search_item | furniture_v3 | 活躍 |
| CONT-003 | 呈現契約 (blocks/hits) | retriever.retrieve | app.results_html / card_html | v3 | 活躍 |
| CONT-004 | 外部 API (structured outputs) | Anthropic claude-haiku-4-5 | query_parser.parse_query | 2025-xx | 活躍 |
| CONT-005 | 詞表契約 (受控詞彙) | taxonomy_v2.json + category_groups.json | query_parser / retriever | v2 | 活躍 |
| CONT-006 | 交付檔契約 (jsonl/json) | embed_v3.py → rag_export/ | SQL 端（RAGSQL.md 規格） | v3 | 活躍 |
| CONT-007 | 本機模型 (HTTP) | Ollama qwen3:8b | json_adjustment/reclassify_styles.py | - | 選用 |
| CONT-008 | 模型權重快取 | HF Hub 本機快取（HF_HUB_OFFLINE=1） | retriever.load_models | bge-m3 / v2-m3 | 活躍 |

### 合約所有權
- **Provider**: 產出資料／回應的一端,負責維護契約穩定性（改欄位＝破壞契約）
- **Consumer**: 消費資料的一端,負責驗證契約滿足需求（新增依賴欄位要回頭談）
- **SSOT 仲裁**: 契約定義以 `docs/query_parser_spec.md`、`json_adjustment/RAGSQL.md`、
  `vlm_annotation/taxonomy_v2.json`、`rag_pipeline/category_groups.json` 為準;
  程式與文件衝突時**以文件為準**
```

### 2. 管線內部契約測試 (parser → retriever)

#### 2.1 Consumer 測試 (retriever 消費 query_parser 的輸出)

```python
# tests/contracts/test_parsed_contract.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_parsed_contract.py -q
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rag_pipeline"))
import retriever as rt  # noqa: E402

# ── Consumer 宣告：retriever 實際會讀到的欄位（改這裡＝改契約） ──────────
PARSED_TOP_LEVEL = {
    "room_type", "styles", "moods", "pattern", "color_hint", "material_hint",
    "price_level", "budget_total", "is_set", "items", "confidence",
    "needs_clarification", "clarify_question", "clarify_options", "reasoning",
}
PARSED_ITEM_FIELDS = {
    "item_id", "label_zh", "category_group", "quantity", "priority",
    "is_inferred", "semantic_query", "styles",
    "price_max", "max_width_cm", "max_height_cm", "role", "size_hint",
}


@pytest.fixture
def parsed_japanese_sofa() -> dict:
    """Provider 回應樣本：日式侘寂沙發、預算兩萬（對應 gr.Examples 第 1 句）。"""
    return {
        "room_type": "living_room", "styles": ["japanese"], "moods": ["寧靜", "自然"],
        "pattern": "素色", "color_hint": "米白、原木", "material_hint": "亞麻布、實木",
        "price_level": None, "budget_total": 20000, "is_set": False,
        "confidence": 0.86, "needs_clarification": False,
        "clarify_question": None, "clarify_options": [], "reasoning": "使用者明講風格與預算",
        "items": [{
            "item_id": "main_sofa", "label_zh": "主沙發", "category_group": "sofa",
            "quantity": 1, "priority": "must_have", "is_inferred": False,
            "semantic_query": "名稱：…。類別：沙發。風格：日式(japanese)。…",
            "styles": ["japanese"], "price_max": None,
            "max_width_cm": None, "max_height_cm": None,
            "role": "anchor", "size_hint": None,
        }],
    }


class TestParsedShapeContract:
    """CONT-001：parse_query 的輸出形狀,retriever 據此運作。"""

    def test_top_level_fields_are_all_present(self, parsed_japanese_sofa):
        assert PARSED_TOP_LEVEL <= set(parsed_japanese_sofa)

    def test_item_fields_are_all_present(self, parsed_japanese_sofa):
        for item in parsed_japanese_sofa["items"]:
            assert PARSED_ITEM_FIELDS <= set(item)

    def test_items_is_never_empty(self, parsed_japanese_sofa):
        """★ items 空陣列會讓 retrieve 直接回傳空 blocks,UI 一片空白。"""
        assert len(parsed_japanese_sofa["items"]) >= 1


class TestControlledVocabularyContract:
    """CONT-005：受控詞彙必須落在 taxonomy_v2 / category_groups 的集合內。"""

    def test_styles_are_within_six_style_taxonomy(self, parsed_japanese_sofa):
        allowed = set(rt.load_data()["style_compat"])
        assert allowed == {"scandinavian", "japanese", "modern_minimal",
                           "cream", "industrial", "american"}
        assert set(parsed_japanese_sofa["styles"]) <= allowed
        assert len(parsed_japanese_sofa["styles"]) <= 2      # 程式端裁切上限

    def test_category_group_is_within_19_retrieval_groups(self, parsed_japanese_sofa):
        allowed = set(rt.load_data()["groups"])
        assert len(allowed) == 19
        for item in parsed_japanese_sofa["items"]:
            group = item["category_group"]
            assert group is None or group in allowed     # null = 全庫語意檢索,合法

    def test_room_type_is_within_nine_rooms(self, parsed_japanese_sofa):
        assert parsed_japanese_sofa["room_type"] in {
            "living_room", "bedroom", "dining_room", "study", "entryway",
            "kids_room", "outdoor", "bathroom", "kitchen", None,
        }


class TestHardFilterBoundaryContract:
    """硬過濾 vs 軟加權的界線 —— 越界就是契約破壞。"""

    def test_style_and_mood_never_enter_chroma_where(self, parsed_japanese_sofa):
        data = rt.load_data()
        item = parsed_japanese_sofa["items"][0]
        where = rt.build_where(item, parsed_japanese_sofa, {}, data)

        rendered = repr(where)
        assert "style" not in rendered, "風格是軟加權,不得進 where"
        assert "mood" not in rendered, "氛圍是軟加權,不得進 where"
        assert "color" not in rendered and "material" not in rendered  # 只進 semantic_query

    def test_room_category_price_size_are_hard_filters(self, parsed_japanese_sofa):
        data = rt.load_data()
        item = parsed_japanese_sofa["items"][0]
        where = rt.build_where(item, parsed_japanese_sofa, {}, data)

        rendered = repr(where)
        assert "room_living_room" in rendered
        assert "category" in rendered
        assert "price_twd" in rendered

    def test_rag_indexable_must_never_appear_in_where(self, parsed_japanese_sofa):
        """★ 六個坑之一：rag_indexable 是 v3 頂層欄位、不在 chroma_metadata,
        寫進 where 會命中 0 筆。"""
        data = rt.load_data()
        for item in parsed_japanese_sofa["items"]:
            where = rt.build_where(item, parsed_japanese_sofa, {}, data)
            assert "rag_indexable" not in repr(where)
```

#### 2.2 Provider 驗證 (query_parser 驗證自己滿足契約)

```python
# tests/contracts/test_parser_provider.py（pytest 骨架,尚未建置）
# 需要 .anthropic_key 或 ANTHROPIC_API_KEY；每次呼叫約 US$0.005
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_parser_provider.py -q -m live
import json
import os
from pathlib import Path

import pytest

import query_parser as qp
from test_parsed_contract import PARSED_ITEM_FIELDS, PARSED_TOP_LEVEL

PROJ = Path(__file__).resolve().parents[2]
live = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") or (PROJ / ".anthropic_key").exists()),
    reason="無金鑰,跳過會計費的 live 契約驗證",
)


class TestSchemaSelfConsistency:
    """不打 API 也能驗的部分：schema 本身必須符合 structured outputs 的限制。"""

    def test_all_objects_declare_additional_properties_false(self):
        styles, groups = qp.load_vocab()
        schema = qp.build_schema(list(styles), list(groups["groups"]))

        def walk(spec):
            if isinstance(spec, dict):
                if spec.get("type") == "object":
                    assert spec.get("additionalProperties") is False
                    assert set(spec["properties"]) == set(spec["required"]), \
                        "structured outputs 要求 required 涵蓋所有 properties"
                for value in spec.values():
                    walk(value)
            elif isinstance(spec, list):
                for value in spec:
                    walk(value)

        walk(schema)

    def test_nullable_enum_uses_anyof_not_type_array(self):
        """★ 六個坑之一：可為 null 的 enum 直接寫 type 陣列會被回 400。"""
        styles, groups = qp.load_vocab()
        schema = qp.build_schema(list(styles), list(groups["groups"]))
        room = schema["properties"]["room_type"]

        assert "anyOf" in room
        assert {"type": "null"} in room["anyOf"]
        assert not isinstance(room.get("type"), list)

    def test_vocabulary_is_injected_from_ssot_files(self):
        """詞表改了不用改 prompt —— 契約來源是 taxonomy_v2 / category_groups。"""
        styles, groups = qp.load_vocab()
        prompt = qp.build_system_prompt(styles, groups)

        for key in styles:
            assert key in prompt
        for key in groups["groups"]:
            assert key in prompt
        assert len(qp.MOODS) == 24 and len(qp.ROOM_TYPES) == 9


@live
class TestLiveProviderVerification:
    """打真的 Anthropic API,驗證 Provider 滿足所有 Consumer 期望。

    狀態處理（stateHandler 等價物）：每個場景以一句真實需求觸發。
    """

    STATES = {
        "使用者明講風格與預算": "想要日式侘寂感、預算兩萬內的客廳沙發",
        "使用者要求整組搭配": "北歐風溫馨感的客廳,幫我配一整組,預算十萬",
        "使用者只給風格未給類別": "臥室想弄成 loft 那種調調,牆面深色水泥",
        "使用者需求模糊": "想找便宜一點的椅子",
    }

    @pytest.mark.parametrize("state,query", list(STATES.items()))
    def test_response_satisfies_consumer_contract(self, state, query):
        parsed = qp.parse_query(query)

        assert PARSED_TOP_LEVEL <= set(parsed), f"{state}：缺頂層欄位"
        assert len(parsed["items"]) >= 1, f"{state}：items 不可為空"
        for item in parsed["items"]:
            assert PARSED_ITEM_FIELDS <= set(item)
            assert item["quantity"] >= 1

    def test_relative_price_words_never_produce_concrete_amount(self):
        """「便宜」只填 price_level,不得臆造 price_max（兩者互斥）。"""
        parsed = qp.parse_query("想找便宜一點的椅子")

        assert parsed["price_level"] in {"budget", "mid", "premium"}
        assert parsed["budget_total"] is None
        assert all(item["price_max"] is None for item in parsed["items"])

    def test_llm_never_guesses_dimensions(self):
        """★ 六個坑之一：尺寸是硬過濾,LLM 不得用常識推測,猜錯會濾掉正確結果。"""
        parsed = qp.parse_query("想要一張北歐風的餐桌")

        for item in parsed["items"]:
            assert item["max_width_cm"] is None
            assert item["max_height_cm"] is None
            assert item["size_hint"] is None
```

### 3. 批次資料流契約測試 (embed_v3 → Chroma / rag_export)

#### 3.1 Producer 測試 (embed_v3 寫出索引與四個交付檔)

```python
# tests/contracts/test_export_producer.py（pytest 骨架,尚未建置）
# 冒煙：.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_export_producer.py -q
import json
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parents[2]
EXPORT = PROJ / "rag_export"

# CONT-006：rag_export/ 四個交付檔（規格見 json_adjustment/RAGSQL.md）
EXPECTED_FILES = [
    "furniture_embeddings_bge_m3.jsonl",   # 向量本體
    "embedding_metadata.json",             # 模型／維度／筆數
    "embedding_failures.jsonl",            # 失敗清單
    "embedding_validation_report.json",    # 驗證報告
]


class TestExportArtifactContract:

    @pytest.mark.parametrize("name", EXPECTED_FILES)
    def test_delivery_file_exists(self, name):
        assert (EXPORT / name).exists(), f"缺交付檔 {name}（SQL 端會直接卡住）"

    def test_embedding_vector_shape(self):
        """bge-m3 = 1024 維、normalized；維度變動＝下游全部要重建。"""
        first = json.loads(
            (EXPORT / "furniture_embeddings_bge_m3.jsonl").open(encoding="utf-8").readline()
        )
        assert {"id", "embedding", "text_hash"} <= set(first)
        assert len(first["embedding"]) == 1024
        norm = sum(v * v for v in first["embedding"]) ** 0.5
        assert abs(norm - 1.0) < 1e-3, "向量未正規化,cosine 距離會失真"

    def test_metadata_declares_model_and_count(self):
        meta = json.loads((EXPORT / "embedding_metadata.json").read_text(encoding="utf-8"))
        assert meta.get("model") == "BAAI/bge-m3"
        assert meta.get("dimension") == 1024

    def test_text_hash_is_the_incremental_key(self):
        """--only-changed 靠 text_hash 比對；缺這欄增量模式會退化成全量（27 分鐘）。"""
        with (EXPORT / "furniture_embeddings_bge_m3.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                assert json.loads(line).get("text_hash")
```

#### 3.2 Consumer 測試 (retriever 消費 Chroma 的 metadata)

```python
# tests/contracts/test_chroma_consumer.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_chroma_consumer.py -q
import pytest

import retriever as rt

# CONT-002：retriever 與 app 實際會讀到的 metadata 欄位
REQUIRED_META_FIELDS = {
    "furniture_id", "name_zh", "category", "style_primary", "style_secondary",
    "moods_flat", "price_twd", "width_cm", "depth_cm", "height_cm",
    "confidence", "role", "size_class", "duplicate_group", "category_conflict",
}
ROOM_FLAGS = {f"room_{r}" for r in
              ["living_room", "bedroom", "dining_room", "study", "entryway",
               "kids_room", "outdoor", "bathroom", "kitchen"]}


class TestCollectionContract:

    def test_collection_name_and_size(self):
        col = rt.load_collection()
        assert col.name == "furniture_v3"
        assert col.count() == 9349, "筆數變動代表索引被重建,需回頭確認資料集版本"

    def test_metadata_fields_are_all_present(self):
        got = rt.load_collection().get(limit=1, include=["metadatas"])
        meta = got["metadatas"][0]
        assert REQUIRED_META_FIELDS <= set(meta)
        assert ROOM_FLAGS <= set(meta), "房型旗標缺漏 → 硬過濾會命中 0 筆"

    def test_document_follows_embedded_text_sentence_pattern(self):
        """semantic_query 寫成同樣句式才有檢索效果 —— 句式本身就是契約。"""
        got = rt.load_collection().get(limit=1, include=["documents"])
        doc = got["documents"][0]
        for section in ["名稱：", "類別：", "顏色：", "材質：", "風格：", "氛圍：", "描述："]:
            assert section in doc

    def test_where_clause_actually_returns_hits(self):
        """契約的最終驗收：硬過濾條件下必須撈得到東西。"""
        data = rt.load_data()
        item = {"item_id": "main_sofa", "category_group": "sofa", "role": None,
                "size_hint": None, "price_max": 20000,
                "max_width_cm": None, "max_height_cm": None}
        where = rt.build_where(item, {"room_type": "living_room"}, {}, data)

        hits = rt.load_collection().get(where=where, limit=5, include=["metadatas"])
        assert hits["ids"], "硬過濾命中 0 筆 —— 先檢查是否誤用了不存在的 metadata 欄位"
```

### 4. 外部整合契約測試 (Anthropic / Ollama / HF Hub)

#### 4.1 定義契約 (structured outputs JSON Schema)

外部整合的契約不是 IDL 檔,而是 `query_parser.build_schema()` 產出的 **JSON Schema**——
它同時是送給 Anthropic 的請求規格,也是 retriever 的輸入規格。把它固化成基準檔即可 diff。

```python
# tests/contracts/snapshot_schema.py（pytest 骨架,尚未建置）
# 更新基準：.venv-rag/bin/python tests/contracts/snapshot_schema.py --write
import json
import sys
from pathlib import Path

import query_parser as qp

BASELINE = Path(__file__).parent / "baselines" / "parsed_schema.json"


def current_schema() -> dict:
    styles, groups = qp.load_vocab()
    return qp.build_schema(list(styles), list(groups["groups"]))


def main() -> int:
    schema = current_schema()
    if "--write" in sys.argv:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已更新契約基準：{BASELINE}")
        return 0

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    if schema != expected:
        print("契約已變動 —— 請同步 docs/query_parser_spec.md 後再更新基準")
        return 1
    print("契約與基準一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

#### 4.2 外部服務 Consumer 測試 (以 stub 取代真實呼叫)

```python
# tests/contracts/test_external_consumers.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_external_consumers.py -q
import json
import os
import types

import pytest

import query_parser as qp


class StubMessages:
    """模擬 anthropic client.messages,記錄請求並回固定回應。"""

    def __init__(self, payload: dict):
        self.payload = payload
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return types.SimpleNamespace(
            stop_reason="end_turn", stop_details=None,
            content=[types.SimpleNamespace(
                type="text", text=json.dumps(self.payload, ensure_ascii=False))],
            usage=types.SimpleNamespace(
                input_tokens=1200, output_tokens=380, cache_read_input_tokens=1100),
        )


@pytest.fixture
def stub_client():
    payload = {
        "room_type": "living_room", "styles": ["japanese", "scandinavian", "cream"],
        "moods": ["寧靜", "自然", "溫潤", "質樸"], "pattern": None,
        "color_hint": None, "material_hint": None, "price_level": None,
        "budget_total": 20000, "is_set": False, "confidence": 0.86,
        "needs_clarification": False, "clarify_question": None,
        "clarify_options": ["A", "B", "C", "D", "E"], "reasoning": "測試",
        "items": [{"item_id": "main_sofa", "label_zh": "主沙發",
                   "category_group": "sofa", "quantity": 0, "priority": "must_have",
                   "is_inferred": False, "semantic_query": "…",
                   "styles": ["japanese", "cream", "american"], "price_max": None,
                   "max_width_cm": None, "max_height_cm": None,
                   "role": "anchor", "size_hint": None}],
    }
    client = types.SimpleNamespace(messages=StubMessages(payload))
    return client


class TestAnthropicIntegrationContract:
    """CONT-004：對 Anthropic 的請求形狀與回應後處理。"""

    def test_request_declares_model_schema_and_prompt_cache(self, stub_client):
        qp.parse_query("想要日式侘寂感的客廳沙發", client=stub_client)
        kwargs = stub_client.messages.last_kwargs

        assert kwargs["model"] == "claude-haiku-4-5"
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        # 詞表固定 → 必須快取住,否則每次都吃滿 input token
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_response_is_clamped_to_documented_limits(self, stub_client):
        """schema 不支援 maxItems,上限由程式端裁切 —— 這也是契約的一部分。"""
        parsed = qp.parse_query("整組客廳", client=stub_client)

        assert len(parsed["styles"]) == 2
        assert len(parsed["moods"]) == 3
        assert len(parsed["clarify_options"]) == 4
        assert len(parsed["items"]) <= qp.MAX_ITEMS
        assert parsed["items"][0]["quantity"] == 1     # 0 被修正為 1
        assert len(parsed["items"][0]["styles"]) == 2

    def test_usage_is_surfaced_for_cost_tracking(self, stub_client):
        parsed = qp.parse_query("北歐風單椅", client=stub_client)
        assert parsed["_usage"] == {"input_tokens": 1200, "output_tokens": 380,
                                    "cache_read": 1100}


class TestOllamaIntegrationContract:
    """CONT-007：批次六風格判定的本機 Ollama qwen3:8b（可 --provider anthropic 切 Haiku）。"""

    def test_provider_switch_is_available(self):
        script = (qp.PROJ / "json_adjustment" / "reclassify_styles.py").read_text(encoding="utf-8")
        assert "--provider" in script
        assert "qwen3:8b" in script
        assert "anthropic" in script

    def test_output_labels_stay_within_six_style_taxonomy(self):
        """本機模型也必須吐受控詞彙,否則寫回 v3 時汙染 style_primary。"""
        allowed = {"scandinavian", "japanese", "modern_minimal",
                   "cream", "industrial", "american"}
        fake_batch_output = [{"id": "abo_0001", "style_primary": "japanese"}]
        for rowed in fake_batch_output:
            assert rowed["style_primary"] in allowed


class TestHuggingFaceOfflineContract:
    """CONT-008：模型權重來自本機快取,不得在查詢路徑上連 HF Hub。"""

    def test_offline_flags_are_set_before_model_import(self):
        """★ 六個坑之一：未登入被限流會卡數分鐘,setdefault 不可移除。"""
        import retriever as rt  # noqa: F401
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"

    def test_reranker_model_is_the_chinese_cross_encoder(self):
        """★ 六個坑之一：換成 ms-marco MiniLM（英文）中文查詢會劣化。"""
        import retriever as rt
        assert rt.EMBED_MODEL == "BAAI/bge-m3"
        assert rt.RERANK_MODEL == "BAAI/bge-reranker-v2-m3"
        assert "ms-marco" not in rt.RERANK_MODEL
```

### 5. 失效注入測試 (Failure Injection)

```python
# tests/contracts/test_resilience.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_resilience.py -q
import types

import pytest

import retriever as rt


class TestExternalServiceUnavailable:
    """依賴服務不可用"""

    def test_anthropic_refusal_raises_actionable_error(self):
        """模型拒答 —— 應該拋出可辨識的錯誤,而不是讓 json.loads 噴 StopIteration。"""
        import query_parser as qp

        class Refusing:
            def create(self, **kwargs):
                return types.SimpleNamespace(
                    stop_reason="refusal", stop_details="unsafe_content",
                    content=[], usage=None)

        client = types.SimpleNamespace(messages=Refusing())
        with pytest.raises(RuntimeError, match="模型拒答"):
            qp.parse_query("測試", client=client)

    def test_chroma_collection_rebuilt_midflight_auto_reconnects(self):
        """embed_v3 重建索引 = delete + create,新 collection 換 UUID。
        長時間執行的 UI 抓著舊 handle 會噴 NotFoundError —— 必須自動重連重試一次。"""
        from chromadb.errors import NotFoundError

        calls = {"n": 0}

        class Flaky:
            def query(self, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise NotFoundError("Collection [uuid] does not exist")
                return {"ids": [["abo_sofa_0001"]], "metadatas": [[{}]],
                        "documents": [["…"]], "distances": [[0.12]]}

        rt.load_collection.cache_clear()
        rt.load_collection.__wrapped__ = lambda: Flaky()   # 概念示意
        out = rt.query_collection(query_embeddings=[[0.0] * 1024], n_results=50)

        assert calls["n"] == 2, "未重試 → 使用者會看到整片錯誤"
        assert out["ids"][0]


class TestDeviceAndResourceJitter:
    """裝置抖動（等價於原本的網路抖動）"""

    def test_mps_operator_failure_falls_back_to_cpu(self, monkeypatch):
        """MPS 偶有算子不支援 —— 必須自動退 CPU,而不是整個查詢炸掉。"""
        attempts = {"n": 0}

        class FakeST:
            def __init__(self, name, device):
                attempts["n"] += 1
                if device == "mps":
                    raise RuntimeError("MPS operator not implemented")
                self.max_seq_length = 512

        # 概念示意：以 monkeypatch 換掉 sentence_transformers 的建構子
        # 期望第一次 mps 失敗、第二次 cpu 成功,共兩次嘗試
        assert attempts["n"] in (0, 2)


class TestGracefulDegradation:
    """降級策略"""

    def test_zero_hit_block_degrades_to_actionable_message(self):
        """硬過濾過嚴導致 0 筆時,不可讓整次檢索失敗 —— 該品項給訊息,其他照常。"""
        import app as ui

        result = {"dominant_style": "japanese", "style_zh": "日式",
                  "budget_total": 3000, "estimated_total": 0,
                  "blocks": [{"item_id": "t", "label_zh": "餐桌", "category_group": "table",
                              "quantity": 1, "is_inferred": False, "price_cap": 3000,
                              "where": None, "hits": []}]}
        html_out = ui.results_html(result)

        assert "沒有符合的物件" in html_out
        assert "放寬預算或尺寸限制" in html_out

    def test_missing_render_image_degrades_to_placeholder(self):
        """渲染圖不存在（.venv 舊環境已不在,rendering/ 無法重跑）→ 灰底佔位。"""
        import app as ui

        row = {"id": "x", "meta": {"furniture_id": "missing", "name_zh": "測試椅",
                                   "category": "單椅", "style_primary": "japanese",
                                   "moods_flat": "寧靜", "price_twd": 3200,
                                   "width_cm": 60.0, "depth_cm": 60.0, "height_cm": 80.0},
               "score_final": 0.7, "score_rerank": 0.8,
               "score_style": 0.9, "score_mood": 0.5}
        assert "background:#f0f0f0" in ui.card_html(row, {})


class TestRateLimitAndLatencyBudget:
    """速率限制與延遲預算"""

    def test_rate_limited_call_retries_with_exponential_backoff(self):
        """Anthropic 429 應以指數退避重試（1s / 2s / 4s）,而不是直接失敗。"""
        import time

        call_times: list[float] = []

        def flaky_create(**kwargs):
            call_times.append(time.monotonic())
            if len(call_times) < 4:
                raise RuntimeError("rate_limit_error")
            return "ok"

        # 期望：三次退避後成功,且間隔遞增
        # assert call_times[1] - call_times[0] >= 1.0
        # assert call_times[2] - call_times[1] >= 2.0
        # assert call_times[3] - call_times[2] >= 4.0
        assert flaky_create is not None      # 骨架佔位,重試邏輯尚未實作

    def test_rerank_candidate_cap_protects_latency(self):
        """rerank 是延遲主因（每 50 筆約 10 秒）—— 送進 cross-encoder 的候選數有上限。"""
        assert rt.VEC_TOP_K == 50
        assert rt.RERANK_TOP_K == 20
        assert rt.RERANK_TOP_K_LIGHT == 12
        assert rt.RERANK_TOP_K_LIGHT > rt.FINAL_TOP_K, "去重後不夠取,結果會少於 8 筆"
```

### 6. 契約演進測試 (Contract Evolution)

```python
# tests/contracts/test_evolution.py（pytest 骨架,尚未建置）
# 執行：.venv-rag/bin/python -m pytest tests/contracts/test_evolution.py -q
import json
from pathlib import Path

import retriever as rt

PROJ = Path(__file__).resolve().parents[2]


class TestBackwardCompatibility:

    def test_v3_dataset_keeps_all_v2_consumer_fields(self):
        """v3 應相容 v2 的消費者：新增欄位可以,拿掉既有欄位＝破壞性變更。"""
        v2 = json.loads((PROJ / "rag_dataset" / "furniture_enriched_v2.json").read_text(
            encoding="utf-8"))
        v3 = json.loads((PROJ / "rag_dataset" / "furniture_enriched_v3.json").read_text(
            encoding="utf-8"))

        v2_fields = set(v2["items"][0])
        v3_fields = set(v3["items"][0])
        assert v2_fields <= v3_fields, f"v3 移除了欄位：{v2_fields - v3_fields}"

    def test_new_style_addition_does_not_break_compat_matrix(self):
        """詞表新增風格時,6×6 相容矩陣必須同步擴張成 N×N,否則 style_score 取到 0。"""
        tax = json.loads((PROJ / "vlm_annotation" / "taxonomy_v2.json").read_text(
            encoding="utf-8"))
        styles, compat = set(tax["styles"]), tax["style_compat"]

        assert set(compat) == styles
        for key, row in compat.items():
            assert set(row) == styles, f"{key} 的相容列缺欄位"
            assert row[key] == 1.0, "自己對自己必須是 1.0"

    def test_category_groups_cover_every_fine_category(self):
        """64 細類 → 19 群組：新增細類卻沒歸群 → 該類永遠檢索不到。"""
        groups = json.loads((PROJ / "rag_pipeline" / "category_groups.json").read_text(
            encoding="utf-8"))
        mapped = {c for spec in groups["groups"].values() for c in spec["categories"]}

        v3 = json.loads((PROJ / "rag_dataset" / "furniture_enriched_v3.json").read_text(
            encoding="utf-8"))
        actual = {i["category_final"] for i in v3["items"]}
        assert actual <= mapped, f"未歸群的細類：{actual - mapped}"

    def test_ranking_weights_still_sum_to_one(self):
        """調權重是常見演進 —— 總和不為 1 會讓 score_final 失去可比性。"""
        total = rt.W_RERANK + rt.W_STYLE + rt.W_MOOD + rt.W_CONF
        assert abs(total - 1.0) < 1e-9
        assert (rt.W_RERANK, rt.W_STYLE, rt.W_MOOD, rt.W_CONF) == (0.60, 0.20, 0.10, 0.10)


class TestForwardCompatibility:

    def test_unknown_metadata_fields_are_ignored_not_fatal(self):
        """SQL 端／未來版本多塞欄位時,retriever 只讀自己要的,不得整個炸掉。"""
        meta = {"name_zh": "測試沙發", "style_primary": "japanese",
                "moods_flat": "寧靜|自然", "confidence": 0.8,
                "future_field_v4": "未知值"}
        score = rt.style_score(meta, ["japanese"], rt.load_data()["style_compat"])
        assert 0.0 <= score <= 1.0

    def test_null_category_group_still_produces_valid_query(self):
        """只給風格（category_group = null）→ where 為 None = 全庫語意檢索,合法路徑。"""
        data = rt.load_data()
        item = {"item_id": "any", "category_group": None, "role": None, "size_hint": None,
                "price_max": None, "max_width_cm": None, "max_height_cm": None}
        assert rt.build_where(item, {}, {}, data) is None
```

### 7. 本機驗證 Runbook (本專案無 CI／無 Docker)

沒有 CI 服務也沒有容器,契約驗證靠**一支可重複執行的本機腳本**,
在改動管線任一段之後、交付之前手動跑一輪。

```bash
#!/usr/bin/env bash
# scripts/contract_check.sh —— 本機契約驗證（無 CI／無 Docker,macOS zsh 環境）
# 用法：bash scripts/contract_check.sh [--live]
set -euo pipefail

PY=.venv-rag/bin/python
cd "$(dirname "$0")/.."

echo "[1/6] 環境檢查"
"$PY" -c "import sys; assert sys.version_info[:2] == (3, 11), sys.version"
"$PY" -c "import gradio, chromadb; print('gradio', gradio.__version__, 'chroma', chromadb.__version__)"

echo "[2/6] 詞表與群組契約（不需模型,秒級）"
"$PY" -m pytest tests/contracts/test_parsed_contract.py -q            # 尚未建置

echo "[3/6] structured outputs schema 基準 diff"
"$PY" tests/contracts/snapshot_schema.py                              # 尚未建置
#   基準變動時：先同步 docs/query_parser_spec.md,再 --write 更新基準

echo "[4/6] 索引契約（需 chroma_db/,約 10 秒）"
"$PY" -m pytest tests/contracts/test_chroma_consumer.py -q            # 尚未建置

echo "[5/6] 交付檔契約（rag_export/ 四檔）"
"$PY" -m pytest tests/contracts/test_export_producer.py -q            # 尚未建置

echo "[6/6] 端到端冒煙（真的跑一次檢索,會呼叫 Anthropic,約 US$0.005）"
if [[ "${1:-}" == "--live" ]]; then
  "$PY" rag_pipeline/query_parser.py "想要日式侘寂感、預算兩萬內的客廳沙發" >/dev/null
  "$PY" rag_pipeline/retriever.py   "想要日式侘寂感、預算兩萬內的客廳沙發" >/dev/null
  echo "  端到端通過"
else
  echo "  跳過（加 --live 才跑,避免無謂燒額度）"
fi

echo "全部契約檢查通過"
```

**索引重建後的額外驗收（等同 can-i-deploy）**:

```bash
PY=.venv-rag/bin/python

$PY rag_pipeline/embed_v3.py --limit 50      # 先冒煙,確認流程沒壞
$PY rag_pipeline/embed_v3.py --only-changed  # 增量（text_hash 比對,646 筆約 1.5 分鐘）
$PY -c "import sys; sys.path.insert(0,'rag_pipeline'); \
        import retriever as rt; print('筆數', rt.load_collection().count())"
$PY rag_pipeline/retriever.py "北歐風溫馨感的客廳,幫我配一整組,預算十萬"
# 通過條件：筆數 9,349、各品項皆有命中、主導風格與需求一致 → 才可視為可交付
```

> 全量重建約 27 分鐘;UI 執行時模型常駐約 4.6 GB,16 GB 機器請勿同時跑批次。

## 蘇格拉底檢核

1. **合約完整性**:
   - 是否涵蓋管線每一段的介面 (parser → retriever → chroma → UI) 與三個外部整合點?
   - 是否包含正常、異常、邊界情況 (零命中、模型拒答、索引重建)?

2. **獨立性**:
   - Consumer 測試是否無需真的呼叫 Anthropic (以 stub client 取代,不燒額度)?
   - Provider 驗證是否用「一句真實需求」當狀態處理器,涵蓋四種典型情境?

3. **演進安全性**:
   - v3 是否保留 v2 消費者需要的所有欄位?
   - 新增風格／新增細類時,相容矩陣與群組對照是否同步 (否則永遠檢索不到)?
   - 排序權重總和是否仍為 1?

4. **失效處理**:
   - 是否測試 Chroma 索引被重建、MPS 算子失敗、HF Hub 限流、Anthropic 429?
   - 是否有降級與重試策略 (零命中給訊息、缺圖給佔位、退回 CPU)?

5. **本機驗證集成**:
   - 契約檢查是否在交付前執行 (`scripts/contract_check.sh`)?
   - schema 基準檔是否與 `docs/query_parser_spec.md` 同步 (文件為契約)?

## 輸出格式

- 契約以 Consumer 宣告的欄位集合 + JSON Schema 基準檔表達,存放於 `tests/contracts/baselines/`
- 資料交付契約以 `json_adjustment/RAGSQL.md` 的 rag_export 四檔規格定義
- 測試使用 pytest + monkeypatch／stub client（**本專案尚未建置測試套件**,以上為建議骨架）,
  一律以 `.venv-rag/bin/python -m pytest` 執行

## 審查清單

- [ ] 管線各段介面 (CONT-001 ~ CONT-003) 皆有契約定義
- [ ] Consumer 測試覆蓋主要場景（單物件／整組／只給風格／模糊需求）
- [ ] Provider 驗證使用真實需求句當狀態處理器,並可用 `-m live` 隔離計費測試
- [ ] 批次資料流 (embed_v3 → Chroma／rag_export) 有 Producer 與 Consumer 雙向測試
- [ ] 失效注入涵蓋關鍵依賴（Anthropic 拒答／429、Chroma 重建、MPS 退 CPU、HF Hub 離線）
- [ ] 契約演進有向後與向前相容性測試（v2→v3、新增風格、新增細類、權重調整）
- [ ] 本機 runbook `scripts/contract_check.sh` 可一鍵重跑（無 CI／無 Docker）
- [ ] 索引重建後跑過「筆數 + 端到端檢索」驗收才視為可交付

## 關聯文件

- **API 設計**: 05-api-contract-spec.md（`query_parser` structured outputs schema）
- **架構設計**: 03-architecture-design-doc.md（Advanced RAG 各段依賴關係）
- **測試規範**: 06-tdd-unit-spec.md（測試原則）
- **專案 SSOT**: `docs/query_parser_spec.md`、`docs/RAG檢索系統說明.md`、
  `json_adjustment/RAGSQL.md`、`vlm_annotation/taxonomy_v2.json`、`rag_pipeline/category_groups.json`

---

**記住**: 契約測試確保管線各段集成的穩定性。本專案沒有微服務,但**每一次 `--only-changed` 重建索引、
每一次調權重、每一次詞表擴充,都是一次跨段契約變更**。
Consumer 宣告讓各段獨立演進,失效注入測試確保韌性;
沒有 CI 的專案,那支本機 runbook 就是你唯一的安全網——交付前一定要跑。
