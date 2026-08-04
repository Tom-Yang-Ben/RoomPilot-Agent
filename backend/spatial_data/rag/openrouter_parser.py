"""OpenRouter JSON-mode adapter for the furniture RAG query schema."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

from .errors import RagDependencyError, RagUpstreamError
from .models import RagQueryPlan
from .openai_parser import ParsedQuery, build_system_prompt
from .settings import RagSettings


LOGGER = logging.getLogger(__name__)


def _explicit_intent_items(text: str) -> list[dict[str, object]]:
    """Extract the furniture types named directly by the user.

    Unicode escapes keep this critical matching logic stable even when the
    repository is opened from a Windows terminal using a legacy code page.
    """
    choices = [
        ("bed", "\u5e8a", ("\u5e8a", "\u7761\u7720", "\u96d9\u4eba\u5e8a", "\u55ae\u4eba\u5e8a"), "anchor"),
        ("desk", "\u66f8\u684c", ("\u66f8\u684c", "\u95b1\u8b80", "\u5de5\u4f5c", "\u8fa6\u516c"), "anchor"),
        ("wardrobe", "\u8863\u6ac3", ("\u8863\u6ac3", "\u8863\u7269"), "accent"),
        ("sofa", "\u6c99\u767c", ("\u6c99\u767c", "\u5ba2\u5ef3", "\u4f11\u606f"), "anchor"),
        ("storage", "\u6536\u7d0d", ("\u6536\u7d0d", "\u7f6e\u7269"), "accent"),
    ]
    items: list[dict[str, object]] = []
    for group, label, keywords, role in choices:
        if any(keyword in text for keyword in keywords):
            items.append(
                {
                    "item_id": group,
                    "label_zh": label,
                    "category_group": group,
                    "quantity": 1,
                    "priority": "must_have",
                    "is_inferred": True,
                    "semantic_query": f"{text} {label}",
                    "styles": ["modern_minimal"],
                    "price_max": None,
                    "max_width_cm": None,
                    "max_height_cm": None,
                    "role": role,
                    "size_hint": None,
                }
            )
    return items


def _fallback_plan(text: str) -> RagQueryPlan:
    """Keep retrieval available when a free model returns incomplete JSON.

    The fallback is intentionally a retrieval plan, not a layout decision. It
    converts the user's words into the same category and semantic-query fields
    used by pgvector and the reranker; geometry remains Step 6's responsibility.
    """
    explicit_items = _explicit_intent_items(text)
    room_type = (
        "bedroom" if any(token in text for token in ("\u81e5\u5ba4", "\u7761\u7720", "\u5e8a"))
        else "storage" if any(token in text for token in ("\u66f8\u684c", "\u95b1\u8b80", "\u5de5\u4f5c"))
        else "living_room" if any(token in text for token in ("\u5ba2\u5ef3", "\u6c99\u767c"))
        else None
    )
    if explicit_items:
        return RagQueryPlan.model_validate(
            {
                "room_type": room_type,
                "styles": ["modern_minimal"],
                "moods": [],
                "pattern": None,
                "color_hint": None,
                "material_hint": None,
                "price_level": None,
                "budget_total": None,
                "is_set": len(explicit_items) > 1,
                "items": explicit_items[:6],
                "confidence": 0.55,
                "needs_clarification": False,
                "clarify_question": None,
                "clarify_options": [],
                "reasoning": "Local fallback retrieval plan.",
            }
        )
    normalized = text.casefold()
    room_type = (
        "bedroom" if any(token in normalized for token in ("臥室", "睡眠", "床"))
        else "study" if any(token in normalized for token in ("書桌", "閱讀", "工作"))
        else "living_room" if any(token in normalized for token in ("客廳", "沙發"))
        else None
    )
    choices = [
        ("bed", "床", ("床", "睡眠", "雙人床", "單人床"), "anchor"),
        ("desk", "書桌", ("書桌", "閱讀", "工作", "辦公"), "anchor"),
        ("wardrobe", "衣櫃", ("衣櫃", "衣物", "收納"), "accent"),
        ("sofa", "沙發", ("沙發", "客廳", "休息"), "anchor"),
        ("storage", "收納", ("收納", "置物", "櫃"), "accent"),
    ]
    items = []
    for group, label, keywords, role in choices:
        if any(keyword in text for keyword in keywords):
            items.append(
                {
                    "item_id": group,
                    "label_zh": label,
                    "category_group": group,
                    "quantity": 1,
                    "priority": "must_have",
                    "is_inferred": True,
                    "semantic_query": f"{text} {label}",
                    "styles": ["modern_minimal"],
                    "price_max": None,
                    "max_width_cm": None,
                    "max_height_cm": None,
                    "role": role,
                    "size_hint": None,
                }
            )
    if not items:
        items.append(
            {
                "item_id": "storage",
                "label_zh": "收納家具",
                "category_group": "storage",
                "quantity": 1,
                "priority": "nice_to_have",
                "is_inferred": True,
                "semantic_query": text,
                "styles": ["modern_minimal"],
                "price_max": None,
                "max_width_cm": None,
                "max_height_cm": None,
                "role": "accent",
                "size_hint": None,
            }
        )
    return RagQueryPlan.model_validate(
        {
            "room_type": room_type,
            "styles": ["modern_minimal"],
            "moods": [],
            "pattern": None,
            "color_hint": None,
            "material_hint": None,
            "price_level": None,
            "budget_total": None,
            "is_set": len(items) > 1,
            "items": items[:6],
            "confidence": 0.55,
            "needs_clarification": False,
            "clarify_question": None,
            "clarify_options": [],
            "reasoning": "已依使用者描述建立檢索條件，配置可行性將在第 6 步驗證。",
        }
    )


def _preserve_explicit_intent(plan: RagQueryPlan, text: str) -> RagQueryPlan:
    """Never let an LLM omit furniture types the user stated explicitly."""
    fallback = _fallback_plan(text)
    existing_groups = {item.category_group for item in plan.items}
    missing = [item for item in fallback.items if item.category_group not in existing_groups]
    if not missing:
        return plan
    payload = plan.model_dump(mode="json")
    payload["items"] = (payload["items"] + [item.model_dump(mode="json") for item in missing])[:6]
    if payload["room_type"] is None:
        payload["room_type"] = fallback.room_type
    return RagQueryPlan.model_validate(payload)


def _fast_styles(text: str) -> list[str]:
    normalized = text.casefold()
    styles = [
        ("scandinavian", ("scandinavian", "\\u5317\\u6b50")),
        ("japanese", ("japanese", "\\u65e5\\u5f0f")),
        ("modern_minimal", ("modern_minimal", "\\u73fe\\u4ee3\\u7c21\\u7d04")),
        ("cream", ("cream", "\\u5976\\u6cb9")),
        ("industrial", ("industrial", "\\u5de5\\u696d")),
        ("american", ("american", "\\u7f8e\\u5f0f")),
    ]
    return [style_id for style_id, hints in styles if _matches_hints(normalized, hints)][:2]


def _decode_hint(value: str) -> str:
    marker = chr(92) + "u"
    return value.encode("ascii").decode("unicode_escape") if marker in value else value


def _matches_hints(text: str, hints: tuple[str, ...]) -> bool:
    return any(_decode_hint(hint) in text for hint in hints)


def _fast_room_type(text: str) -> str | None:
    normalized = text.casefold()
    rooms = [
        ("bedroom", ("bedroom", "\\u4e3b\\u81e5", "\\u6b21\\u81e5", "\\u81e5\\u5ba4")),
        ("living_room", ("living_room", "\\u5ba2\\u5ef3")),
        ("kitchen", ("kitchen", "dining_room", "\\u5eda\\u623f", "\\u9910\\u5ef3")),
        ("bathroom", ("bathroom", "\\u6d74\\u5ba4")),
        ("storage", ("storage", "study", "\\u66f8\\u623f", "\\u5de5\\u4f5c\\u5340", "\\u5132\\u85cf")),
        ("balcony", ("balcony", "outdoor", "\\u967d\\u53f0")),
        ("entryway", ("entryway", "\\u7384\\u95dc")),
        ("hallway", ("hallway", "\\u8d70\\u9053", "\\u52d5\\u7dda")),
        ("stair", ("stair", "\\u6a13\\u68af")),
        ("garage", ("garage", "\\u8eca\\u5eab")),
    ]
    return next((room for room, hints in rooms if _matches_hints(normalized, hints)), None)


def _explicit_intent_items(text: str) -> list[dict[str, object]]:
    """Normalize all catalog category groups used by the questionnaire."""
    groups = [
        ("bed", "\\u5e8a", ("bed", "\\u5e8a", "\\u7761\\u7720"), "anchor"),
        ("wardrobe", "\\u8863\\u6ac3", ("wardrobe", "\\u8863\\u6ac3", "\\u8863\\u7269"), "anchor"),
        ("desk", "\\u66f8\\u684c", ("desk", "\\u66f8\\u684c", "\\u5de5\\u4f5c\\u684c", "\\u95b1\\u8b80"), "anchor"),
        ("office_chair", "\\u5de5\\u4f5c\\u6905", ("office_chair", "\\u5de5\\u4f5c\\u6905", "\\u8fa6\\u516c\\u6905"), "accent"),
        ("sofa", "\\u6c99\\u767c", ("sofa", "\\u6c99\\u767c"), "anchor"),
        ("armchair", "\\u55ae\\u6905", ("armchair", "\\u55ae\\u6905", "\\u6276\\u624b\\u6905"), "accent"),
        ("dining_table", "\\u9910\\u684c", ("dining_table", "\\u9910\\u684c"), "anchor"),
        ("dining_chair", "\\u9910\\u6905", ("dining_chair", "\\u9910\\u6905"), "accent"),
        ("coffee_table", "\\u8336\\u51e0", ("coffee_table", "\\u8336\\u51e0"), "accent"),
        ("side_table", "\\u908a\\u684c", ("side_table", "\\u908a\\u684c", "\\u5e8a\\u908a\\u684c"), "accent"),
        ("storage", "\\u6536\\u7d0d", ("storage", "\\u6536\\u7d0d", "\\u7f6e\\u7269"), "accent"),
        ("rug", "\\u5730\\u6bef", ("rug", "\\u5730\\u6bef"), "accent"),
        ("lighting", "\\u71c8\\u5177", ("lighting", "\\u71c8", "\\u540a\\u71c8", "\\u8ecc\\u9053\\u71c8", "\\u5d4c\\u71c8"), "accent"),
        ("mirror", "\\u93e1\\u5b50", ("mirror", "\\u93e1", "\\u5168\\u8eab\\u93e1"), "accent"),
        ("media", "\\u96fb\\u8996\\u6ac3", ("media", "\\u96fb\\u8996\\u6ac3", "\\u96fb\\u8996"), "anchor"),
        ("partition", "\\u5c4f\\u98a8", ("partition", "\\u5c4f\\u98a8", "\\u9694\\u9593"), "accent"),
        ("stool_bench", "\\u9577\\u51f3", ("stool_bench", "\\u9577\\u51f3", "\\u51f3\\u5b50"), "accent"),
        ("kids", "\\u5152\\u7ae5\\u5bb6\\u5177", ("kids", "\\u5152\\u7ae5"), "accent"),
        ("decor", "\\u64fa\\u98fe", ("decor", "\\u64fa\\u98fe", "\\u88dd\\u98fe"), "accent"),
    ]
    styles = _fast_styles(text)
    normalized = text.casefold()
    return [
        {
            "item_id": group,
            "label_zh": _decode_hint(label),
            "category_group": group,
            "quantity": 1,
            "priority": "must_have",
            "is_inferred": True,
            "semantic_query": f"{text} {label}",
            "styles": styles,
            "price_max": None,
            "max_width_cm": None,
            "max_height_cm": None,
            "role": role,
            "size_hint": None,
        }
        for group, label, hints, role in groups
        if _matches_hints(normalized, hints)
    ][:6]


def _fallback_plan(text: str) -> RagQueryPlan:
    styles = _fast_styles(text)
    items = _explicit_intent_items(text)
    if not items:
        items = [{
            "item_id": "storage", "label_zh": "\\u6536\\u7d0d", "category_group": "storage",
            "quantity": 1, "priority": "nice_to_have", "is_inferred": True,
            "semantic_query": text, "styles": styles, "price_max": None,
            "max_width_cm": None, "max_height_cm": None, "role": "accent", "size_hint": None,
        }]
    return RagQueryPlan.model_validate({
        "room_type": _fast_room_type(text), "styles": styles, "moods": [],
        "pattern": None, "color_hint": None, "material_hint": None,
        "price_level": None, "budget_total": None, "is_set": len(items) > 1,
        "items": items, "confidence": 0.65, "needs_clarification": False,
        "clarify_question": None, "clarify_options": [],
        "reasoning": "Deterministic questionnaire retrieval plan.",
    })


def build_fast_plan(text: str) -> ParsedQuery:
    """Build a deterministic retrieval plan for non-blocking questionnaire use.

    This only normalizes selected uses and optional furniture words into the
    controlled retrieval schema. Geometry and placement stay in Step 6.
    """
    return ParsedQuery(
        plan=_fallback_plan(text),
        usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )


def _content(body: dict[str, Any]) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RagUpstreamError("OpenRouter returned no assistant content") from exc
    if isinstance(content, list):
        content = "".join(
            str(part.get("text") or "") if isinstance(part, dict) else str(part)
            for part in content
        )
    if not isinstance(content, str) or not content.strip():
        raise RagUpstreamError("OpenRouter returned empty assistant content")
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3]
    return content.strip()


def _usage(body: dict[str, Any]) -> dict[str, int]:
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(usage.get("total_tokens") or input_tokens + output_tokens),
    }


def parse_query(
    text: str,
    settings: RagSettings,
    *,
    client: Any | None = None,
) -> ParsedQuery:
    if not settings.openrouter_api_key:
        raise RagDependencyError("OPENROUTER_API_KEY is not configured")

    payload = {
        "model": settings.parser_model,
        "messages": [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1:8027",
        "X-Title": "RoomPilot Furniture RAG",
    }
    try:
        if client is not None:
            body = client(payload, headers)
        else:
            req = request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with request.urlopen(req, timeout=settings.parser_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
    except RagDependencyError:
        raise
    except error.HTTPError as exc:
        LOGGER.warning("OpenRouter RAG parser request failed with HTTP %s", exc.code)
        raise RagUpstreamError("OpenRouter query parsing failed") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("OpenRouter RAG parser request failed: %s", type(exc).__name__)
        raise RagUpstreamError("OpenRouter query parsing failed") from exc
    except Exception as exc:
        raise RagUpstreamError("OpenRouter query parsing failed") from exc

    if not isinstance(body, dict):
        raise RagUpstreamError("OpenRouter returned an invalid response")
    try:
        plan = RagQueryPlan.model_validate(json.loads(_content(body)))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        LOGGER.warning("OpenRouter returned incomplete JSON; using local retrieval plan")
        plan = _fallback_plan(text)
    plan = _preserve_explicit_intent(plan, text)
    return ParsedQuery(plan=plan, usage=_usage(body))
