---
name: 10-backend-python-impl
description: "RoomPilot Python 管線實作 - 以務實版 Clean Architecture 生成 rag_pipeline 程式碼骨架"
stage: "Development"
template_ref: "07_module_specification_and_tests.md"
---

# 指令 (你是資深 Python 檢索系統架構師)

基於六風格 taxonomy 與 v3 資料集契約,生成符合「務實版 Clean Architecture」的 Python 3.11 程式碼骨架。

RoomPilot 是**純檢索系統(R 沒有 G)**:沒有 Web 框架、沒有 ORM、沒有資料庫連線池。
外部依賴只有五種——本機 JSON 資料集(`furniture_enriched_v3.json`,**49.9 MB**)、
ChromaDB persistent client(`chroma_db/`,collection `furniture_v3`,9,349 筆)、
HuggingFace 本機模型(`BAAI/bge-m3` + `BAAI/bge-reranker-v2-m3`,UI 執行時常駐約 **4.6 GB**)、
雲端 LLM(`claude-haiku-4-5`,structured outputs + prompt caching)、
本機 Ollama(`qwen3:8b`,批次風格判定)。

代碼需包含完整型別註記、frozen dataclass 值物件、明確的錯誤處理與重試策略,並將職責清晰分離。
執行方式**一律** `.venv-rag/bin/python`(Python 3.11.15,唯一環境 `.venv-rag/`)。

## 交付結構

### 1. 目錄結構 (務實版 Clean Architecture)

#### 1.1 現況:分層存在,但落在單體腳本裡

本專案**沒有** `src/` 佈局,四支腳本各自身兼多層。這是刻意的取捨——
9,349 筆的單機檢索 demo,拆成 20 個檔案的 import 成本大於收益。
但**分層邊界必須在腦中清楚存在**,否則調權重時會誤改到 I/O、換模型時會動到排序公式。

```
RAG/
├── rag_pipeline/                  # 「應用程式」本體(單體腳本,無 Web 框架)
│   ├── app.py                     # Presentation:Gradio Blocks + 卡片 HTML + 啟動預熱
│   ├── query_parser.py            # Infrastructure(LLM 呼叫) + Domain(受控詞彙與 schema)
│   ├── retriever.py               # Application(檢索編排) + Domain(排序公式與權重)
│   ├── embed_v3.py                # Infrastructure(批次):建索引 + rag_export 四個交付檔
│   ├── category_groups.json       # Domain 詞彙契約:64 細類 → 19 檢索群組 + 房型典型組合
│   └── README.md                  # 管線操作手冊(SSOT)
├── json_adjustment/               # 資料建置批次(Infrastructure/Batch)
│   ├── build_rag_v3.py            # v2 → v3 加工(embedded_text / chroma_metadata / text_hash)
│   ├── build_taxonomy_v2.py       # 六風格詞表與 6×6 相容矩陣建置
│   ├── reclassify_styles.py       # 六風格判定(Ollama qwen3:8b,可 --provider anthropic)
│   ├── RAGSQL.md                  # SQL 端交付規格(契約文件)
│   └── i_need_rag.md              # SQL 端欄位需求(契約文件)
├── vlm_annotation/                # VLM 標註批次(可續跑)
│   ├── taxonomy_v2.json           # Domain 詞彙契約:六風格 + style_compat 矩陣
│   ├── annotate_full.py           # 全量標註(jsonl 進度檔 + 就地合併前先備份)
│   └── *.jsonl                    # append-only 進度檔
├── rag_dataset/                   # furniture_enriched_v1/v2/v3.json(v3 現役,49.9 MB)
├── rag_export/                    # SQL 端交付:向量 jsonl、metadata、失敗清單、驗證報告
├── chroma_db/                     # ChromaDB persistent(collection furniture_v3)
├── rendering/                     # 預渲染 PNG(正面圖為 UI 卡片用)
└── docs/                          # SSOT 規格:RAG檢索系統說明.md、query_parser_spec.md 等
```

#### 1.2 四層職責在單體腳本裡的落點

| 層 | 職責 | 現況落點 | 絕對不可以做的事 |
| :--- | :--- | :--- | :--- |
| Domain | 六風格詞表、style_compat 矩陣、19 群組、排序公式與權重、硬過濾/軟加權界線 | `taxonomy_v2.json`、`category_groups.json`、`retriever.py` 的 `W_*` 與 `style_score` / `mood_score` | 直接讀檔、呼叫 Chroma、呼叫 Anthropic |
| Application | 檢索用例編排(解析→過濾→召回→rerank→預算→收斂→去重) | `retriever.py` 的 `retrieve()` / `search_item()` | 產生 HTML、決定 Gradio 元件可見性 |
| Infrastructure | Chroma 讀寫、HF 模型載入、Anthropic / Ollama 呼叫、jsonl 與 JSON 檔 I/O | `embed_v3.py`、`query_parser.py` 的 `get_client()`、`retriever.py` 的 `load_*()` | 決定排序權重、修改詞表語意 |
| Presentation | 卡片 HTML、追問按鈕、CLI 表格輸出、啟動預熱 | `app.py`、各腳本的 `main()` | 直接查 Chroma、直接呼叫 reranker |

#### 1.3 目標結構:模組長大時才抽層

當任一檔案逼近 **800 行上限**(見 `.claude-roompilot/rules/coding-style.md`)、
或第二個呈現端(例如 SQL 端要共用檢索邏輯)出現時,依下列結構抽層。
在那之前**不要**預先拆——多一層 import 就多一次「改哪裡」的猶豫。

```
rag_pipeline/
├── __init__.py
├── domain/                     # 領域層 - 純邏輯,零 I/O、零第三方 SDK
│   ├── __init__.py
│   ├── models.py               # ParsedQuery 聚合根、RetrievalItem、PriceTWD 值物件
│   ├── vocabulary.py           # 六風格 / 24 氛圍 / 9 房型 / 19 群組的受控詞彙
│   ├── scoring.py              # 排序公式:0.60 rerank + 0.20 style + 0.10 mood + 0.10 conf
│   ├── events.py               # 管線事件(已發生的事實,過去式命名)
│   ├── exceptions.py           # 領域例外
│   └── ports.py                # 對外埠(Protocol):ItemRepository / VectorIndex / …
├── application/                # 應用層 - 用例編排
│   ├── __init__.py
│   ├── services.py             # RetrievalService(search / refine)
│   ├── commands.py             # SearchCommand / ReindexCommand / …(對應 argparse)
│   └── batch.py                # 可續跑批次編排(進度檔 + append)
├── infrastructure/             # 基礎設施層 - 外部實作
│   ├── __init__.py
│   ├── store/
│   │   ├── __init__.py
│   │   ├── dataset.py          # v3 JSON 讀取(49.9 MB,單例快取)
│   │   ├── metadata.py         # chroma_metadata 攤平規則(純量化契約)
│   │   └── mappers.py          # v3 item ↔ chroma_metadata ↔ 卡片 ViewModel
│   ├── vector/
│   │   ├── __init__.py
│   │   └── chroma_index.py     # VectorIndex 實作(含索引重建後自動重連)
│   ├── models/
│   │   ├── __init__.py
│   │   └── encoders.py         # bge-m3 / bge-reranker 載入、MPS→CPU 退回、預熱
│   └── llm/
│       ├── __init__.py
│       ├── anthropic_parser.py # claude-haiku-4-5 structured outputs
│       └── ollama_classifier.py# qwen3:8b 本機批次判定
└── presentation/               # 表現層
    ├── __init__.py
    ├── ui/
    │   ├── __init__.py
    │   ├── blocks.py           # Gradio Blocks 組裝與事件接線
    │   ├── view_models.py      # 卡片 / 區塊 / 條件摘要的呈現資料契約
    │   └── bootstrap.py        # 資源預熱與單例組裝(取代 DI 容器)
    └── cli/                    # CLI 入口(argparse)
        └── __init__.py
```

### 2. 領域層 (Domain Layer)

#### 2.1 領域模型 (domain/models.py)

