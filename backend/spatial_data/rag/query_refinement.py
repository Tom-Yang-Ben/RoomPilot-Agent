"""問卷自由文字的 LLM 前置解析（shortlist 主線用）。

shortlist 原本把自由文字斷詞去重後直接做向量嵌入：語意有了，但「三萬以內」
「寬度不要超過 180」這種硬條件會被當成軟語意，過濾不掉。這裡在嵌入之前讓
``openai_parser.parse_query`` 先過一手，把自由文字解成 ``RagQueryPlan``，再
保守地取用三樣東西：

1. ``semantic_query``——parser 產的 30–120 字外觀描述（規則禁含價格尺寸），
   取代斷詞大雜燴作為嵌入文字。
2. 逐品項的 ``price_max`` / ``max_width_cm``——轉成逐分類的硬過濾條件。
   parser 的 category_group 先經 ``GROUP_TO_FAMILY`` 對到擺放族系，再走
   ``categories_for_family()`` 換成型錄英文 category_code；對不上的群組
   一律放棄該條硬條件（寧可漏擋，不可錯擋）。
3. ``moods`` / ``color_hint`` / ``material_hint``——併進嵌入文字當軟語意。

失敗永遠降級：沒 key、逾時、解析錯誤都回 ``parsed=False``，shortlist 照舊
走原路徑，問卷不會因此送不出去。解析結果按（文字, 模型）雜湊做行程內 LRU
快取；需求指紋沿用原始欄位計算，parser 的抖動不會讓快取失效。

一鍵止血：``ROOMPILOT_SHORTLIST_PARSER=0``。
"""

from __future__ import annotations

import hashlib
import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .settings import RagSettings

# parser 群組 → 擺放族系。只列一對一且語意明確的；rug/lighting/mirror/decor
# 這類在型錄裡跨多分類或另有 lane 的群組刻意不列，對不上就不下硬條件。
GROUP_TO_FAMILY: dict[str, str] = {
    "sofa": "sofa",
    "armchair": "armchair",
    "dining_chair": "dining-chair",
    "office_chair": "office-chair",
    "coffee_table": "coffee-table",
    "dining_table": "dining-table",
    "desk": "desk",
    "bed": "bed",
    "wardrobe": "wardrobe",
    "storage": "storage-cabinet",
}

# 自由文字短於這個長度就不值得花一次 LLM 呼叫——斷詞嵌入已足夠。
MIN_FREE_TEXT_CHARS = 12

_CACHE_MAX = 256
_cache: OrderedDict[str, "RefinedQuery"] = OrderedDict()
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class CategoryCap:
    """一組分類的硬上限（價格或寬度擇一使用，None 表不限制）。"""

    categories: tuple[str, ...]
    price_max: int | None = None
    max_width_cm: float | None = None


@dataclass(frozen=True)
class RefinedQuery:
    parsed: bool
    semantic_text: str | None = None
    caps: tuple[CategoryCap, ...] = ()
    reason: str | None = None

    def as_stats(self) -> dict[str, Any]:
        return {
            "parsed": self.parsed,
            "caps": len(self.caps),
            **({"reason": self.reason} if self.reason else {}),
        }


def parser_enabled() -> bool:
    return os.getenv("ROOMPILOT_SHORTLIST_PARSER", "1").strip() not in {
        "0", "false", "False", "no", "off",
    }


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()
    return digest


def _cache_get(key: str) -> "RefinedQuery | None":
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
        return hit


def _cache_put(key: str, value: "RefinedQuery") -> None:
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def _caps_from_plan(plan: Any, categories_for_family: Callable[[str], tuple[str, ...]]) -> tuple[CategoryCap, ...]:
    caps: list[CategoryCap] = []
    for item in getattr(plan, "items", []) or []:
        group = getattr(item, "category_group", None)
        family = GROUP_TO_FAMILY.get(str(group or ""))
        if not family:
            continue
        categories = tuple(categories_for_family(family))
        if not categories:
            continue
        price_max = getattr(item, "price_max", None)
        max_width = getattr(item, "max_width_cm", None)
        if price_max is None and max_width is None:
            continue
        caps.append(
            CategoryCap(
                categories=categories,
                price_max=int(price_max) if price_max is not None else None,
                max_width_cm=float(max_width) if max_width is not None else None,
            )
        )
    return tuple(caps)


