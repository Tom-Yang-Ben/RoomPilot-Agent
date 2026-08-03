"""問卷送出時建立的逐房家具候選集（shortlist）。

這是第 6 步之前的一次性檢索：把需求問卷轉成語意查詢，先用正規化欄位做結構化
過濾（房型、尺寸、風格、價格），再用 pgvector 對過濾後的子集做語意排序，逐房
逐類取 top-N。結果由呼叫端寫進 ``scene_json``，之後選件與擺放 agent 只讀這份
候選集，不再掃全庫。

為什麼不用 ``rag_repository.search_embedding_candidates``：那支函式改走
``furniture_embedding_source_current.chroma_metadata`` 的 JSONB 過濾，實測每次
797ms（JSONB 述詞用不到索引），而同樣條件走 ``furniture_catalog_current`` 的
正規化欄位是 62–94ms。它的 ``categories`` 參數還要求中文分類名，與本專案其他
地方一律使用英文 ``category_code`` 的慣例相反，傳錯會靜默回 0 筆。兩者都是
Kai 目錄的既有問題，已記錄待回饋；在修好之前這裡直接查正規化欄位。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from ...agent.knowledge import FAMILY_OF, family_of
from ...catalog.postgres_repository import (
    borrow_catalog_connection,
    catalog_dict_cursor,
)
from .model_runtime import EMBED_MODEL, MODEL_RUNTIME, RagModelRuntime
from .settings import RagSettings, load_rag_settings


SHORTLIST_SCHEMA_VERSION = "roompilot.furniture-shortlist.v1"

# 每個族系預設保留的候選數。12 是實測值：足夠讓選件 agent 有選擇餘地，
# 又不會把 prompt 撐大到讓免費模型截斷。
DEFAULT_PER_FAMILY = 12
# 單一房間的候選上限，避免某個房型的族系特別多時把 workflow 撐爆。
MAX_ITEMS_PER_ROOM = 240


# SPACE_DEFAULTS 的族系名與 Kai 型錄的 category_code 有六處對不上，實測時
# 這些族系一律查不到候選（廚房的 storage-cabinet 就是整個房間 0 筆）。這裡
# 補上對照，值取自型錄實際存在的 category_code：
#
#   storage-cabinet / appliance-cabinet / bathroom-vanity
#       型錄只有 cabinet-cupboard 一種櫃體，前端 CATALOG_RETRIEVAL_ROUTES
#       早就這樣繞過，但後端沒有對應的表。
#   flower-pots-planter → 型錄叫 planter。
#   FAMILY_OF 的 cabinets-cupboard 是複數，型錄是單數 cabinet-cupboard，
#       所以那條「櫃體歸到 wardrobe」的映射從未生效。
#   FAMILY_OF 的 bed-frame 在型錄中不存在（床一律是 bed），保留不影響結果。
#
# 這是三方詞彙不一致，正解是在 Yen 的 FAMILY_OF 與 Bella 的 SPACE_DEFAULTS
# 對齊型錄用語；在那之前這張表讓檢索不會整族落空。
FAMILY_CATEGORY_OVERRIDES: dict[str, tuple[str, ...]] = {
    "storage-cabinet": ("cabinet-cupboard",),
    "appliance-cabinet": ("cabinet-cupboard",),
    "bathroom-vanity": ("cabinet-cupboard",),
    "flower-pots-planter": ("planter",),
    # 問卷會產生 lounge-chair，型錄的休閒椅一律是 armchair。
    "lounge-chair": ("armchair",),
}

# 正典房型（SPACE_DEFAULTS）與型錄 room_codes 是兩套詞彙，五個房型對不上：
# 型錄沒有 balcony / circulation / storage / studio / workspace，卻多出
# entryway / kids_room / outdoor / study。實測時這些房型一律 0 筆候選。
# 其中四個是同義詞，直接對照；storage 型錄真的沒有對應房型，映射成 None
# 表示「不限房型」——讓語意排序自己決定，總比整個房間查不到東西好。
CATALOG_ROOM_ALIASES: dict[str, str | None] = {
    "workspace": "study",
    "balcony": "outdoor",
    "circulation": "entryway",
    # hallway 是第 4 步的 visual_space_type，會被當成 room_type 傳進來。
    "hallway": "entryway",
    "studio": "living_room",
    "storage": None,
}

# 型錄實際存在的 room_codes。房型不在這裡也沒有別名時就不加房型條件，
# 而不是讓查詢必然落空。
CATALOG_ROOM_CODES = frozenset(
    {
        "living_room",
        "bedroom",
        "dining_room",
        "entryway",
        "study",
        "kids_room",
        "outdoor",
        "bathroom",
        "kitchen",
    }
)


def catalog_room_code(room_type: str | None) -> str | None:
    """把正典房型轉成型錄的 room_code；無對應時回 None（不限房型）。"""
    key = str(room_type or "").strip()
    if not key:
        return None
    if key in CATALOG_ROOM_ALIASES:
        return CATALOG_ROOM_ALIASES[key]
    return key if key in CATALOG_ROOM_CODES else None


def clean_families(values: Iterable[Any]) -> tuple[str, ...]:
    """濾掉不是家具族系的項目。

    實測發現部分房間的 ``furniture.required`` 混進了問卷標籤，例如
    ``use:保持通行``、``lighting:端景展示光``。那些帶前綴的字串不是族系，
    拿去查型錄一定 0 筆，還會讓 missing_families 充滿雜訊而掩蓋真正的缺漏。
    """
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or ":" in text or "：" in text:
            continue
        cleaned.append(text)
    return tuple(dict.fromkeys(cleaned))


def _family_to_categories() -> dict[str, tuple[str, ...]]:
    """反轉 Yen 的 FAMILY_OF，得到族系 → 型錄分類清單。

    FAMILY_OF 只列出需要摺疊的型錄分類；未列出的分類其族系就是自己，所以
    每個族系都要把同名分類補進去（例如族系 sofa 也要能吃到 category_code
    就叫 sofa 的品項）。
    """
    mapping: dict[str, list[str]] = {}
    for category, family in FAMILY_OF.items():
        mapping.setdefault(family, []).append(category)
    for family in list(mapping):
        if family not in mapping[family]:
            mapping[family].append(family)
    for family, extra in FAMILY_CATEGORY_OVERRIDES.items():
        mapping.setdefault(family, [family]).extend(extra)
    # 修正 FAMILY_OF 的複數錯字：櫃體實際歸到 wardrobe 族系。
    mapping.setdefault("wardrobe", ["wardrobe"]).append("cabinet-cupboard")
    return {family: tuple(sorted(set(values))) for family, values in mapping.items()}


FAMILY_TO_CATEGORIES = _family_to_categories()


def categories_for_family(family: str) -> tuple[str, ...]:
    """族系對應的型錄分類；未登錄的族系以自身作為唯一分類。"""
    key = str(family or "").strip()
    if not key:
        return ()
    return FAMILY_TO_CATEGORIES.get(key, (key,))


@dataclass(frozen=True)
class RoomNeed:
    """單一房間的檢索輸入，全部來自需求問卷與第 4 步確認的幾何。"""

    room_id: str
    room_type: str
    width_cm: float
    depth_cm: float
    # 問卷自由文字加上用途、標籤等，組成語意查詢。空字串代表只做結構化過濾。
    query_text: str
    required_families: tuple[str, ...] = ()
    style_id: str | None = None
    price_max: int | None = None

    def filter_width_cm(self) -> float:
        """家具寬度上限。取房間短邊，因為家具可以轉向擺放。"""
        return max(float(self.width_cm), float(self.depth_cm))

    def fingerprint_payload(self) -> dict[str, Any]:
        """參與指紋計算的欄位。

        只納入會改變檢索結果的輸入。房間顯示名稱之類的欄位刻意不納入，
        改個名字不該讓使用者重等一次檢索。
        """
        return {
            "room_id": self.room_id,
            "room_type": self.room_type,
            # 尺寸取整到公分：第 4 步微調牆面產生的浮點誤差不該讓快取失效。
            "width_cm": round(float(self.width_cm)),
            "depth_cm": round(float(self.depth_cm)),
            "query_text": " ".join(self.query_text.split()),
            "required_families": sorted(self.required_families),
            "style_id": self.style_id,
            "price_max": self.price_max,
        }


@dataclass(frozen=True)
class ShortlistItem:
    """候選家具。只保留下游決策需要的欄位，完整資料仍在型錄。"""

    item_id: str
    category_code: str
    family: str
    name_zh: str
    width_cm: float
    depth_cm: float
    height_cm: float
    price_twd: int | None
    score: float
    has_model: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "category_code": self.category_code,
            "family": self.family,
            "name_zh": self.name_zh,
            "width_cm": self.width_cm,
            "depth_cm": self.depth_cm,
            "height_cm": self.height_cm,
            "price_twd": self.price_twd,
            "score": round(self.score, 4),
            "has_model": self.has_model,
        }


@dataclass(frozen=True)
class RoomShortlist:
    room_id: str
    room_type: str
    query_text: str
    items: tuple[ShortlistItem, ...]
    # 問卷要求但檢索不到候選的族系。下游必須看這個欄位才知道要退回全庫，
    # 否則會誤以為「這個房間不需要沙發」。
    missing_families: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "room_type": self.room_type,
            "query_text": self.query_text,
            "items": [item.as_dict() for item in self.items],
            "missing_families": list(self.missing_families),
            # 逐房終態(契約:BEN_第5第6步整合規格_中文.md「回應與狀態」)。
            # 同步建構只會產生 completed / unavailable;failed 由 API 層的
            # HTTP 錯誤承載,cancelled / expired 保留給非同步流程。
            "status": "completed" if self.items else "unavailable",
            "status_reason": "" if self.items else "型錄查無符合此房需求的候選",
        }


@dataclass(frozen=True)
class ShortlistResult:
    rooms: tuple[RoomShortlist, ...]
    embedding_model: str
    generated_at: datetime
    semantic: bool
    # 需求指紋。存進 scene_json 後，下次問卷送出只要指紋沒變就直接沿用，
    # 使用者在第 5、6 步之間來回微調時不必每次重等檢索。
    fingerprint: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SHORTLIST_SCHEMA_VERSION,
            "embedding_model": self.embedding_model,
            "generated_at": self.generated_at.isoformat(),
            # semantic=False 代表只做了結構化過濾（模型未就緒），排序不含語意。
            "semantic": self.semantic,
            "fingerprint": self.fingerprint,
            "rooms": [room.as_dict() for room in self.rooms],
            "stats": dict(self.stats),
        }

    def item_ids(self) -> list[str]:
        return [item.item_id for room in self.rooms for item in room.items]


def needs_fingerprint(
    needs: Sequence[RoomNeed],
    *,
    per_family: int = DEFAULT_PER_FAMILY,
    semantic: bool = True,
    questionnaire_version: int | None = None,
) -> str:
    """算出這組需求的指紋。

    ``semantic`` 也要納入：純結構化過濾產生的候選集在模型就緒後應該重算，
    否則使用者永遠拿到降級結果卻不知道。``questionnaire_version`` 是問卷
    schema 的改版記號(契約要求 room_id+版本+內容雜湊構成工作識別):
    版本升級代表欄位語意可能變了,內容雜湊相同也不得沿用舊 completed 結果。
    """
    payload = {
        "schema": SHORTLIST_SCHEMA_VERSION,
        "embedding_model": EMBED_MODEL,
        "per_family": per_family,
        "semantic": semantic,
        "questionnaire_version": int(questionnaire_version or 1),
        "rooms": sorted(
            (need.fingerprint_payload() for need in needs),
            key=lambda item: item["room_id"],
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def shortlist_is_current(
    stored: dict[str, Any] | None,
    needs: Sequence[RoomNeed],
    *,
    per_family: int = DEFAULT_PER_FAMILY,
    questionnaire_version: int | None = None,
) -> bool:
    """已保存的候選集是否仍對應目前的需求。

    降級產生的候選集（``semantic=false``）一律視為過期，這樣模型載入完成後
    下一次送出就會補算語意排序。
    """
    if not isinstance(stored, dict) or not stored.get("fingerprint"):
        return False
    if stored.get("schema_version") != SHORTLIST_SCHEMA_VERSION:
        return False
    if not stored.get("semantic"):
        return False
    expected = needs_fingerprint(
        needs,
        per_family=per_family,
        semantic=True,
        questionnaire_version=questionnaire_version,
    )
    return str(stored.get("fingerprint")) == expected


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FurnitureShortlistService:
    """建立逐房候選集。資料庫不可用或模型未就緒時降級，不拋給使用者。"""

    def __init__(
        self,
        project_dir: Path,
        *,
        runtime: RagModelRuntime = MODEL_RUNTIME,
        settings: RagSettings | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.runtime = runtime
        self._settings = settings

    def settings(self) -> RagSettings:
        return self._settings or load_rag_settings(self.project_dir)

    def build(
        self,
        needs: Sequence[RoomNeed],
        *,
        per_family: int = DEFAULT_PER_FAMILY,
        questionnaire_version: int | None = None,
    ) -> ShortlistResult:
        if not needs:
            return ShortlistResult(
                rooms=(),
                embedding_model=EMBED_MODEL,
                generated_at=datetime.now(timezone.utc),
                semantic=False,
                fingerprint=needs_fingerprint(
                    (),
                    per_family=per_family,
                    semantic=False,
                    questionnaire_version=questionnaire_version,
                ),
                stats={"rooms": 0, "items": 0},
            )

        vectors, semantic, embed_error = self._embed_queries(
            [need.query_text for need in needs]
        )
        rooms: list[RoomShortlist] = []
        with borrow_catalog_connection(self.project_dir) as connection:
            with catalog_dict_cursor(connection) as cursor:
                for need, vector in zip(needs, vectors):
                    rooms.append(
                        self._build_room(cursor, need, vector, per_family=per_family)
                    )

        stats: dict[str, Any] = {
            "rooms": len(rooms),
            "items": sum(len(room.items) for room in rooms),
            "rooms_with_missing_families": sum(
                1 for room in rooms if room.missing_families
            ),
        }
        if embed_error:
            stats["embedding_error"] = embed_error
        return ShortlistResult(
            rooms=tuple(rooms),
            embedding_model=EMBED_MODEL,
            generated_at=datetime.now(timezone.utc),
            semantic=semantic,
            fingerprint=needs_fingerprint(
                needs,
                per_family=per_family,
                semantic=semantic,
                questionnaire_version=questionnaire_version,
            ),
            stats=stats,
        )

    def _embed_queries(
        self, texts: Sequence[str]
    ) -> tuple[list[list[float] | None], bool, str | None]:
        """一次編碼所有房間的查詢文字。

        批次編碼比逐句快得多，而且模型只需鎖一次。模型未就緒或權重缺失時
        回傳全 None，呼叫端會退成純結構化過濾而不是讓整個問卷送不出去。
        """
        usable = [index for index, text in enumerate(texts) if str(text or "").strip()]
        if not usable:
            return [None] * len(texts), False, None
        try:
            encoded = self.runtime.embed(
                [texts[index] for index in usable], self.settings()
            )
        except Exception as exc:  # noqa: BLE001 - 檢索降級不該中斷問卷
            return [None] * len(texts), False, f"{type(exc).__name__}: {exc}"[:200]
        vectors: list[list[float] | None] = [None] * len(texts)
        for slot, index in enumerate(usable):
            vectors[index] = encoded[slot]
        return vectors, True, None

    def _build_room(
        self,
        cursor: Any,
        need: RoomNeed,
        vector: Sequence[float] | None,
        *,
        per_family: int,
    ) -> RoomShortlist:
        wanted = clean_families(need.required_families)
        categories: list[str] = []
        for family in wanted:
            categories.extend(categories_for_family(family))
        categories = list(dict.fromkeys(categories))

        rows = self._query(
            cursor,
            need,
            vector,
            categories=categories,
            per_family=per_family,
        )
        items = list(self._to_items(rows))
        still_missing = self._unsatisfied(wanted, items)

        if still_missing:
            # 房型是型錄的標註，不是使用者的意圖。開放式廚房要餐桌椅時，型錄
            # 把餐桌椅標成 dining_room 就會整族落空。第一輪查不到的族系放寬
            # 房型再查一次——語意排序仍會把不合適的排後面。
            relaxed_categories: list[str] = []
            for family in still_missing:
                relaxed_categories.extend(categories_for_family(family))
            extra = self._query(
                cursor,
                need,
                vector,
                categories=list(dict.fromkeys(relaxed_categories)),
                per_family=per_family,
                ignore_room=True,
            )
            seen = {existing.item_id for existing in items}
            for item in self._to_items(extra):
                if item.item_id not in seen:
                    seen.add(item.item_id)
                    items.append(item)
            still_missing = self._unsatisfied(wanted, items)

        trimmed = tuple(items[:MAX_ITEMS_PER_ROOM])
        return RoomShortlist(
            room_id=need.room_id,
            room_type=need.room_type,
            query_text=need.query_text,
            items=trimmed,
            missing_families=tuple(still_missing),
        )

    @staticmethod
    def _unsatisfied(
        wanted: Sequence[str], items: Sequence[ShortlistItem]
    ) -> list[str]:
        """問卷要求但確實沒有候選的族系。

        比對要走 categories_for_family 而不是直接比族系名：問卷說
        ``lounge-chair``、型錄給的是 ``armchair``，那筆需求其實已經滿足，
        不該報成缺漏。誤報會讓下游白白退回全庫掃描。
        """
        available = {item.category_code for item in items}
        missing: list[str] = []
        for family in wanted:
            accepted = set(categories_for_family(family))
            if not accepted & available:
                missing.append(family)
        return missing

    @staticmethod
    def _to_items(rows: Iterable[dict[str, Any]]) -> Iterable[ShortlistItem]:
        for row in rows:
            yield ShortlistItem(
                item_id=str(row["item_id"]),
                category_code=str(row["category_code"] or ""),
                family=family_of(row["category_code"]),
                name_zh=str(row["name_zh"] or ""),
                width_cm=_number(row["width_cm"]),
                depth_cm=_number(row["depth_cm"]),
                height_cm=_number(row["height_cm"]),
                price_twd=_optional_int(row["price_twd"]),
                score=_number(row["score"]),
                has_model=bool(row["glb_url"]),
            )

    def _query(
        self,
        cursor: Any,
        need: RoomNeed,
        vector: Sequence[float] | None,
        *,
        categories: Sequence[str],
        per_family: int,
        ignore_room: bool = False,
    ) -> list[dict[str, Any]]:
        """一次查完整個房間。

        用 ROW_NUMBER 依 category_code 分組取 top-N，比每個分類各發一次查詢
        快得多（實測 5 房 1.1s vs 逐類 13.5s），而且保證每個分類都有候選，
        不會因為某個分類的語意分數整體偏低就整族落空。

        沒有查詢向量時退成依尺寸排序：大件優先，因為擺放失敗的通常是大件，
        先讓 agent 看到它們。
        """
        params: list[Any] = []
        conditions = [
            "c.kind = 'furniture'",
            "c.width_cm IS NOT NULL",
            "c.depth_cm IS NOT NULL",
        ]

        room_code = None if ignore_room else catalog_room_code(need.room_type)
        if room_code:
            conditions.append("%s = ANY(c.room_codes)")
            params.append(room_code)

        limit_cm = need.filter_width_cm()
        conditions.append("c.width_cm <= %s")
        params.append(limit_cm)
        conditions.append("c.depth_cm <= %s")
        params.append(limit_cm)

        if categories:
            conditions.append("c.category_code = ANY(%s)")
            params.append(list(categories))
        if need.style_id:
            # 風格是加分不是硬條件：只有這個風格真的有候選時才收斂，
            # 否則冷門風格會讓整個房間查不到東西。
            if room_code:
                conditions.append(
                    "(%s = ANY(c.style_codes) OR NOT EXISTS ("
                    "  SELECT 1 FROM roompilot.furniture_catalog_current s"
                    "  WHERE s.kind = 'furniture' AND %s = ANY(s.style_codes)"
                    "    AND %s = ANY(s.room_codes)"
                    "))"
                )
                params.extend([need.style_id, need.style_id, room_code])
            else:
                conditions.append(
                    "(%s = ANY(c.style_codes) OR NOT EXISTS ("
                    "  SELECT 1 FROM roompilot.furniture_catalog_current s"
                    "  WHERE s.kind = 'furniture' AND %s = ANY(s.style_codes)"
                    "))"
                )
                params.extend([need.style_id, need.style_id])
        if need.price_max is not None:
            conditions.append("(c.price_twd IS NULL OR c.price_twd <= %s)")
            params.append(need.price_max)

        where = " AND ".join(conditions)
        if vector is not None:
            literal = _vector_literal(vector)
            select_score = "1 - (e.embedding <=> %s::vector) AS score"
            order_by = "e.embedding <=> %s::vector"
            join = (
                "JOIN roompilot.furniture_embeddings e "
                "  ON e.item_id = c.item_id AND e.embedding_model = %s"
            )
            sql = f"""
                SELECT item_id, category_code, name_zh, width_cm, depth_cm,
                       height_cm, price_twd, glb_url, score
                FROM (
                    SELECT c.item_id, c.category_code, c.name_zh, c.width_cm,
                           c.depth_cm, c.height_cm, c.price_twd, c.glb_url,
                           {select_score},
                           ROW_NUMBER() OVER (
                               PARTITION BY c.category_code ORDER BY {order_by}
                           ) AS rn
                    FROM roompilot.furniture_catalog_current c
                    {join}
                    WHERE {where}
                ) ranked
                WHERE rn <= %s
                ORDER BY score DESC
            """
            query_params = [literal, literal, EMBED_MODEL, *params, per_family]
        else:
            sql = f"""
                SELECT item_id, category_code, name_zh, width_cm, depth_cm,
                       height_cm, price_twd, glb_url, score
                FROM (
                    SELECT c.item_id, c.category_code, c.name_zh, c.width_cm,
                           c.depth_cm, c.height_cm, c.price_twd, c.glb_url,
                           0.0 AS score,
                           ROW_NUMBER() OVER (
                               PARTITION BY c.category_code
                               ORDER BY c.width_cm DESC NULLS LAST, c.item_id
                           ) AS rn
                    FROM roompilot.furniture_catalog_current c
                    WHERE {where}
                ) ranked
                WHERE rn <= %s
                ORDER BY width_cm DESC NULLS LAST
            """
            query_params = [*params, per_family]

        cursor.execute(sql, query_params)
        return [dict(row) for row in cursor.fetchall()]


def build_room_needs(
    rooms: Iterable[dict[str, Any]],
    *,
    style_id: str | None = None,
) -> list[RoomNeed]:
    """把第 4/5 步的房間狀態轉成檢索輸入。

    ``query_text`` 刻意把用途、家具偏好與特殊需求串在一起：bge-m3 的
    ``embedded_text`` 本身就是「名稱／類別／顏色／材質／適用空間／風格／氛圍／
    描述」的自然語言，查詢端用同樣的語言型態命中率才會高。
    """
    needs: list[RoomNeed] = []
    for room in rooms:
        room_id = str(room.get("room_id") or room.get("id") or "").strip()
        if not room_id:
            continue
        requirement = room.get("requirement") or {}
        furniture = requirement.get("furniture") or {}
        parts = [
            room.get("label") or room.get("name") or "",
            room.get("room_type") or room.get("type") or "",
            requirement.get("summary") or "",
            " ".join(requirement.get("usage") or []),
            furniture.get("preferenceText") or "",
            " ".join(furniture.get("preferenceTags") or []),
            requirement.get("specialRequests")
            if isinstance(requirement.get("specialRequests"), str)
            else " ".join(requirement.get("specialRequests") or []),
        ]
        needs.append(
            RoomNeed(
                room_id=room_id,
                room_type=str(room.get("room_type") or room.get("type") or "living_room"),
                width_cm=_number(room.get("width_cm")),
                depth_cm=_number(room.get("depth_cm")),
                query_text=" ".join(part for part in parts if part).strip(),
                required_families=tuple(
                    family_of(item)
                    for item in (room.get("required_furniture_ids") or [])
                ),
                style_id=room.get("style_id") or style_id,
                price_max=_optional_int(requirement.get("budget_per_item_twd")),
            )
        )
    return needs