```python
"""
領域模型 - 以 frozen dataclass 確保不可變
(見 .claude-roompilot/rules/coding-style.md「不可變性 (CRITICAL)」)

為什麼不用 Pydantic:pydantic 2.13.4 在環境裡,但它只是 anthropic / chromadb /
gradio 的**傳遞依賴**,本專案沒有直接相依。領域層用標準庫 dataclass 就夠。
真要引入時務必用 **Pydantic v2 API**(model_config / field_validator / pattern=),
v1 的 @validator、root_validator、regex= 在 v2 會直接報錯。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal

from .events import (
    ClarificationRequestedEvent,
    DominantStyleResolvedEvent,
    PipelineEvent,
    QueryParsedEvent,
)
from .exceptions import DomainError

# 上限與 query_parser.py 的裁切邏輯一致(structured outputs schema 不支援 maxItems,
# 上限在 prompt 講、程式端再裁切,所以領域層必須自己守住)
MAX_STYLES = 2
MAX_MOODS = 3
MAX_ITEMS = 6
MAX_CLARIFY_OPTIONS = 4


class StyleKey(str, Enum):
    """六風格 —— 唯一合法的風格值。

    詞表 SSOT 為 vlm_annotation/taxonomy_v2.json,新增風格必須先改詞表再改此列舉,
    否則 style_compat 6×6 矩陣查不到對應列,加權會全部退化成 0。
    """

    SCANDINAVIAN = "scandinavian"
    JAPANESE = "japanese"
    MODERN_MINIMAL = "modern_minimal"
    CREAM = "cream"
    INDUSTRIAL = "industrial"
    AMERICAN = "american"


class RoomType(str, Enum):
    """9 種房型 —— **硬過濾**條件(對應 chroma_metadata 的 room_* 布林旗標)"""

    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    DINING_ROOM = "dining_room"
    STUDY = "study"
    ENTRYWAY = "entryway"
    KIDS_ROOM = "kids_room"
    OUTDOOR = "outdoor"
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"


class Priority(str, Enum):
    """品項優先度 —— 影響組合階段的取捨,不影響硬過濾"""

    MUST_HAVE = "must_have"
    NICE_TO_HAVE = "nice_to_have"


PriceLevel = Literal["budget", "mid", "premium"]
Role = Literal["anchor", "accent"]
SizeHint = Literal["S", "M", "L"]


@dataclass(frozen=True, slots=True)
class PriceTWD:
    """價格值物件(新台幣整數元)。

    幣別固定 TWD:資料集只有 price_twd 一個欄位,不做多幣別,
    硬造一個 currency 欄位只會讓每次比較都要多寫一個判斷。
    """

    amount: int

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise DomainError("價格不可為負數", {"amount": self.amount})

    def add(self, other: PriceTWD) -> PriceTWD:
        """加法(回傳新物件,絕不修改自身)"""
        return PriceTWD(self.amount + other.amount)

    def multiply(self, factor: int) -> PriceTWD:
        """乘法 —— 用於 quantity 展開(餐椅 ×4)"""
        if factor < 0:
            raise DomainError("倍數不可為負數", {"factor": factor})
        return PriceTWD(self.amount * factor)

    def with_slack(self, slack: float) -> PriceTWD:
        """檢索階段放寬(BUDGET_SLACK=1.3);總價約束留到組合階段"""
        if slack <= 0:
            raise DomainError("寬容係數必須為正數", {"slack": slack})
        return PriceTWD(int(self.amount * slack))

    def ratio_of(self, total: PriceTWD, weight: float) -> PriceTWD:
        """依中位價權重分配總預算(見 retriever.allocate_budget)"""
        if total.amount <= 0:
            return PriceTWD.zero()
        return PriceTWD(int(total.amount * weight))

    @classmethod
    def zero(cls) -> PriceTWD:
        """零元"""
        return cls(0)

    def __str__(self) -> str:
        return f"NT$ {self.amount:,}"


@dataclass(frozen=True, slots=True)
class Quantity:
    """件數值物件,範圍 1-99。

    上限訂 99 而非 999:家具是大件商品,超過兩位數幾乎都是解析錯誤,
    寬鬆的上限只會讓錯誤悄悄流到預算分配階段。
    """

    value: int = 1

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise DomainError("件數必須大於 0", {"value": self.value})
        if self.value > 99:
            raise DomainError("件數不可超過 99", {"value": self.value})


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """排序分數拆解值物件 —— 每個候選都要能回答「為什麼排這麼前面」。

    公式(權重定義在 rag_pipeline/retriever.py:47):
        final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence
    """

    rerank: float
    style: float
    mood: float
    confidence: float
    final: float

    W_RERANK, W_STYLE, W_MOOD, W_CONF = 0.60, 0.20, 0.10, 0.10

    def __post_init__(self) -> None:
        for name in ("rerank", "style", "mood", "confidence"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise DomainError(
                    f"{name} 分數必須落在 0-1", {"field": name, "value": value}
                )
        expected = self.compose(self.rerank, self.style, self.mood, self.confidence)
        if abs(expected - self.final) > 1e-4:
            raise DomainError(
                f"綜合分數錯誤: 預期 {expected:.4f}, 實際 {self.final:.4f}"
            )

    @classmethod
    def compose(cls, rerank: float, style: float, mood: float, conf: float) -> float:
        """唯一的加權公式入口 —— 任何地方要算 final 都必須走這裡"""
        return round(
            cls.W_RERANK * rerank
            + cls.W_STYLE * style
            + cls.W_MOOD * mood
            + cls.W_CONF * conf,
            4,
        )

    @classmethod
    def create(
        cls, rerank: float, style: float, mood: float, conf: float
    ) -> ScoreBreakdown:
        """工廠方法:先算 final 再建構,避免呼叫端各自加權"""
        return cls(
            rerank=rerank,
            style=style,
            mood=mood,
            confidence=conf,
            final=cls.compose(rerank, style, mood, conf),
        )


@dataclass(frozen=True, slots=True)
class RetrievalItem:
    """單一檢索品項 - 實體 (Entity)。

    對應 query_parser 輸出的 items[] 一個元素;單物件需求 = items 長度 1,
    多物件走同一條程式路徑,呈現層不需要兩套邏輯。
    """

    item_id: str
    label_zh: str
    semantic_query: str
    category_group: str | None = None
    quantity: Quantity = field(default_factory=Quantity)
    priority: Priority = Priority.MUST_HAVE
    is_inferred: bool = False
    styles: tuple[StyleKey, ...] = ()
    price_max: PriceTWD | None = None
    max_width_cm: float | None = None
    max_height_cm: float | None = None
    role: Role | None = None
    size_hint: SizeHint | None = None

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise DomainError("item_id 不可為空")
        if not self.semantic_query.strip():
            raise DomainError(
                "semantic_query 不可為空 —— 它是向量檢索的唯一輸入",
                {"item_id": self.item_id},
            )
        if len(self.styles) > MAX_STYLES:
            raise DomainError(
                f"單一品項最多 {MAX_STYLES} 個風格", {"got": len(self.styles)}
            )
        for cm in (self.max_width_cm, self.max_height_cm):
            if cm is not None and cm <= 0:
                raise DomainError("尺寸限制必須為正數", {"item_id": self.item_id})

    @property
    def is_light(self) -> bool:
        """推論出的配件品項 → rerank 降額(RERANK_TOP_K_LIGHT=12)。

        rerank 是延遲主因(cross-encoder 每 50 筆約 10 秒),
        算力留給使用者明講的主件。
        """
        return self.is_inferred or self.role == "accent"

    @property
    def has_hard_size_limit(self) -> bool:
        """尺寸是硬過濾 —— 有值就代表使用者**明講過**,不是常識推測"""
        return self.max_width_cm is not None or self.max_height_cm is not None

    @classmethod
    def create(
        cls,
        item_id: str,
        label_zh: str,
        semantic_query: str,
        quantity: int = 1,
        **kwargs: object,
    ) -> RetrievalItem:
        """工廠方法:把 LLM 回傳的原生型別收斂成值物件"""
        price_max = kwargs.pop("price_max", None)
        return cls(
            item_id=item_id,
            label_zh=label_zh,
            semantic_query=semantic_query,
            quantity=Quantity(max(1, int(quantity or 1))),
            price_max=PriceTWD(int(price_max)) if price_max else None,
            **kwargs,  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    """需求解析結果 - 聚合根 (Aggregate Root)。

    所有檢索條件的唯一入口。硬過濾 vs 軟加權的界線在這裡定義並保護:
      硬過濾:room_type / category_group / price / 尺寸
      軟加權:styles / moods
      只進 semantic_query:color_hint / material_hint(不做過濾)
    """

    items: tuple[RetrievalItem, ...]
    room_type: RoomType | None = None
    styles: tuple[StyleKey, ...] = ()
    moods: tuple[str, ...] = ()
    pattern: str | None = None
    color_hint: str | None = None
    material_hint: str | None = None
    price_level: PriceLevel | None = None
    budget_total: PriceTWD | None = None
    is_set: bool = False
    confidence: float = 0.0
    needs_clarification: bool = False
    clarify_question: str | None = None
    clarify_options: tuple[str, ...] = ()
    reasoning: str = ""
    dominant_style: StyleKey | None = None
    # 管線事件(不持久化,只在同一次請求內流動)
    events: tuple[PipelineEvent, ...] = ()

    # ===== 不變量驗證 =====

    def _validate_invariants(self) -> None:
        """驗證聚合不變量"""
        # 不變量 1: items 絕對不可為空陣列
        if not self.items:
            raise DomainError("items 絕對不可以是空陣列,至少要有 1 個品項")

        # 不變量 2: 受控詞彙的數量上限
        if len(self.styles) > MAX_STYLES:
            raise DomainError(f"最多 {MAX_STYLES} 個風格", {"got": len(self.styles)})
        if len(self.moods) > MAX_MOODS:
            raise DomainError(f"最多 {MAX_MOODS} 個氛圍", {"got": len(self.moods)})
        if len(self.items) > MAX_ITEMS:
            raise DomainError(f"最多 {MAX_ITEMS} 個品項", {"got": len(self.items)})

        # 不變量 3: 具體金額與相對價位互斥
        if self.budget_total and self.price_level:
            raise DomainError(
                "budget_total 與 price_level 互斥:已有具體金額就不該再填相對價位",
                {"budget_total": self.budget_total.amount, "price_level": self.price_level},
            )

        # 不變量 4: 需要追問時必須給得出問題
        if self.needs_clarification and not self.clarify_question:
            raise DomainError("needs_clarification=True 時必須提供 clarify_question")

        # 不變量 5: item_id 在同一次查詢內唯一(去重與預算分配都以它為鍵)
        ids = [i.item_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise DomainError("item_id 重複", {"ids": ids})

        # 不變量 6: 把握度落在 0-1
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainError("confidence 必須落在 0-1", {"got": self.confidence})

    # ===== 工廠方法 =====

    @classmethod
    def create(
        cls, items: tuple[RetrievalItem, ...], **kwargs: object
    ) -> ParsedQuery:
        """建立解析結果(唯一建構入口,建構後立刻驗證不變量)"""
        if not items:
            raise DomainError("items 絕對不可以是空陣列,至少要有 1 個品項")

        parsed = cls(items=items, **kwargs)  # type: ignore[arg-type]
        parsed._validate_invariants()
        return parsed._emit(
            QueryParsedEvent(
                item_count=len(items),
                styles=tuple(s.value for s in parsed.styles),
                is_set=parsed.is_set,
                confidence=parsed.confidence,
            )
        )

    # ===== 領域方法(一律回傳新物件,絕不修改自身) =====

    def with_clamped_vocabulary(self) -> ParsedQuery:
        """把 LLM 溢出的詞彙裁到上限。

        structured outputs 的 schema 不支援 maxItems / minLength,
        所以上限只能在 prompt 講、在這裡強制執行。
        """
        clamped = replace(
            self,
            styles=self.styles[:MAX_STYLES],
            moods=self.moods[:MAX_MOODS],
            items=self.items[:MAX_ITEMS],
            clarify_options=self.clarify_options[:MAX_CLARIFY_OPTIONS],
        )
        clamped._validate_invariants()
        return clamped

    def with_dominant_style(self, style: StyleKey | None) -> ParsedQuery:
        """定下主導風格 —— 整組家具的風格一致性由它收斂。

        使用者已指定風格時直接沿用;沒指定時由 anchor 品項的 top-1 事後決定,
        決定後第一個品項要重排一次,否則整組風格會不一致。
        """
        if style is None:
            return self
        if self.dominant_style == style:
            return self
        return replace(self, dominant_style=style)._emit(
            DominantStyleResolvedEvent(
                style=style.value, inferred=not bool(self.styles)
            )
        )

    def with_clarification(self, question: str, options: tuple[str, ...]) -> ParsedQuery:
        """標記需要追問(結果仍照目前理解先呈現,不阻斷檢索)"""
        if not question.strip():
            raise DomainError("追問問題不可為空")
        updated = replace(
            self,
            needs_clarification=True,
            clarify_question=question,
            clarify_options=options[:MAX_CLARIFY_OPTIONS],
        )
        updated._validate_invariants()
        return updated._emit(
            ClarificationRequestedEvent(question=question, options=options)
        )

    # ===== 查詢方法 =====

    @property
    def anchor_first(self) -> tuple[RetrievalItem, ...]:
        """anchor 先跑 —— 用它的 top-1 決定主導風格"""
        return tuple(
            sorted(self.items, key=lambda i: 0 if i.role == "anchor" else 1)
        )

    @property
    def effective_styles(self) -> tuple[StyleKey, ...]:
        """實際用於加權的風格(主導風格優先於使用者原始輸入)"""
        if self.dominant_style:
            return (self.dominant_style,)
        return self.styles

    # ===== 管線事件管理 =====

    def _emit(self, event: PipelineEvent) -> ParsedQuery:
        """附加事件(回傳新物件)"""
        return replace(self, events=self.events + (event,))

    def collected_events(self) -> tuple[PipelineEvent, ...]:
        """取出事件(tuple 本身不可變,不需要 copy)"""
        return self.events

    def cleared_events(self) -> ParsedQuery:
        """清除事件 —— 回傳新物件而非就地清空"""
        return replace(self, events=())
```

#### 2.2 管線事件 (domain/events.py)

本專案沒有事件總線、沒有非同步訂閱者——事件的用途是**可觀測性**:
一次檢索走過七個階段(解析 → 硬過濾 → 向量召回 → rerank → 預算分配 → 收斂 → 呈現),
出問題時要能回答「是哪一段把結果吃掉的」。事件即那七段的結構化日誌來源。

```python
"""
管線事件 - 描述已發生的事實(過去式命名),供 stdout 進度與批次進度檔使用
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

TZ8 = timezone(timedelta(hours=8))  # 全專案時間戳一律 UTC+8,與交付檔一致


def _now() -> str:
    return datetime.now(TZ8).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """管線事件基類"""

    event_id: UUID = field(default_factory=uuid4)
    occurred_on: str = field(default_factory=_now)

    @property
    def name(self) -> str:
        """事件名(給日誌前綴用)"""
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class QueryParsedEvent(PipelineEvent):
    """需求已解析事件(claude-haiku-4-5 回傳並通過不變量驗證)"""

    item_count: int = 0
    styles: tuple[str, ...] = ()
    is_set: bool = False
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class DominantStyleResolvedEvent(PipelineEvent):
    """主導風格已決定事件(inferred=True 代表由 anchor top-1 事後推得)"""

    style: str = ""
    inferred: bool = False


@dataclass(frozen=True, slots=True)
class VectorRecalledEvent(PipelineEvent):
    """向量已召回事件(VEC_TOP_K=50;hit_count=0 通常代表硬過濾過嚴)"""

    item_id: str = ""
    hit_count: int = 0
    where_clause_count: int = 0


@dataclass(frozen=True, slots=True)
class RerankCompletedEvent(PipelineEvent):
    """重排已完成事件(candidate_count 為 RERANK_TOP_K 或 LIGHT 版)"""

    item_id: str = ""
    candidate_count: int = 0
    elapsed_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class SetComposedEvent(PipelineEvent):
    """組合已收斂事件(跨品項去重後的最終筆數與首選總價)"""

    block_count: int = 0
    deduplicated: int = 0
    estimated_total: int = 0


@dataclass(frozen=True, slots=True)
class ClarificationRequestedEvent(PipelineEvent):
    """已提出追問事件(結果仍照目前理解呈現,不阻斷檢索)"""

    question: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IndexRebuiltEvent(PipelineEvent):
    """索引已重建事件(embed_v3 delete+create 後,collection UUID 已更換)"""

    collection: str = "furniture_v3"
    item_count: int = 0
    reused_vector_count: int = 0
```

#### 2.3 領域例外 (domain/exceptions.py)

```python
"""
領域例外 - 業務規則違反與外部資源不可用

分兩族:
  DomainError    —— 規則違反,錯在輸入或程式(修程式/修 prompt)
  ResourceError  —— 外部資源不可用,錯在環境(重試/重建環境)
呈現層據此決定「顯示什麼訊息、要不要建議重試」。
絕不靜默吞噬:每一個 except 都必須記錄或轉譯,見 rules/coding-style.md。
"""
from __future__ import annotations


class RoomPilotError(Exception):
    """本專案所有自訂例外的根"""

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if not self.details:
            return self.message
        return f"{self.message} | {self.details}"


class DomainError(RoomPilotError):
    """領域例外基類 —— 不變量或受控詞彙違反"""


class InvalidVocabularyError(DomainError):
    """出現受控詞彙以外的值(六風格 / 24 氛圍 / 9 房型 / 19 群組之外)"""


class EmptyItemsError(DomainError):
    """items 為空陣列 —— 解析器必須至少給 1 個品項"""


class BudgetConflictError(DomainError):
    """budget_total 與 price_level 同時出現(互斥)"""


class ItemNotFoundError(DomainError):
    """v3 資料集裡找不到該 id(通常是 Chroma 與 v3 不同步)"""


class EmptyResultError(DomainError):
    """硬過濾後命中 0 筆 —— 呈現層應建議放寬預算或尺寸限制"""


class ResourceError(RoomPilotError):
    """外部資源例外基類 —— 環境問題,通常可重試"""


class ModelLoadError(ResourceError):
    """bge-m3 / bge-reranker-v2-m3 載入失敗(MPS 算子不支援、快取缺檔)"""


class IndexNotReadyError(ResourceError):
    """chroma_db/ 不存在或 collection furniture_v3 尚未建立"""


class IndexRebuiltError(ResourceError):
    """查詢期間索引被 embed_v3 重建(collection UUID 已換),需重連後重試"""


class ParserRefusalError(ResourceError):
    """claude-haiku-4-5 拒答(stop_reason == "refusal")"""


class ProviderUnavailableError(ResourceError):
    """Anthropic API 或本機 Ollama 連不上(qwen3:8b 需先 `ollama serve`)"""


class MissingCredentialError(ResourceError):
    """找不到 API 金鑰(.anthropic_key 或環境變數 ANTHROPIC_API_KEY)"""


class BatchItemError(ResourceError):
    """單筆批次項目失敗 —— 記進失敗清單,不中斷整批"""
```

#### 2.4 對外埠 (domain/ports.py)

**為什麼全部同步、沒有 async**:Gradio 事件處理函式是同步的;
bge-m3 編碼與 cross-encoder 重排是 CPU/GPU-bound,`async` 不會讓它們變快,
只會讓 stack trace 變長、讓 `lru_cache` 單例更難推理。
唯一有 I/O 等待的是 Anthropic 呼叫,批次端已用 `ThreadPoolExecutor` 併發解決。
**不要為了「看起來現代」把管線改成 async。**