def _semantic_text_from_plan(plan: Any) -> str | None:
    parts: list[str] = []
    for item in getattr(plan, "items", []) or []:
        text = str(getattr(item, "semantic_query", "") or "").strip()
        if text:
            parts.append(text)
    for attr in ("color_hint", "material_hint"):
        value = str(getattr(plan, attr, "") or "").strip()
        if value:
            parts.append(value)
    moods = [str(mood) for mood in (getattr(plan, "moods", None) or []) if str(mood).strip()]
    if moods:
        parts.append("氛圍：" + "、".join(moods))
    joined = "；".join(dict.fromkeys(parts)).strip()
    return joined or None


def refine_free_text(
    free_text: str,
    settings: RagSettings,
    *,
    categories_for_family: Callable[[str], tuple[str, ...]],
    parser: Callable[..., Any] | None = None,
) -> RefinedQuery:
    """把單一房間的自由文字解析成語意文字與硬條件；任何失敗都降級。"""
    text = " ".join(str(free_text or "").split())
    if len(text) < MIN_FREE_TEXT_CHARS:
        return RefinedQuery(parsed=False, reason="below_threshold")
    if not parser_enabled():
        return RefinedQuery(parsed=False, reason="disabled")
    if not settings.parser_api_key:
        return RefinedQuery(parsed=False, reason="parser_unconfigured")

    key = _cache_key(text, str(settings.parser_model or ""))
    cached = _cache_get(key)
    if cached is not None:
        return cached

    if parser is None:
        from .parser import parse_query as parser  # noqa: PLC0415 - 惰性載入，避免測試環境強制依賴 openai

    try:
        parsed = parser(text, settings)
    except Exception as exc:  # noqa: BLE001 - 解析降級不該中斷問卷
        result = RefinedQuery(
            parsed=False,
            reason=f"{type(exc).__name__}: {exc}"[:160],
        )
        # 失敗不進快取：暫時性錯誤（限流、逾時）下一次應該重試。
        return result

    plan = getattr(parsed, "plan", parsed)
    result = RefinedQuery(
        parsed=True,
        semantic_text=_semantic_text_from_plan(plan),
        caps=_caps_from_plan(plan, categories_for_family),
    )
    _cache_put(key, result)
    return result


def refine_many(
    free_texts: Sequence[str],
    settings: RagSettings,
    *,
    categories_for_family: Callable[[str], tuple[str, ...]],
    parser: Callable[..., Any] | None = None,
    max_workers: int = 4,
) -> list[RefinedQuery]:
    """平行解析多個房間。順序與輸入一致。

    每房一次 HTTP 呼叫、逾時由 parser client 自管；平行只是縮短牆鐘時間，
    不改變任何單房行為。
    """
    if not free_texts:
        return []
    needing = [
        index
        for index, text in enumerate(free_texts)
        if len(" ".join(str(text or "").split())) >= MIN_FREE_TEXT_CHARS
    ]
    results: list[RefinedQuery] = [
        RefinedQuery(parsed=False, reason="below_threshold") for _ in free_texts
    ]
    if not needing:
        return results
    if len(needing) == 1:
        index = needing[0]
        results[index] = refine_free_text(
            free_texts[index],
            settings,
            categories_for_family=categories_for_family,
            parser=parser,
        )
        return results
    with ThreadPoolExecutor(max_workers=min(max_workers, len(needing))) as pool:
        futures = {
            index: pool.submit(
                refine_free_text,
                free_texts[index],
                settings,
                categories_for_family=categories_for_family,
                parser=parser,
            )
            for index in needing
        }
        for index, future in futures.items():
            results[index] = future.result()
    return results