```python
"""
對外埠 (Ports) - 在領域層定義,基礎設施層實作(DIP)

用 typing.Protocol 而非 ABC:實作端(chroma / sentence-transformers 包裝)
不需要 import 領域層就能滿足介面,避免基礎設施 → 領域的編譯期耦合。
"""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from .models import ParsedQuery, RetrievalItem, StyleKey


@runtime_checkable
class ItemRepository(Protocol):
    """家具資料集倉儲(來源:rag_dataset/furniture_enriched_v3.json,49.9 MB)"""

    def find_by_id(self, item_id: str) -> dict | None:
        """根據 id 取單筆(找不到回 None,不丟例外)"""
        ...

    def find_by_category_group(self, group: str) -> list[dict]:
        """取某個檢索群組(19 群組之一)底下的所有品項"""
        ...

    def iter_indexable(self) -> Iterator[dict]:
        """逐筆吐出 rag_indexable=True 的品項(建索引用,避免一次全載入清單)"""
        ...

    def price_stats(self, group: str) -> dict[str, float]:
        """該群組的中位價與 p33/p67(預算分配與相對價位換算的依據)"""
        ...

    def count(self) -> int:
        """可索引筆數(現況 9,349)"""
        ...


@runtime_checkable
class VectorIndex(Protocol):
    """向量索引(實作:ChromaDB persistent,collection furniture_v3,cosine)"""

    def query(
        self,
        embedding: list[float],
        n_results: int,
        where: dict | None = None,
    ) -> dict:
        """向量檢索 + metadata 硬過濾。

        ★ where 裡**不可**出現 rag_indexable —— 它是 v3 頂層欄位、
        不在 chroma_metadata 裡,寫了會命中 0 筆。
        """
        ...

    def upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """批次寫入(建議每批 1000 筆)"""
        ...

    def rebuild(self, collection: str) -> None:
        """刪除並重建 collection(會產生新的 UUID,長時間執行的 UI 需重連)"""
        ...

    def count(self) -> int:
        """索引筆數(啟動預熱時印出來當健康檢查)"""
        ...


@runtime_checkable
class QueryParserPort(Protocol):
    """自然語言 → ParsedQuery(實作:claude-haiku-4-5 structured outputs)"""

    def parse(self, text: str) -> ParsedQuery:
        """解析需求;拒答時丟 ParserRefusalError"""
        ...


@runtime_checkable
class EmbedderPort(Protocol):
    """文本 → 1024 維單位向量(實作:BAAI/bge-m3,MAX_SEQ_LEN=512)"""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """一律 normalize_embeddings=True —— 交付規格宣告 normalized=true"""
        ...


@runtime_checkable
class RerankerPort(Protocol):
    """(query, document) → 相關度(實作:BAAI/bge-reranker-v2-m3 cross-encoder)"""

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """★ 回傳值已是 0-1,不可再套 sigmoid,否則會壓平判別力"""
        ...


@runtime_checkable
class StyleTaxonomy(Protocol):
    """六風格詞表與 6×6 相容矩陣(來源:vlm_annotation/taxonomy_v2.json)"""

    def compat(self, want: StyleKey, got: str) -> float:
        """相容度 0-1(japanese↔scandinavian 0.9、cream↔american 0.7)"""
        ...

    def label_zh(self, style: StyleKey) -> str:
        """風格中文名(呈現用)"""
        ...


@runtime_checkable
class ProgressStore(Protocol):
    """可續跑批次的進度檔(append-only jsonl)"""

    def done_ids(self) -> set[str]:
        """已完成的 id;**只有成功的列算完成**,錯誤列留待重跑時自動重試"""
        ...

    def append(self, row: dict) -> None:
        """寫一列並 flush(中途 Ctrl-C 也不會掉整批)"""
        ...
```

### 3. 基礎設施層 (Infrastructure Layer)

#### 3.1 持久化綱要 (infrastructure/store/metadata.py)

本專案**沒有 ORM、沒有資料庫連線**。持久化只有三種形態,各自有明確契約:

| 形態 | 位置 | 契約來源 | 特性 |
| :--- | :--- | :--- | :--- |
| 主資料集 | `rag_dataset/furniture_enriched_v3.json`(49.9 MB) | `json_adjustment/build_rag_v3.py` header | 只增不覆寫,v2 欄位原封保留 |
| 向量索引 metadata | `chroma_db/` collection `furniture_v3` | `chroma_metadata` 攤平規則 | **只吃純量**(str / int / float / bool) |
| SQL 端交付 | `rag_export/*.jsonl` + 3 個 json | `json_adjustment/i_need_rag.md` | append 一行一筆,ID 欄位名 `item_id` |

```python
"""
chroma_metadata 攤平規則 - Chroma where 只吃純量,list / dict 一律先攤平

★ 三個必記的約束:
  1. rag_indexable 是 v3 的**頂層欄位**,不在 chroma_metadata 裡。
     寫進 where 會命中 0 筆 —— collection 本來就只收可索引的 9,349 筆。
  2. list 欄位攤平成 "|" 分隔字串(moods_flat),命中率在領域層算,不在 Chroma 算。
  3. 房型是 9 個布林旗標(room_living_room…),不是一個字串欄位 ——
     一件家具可以同時適用客廳與書房。
"""
from __future__ import annotations

from typing import Literal, TypedDict

# where 子句允許使用的欄位(白名單);不在此表的欄位一律不可進 where
FILTERABLE_FIELDS: frozenset[str] = frozenset(
    {
        "category",
        "price_twd",
        "width_cm",
        "depth_cm",
        "height_cm",
        "role",
        "size_class",
        "style_primary",
        "style_secondary",
    }
)

# 硬過濾 vs 軟加權的界線(改這裡等於改檢索語意,必須同步 docs/RAG檢索系統說明.md)
HARD_FILTER_FIELDS: frozenset[str] = frozenset(
    {"room_type", "category_group", "price", "width_cm", "height_cm", "size_class"}
)
SOFT_WEIGHT_FIELDS: frozenset[str] = frozenset({"styles", "moods"})
SEMANTIC_ONLY_FIELDS: frozenset[str] = frozenset({"color_hint", "material_hint"})


class ChromaMetadata(TypedDict, total=False):
    """collection furniture_v3 的 metadata 綱要(全部純量)"""

    furniture_id: str          # 與 collection id 相同,卡片連結用
    name_zh: str               # 顯示名稱(卡片標題,呈現層截斷 40 字)
    category: str              # 64 細類之一;where $in 用群組展開後的清單
    category_conflict: bool    # True = 名稱與原分類衝突,已改用 suggested_category
    style_primary: str         # 六風格之一(style_compat 矩陣的查詢鍵)
    style_secondary: str       # 次風格,加權時乘 0.6
    moods_flat: str            # 24 氛圍詞的 "|" 分隔字串,例:"寧靜|自然"
    price_twd: int             # 硬過濾:$gte / $lte
    width_cm: float            # 硬過濾:$lte(使用者明講的空間限制)
    depth_cm: float
    height_cm: float           # 硬過濾:$lte
    role: str                  # anchor / accent
    size_class: str            # S / M / L
    confidence: float          # 標註把握度,佔最終分數 0.10
    duplicate_group: str       # 同款不同色的群組鍵,跨品項去重用
    room_living_room: bool     # ↓ 9 個房型旗標,硬過濾 {"room_bedroom": {"$eq": True}}
    room_bedroom: bool
    room_dining_room: bool
    room_study: bool
    room_entryway: bool
    room_kids_room: bool
    room_outdoor: bool
    room_bathroom: bool
    room_kitchen: bool


class EmbeddingRecord(TypedDict):
    """rag_export/furniture_embeddings_bge_m3.jsonl 的一列(SQL 端交付契約)。

    欄位名與順序由 json_adjustment/i_need_rag.md 指定;
    舊規格 RAGSQL.md 用 furniture_id,增量重跑時必須正規化成 item_id,
    否則沿用的舊列會把舊欄位名帶回交付檔。
    """

    item_id: str
    embedded_text: str
    text_hash: str                 # sha256(embedded_text),增量重算的判斷依據
    embedding_model: Literal["BAAI/bge-m3"]
    embedding_dimension: Literal[1024]
    embedding: list[float]         # 每個值 round 到小數 6 位,壓檔案大小
    embedded_at: str               # UTC+8 ISO8601
    text_format_version: str
    source_schema_version: str
    normalized: Literal[True]


class FailureRecord(TypedDict, total=False):
    """rag_export/embedding_failures.jsonl 的一列 —— 失敗必須留痕,不可靜默略過"""

    item_id: str
    error_type: Literal[
        "model_error", "invalid_dimension", "empty_embedded_text", "not_indexable"
    ]
    error_message: str
    expected_dimension: int
    actual_dimension: int
```

#### 3.2 模型轉換 (infrastructure/store/mappers.py)

```python
"""
v3 item ↔ chroma_metadata ↔ 領域模型 ↔ 卡片 ViewModel 的四向轉換

轉換集中在這一個檔案的理由:欄位名不一致是本專案最容易踩的坑
(id / furniture_id / item_id 三種寫法散在不同世代的規格裡),
只要轉換散開,增量重跑就會把舊欄位名帶回交付檔。
"""
from __future__ import annotations

from domain.models import (
    ParsedQuery,
    PriceTWD,
    Quantity,
    RetrievalItem,
    RoomType,
    ScoreBreakdown,
    StyleKey,
)

from .metadata import ChromaMetadata

ROOM_FLAG_PREFIX = "room_"


class MetadataMapper:
    """v3 item ↔ chroma_metadata"""

    @staticmethod
    def to_metadata(item: dict) -> ChromaMetadata:
        """v3 item -> Chroma metadata(攤平成純量)"""
        meta: ChromaMetadata = {
            "furniture_id": item["id"],
            "name_zh": item.get("name_zh", ""),
            "category": item["category_final"],
            "category_conflict": bool(item.get("category_conflict")),
            "style_primary": item.get("style_primary", ""),
            "style_secondary": item.get("style_secondary", ""),
            # list -> "|" 分隔字串;命中率在領域層算,Chroma 不做集合運算
            "moods_flat": "|".join(item.get("moods") or []),
            "price_twd": int(item["price_twd"]),
            "width_cm": float(item.get("width_cm") or 0),
            "depth_cm": float(item.get("depth_cm") or 0),
            "height_cm": float(item.get("height_cm") or 0),
            "role": item.get("role") or "",
            "size_class": item.get("size_class") or "",
            "confidence": float(item.get("confidence") or 0),
            "duplicate_group": item.get("duplicate_group") or "",
        }
        # 9 個房型旗標;一件家具可同時適用多個房型
        for room in RoomType:
            meta[f"{ROOM_FLAG_PREFIX}{room.value}"] = room.value in (
                item.get("room_types") or []
            )
        # ★ 刻意不寫 rag_indexable:它是頂層欄位,寫進來會誘使有人拿去 where
        return meta

    @staticmethod
    def to_export_row(item: dict, vector: list[float], now: str, src: dict) -> dict:
        """v3 item + 向量 -> rag_export jsonl 一列(SQL 端交付契約)"""
        return {
            "item_id": item["id"],
            "embedded_text": item["embedded_text"],
            "text_hash": item["text_hash"],
            "embedding_model": "BAAI/bge-m3",
            "embedding_dimension": 1024,
            "embedding": [round(float(x), 6) for x in vector],
            "embedded_at": now,
            "text_format_version": item["text_format_version"],
            "source_schema_version": src["schema_version"],
            "normalized": True,
        }

    @staticmethod
    def normalize_legacy_row(row: dict) -> dict:
        """舊交付檔的欄位名正規化(furniture_id -> item_id)。

        增量模式會把沒變動的舊列**原樣寫回**,所以正規化必須發生在讀入時,
        否則舊欄位名會在下一輪交付檔裡復活。
        """
        if "furniture_id" not in row:
            return row
        return {("item_id" if k == "furniture_id" else k): v for k, v in row.items()}


class QueryMapper:
    """LLM structured outputs payload ↔ ParsedQuery 聚合根"""

    @staticmethod
    def to_domain(payload: dict) -> ParsedQuery:
        """payload -> 領域模型(所有裁切與驗證都在聚合根內完成)"""
        items = tuple(
            RetrievalItem.create(
                item_id=raw["item_id"],
                label_zh=raw["label_zh"],
                semantic_query=raw["semantic_query"],
                quantity=raw.get("quantity") or 1,
                category_group=raw.get("category_group"),
                is_inferred=bool(raw.get("is_inferred")),
                styles=tuple(StyleKey(s) for s in (raw.get("styles") or [])[:2]),
                price_max=raw.get("price_max"),
                max_width_cm=raw.get("max_width_cm"),
                max_height_cm=raw.get("max_height_cm"),
                role=raw.get("role"),
                size_hint=raw.get("size_hint"),
            )
            for raw in payload.get("items") or []
        )
        budget = payload.get("budget_total")
        return ParsedQuery.create(
            items=items,
            room_type=RoomType(payload["room_type"]) if payload.get("room_type") else None,
            styles=tuple(StyleKey(s) for s in payload.get("styles") or []),
            moods=tuple(payload.get("moods") or []),
            pattern=payload.get("pattern"),
            color_hint=payload.get("color_hint"),
            material_hint=payload.get("material_hint"),
            price_level=payload.get("price_level"),
            budget_total=PriceTWD(int(budget)) if budget else None,
            is_set=bool(payload.get("is_set")),
            confidence=float(payload.get("confidence") or 0),
            needs_clarification=bool(payload.get("needs_clarification")),
            clarify_question=payload.get("clarify_question"),
            clarify_options=tuple(payload.get("clarify_options") or []),
            reasoning=payload.get("reasoning") or "",
        ).with_clamped_vocabulary()

    @staticmethod
    def to_payload(parsed: ParsedQuery) -> dict:
        """領域模型 -> 純 dict(寫進偵錯日誌或當作追問的下一輪輸入)"""
        return {
            "room_type": parsed.room_type.value if parsed.room_type else None,
            "styles": [s.value for s in parsed.styles],
            "moods": list(parsed.moods),
            "pattern": parsed.pattern,
            "color_hint": parsed.color_hint,
            "material_hint": parsed.material_hint,
            "price_level": parsed.price_level,
            "budget_total": parsed.budget_total.amount if parsed.budget_total else None,
            "is_set": parsed.is_set,
            "confidence": parsed.confidence,
            "dominant_style": (
                parsed.dominant_style.value if parsed.dominant_style else None
            ),
            "items": [
                {
                    "item_id": i.item_id,
                    "label_zh": i.label_zh,
                    "category_group": i.category_group,
                    "quantity": i.quantity.value,
                    "is_inferred": i.is_inferred,
                    "semantic_query": i.semantic_query,
                    "styles": [s.value for s in i.styles],
                    "price_max": i.price_max.amount if i.price_max else None,
                    "max_width_cm": i.max_width_cm,
                    "max_height_cm": i.max_height_cm,
                    "role": i.role,
                    "size_hint": i.size_hint,
                }
                for i in parsed.items
            ],
        }
```

#### 3.3 索引與資料集實作 (infrastructure/vector/chroma_index.py)

```python
"""
ChromaDB 索引實作 + v3 資料集倉儲實作

兩個實作放在一起的理由:它們共享同一個「重建即失效」的生命週期 ——
embed_v3 重建索引時 v3 通常也剛更新過,兩邊的快取必須一起清。
"""
from __future__ import annotations

import json
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from domain.exceptions import (
    IndexNotReadyError,
    IndexRebuiltError,
    ItemNotFoundError,
)

PROJ = Path(__file__).resolve().parents[3]
V3 = PROJ / "rag_dataset" / "furniture_enriched_v3.json"
GROUPS = PROJ / "rag_pipeline" / "category_groups.json"
CHROMA_DIR = PROJ / "chroma_db"
COLLECTION = "furniture_v3"
CHUNK = 1000  # 單次 add 的筆數;再大會讓 Chroma 的一次寫入卡住數十秒


class ChromaVectorIndex:
    """VectorIndex 埠的 ChromaDB 實作(persistent client,cosine)"""

    def __init__(self, path: Path = CHROMA_DIR, collection: str = COLLECTION) -> None:
        self._path = path
        self._collection_name = collection
        self._handle = None

    # ── 連線 ────────────────────────────────────────────────

    def _connect(self):
        """取得 collection handle;不存在時給出可行動的錯誤訊息"""
        import chromadb
        from chromadb.errors import NotFoundError

        if not self._path.exists():
            raise IndexNotReadyError(
                "找不到 chroma_db/,請先執行 "
                "`.venv-rag/bin/python rag_pipeline/embed_v3.py`",
                {"path": str(self._path)},
            )
        client = chromadb.PersistentClient(path=str(self._path))
        try:
            return client.get_collection(self._collection_name)
        except NotFoundError as exc:
            raise IndexNotReadyError(
                f"collection {self._collection_name} 尚未建立,請先建索引",
                {"error": str(exc)},
            ) from exc

    def _handle_or_connect(self):
        if self._handle is None:
            self._handle = self._connect()
        return self._handle

    # ── 查詢 ────────────────────────────────────────────────

    def query(
        self, embedding: list[float], n_results: int, where: dict | None = None
    ) -> dict:
        """向量檢索;索引在背後被重建時自動重連一次。

        embed_v3 重建索引的方式是 delete_collection + create_collection,
        新 collection 會拿到新的 UUID。長時間執行的 UI 抓著舊 handle,
        重建後第一次查詢會噴 NotFoundError。這裡攔下來重連再試一次 ——
        使用者只會感覺那一次查詢慢了一點。
        """
        from chromadb.errors import NotFoundError

        payload = {
            "query_embeddings": [embedding],
            "n_results": n_results,
            "where": where,
            "include": ["metadatas", "documents", "distances"],
        }
        try:
            return self._handle_or_connect().query(**payload)
        except NotFoundError:
            self._handle = None
            load_dataset.cache_clear()  # 索引重建通常伴隨 v3 更新,一併重讀
            print("[index] 索引已被重建,重新連線後重試", flush=True)
            try:
                return self._handle_or_connect().query(**payload)
            except NotFoundError as exc:
                raise IndexRebuiltError(
                    "索引重建中,請稍候再查詢", {"error": str(exc)}
                ) from exc

    # ── 寫入 ────────────────────────────────────────────────

    def upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """分塊寫入並印進度 —— 9,349 筆一次送進去看不到任何回饋"""
        coll = self._handle_or_connect()
        for start in range(0, len(ids), CHUNK):
            end = start + CHUNK
            coll.add(
                ids=ids[start:end],
                embeddings=[[float(x) for x in v] for v in embeddings[start:end]],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
            print(f"      {min(end, len(ids))}/{len(ids)}", flush=True)

    def rebuild(self, collection: str = COLLECTION) -> None:
        """刪除並重建 collection(建索引前呼叫)"""
        import chromadb

        client = chromadb.PersistentClient(path=str(self._path))
        try:
            client.delete_collection(collection)
        except Exception:  # 首次建立時本來就不存在,不是錯誤
            pass
        self._handle = client.create_collection(
            collection,
            metadata={"hnsw:space": "cosine", "embedding_model": "BAAI/bge-m3"},
        )
        self._collection_name = collection

    def count(self) -> int:
        """索引筆數(啟動預熱時印出來當健康檢查)"""
        return self._handle_or_connect().count()


@lru_cache(maxsize=1)
def load_dataset() -> dict:
    """v3 資料集單例(49.9 MB,解析後常駐記憶體約 300-400 MB)。

    lru_cache 而非模組層全域變數:Gradio 重複查詢不重載,
    但索引重建後可以 cache_clear() 強制重讀,全域變數做不到這件事。
    """
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))

    items = {i["id"]: i for i in v3["items"]}
    prices: dict[str, dict[str, float]] = {}
    for key, spec in groups["groups"].items():
        cats = set(spec["categories"])
        vals = sorted(
            i["price_twd"] for i in v3["items"] if i["category_final"] in cats
        )
        if vals:
            prices[key] = {
                "median": statistics.median(vals),
                "p33": vals[len(vals) // 3],
                "p67": vals[len(vals) * 2 // 3],
            }
    return {
        "items": items,
        "groups": groups["groups"],
        "room_sets": groups["room_default_sets"],
        "prices": prices,
    }


class JsonItemRepository:
    """ItemRepository 埠的實作(來源:furniture_enriched_v3.json)"""

    def find_by_id(self, item_id: str) -> dict | None:
        return load_dataset()["items"].get(item_id)

    def require(self, item_id: str) -> dict:
        """找不到就丟例外的版本(呈現層拿 id 反查時用)"""
        item = self.find_by_id(item_id)
        if item is None:
            raise ItemNotFoundError(
                "v3 資料集找不到該 id,Chroma 與 v3 可能不同步,請重建索引",
                {"item_id": item_id},
            )
        return item

    def find_by_category_group(self, group: str) -> list[dict]:
        data = load_dataset()
        cats = set(data["groups"].get(group, {}).get("categories", []))
        return [i for i in data["items"].values() if i["category_final"] in cats]

    def iter_indexable(self) -> Iterator[dict]:
        """逐筆吐出可索引品項 —— 建索引時不要再複製一份 9,349 筆清單"""
        for item in load_dataset()["items"].values():
            if item.get("rag_indexable"):
                yield item

    def price_stats(self, group: str) -> dict[str, float]:
        return load_dataset()["prices"].get(group, {})

    def count(self) -> int:
        return sum(1 for _ in self.iter_indexable())
```

#### 3.4 模型載入與 device 選擇 (infrastructure/models/encoders.py)

```python
"""
bge-m3 / bge-reranker-v2-m3 載入 —— 單例、離線、MPS 優先退 CPU

★ 兩個必守的規矩:
  1. HF_HUB_OFFLINE 的 setdefault **不可移除**。不設離線的話
     sentence_transformers 每次載入都會連 HF Hub 檢查更新,
     未登入被限流時會乾等數分鐘,看起來像當機。
     首次在新機器跑要先 HF_HUB_OFFLINE=0 下載。
  2. 絕不把 reranker 換成 ms-marco MiniLM —— 那是英文模型,中文查詢會劣化。
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

# import sentence_transformers **之前**就要設好,晚了不生效
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from domain.exceptions import ModelLoadError  # noqa: E402

EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
MAX_SEQ_LEN = 512  # 文本中位 326 字(約 250-400 token),無需 bge-m3 預設的 8192


def pick_device(requested: str = "auto") -> str:
    """device 選擇:明示優先,否則 MPS → CPU。

    本專案只跑 macOS(Apple Silicon 16 GB),沒有 CUDA 機器;
    保留 "cuda" 選項只是為了讓 --device 的錯誤訊息好懂,不代表測過。
    """
    import torch

    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def load_models(device: str = "auto") -> tuple:
    """載入 embedder 與 reranker(單例;常駐約 4.6 GB)。

    MPS 偶有算子不支援 —— 整個載入包在 try 裡,失敗就整組退回 CPU。
    不做「embedder 用 MPS、reranker 用 CPU」的混搭:兩邊 device 不一致時,
    出錯的堆疊會非常難讀,而 CPU 全退只慢約 2-3 倍,還跑得動。
    """
    from sentence_transformers import CrossEncoder, SentenceTransformer

    picked = pick_device(device)
    started = time.time()
    try:
        embedder = SentenceTransformer(EMBED_MODEL, device=picked)
        reranker = CrossEncoder(RERANK_MODEL, device=picked, max_length=MAX_SEQ_LEN)
    except Exception as exc:
        print(f"[models] {picked} 載入失敗({type(exc).__name__}),退回 CPU", flush=True)
        try:
            embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
            reranker = CrossEncoder(RERANK_MODEL, device="cpu", max_length=MAX_SEQ_LEN)
        except Exception as cpu_exc:
            raise ModelLoadError(
                "模型載入失敗;若是首次在本機執行,請先以 HF_HUB_OFFLINE=0 下載權重",
                {"device": picked, "error": f"{type(cpu_exc).__name__}: {cpu_exc}"},
            ) from cpu_exc
    embedder.max_seq_length = MAX_SEQ_LEN
    print(f"[models] 就緒,耗時 {time.time() - started:.1f}s(device={picked})", flush=True)
    return embedder, reranker


class SentenceTransformerEmbedder:
    """EmbedderPort 實作"""

    def encode(self, texts: list[str]) -> list[list[float]]:
        embedder, _ = load_models()
        vectors = embedder.encode(
            texts,
            normalize_embeddings=True,  # 交付規格宣告 normalized=true,不可關掉
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]


class CrossEncoderReranker:
    """RerankerPort 實作"""

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """★ bge-reranker-v2-m3 經 CrossEncoder 已內建 sigmoid,輸出就是 0-1。

        只有當模型換成輸出 logit 的版本時才需要補 sigmoid;
        對已經 0-1 的分數再套一次會把判別力壓平。
        """
        import math

        _, reranker = load_models()
        scores = [float(s) for s in reranker.predict(pairs)]
        return [s if 0.0 <= s <= 1.0 else 1 / (1 + math.exp(-s)) for s in scores]
```

#### 3.5 LLM 轉接器 (infrastructure/llm/)

```python
"""
claude-haiku-4-5 需求解析 + 本機 Ollama qwen3:8b 批次判定

分工:互動端(需求解析)走 Haiku,延遲才是關鍵;
批次端(9,349 筆風格判定)預設走本機 Ollama,零 API 成本、不會跑到一半額度用盡。
兩邊共用同一份 prompt 與 JSON schema,只有呼叫層不同。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

from domain.exceptions import (
    MissingCredentialError,
    ParserRefusalError,
    ProviderUnavailableError,
)

PROJ = Path(__file__).resolve().parents[3]
KEY_FILE = PROJ / ".anthropic_key"
MODEL = "claude-haiku-4-5"
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434"


def get_client(max_retries: int = 5) -> anthropic.Anthropic:
    """金鑰讀取順序:環境變數 → .anthropic_key → SDK 預設解析。

    ★ .anthropic_key 是純文字檔、已列入 .gitignore,
    **絕不可提交、絕不可回顯內容、絕不可寫進日誌或錯誤訊息**。
    max_retries 交給 SDK 做指數退避 —— 併發批次下 429 是常態,不是例外。
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if key:
        return anthropic.Anthropic(api_key=key, max_retries=max_retries)
    try:
        return anthropic.Anthropic(max_retries=max_retries)
    except Exception as exc:
        raise MissingCredentialError(
            "找不到 API 金鑰:請設定 ANTHROPIC_API_KEY 或建立 .anthropic_key",
            {"error": type(exc).__name__},  # 不要把 exc 內容原樣帶出,可能含金鑰片段
        ) from exc


def nullable(inner: dict) -> dict:
    """可為 null 的欄位。

    ★ 不能寫成 {"type": ["string", "null"], "enum": [...]} ——
    structured outputs 的 schema 驗證會判定 enum 值與宣告型別不符,直接 400。
    用 anyOf 包一層才過。
    """
    return {"anyOf": [inner, {"type": "null"}]}


class AnthropicQueryParser:
    """QueryParserPort 實作(structured outputs + prompt caching)"""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or get_client()

    def parse_raw(self, text: str, system_prompt: str, schema: dict) -> dict:
        """回傳 payload dict;轉成領域模型的工作交給 QueryMapper"""
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    # 詞表固定,快取住省成本(單次解析約 US$0.005)
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={
                "format": {"type": "json_schema", "schema": schema}
            },
            messages=[{"role": "user", "content": text}],
        )
        if response.stop_reason == "refusal":
            raise ParserRefusalError(
                "模型拒答", {"stop_details": str(response.stop_details)}
            )
        payload = json.loads(
            next(b.text for b in response.content if b.type == "text")
        )
        payload["_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read": getattr(response.usage, "cache_read_input_tokens", 0),
        }
        return payload


class OllamaStyleClassifier:
    """本機批次風格判定(零 API 成本;需先 `ollama serve`)"""

    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL) -> None:
        import requests

        self._url = url
        self._model = model
        self._session = requests.Session()
        # 快速失敗:連不上就立刻講清楚怎麼修,不要等第一筆逾時
        try:
            self._session.get(f"{url}/api/version", timeout=5).raise_for_status()
        except Exception as exc:
            raise ProviderUnavailableError(
                f"連不上 Ollama({url}),請先執行 `ollama serve`",
                {"error": f"{type(exc).__name__}: {exc}"},
            ) from exc

    def classify(self, system: str, schema: dict, item: dict) -> tuple[dict, dict]:
        """回傳 (判定結果, token 用量);與 Anthropic 路徑輸出同一種 row"""
        resp = self._session.post(
            f"{self._url}/api/chat",
            json={
                "model": self._model,
                "format": schema,       # Ollama 的結構化輸出
                "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": item["embedded_text"]},
                ],
            },
            timeout=180,  # 本機 8B 模型單筆可能數十秒,逾時要放寬
        )
        resp.raise_for_status()
        body = resp.json()
        usage = {
            "in": body.get("prompt_eval_count", 0),
            "out": body.get("eval_count", 0),
            "cache_read": 0,
        }
        return json.loads(body["message"]["content"]), usage
```

### 4. 應用層 (Application Layer)

#### 4.1 命令 DTO (application/commands.py)

命令同時是 **CLI argparse 的型別化對應**——每個 `main()` 只做「argparse → Command → Service」,
不做任何業務判斷。這讓同一個用例能被 Gradio 與 CLI 共用,不必寫兩份。

```python
"""
命令 DTO - 表現層(Gradio / CLI)-> 應用層

在系統邊界驗證(見 rules/coding-style.md「輸入驗證」):
使用者輸入的長度、批次參數的範圍,全部在這裡快速失敗,錯誤訊息要能直接給人看。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domain.exceptions import DomainError

MAX_QUERY_CHARS = 500  # 超長輸入多半是貼錯內容,先擋下來省一次 Haiku 呼叫


@dataclass(frozen=True, slots=True)
class SearchCommand:
    """一次檢索:自然語言需求 → 卡片結果"""

    text: str
    top_k: int = 8  # FINAL_TOP_K

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise DomainError("請先輸入你想要的家具風格或設計需求")
        if len(self.text) > MAX_QUERY_CHARS:
            raise DomainError(
                f"需求描述請控制在 {MAX_QUERY_CHARS} 字以內",
                {"length": len(self.text)},
            )
        if not 1 <= self.top_k <= 24:
            raise DomainError("top_k 必須介於 1-24", {"top_k": self.top_k})


@dataclass(frozen=True, slots=True)
class RefineCommand:
    """追問後的再檢索:原需求 + 使用者點選的快速選項"""

    original_text: str
    option: str

    def to_search(self) -> SearchCommand:
        """把追問選項併回原需求,走同一條檢索路徑"""
        return SearchCommand(text=f"{self.original_text}，{self.option}")


@dataclass(frozen=True, slots=True)
class ReindexCommand:
    """建索引批次(對應 embed_v3.py 的 argparse)"""

    limit: int = 0                     # 0 = 全量;--limit 50 為冒煙測試
    batch_size: int = 16
    device: Literal["auto", "mps", "cpu", "cuda"] = "auto"
    only_changed: bool = False         # text_hash 比對的增量模式
    skip_chroma: bool = False          # 只產交付檔、不寫索引

    def __post_init__(self) -> None:
        if self.limit < 0:
            raise DomainError("--limit 不可為負數", {"limit": self.limit})
        if not 1 <= self.batch_size <= 256:
            raise DomainError("--batch-size 必須介於 1-256")
        if self.only_changed and self.limit:
            raise DomainError("--only-changed 與 --limit 不可同時使用:兩者的取樣邏輯衝突")


@dataclass(frozen=True, slots=True)
class ReclassifyCommand:
    """六風格重新判定批次(對應 reclassify_styles.py)"""

    provider: Literal["ollama", "anthropic"] = "ollama"
    limit: int = 0
    workers: int = 4
    compare: int = 0                   # >0 = 只跑一致率比對,不寫進度檔

    def __post_init__(self) -> None:
        if not 1 <= self.workers <= 16:
            raise DomainError("--workers 必須介於 1-16")
        if self.provider == "anthropic" and self.limit == 0 and self.compare == 0:
            # 全量約 US$7,不是不能跑,但要有人按下確認
            raise DomainError(
                "以 anthropic 跑全量會產生約 US$7 費用,請加 --limit 或明確確認"
            )
```

#### 4.2 應用服務 (application/services.py)

```python
"""
應用服務 - 用例編排(七階段管線的唯一編排點)

Query Understanding → Query Rewriting(與前者同一次 Haiku 呼叫)
  → Metadata Filtering(Chroma where 硬過濾)
  → Vector Retrieval(bge-m3,VEC_TOP_K=50)
  → Re-ranking(cross-encoder,RERANK_TOP_K=20 / 配件 RERANK_TOP_K_LIGHT=12)
  → Budget Allocation(中位價比例分配)
  → Set Composition(主導風格收斂、去重)
  → Result Presenter(Gradio,FINAL_TOP_K=8)
"""
from __future__ import annotations

import time

from domain.events import RerankCompletedEvent, SetComposedEvent, VectorRecalledEvent
from domain.exceptions import EmptyResultError, RoomPilotError
from domain.models import ParsedQuery, PriceTWD, RetrievalItem, ScoreBreakdown
from domain.ports import (
    EmbedderPort,
    ItemRepository,
    QueryParserPort,
    RerankerPort,
    StyleTaxonomy,
    VectorIndex,
)

from .commands import RefineCommand, SearchCommand

VEC_TOP_K = 50           # 向量召回(硬過濾緩衝)
RERANK_TOP_K = 20        # 送進 cross-encoder 的候選數(延遲主因)
RERANK_TOP_K_LIGHT = 12  # 配件品項降額;仍 > FINAL_TOP_K,去重後夠取
FINAL_TOP_K = 8
BUDGET_SLACK = 1.3       # 檢索階段的預算寬容係數


class RetrievalService:
    """檢索應用服務 —— 只做編排,不含排序公式,也不產生任何 HTML"""

    def __init__(
        self,
        parser: QueryParserPort,
        items: ItemRepository,
        index: VectorIndex,
        embedder: EmbedderPort,
        reranker: RerankerPort,
        taxonomy: StyleTaxonomy,
    ) -> None:
        self.parser = parser
        self.items = items
        self.index = index
        self.embedder = embedder
        self.reranker = reranker
        self.taxonomy = taxonomy

    # ===== 用例 1:檢索 =====

    def search(self, command: SearchCommand) -> dict:
        """檢索用例"""
        # 1. 需求解析(Query Understanding + Rewriting,同一次 Haiku 呼叫)
        parsed = self.parser.parse(command.text)

        # 2. 預算分配(中位價比例;平均分配會讓沙發一件都撈不到)
        allocated = self.allocate_budget(parsed)

        # 3. anchor 先跑,用它的 top-1 決定主導風格
        order = parsed.anchor_first
        first = self._search_item(order[0], parsed, allocated, command.top_k)
        per_item = {order[0].item_id: first}

        # 4. 主導風格事後才定 → 第一個品項要重排一次,否則整組風格會不一致
        if not parsed.dominant_style and first["hits"]:
            inferred = first["hits"][0]["meta"].get("style_primary")
            parsed = parsed.with_dominant_style(inferred)
            per_item[order[0].item_id] = self._search_item(
                order[0], parsed, allocated, command.top_k
            )

        # 5. 其餘品項沿用同一個主導風格
        for item in order[1:]:
            per_item[item.item_id] = self._search_item(
                item, parsed, allocated, command.top_k
            )

        # 6. 跨品項去重與收斂,並帶出管線事件供呈現層與日誌使用
        result = self._compose(parsed, per_item, allocated, command.top_k)
        result["events"] = parsed.collected_events()
        return result

    # ===== 用例 2:追問後再檢索 =====

    def refine(self, command: RefineCommand) -> dict:
        """把追問選項併回原需求,重走同一條路徑 —— 不做增量修補。

        增量修補(只改動被追問的那個欄位)看似省一次呼叫,
        但使用者的補充常常同時改變風格與預算,重解一次才不會前後矛盾。
        """
        return self.search(command.to_search())

    # ===== 用例 3:預算分配 =====

    def allocate_budget(self, parsed: ParsedQuery) -> dict[str, PriceTWD]:
        """總預算依各類別群組的實際中位價按比例分配。

        平均分配會讓沙發(中位價 18,000)在 6 萬 / 5 件的情境下一件都撈不到,
        所以用中位價當權重;檢索階段再乘 BUDGET_SLACK 放寬,
        總價約束留到組合階段。
        """
        if not parsed.budget_total:
            return {}
        weights: dict[str, float] = {}
        for item in parsed.items:
            stats = self.items.price_stats(item.category_group or "")
            median = stats.get("median", 5000.0)
            weights[item.item_id] = median * item.quantity.value
        total = sum(weights.values()) or 1.0
        return {
            key: PriceTWD(
                int(parsed.budget_total.amount * weight / total * BUDGET_SLACK)
            )
            for key, weight in weights.items()
        }

    # ===== 內部步驟 =====

    def _search_item(
        self,
        item: RetrievalItem,
        parsed: ParsedQuery,
        allocated: dict[str, PriceTWD],
        top_k: int,
    ) -> dict:
        """單一品項:硬過濾 → 向量召回 → rerank → 加權排序"""
        where = self._build_where(item, parsed, allocated)
        vector = self.embedder.encode([item.semantic_query])[0]
        hits = self.index.query(vector, n_results=VEC_TOP_K, where=where)

        ids = hits["ids"][0]
        parsed._emit(
            VectorRecalledEvent(
                item_id=item.item_id,
                hit_count=len(ids),
                where_clause_count=len((where or {}).get("$and", [where] if where else [])),
            )
        )
        if not ids:
            return {"item": item, "where": where, "hits": []}

        # 只把前段送進 cross-encoder:正解幾乎都落在向量 top 20 內
        n_rerank = RERANK_TOP_K_LIGHT if item.is_light else RERANK_TOP_K
        ids = ids[:n_rerank]
        metas = hits["metadatas"][0][:n_rerank]
        docs = hits["documents"][0][:n_rerank]

        started = time.time()
        scores = self.reranker.predict([(item.semantic_query, d) for d in docs])
        parsed._emit(
            RerankCompletedEvent(
                item_id=item.item_id,
                candidate_count=len(ids),
                elapsed_seconds=round(time.time() - started, 2),
            )
        )

        styles = item.styles or parsed.effective_styles
        ranked = []
        for fid, meta, doc, rerank_score in zip(ids, metas, docs, scores):
            breakdown = ScoreBreakdown.create(
                rerank=rerank_score,
                style=self._style_score(meta, styles),
                mood=self._mood_score(meta, parsed.moods),
                conf=float(meta.get("confidence") or 0),
            )
            ranked.append(
                {"id": fid, "meta": meta, "document": doc, "score": breakdown}
            )
        ranked.sort(key=lambda r: r["score"].final, reverse=True)
        return {"item": item, "where": where, "hits": ranked[: top_k * 3]}

    def _build_where(
        self,
        item: RetrievalItem,
        parsed: ParsedQuery,
        allocated: dict[str, PriceTWD],
    ) -> dict | None:
        """Chroma metadata 硬過濾。風格與氛圍不進來 —— 它們只影響排序。

        ★ 不要過濾 rag_indexable —— 它是 v3 頂層欄位、不在 chroma_metadata 裡,
        寫進 where 會命中 0 筆。
        """
        clauses: list[dict] = []
        if parsed.room_type:
            clauses.append({f"room_{parsed.room_type.value}": {"$eq": True}})
        if item.category_group:
            cats = self.items.find_by_category_group(item.category_group)
            if cats:
                clauses.append(
                    {"category": {"$in": sorted({c["category_final"] for c in cats})}}
                )
        low, high = self._price_bounds(item, parsed, allocated)
        if low:
            clauses.append({"price_twd": {"$gte": low.amount}})
        if high:
            clauses.append({"price_twd": {"$lte": high.amount}})
        if item.max_width_cm:
            clauses.append({"width_cm": {"$lte": float(item.max_width_cm)}})
        if item.max_height_cm:
            clauses.append({"height_cm": {"$lte": float(item.max_height_cm)}})
        if item.role:
            clauses.append({"role": {"$eq": item.role}})
        if item.size_hint:
            clauses.append({"size_class": {"$eq": item.size_hint}})

        if not clauses:
            return None  # 完全沒有硬條件(只給風格)→ 全庫語意檢索
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def _price_bounds(
        self,
        item: RetrievalItem,
        parsed: ParsedQuery,
        allocated: dict[str, PriceTWD],
    ) -> tuple[PriceTWD | None, PriceTWD | None]:
        """相對詞(便宜 / 高級)換算成該類別群組的分位數"""
        if item.price_max:
            return None, item.price_max
        if item.item_id in allocated:
            return None, allocated[item.item_id]
        stats = self.items.price_stats(item.category_group or "")
        if parsed.price_level and stats:
            if parsed.price_level == "budget":
                return None, PriceTWD(int(stats["p33"]))
            if parsed.price_level == "premium":
                return PriceTWD(int(stats["p67"])), None
            return PriceTWD(int(stats["p33"])), PriceTWD(int(stats["p67"]))
        if parsed.budget_total:
            return None, parsed.budget_total.with_slack(BUDGET_SLACK)
        return None, None

    def _style_score(self, meta: dict, styles: tuple) -> float:
        """使用者風格 vs 物件風格的相容度(取主 / 次風格的較佳者)"""
        if not styles:
            return 0.5
        best = 0.0
        for want in styles:
            for key, weight in (("style_primary", 1.0), ("style_secondary", 0.6)):
                got = meta.get(key)
                if got:
                    best = max(best, self.taxonomy.compat(want, got) * weight)
        return best

    @staticmethod
    def _mood_score(meta: dict, moods: tuple[str, ...]) -> float:
        """氛圍命中率(moods_flat 是 "|" 分隔字串)"""
        if not moods:
            return 0.5
        got = set((meta.get("moods_flat") or "").split("|")) - {""}
        return len(got & set(moods)) / len(moods)

    def _compose(
        self,
        parsed: ParsedQuery,
        per_item: dict[str, dict],
        allocated: dict[str, PriceTWD],
        top_k: int,
    ) -> dict:
        """跨品項去重:同一 id 或同一 duplicate_group 不重複出現"""
        seen_ids: set[str] = set()
        seen_groups: set[str] = set()
        dropped = 0
        blocks = []

        for item in parsed.anchor_first:
            picked = []
            for row in per_item[item.item_id]["hits"]:
                dup = row["meta"].get("duplicate_group") or ""
                if row["id"] in seen_ids or (dup and dup in seen_groups):
                    dropped += 1
                    continue
                seen_ids.add(row["id"])
                if dup:
                    seen_groups.add(dup)
                picked.append(row)
                if len(picked) >= top_k:
                    break
            blocks.append(
                {
                    "item_id": item.item_id,
                    "label_zh": item.label_zh,
                    "category_group": item.category_group,
                    "quantity": item.quantity.value,
                    "is_inferred": item.is_inferred,
                    "price_cap": allocated.get(item.item_id),
                    "where": per_item[item.item_id]["where"],
                    "hits": picked,
                }
            )

        estimated = sum(
            b["hits"][0]["meta"]["price_twd"] * b["quantity"] for b in blocks if b["hits"]
        )
        if all(not b["hits"] for b in blocks):
            raise EmptyResultError(
                "這個條件下沒有符合的物件,請放寬預算或尺寸限制",
                {"blocks": len(blocks)},
            )
        parsed._emit(
            SetComposedEvent(
                block_count=len(blocks),
                deduplicated=dropped,
                estimated_total=estimated,
            )
        )
        return {
            "dominant_style": (
                parsed.dominant_style.value if parsed.dominant_style else None
            ),
            "style_zh": (
                self.taxonomy.label_zh(parsed.dominant_style)
                if parsed.dominant_style
                else ""
            ),
            "budget_total": parsed.budget_total.amount if parsed.budget_total else None,
            "estimated_total": estimated,
            "blocks": blocks,
            "parsed": parsed,
        }


class ApplicationError(RoomPilotError):
    """應用層例外(用例編排失敗,非領域規則違反)"""
```

### 5. 表現層 (Presentation Layer)

#### 5.1 呈現資料契約 (presentation/ui/view_models.py)

本專案**沒有 HTTP API**——呈現層的「契約」是 Gradio 元件與卡片 HTML 之間的資料形狀。
把它顯式寫成 ViewModel 的價值在於:HTML 樣板只能讀 ViewModel 的欄位,
不能直接伸手進 `meta` dict 撈東西,否則欄位改名時整版卡片會靜默變空白。

```python
"""
呈現資料契約 - 應用層結果 -> UI 可直接渲染的形狀

所有進 HTML 的字串都必須先 html.escape():家具名稱含品牌原文與括號,
未跳脫會直接破版(這不是理論風險,是資料集裡真實存在的字元)。
"""
from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryInput:
    """使用者輸入(Textbox 內容 + 追問選項)"""

    text: str
    picked_option: str | None = None

    @property
    def combined(self) -> str:
        """追問選項併回原句"""
        if not self.picked_option:
            return self.text
        return f"{self.text}，{self.picked_option}"


@dataclass(frozen=True, slots=True)
class ConditionViewModel:
    """解析出的條件摘要(顯示在結果上方,讓使用者看得到系統怎麼理解他)"""

    room_zh: str | None
    styles_zh: tuple[str, ...]
    moods: tuple[str, ...]
    pattern: str | None
    budget_total: int | None
    price_level: str | None
    color_hint: str | None
    material_hint: str | None
    confidence: float
    reasoning: str

    def to_markdown(self) -> str:
        rows: list[str] = []
        if self.room_zh:
            rows.append(f"**房型** {self.room_zh}")
        if self.styles_zh:
            rows.append("**風格** " + "、".join(self.styles_zh))
        if self.moods:
            rows.append("**氛圍** " + "、".join(self.moods))
        if self.pattern:
            rows.append(f"**圖樣** {self.pattern}")
        if self.budget_total:
            rows.append(f"**總預算** {self.budget_total:,}")
        if self.price_level:
            rows.append(f"**價位** {self.price_level}")
        if self.color_hint:
            rows.append(f"**顏色** {self.color_hint}")
        if self.material_hint:
            rows.append(f"**材質** {self.material_hint}")
        rows.append(f"**解析把握度** {self.confidence:.2f}")
        body = "　｜　".join(rows)
        return f"### 解析出的條件\n{body}\n\n<sub>{html.escape(self.reasoning)}</sub>"


@dataclass(frozen=True, slots=True)
class CardViewModel:
    """單張家具卡片"""

    furniture_id: str
    name_zh: str
    category: str
    category_conflict: bool
    style_zh: str
    moods_text: str          # "|" 已換成「、」
    width_cm: float
    depth_cm: float
    height_cm: float
    price_twd: int
    thumb_data_uri: str      # 240px 縮圖的 base64 data URI(空字串 = 無圖佔位)
    score_final: float
    score_rerank: float
    score_style: float
    score_mood: float

    @property
    def size_text(self) -> str:
        return f"{self.width_cm:.0f}×{self.depth_cm:.0f}×{self.height_cm:.0f} cm"

    @property
    def score_text(self) -> str:
        return (
            f"綜合 {self.score_final:.3f}"
            f"(相關 {self.score_rerank:.2f}／風格 {self.score_style:.2f}"
            f"／氛圍 {self.score_mood:.2f})"
        )


@dataclass(frozen=True, slots=True)
class BlockViewModel:
    """一個品項的結果區塊(標題 + 卡片列)"""

    label_zh: str
    quantity: int
    is_inferred: bool        # True → 顯示「建議加入」標籤
    price_cap: int | None
    cards: tuple[CardViewModel, ...]

    @property
    def empty_message(self) -> str:
        """空結果的使用者訊息 —— 必須告訴他「下一步能做什麼」"""
        return "這個條件下沒有符合的物件,請放寬預算或尺寸限制。"


@dataclass(frozen=True, slots=True)
class ClarifyViewModel:
    """追問列(最多 4 個快速選項按鈕)"""

    question: str
    options: tuple[str, ...]

    @property
    def markdown(self) -> str:
        return f"**需要確認**：{self.question}（下方結果先依目前理解呈現）"


@dataclass(frozen=True, slots=True)
class ResultViewModel:
    """整頁結果"""

    dominant_style_zh: str
    dominant_style_key: str
    budget_total: int | None
    estimated_total: int
    blocks: tuple[BlockViewModel, ...]
    clarify: ClarifyViewModel | None = None
```

#### 5.2 Gradio 事件接線 (presentation/ui/blocks.py)

沒有 HTTP 狀態碼可用,所以**例外 → 使用者訊息**的映射必須自己寫死一張表。
原則(見 `rules/coding-style.md`):UI 面向使用者的友善訊息、
伺服器端(此處為 stdout)記錄詳細錯誤上下文,兩者內容不同但同時發生。

| 例外 | UI 訊息 | stdout | 使用者能做的事 |
| :--- | :--- | :--- | :--- |
| `DomainError`(輸入驗證) | 直接顯示 `message` | WARN + details | 改輸入 |
| `EmptyResultError` | 「沒有符合的物件,請放寬預算或尺寸限制」 | INFO + where 子句 | 放寬條件 |
| `ParserRefusalError` | 「這個需求我沒辦法解析,換個說法試試」 | WARN + stop_details | 換句話說 |
| `MissingCredentialError` | 「系統未設定 API 金鑰,請聯絡管理者」 | ERROR(**不印金鑰**) | 無 |
| `IndexNotReadyError` | 「索引尚未建立,請先建索引」 | ERROR + 指令 | 無 |
| `IndexRebuiltError` | 「索引重建中,請稍候再試」 | INFO | 重試 |
| `ModelLoadError` | 「模型載入失敗,請確認本機模型快取」 | ERROR + device | 無 |
| 其他 `Exception` | 「系統暫時無法處理,請稍後再試」 | ERROR + traceback | 重試 |

```python
"""
Gradio Blocks 組裝與事件接線 - 取代 HTTP router 的角色

三個事件入口(對等於三個端點):
  go.click / query.submit  → search   (檢索)
  opt_button.click         → refine   (追問後再檢索)
  gr.Examples              → search   (示範查詢,共用同一個 handler)
"""
from __future__ import annotations

import traceback

import gradio as gr

from application.commands import RefineCommand, SearchCommand
from application.services import RetrievalService
from domain.exceptions import (
    DomainError,
    EmptyResultError,
    IndexNotReadyError,
    IndexRebuiltError,
    MissingCredentialError,
    ModelLoadError,
    ParserRefusalError,
)

MAX_CLARIFY = 4

FRIENDLY: tuple[tuple[type[Exception], str], ...] = (
    (EmptyResultError, "這個條件下沒有符合的物件,請放寬預算或尺寸限制。"),
    (ParserRefusalError, "這個需求我沒辦法解析,換個說法再試一次。"),
    (MissingCredentialError, "系統未設定 API 金鑰,請聯絡管理者。"),
    (IndexRebuiltError, "索引重建中,請稍候幾秒再試一次。"),
    (IndexNotReadyError, "索引尚未建立,請先執行建索引流程。"),
    (ModelLoadError, "模型載入失敗,請確認本機模型快取是否完整。"),
    (DomainError, ""),  # 空字串 = 直接顯示 message(輸入驗證訊息本來就給人看)
)


def to_user_message(exc: Exception) -> str:
    """例外 → 使用者訊息;同時把技術細節寫到 stdout,絕不靜默吞噬"""
    for exc_type, message in FRIENDLY:
        if isinstance(exc, exc_type):
            detail = getattr(exc, "details", {})
            print(f"[ui] {type(exc).__name__}: {exc.args[0]} | {detail}", flush=True)
            return message or str(exc.args[0])
    print(f"[ui] 未預期例外\n{traceback.format_exc()}", flush=True)
    return "系統暫時無法處理,請稍後再試。"


def _error_outputs(message: str) -> tuple:
    """統一的錯誤回傳形狀(欄位數必須與正常路徑完全一致)"""
    banner = f'<div style="color:#b91c1c;padding:8px 0">{message}</div>'
    return (
        "",
        "",
        gr.update(visible=False),
        *[gr.update(visible=False)] * MAX_CLARIFY,
        banner,
    )


def make_handlers(service: RetrievalService, renderer) -> tuple:
    """把應用服務綁進 Gradio handler(取代依賴注入裝飾器)"""

    def search(query: str):
        """檢索"""
        try:
            command = SearchCommand(text=(query or "").strip())
            result = service.search(command)
        except Exception as exc:  # noqa: BLE001 —— UI 是最外層,必須攔下所有例外
            return _error_outputs(to_user_message(exc))

        view = renderer.to_view(result)
        buttons = [gr.update(visible=False) for _ in range(MAX_CLARIFY)]
        clarify_md = ""
        show_row = False
        if view.clarify:
            clarify_md = view.clarify.markdown
            show_row = True
            for i, option in enumerate(view.clarify.options[:MAX_CLARIFY]):
                buttons[i] = gr.update(value=option, visible=True)

        return (
            renderer.condition_markdown(result),
            clarify_md,
            gr.update(visible=show_row),
            *buttons,
            renderer.results_html(view),
        )

    def refine(query: str, option: str):
        """追問後再檢索(併回原句,重走同一條路徑)"""
        try:
            command = RefineCommand(original_text=query or "", option=option)
        except Exception as exc:  # noqa: BLE001
            return _error_outputs(to_user_message(exc))
        return search(command.to_search().text)

    return search, refine


def build_ui(service: RetrievalService, renderer) -> gr.Blocks:
    """組裝介面 —— 這個函式只做接線,不含任何檢索邏輯"""
    search, refine = make_handlers(service, renderer)

    with gr.Blocks(title="RoomPilot 家具風格檢索") as demo:  # Gradio 6:theme 在 launch() 傳
        gr.Markdown(
            "# RoomPilot 家具風格檢索\n"
            "輸入想要的風格或設計,系統會解析條件並從 9,349 件家具中找出最合適的物件。"
        )

        with gr.Row():
            query = gr.Textbox(
                label="你想要什麼樣的家具？",
                placeholder="例如：想要日式侘寂感、預算兩萬內的客廳沙發",
                scale=5,
            )
            go = gr.Button("檢索", variant="primary", scale=1)

        gr.Examples(
            examples=[
                "想要日式侘寂感、預算兩萬內的客廳沙發",
                "北歐風溫馨感的客廳，幫我配一整組，預算十萬",
                "臥室想弄成 loft 那種調調，牆面深色水泥",
                "餐廳要一張餐桌配四張餐椅，中古世紀現代風",
                "想找便宜一點的椅子",
            ],
            inputs=query,
        )

        condition = gr.Markdown()
        clarify = gr.Markdown()
        with gr.Row(visible=False) as clarify_row:
            opt_buttons = [gr.Button(visible=False, size="sm") for _ in range(MAX_CLARIFY)]
        results = gr.HTML()

        outputs = [condition, clarify, clarify_row, *opt_buttons, results]
        go.click(search, inputs=query, outputs=outputs)
        query.submit(search, inputs=query, outputs=outputs)
        for btn in opt_buttons:
            btn.click(refine, inputs=[query, btn], outputs=outputs)

    return demo
```

#### 5.3 資源組裝與預熱 (presentation/ui/bootstrap.py)

沒有 DI 框架、沒有 request scope。本專案的「容器」就是 `lru_cache` 單例 +
一個 `build_service()` 組裝函式。**預熱是必要的,不是最佳化**——
不預熱的話第一位使用者要乾等約一分鐘看著空白畫面,他會以為系統壞了。

```python
"""
資源組裝與啟動預熱 - 取代依賴注入容器

單例的生命週期 = 行程的生命週期。UI 執行時 bge-m3 + reranker 常駐約 4.6 GB,
機器只有 16 GB —— **不要在 UI 開著的時候同時跑批次**(建索引 / 全量風格判定),
兩個行程各載一份模型會直接把機器推進 swap。
"""
from __future__ import annotations

from functools import lru_cache

import gradio as gr

from application.services import RetrievalService
from infrastructure.llm.anthropic_parser import AnthropicQueryParser
from infrastructure.models.encoders import (
    CrossEncoderReranker,
    SentenceTransformerEmbedder,
    load_models,
)
from infrastructure.store.dataset import JsonItemRepository, TaxonomyAdapter
from infrastructure.vector.chroma_index import ChromaVectorIndex


@lru_cache(maxsize=1)
def build_service() -> RetrievalService:
    """組裝應用服務(全域單例;所有相依都在這一個地方決定)"""
    return RetrievalService(
        parser=AnthropicQueryParser(),
        items=JsonItemRepository(),
        index=ChromaVectorIndex(),
        embedder=SentenceTransformerEmbedder(),
        reranker=CrossEncoderReranker(),
        taxonomy=TaxonomyAdapter(),
    )


def warmup() -> None:
    """啟動預熱:先把模型與索引載進來,避免第一次查詢乾等一分鐘。

    順序有意義:模型載入最慢(約 30-60 秒),先載;
    索引 count() 順便當健康檢查 —— 印出來的數字不是 9,349 就代表索引不對。
    """
    print("預熱模型與索引…", flush=True)
    load_models()
    index = ChromaVectorIndex()
    print(f"索引就緒：{index.count()} 筆", flush=True)


def launch() -> None:
    """本機啟動(無 CI、無 Docker、無反向代理)。

    server_name 固定 127.0.0.1:**不要**改成 0.0.0.0 或開 share=True,
    這個 demo 沒有任何認證,對外開放等同把 API 額度送人。
    """
    from .blocks import build_ui
    from .renderer import CardRenderer

    warmup()
    build_ui(build_service(), CardRenderer()).launch(
        server_name="127.0.0.1",
        server_port=7860,
        theme=gr.themes.Soft(),  # Gradio 6:theme 在 launch() 傳,不是 Blocks()
    )
```

#### 5.4 CLI 入口 (presentation/cli/)

CLI 與 UI 共用同一個應用服務,是本專案最重要的可測試性來源——
在沒有測試套件的現況下,`retriever.py "<需求>"` 就是實際跑得動的迴歸手段。

```python
"""
CLI 入口 - argparse -> Command -> Service -> 純文字輸出

用法(一律 .venv-rag/bin/python):
    .venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"   # 只看解析結果
    .venv-rag/bin/python rag_pipeline/retriever.py   "<需求>"   # 完整檢索
    .venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50     # 冒煙測試
"""
from __future__ import annotations

import argparse
import sys

from application.commands import ReindexCommand, SearchCommand
from presentation.ui.bootstrap import build_service


def search_main(argv: list[str] | None = None) -> int:
    """檢索 CLI;回傳值即 exit code(0 成功 / 1 使用者錯誤 / 2 系統錯誤)"""
    parser = argparse.ArgumentParser(description="RoomPilot 家具風格檢索")
    parser.add_argument("query", nargs="+", help="自然語言需求")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args(argv)

    try:
        result = build_service().search(
            SearchCommand(text=" ".join(args.query), top_k=args.top_k)
        )
    except Exception as exc:  # noqa: BLE001
        print(f"檢索失敗：{exc}", file=sys.stderr)
        return 2

    print(f"主導風格：{result['dominant_style']}（{result['style_zh']}）")
    if result["budget_total"]:
        print(
            f"預算：{result['budget_total']:,} / "
            f"目前組合首選總價：{result['estimated_total']:,}"
        )
    for block in result["blocks"]:
        tag = "（建議加入）" if block["is_inferred"] else ""
        cap = f"，分配預算 {block['price_cap'].amount:,}" if block["price_cap"] else ""
        print(
            f"\n■ {block['label_zh']} ×{block['quantity']}{tag}{cap}"
            f" — {len(block['hits'])} 筆"
        )
        for row in block["hits"]:
            meta, score = row["meta"], row["score"]
            print(
                f"   {score.final:.3f} | {meta['name_zh'][:34]:36s} "
                f"{meta['category']:8s} {meta['style_primary']:16s} "
                f"{meta['price_twd']:>6,} "
                f"(rr {score.rerank:.2f} st {score.style:.2f} md {score.mood:.2f})"
            )
    return 0


def reindex_main(argv: list[str] | None = None) -> int:
    """建索引 CLI(argparse 只負責取值,範圍檢查交給 Command)"""
    parser = argparse.ArgumentParser(description="建立 furniture_v3 向量索引")
    parser.add_argument("--limit", type=int, default=0, help="只處理前 N 筆(冒煙測試)")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="auto", choices=["auto", "mps", "cpu", "cuda"])
    parser.add_argument("--only-changed", action="store_true", help="text_hash 增量重算")
    parser.add_argument("--skip-chroma", action="store_true")
    args = parser.parse_args(argv)

    command = ReindexCommand(
        limit=args.limit,
        batch_size=args.batch_size,
        device=args.device,
        only_changed=args.only_changed,
        skip_chroma=args.skip_chroma,
    )
    from application.batch import ReindexService

    return ReindexService().run(command)


if __name__ == "__main__":
    sys.exit(search_main())
```

### 6. 橫切關注 (Cross-cutting Concerns)

這一節是本專案吃過虧才長出來的規矩。**每一條都對應一次真實的失敗。**

#### 6.1 型別註記慣例

```python
# ✅ 檔案第一行永遠是這句 —— 讓 X | None 與前向參照在執行期不必求值
from __future__ import annotations

# ✅ Python 3.11 語法:內建泛型 + | 聯集,不要 typing.List / typing.Optional
def price_stats(group: str) -> dict[str, float]: ...
def find_by_id(item_id: str) -> dict | None: ...

# ✅ 受控詞彙用 Literal 或 Enum,不要裸 str
Role = Literal["anchor", "accent"]

# ✅ 外部 JSON 邊界用 TypedDict 表達形狀(執行期零成本,但 IDE 會擋錯欄位名)
class ChromaMetadata(TypedDict, total=False): ...

# ❌ 禁止 Any:寧可寫 object 再顯式 cast,也不要讓錯誤欄位名一路流到 UI
def parse(payload: Any) -> Any: ...

# ⚠️ 第三方套件的回傳值型別很鬆(chromadb 的 query 回 dict、
#    sentence-transformers 回 ndarray),在**轉換層**收斂成本專案型別,
#    不要讓 ndarray 流進領域層 —— 它的相等比較行為和 list 不一樣。
```

- 公開函式一律標註參數與回傳型別;內部小工具函式至少標回傳型別
- `dataclass` 一律 `frozen=True, slots=True`(不可變 + 省記憶體 + 擋拼錯欄位)
- 領域層**不得** import `anthropic` / `chromadb` / `torch` / `gradio` 任何一個

#### 6.2 錯誤處理與重試

三種外部依賴,三種失敗模式,三套策略——**不要用同一套 try/except 打發**。

| 依賴 | 典型失敗 | 策略 | 為什麼 |
| :--- | :--- | :--- | :--- |
| Anthropic API | 429 / 529 / 逾時 | SDK `max_retries=5` 指數退避 | 併發批次下 429 是常態;自己寫退避只會寫錯 |
| HF 模型載入 | MPS 算子不支援、快取缺檔 | 整組退回 CPU,再失敗才丟 `ModelLoadError` | 退回 CPU 只慢 2-3 倍,還跑得動 |
| Ollama | 連不上(未 `ollama serve`) | 啟動時探活 `/api/version`,快速失敗 | 等第一筆逾時才發現,已浪費數分鐘 |
| Chroma | 索引被重建、collection 不存在 | 清快取重連一次,再失敗才丟 | 重建是預期事件,不該讓 UI 死掉 |
| 單筆批次項目 | 任意例外 | 記進失敗清單,**不中斷整批** | 9,349 筆跑到第 8,000 筆才掛掉最傷 |

```python
# ✅ 批次:單批失敗不中斷全量,失敗留痕
for start in range(0, len(texts), batch_size):
    chunk = texts[start : start + batch_size]
    try:
        vectors.extend(model.encode(chunk, normalize_embeddings=True))
    except Exception as exc:  # 單批失敗不中斷全量
        for item in items[start : start + len(chunk)]:
            failures.append({
                "item_id": item["id"],
                "error_type": "model_error",
                "error_message": f"{type(exc).__name__}: {exc}",
            })
        vectors.extend([None] * len(chunk))   # 佔位,保持索引對齊

# ✅ 併發:每筆各自 try,失敗計數但繼續
with OUT.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=4) as pool:
    futures = {pool.submit(classify, runner, system, schema, it): it for it in todo}
    for fut in as_completed(futures):
        item = futures[fut]
        try:
            row = fut.result()
            with _write_lock:            # append 是多執行緒共享資源,必須上鎖
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()               # 中途 Ctrl-C 也不會掉整批
            ok += 1
        except Exception as exc:
            fail += 1
            print(f"  ✗ {item['id'][:50]} {type(exc).__name__}: {exc}", flush=True)

# ❌ 絕對禁止:靜默吞噬
try:
    result = risky()
except Exception:
    pass          # 這行會讓「為什麼結果變少了」變成永遠查不出來的鬼故事

# ⚠️ 唯一可接受的 except-pass:語意上「本來就可能不存在」
try:
    client.delete_collection(COLLECTION)
except Exception:
    pass          # 首次建立時本來就沒有這個 collection,不是錯誤
```

#### 6.3 資源預熱與快取

```python
# ✅ 單例三兄弟 —— 全部用 lru_cache(maxsize=1),不用模組層全域變數
@lru_cache(maxsize=1)
def load_data() -> dict: ...        # v3 資料集(49.9 MB)
@lru_cache(maxsize=1)
def load_models() -> tuple: ...     # bge-m3 + reranker(常駐約 4.6 GB)
@lru_cache(maxsize=1)
def load_collection(): ...          # Chroma collection handle

# ✅ 索引被重建時要能清掉重來 —— 全域變數做不到這件事
load_collection.cache_clear()
load_data.cache_clear()             # 索引重建通常伴隨 v3 更新,一併重讀

# ✅ 縮圖快取:數量有上限,用有界 LRU
@lru_cache(maxsize=2048)
def thumb_data_uri(path: str) -> str: ...
```

記憶體預算(16 GB 機器):

| 常駐項目 | 約略用量 | 備註 |
| :--- | :--- | :--- |
| bge-m3 + bge-reranker-v2-m3 | **4.6 GB** | UI 開著就一直在 |
| v3 資料集(解析後的 Python 物件) | 300-400 MB | 49.9 MB 的 JSON 展開後約 6-8 倍 |
| 縮圖 LRU(2048 張 240px JPEG) | 100-200 MB | base64 字串比原圖大 1/3 |
| Chroma 索引(HNSW 常駐部分) | 依查詢量成長 | 9,349×1024 維向量約 38 MB |

**鐵律:UI 開著時不要同時跑批次。** 兩個行程各載一份模型 = 9.2 GB,直接進 swap。

#### 6.4 可續跑批次(jsonl append + 進度檔)

批次工作(建索引 27 分鐘、全量風格判定數小時、VLM 標註更久)**一定會被中斷**——
關筆電、網路斷、額度用盡。設計時就假設它會中斷。

```python
# ✅ 進度檔即事實來源:一行一筆,append-only
def load_done() -> set[str]:
    """只把『成功』的列視為完成;錯誤列(暫時性 429 等)留待重跑時自動重試。"""
    if not OUT.exists():
        return set()
    done = set()
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue          # 中斷點可能留下半行,跳過即可,不要讓它炸掉續跑
            if "error" not in row:
                done.add(row["id"])
    return done

# ✅ 待辦 = 全體 - 已完成
todo = [i for i in items if i["id"] not in load_done()]
print(f"總數 {len(items)}／已完成 {len(done)}／本次處理 {len(todo)}", flush=True)

# ✅ 寫入即 flush;不要等 with 區塊結束才落地
fh.write(json.dumps(row, ensure_ascii=False) + "\n")
fh.flush()

# ✅ 進度回報要有速率與 ETA —— 沒有 ETA 的長任務,人會忍不住去按 Ctrl-C
if n % 200 == 0 or n == len(todo):
    rate = n / (time.time() - started)
    print(f"  {n}/{len(todo)}  {rate:.1f} 筆/秒  剩餘 {(len(todo)-n)/rate/60:.1f}m",
          flush=True)
```

- 進度檔一律 `.jsonl`,不要用 `.json`(整檔覆寫 = 中斷就全毀)
- 續跑必須**冪等**:同一筆重跑兩次的結果要能取代彼此,不是兩筆都留著
- 增量重算用 `text_hash` 比對(646 筆約 1.5 分鐘 vs 全量 27 分鐘)
- 併發寫 append 一定要 `threading.Lock`,否則兩行會交錯成一行壞 JSON

#### 6.5 就地寫入前先備份

```python
# ✅ 就地更新主資料集之前,先備份 —— 這是不可跳過的步驟
import shutil

BAK_PATH = PROJ / "rag_dataset" / "furniture_enriched_v2.bak_before_full.json"

if V2_PATH.exists() and not BAK_PATH.exists():
    shutil.copy2(V2_PATH, BAK_PATH)     # copy2 保留 mtime,方便事後比對是哪一版

# ✅ 寫檔用「先寫暫存再改名」,避免寫到一半斷電留下半個檔
tmp = DST.with_suffix(".json.tmp")
tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
tmp.replace(DST)                        # 同一檔案系統上 replace 是原子操作

# ✅ 破壞性腳本一律提供 --dry-run,先看統計再寫檔
if args.dry_run:
    print("--- 範例 embedded_text ---")
    print(out_items[0]["embedded_text"])
    return 0
```

- **只增不覆寫**:v2 既有欄位一律保留原值,v3 只新增衍生欄位
- 世代檔案不要就地改(`v1` / `v2` / `v3` 各自保留),回溯是靠世代不是靠 git
  (本專案**尚未 git init**,誤覆寫沒有版本控制可以救)
- 備份檔名要說明「備份的是哪個動作之前的狀態」(`*.bak_before_full.json`),
  不要叫 `backup.json`

#### 6.6 環境變數與金鑰讀取

```python
# ✅ 金鑰讀取順序:環境變數 → .anthropic_key → SDK 預設
key = os.environ.get("ANTHROPIC_API_KEY")
if not key and KEY_FILE.exists():
    key = KEY_FILE.read_text(encoding="utf-8").strip()   # strip() 不可省:檔尾有換行

# ✅ 離線旗標必須在 import sentence_transformers **之前**設定
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
# setdefault 而非直接指派:讓「首次下載模型」的人可以用
# HF_HUB_OFFLINE=0 .venv-rag/bin/python … 覆蓋掉

# ❌ 絕不硬編碼金鑰、絕不 print 金鑰、絕不把金鑰寫進錯誤訊息或日誌
raise MissingCredentialError("找不到 API 金鑰", {"error": type(exc).__name__})
#                                              ^ 只帶型別名,不帶 exc 內容
```

- `.anthropic_key` 是純文字檔、已列入 `.gitignore`,**絕不可提交或回顯內容**
- 啟動時就驗證必要金鑰存在(快速失敗),不要等第一次呼叫才發現
- 成本意識:需求解析每次約 US$0.005;六風格全量判定約 **US$7**——
  會燒額度的是批次工作,批次預設走本機 Ollama

#### 6.7 device 選擇(MPS → CPU)

```python
def pick_device(requested: str = "auto") -> str:
    """明示優先,否則 MPS → CPU。本專案只跑 macOS Apple Silicon。"""
    import torch

    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
```

- `import torch` 放在函式內:torch 載入要好幾秒,`--help` 不該為此等待
- MPS 失敗時**整組**退回 CPU,不要混搭(兩邊 device 不一致的堆疊極難讀)
- 所有批次腳本都要提供 `--device cpu` 逃生口
- 沒有 CUDA 機器;保留 `"cuda"` 選項只是讓錯誤訊息好懂,**不代表測過**

#### 6.8 大型 JSON 的記憶體考量

`furniture_enriched_v3.json` = **49.9 MB**、9,349 筆、每筆含 80-120 字描述與攤平 metadata。

```python
# ✅ 讀一次、快取起來、共用(全專案只有這一個入口)
@lru_cache(maxsize=1)
def load_data() -> dict:
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    items = {i["id"]: i for i in v3["items"]}   # 建索引鍵,避免每次線性掃 9,349 筆
    return {"items": items, "groups": ..., "prices": ...}   # 其餘欄位見 3.3

# ✅ 建索引時逐筆吐出,不要再複製一份清單
def iter_indexable(self) -> Iterator[dict]:
    for item in load_dataset()["items"].values():
        if item.get("rag_indexable"):
            yield item

# ✅ 交付檔逐行寫,不要先在記憶體組出 9,349 筆的大 list
with (EXPORT_DIR / EMBEDDINGS_FILE).open("w", encoding="utf-8") as fh:
    for item, vec in zip(items, vectors):
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

# ✅ 向量寫檔前 round 到 6 位;1024 維 × 9,349 筆,多餘位數會讓交付檔膨脹數倍
row = {"item_id": item["id"], "embedding": [round(float(x), 6) for x in vec]}

# ❌ 不要在迴圈裡反覆 json.loads 同一個大檔
for item_id in ids:
    data = json.loads(V3.read_text(encoding="utf-8"))   # 每次 50 MB,直接卡死

# ⚠️ 需要「只讀幾筆」時,寧可讀 rag_export/*.jsonl(逐行)也不要讀 v3 全檔
```

### 7. 本專案的誠實邊界

寫程式碼骨架時**不要**憑空引入下列東西——它們在本專案裡不存在:

| 主題 | 現況 | 對應做法 |
| :--- | :--- | :--- |
| 測試框架 | **目前無正式測試套件** | 建議 pytest,但**尚未建置**;現階段用 CLI 冒煙測試(`--limit 50`、`--compare 30`)當迴歸手段 |
| CI | **本專案無 CI** | 所有檢查都是本機手動執行,寫進 `rag_pipeline/README.md` 的 runbook |
| 容器化 | **本專案無 Docker** | 唯一環境是 `.venv-rag/`;部署 = 在本機 `127.0.0.1:7860` 跑起來 |
| 版本控制 | **專案尚未 git init** | 流程照 `rules/git-workflow.md` 走,但指令目前無法執行;誤覆寫沒有版本控制可救,所以備份與世代檔更重要 |
| Web 框架 | 無(只有 Gradio) | 沒有路由、沒有中介層、沒有 HTTP 狀態碼;例外 → 使用者訊息的映射自己維護一張表 |
| ORM / 資料庫 | 無 | 持久化只有 JSON 檔、Chroma、jsonl 交付檔;SQL 端是**別的團隊**,我們只交付 `rag_export/` |
| 非同步 | 無 | 全同步;唯一的併發是批次端的 `ThreadPoolExecutor` |
| 舊 `.venv/`(Python 3.9) | **目前不存在** | `rendering/` 與 `vlm_annotation/` 重跑前需先重建環境;配置檔**不得**再寫 `PY=.venv/bin/python` |

## 蘇格拉底檢核

1. **依賴反轉**:
   - 應用層與領域層是否完全不依賴基礎設施層的具體實作?
   - 對外埠(Protocol)在領域層定義,ChromaDB / sentence-transformers / anthropic 的實作在基礎設施層?

2. **領域純淨性**:
   - 領域模型是否不含任何 `chromadb` / `torch` / `anthropic` / `gradio` 的 import?
   - 排序公式(0.60/0.20/0.10/0.10)是否能脫離 Chroma 與模型單獨驗證?

3. **不變量保護**:
   - 聚合根 `ParsedQuery` 是否在建構與每個轉換方法後都驗證不變量?
   - 值物件是否全部 `frozen=True`,且所有「修改」都回傳新物件?

4. **硬過濾與軟加權的界線**:
   - 房型 / 類別 / 價格 / 尺寸有沒有不小心變成加權?
   - 風格 / 氛圍有沒有不小心進了 Chroma `where`?
   - 顏色 / 材質是否只進了 `semantic_query`,沒有做任何過濾?

5. **錯誤處理**:
   - `DomainError`(規則違反)與 `ResourceError`(環境不可用)是否明確區分?
   - 呈現層是否把每一種例外都轉成「使用者知道下一步該做什麼」的訊息?
   - 有沒有任何 `except: pass` 不是「本來就可能不存在」的情況?

6. **管線事件與可觀測性**:
   - 事件是否描述過去已發生的事實(過去式命名)?
   - 一次檢索的七個階段,出問題時能不能從輸出判斷是哪一段吃掉了結果?

7. **批次的可續跑性**:
   - 中斷後重跑會不會重做已完成的部分?錯誤列會不會被誤判為完成?
   - 就地寫入前有沒有備份?有沒有 `--dry-run`?

8. **資源與成本**:
   - 模型是否只載入一次?UI 與批次會不會同時各載一份(16 GB 機器會爆)?
   - 這段程式碼會呼叫幾次 Anthropic API?全量跑一次要多少錢?

## 輸出格式

- Python 代碼使用 Black 格式化 (行長 88)
- 所有公開函式/類別需有 Docstring;Docstring 要寫**為什麼**,不是重述函式名
- 使用 Type Hints (Python **3.11**;內建泛型 `dict[str, float]`、聯集 `X | None`)
- 遵循 PEP 8 規範
- 檔案開頭一律 `from __future__ import annotations`
- 模組層 docstring 必須包含「用法」段落,且指令一律寫 `.venv-rag/bin/python …`
- 中文註解說明取捨與坑,英文識別字;避免只有一句「初始化」的空註解
- 檔案 200-400 行為典型、**800 行為上限**;函式 < 50 行、巢狀 < 4 層

## 審查清單

**分層與依賴**

- [ ] 目錄結構(或單體腳本內的職責)遵循務實版 Clean Architecture 分層
- [ ] 領域層沒有 import 任何第三方 SDK(`chromadb` / `torch` / `anthropic` / `gradio`)
- [ ] 對外埠以 `typing.Protocol` 定義在領域層,實作在基礎設施層
- [ ] 應用服務只負責用例編排,不含排序公式、不產生 HTML
- [ ] 呈現層只讀 ViewModel,沒有直接伸手進 `meta` dict

**模型與不可變性**

- [ ] 值物件與實體一律 `@dataclass(frozen=True, slots=True)`
- [ ] 所有「修改」都回傳新物件(`dataclasses.replace`),沒有就地變更
- [ ] 聚合根在建構與每個轉換方法後驗證不變量
- [ ] 受控詞彙用 `Enum` / `Literal`,沒有裸字串魔法值
- [ ] 有 Mapper 集中處理 v3 item ↔ chroma_metadata ↔ ViewModel 轉換

**型別與風格**

- [ ] 包含完整型別註記,且沒有使用 `Any`
- [ ] 外部 JSON 邊界以 `TypedDict` 表達形狀
- [ ] 檔案 < 800 行、函式 < 50 行、無深層巢狀

**檢索正確性(六個坑)**

- [ ] `rag_indexable` **沒有**出現在任何 Chroma `where` 子句裡
- [ ] rerank 分數**沒有**再套一次 sigmoid
- [ ] structured outputs 可為 null 的 enum 用 `anyOf` 包覆
- [ ] `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` 的 `setdefault` 沒有被移除
- [ ] 尺寸欄位只在使用者明講時才填,程式端不做常識推測
- [ ] reranker 仍是 `BAAI/bge-reranker-v2-m3`(未被換成英文 ms-marco 模型)

**錯誤處理與資源**

- [ ] 例外分成 `DomainError` / `ResourceError` 兩族,呈現層有完整映射
- [ ] 沒有靜默吞噬(`except: pass` 僅用於「本來就可能不存在」)
- [ ] 外部呼叫有明確的重試或退回策略(Anthropic 退避 / MPS→CPU / Chroma 重連)
- [ ] 模型與資料集以 `lru_cache(maxsize=1)` 單例載入,且可 `cache_clear()`
- [ ] 啟動有預熱,並印出索引筆數當健康檢查

**批次與資料安全**

- [ ] 長批次可續跑(jsonl append + 進度檔,只有成功列算完成)
- [ ] 併發寫入有 `threading.Lock`,寫一行 `flush` 一次
- [ ] 單筆失敗記進失敗清單,不中斷整批
- [ ] 就地寫入前先備份;破壞性腳本提供 `--dry-run`
- [ ] 金鑰只從環境變數或 `.anthropic_key` 讀,沒有硬編碼、沒有回顯
- [ ] 大型 JSON 只讀一次並快取,交付檔逐行寫出

## 關聯文件

- **領域模型**: 04-ddd-aggregate-spec.md (六風格 / 品項聚合設計)
- **持久化設計**: 09-database-schema-spec.md (v3 欄位、chroma_metadata、rag_export 交付契約)
- **介面契約**: 05-api-contract-spec.md (query_parser structured outputs schema 依據)
- **測試規範**: 06-tdd-unit-spec.md (pytest 建議,**尚未建置**)
- **專案事實**: `.claude-roompilot/PROJECT_BRIEF.md`(技術棧、指令、六個坑的 SSOT)
- **管線規格**: `docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`
- **詞彙契約**: `vlm_annotation/taxonomy_v2.json`、`rag_pipeline/category_groups.json`
- **交付規格**: `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md`
- **操作手冊**: `rag_pipeline/README.md`(本機 runbook;**無 CI、無 Docker**)

---

**記住**: Clean Architecture 的核心是依賴反轉,讓業務邏輯獨立於框架與基礎設施。
本專案沒有 Web 框架、沒有 ORM、沒有 CI,但這不代表可以沒有邊界——
恰恰相反:**當沒有框架強迫你分層時,分層只能靠自律。**
排序公式、六風格詞表、硬過濾與軟加權的界線,是這個系統的領域核心;
它們必須能脫離 ChromaDB、脫離 bge-m3、脫離 Gradio 單獨被理解與驗證。
