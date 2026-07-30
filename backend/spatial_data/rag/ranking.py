"""Django's deterministic furniture filtering and ranking rules."""

from __future__ import annotations

import math
from typing import Any

from .models import RagQueryItem, RagQueryPlan


VEC_TOP_K = 50
RERANK_TOP_K = 20
RERANK_TOP_K_LIGHT = 12
FINAL_TOP_K = 8
BUDGET_SLACK = 1.3
W_RERANK, W_STYLE, W_MOOD, W_CONFIDENCE = 0.60, 0.20, 0.10, 0.10


def allocate_budget(
    items: list[RagQueryItem],
    budget_total: int | None,
    price_stats: dict[str, dict[str, float]],
) -> dict[str, int]:
    if not budget_total:
        return {}
    weights = {
        item.item_id: price_stats.get(item.category_group or "", {}).get("median", 5000)
        * max(1, item.quantity)
        for item in items
    }
    total = sum(weights.values()) or 1
    return {
        item_id: int(budget_total * weight / total * BUDGET_SLACK)
        for item_id, weight in weights.items()
    }


def resolve_price_bounds(
    item: RagQueryItem,
    plan: RagQueryPlan,
    allocated: dict[str, int],
    price_stats: dict[str, dict[str, float]],
) -> tuple[int | None, int | None]:
    if item.price_max:
        return None, item.price_max
    if item.item_id in allocated:
        return None, allocated[item.item_id]
    stats = price_stats.get(item.category_group or "")
    if plan.price_level and stats:
        if plan.price_level == "budget":
            return None, int(stats["p33"])
        if plan.price_level == "premium":
            return int(stats["p67"]), None
        return int(stats["p33"]), int(stats["p67"])
    if plan.budget_total:
        return None, int(plan.budget_total * BUDGET_SLACK)
    return None, None


def build_filters(
    item: RagQueryItem,
    plan: RagQueryPlan,
    allocated: dict[str, int],
    price_stats: dict[str, dict[str, float]],
    groups: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    price_min, price_max = resolve_price_bounds(item, plan, allocated, price_stats)
    group = groups.get(item.category_group or "", {})
    return {
        "room_type": plan.room_type,
        "categories": list(group.get("categories", [])) or None,
        "price_min": price_min,
        "price_max": price_max,
        "max_width_cm": item.max_width_cm,
        "max_height_cm": item.max_height_cm,
        "role": item.role,
        "size_class": item.size_hint,
    }


def style_score(
    metadata: dict[str, Any],
    styles: list[str],
    compatibility: dict[str, dict[str, float]],
) -> float:
    if not styles:
        return 0.5
    best = 0.0
    for wanted in styles:
        row = compatibility.get(wanted, {})
        for key, weight in (("style_primary", 1.0), ("style_secondary", 0.6)):
            actual = metadata.get(key)
            if actual:
                best = max(best, row.get(str(actual), 0.0) * weight)
    return best


def mood_score(metadata: dict[str, Any], moods: list[str]) -> float:
    if not moods:
        return 0.5
    actual = set(str(metadata.get("moods_flat") or "").split("|")) - {""}
    return len(actual & set(moods)) / len(moods)


def normalize_rerank_score(raw_score: float) -> float:
    if 0 <= raw_score <= 1:
        return raw_score
    if raw_score >= 0:
        return 1 / (1 + math.exp(-raw_score))
    exp_score = math.exp(raw_score)
    return exp_score / (1 + exp_score)


def rank_candidates(
    *,
    item: RagQueryItem,
    plan: RagQueryPlan,
    candidates: list[dict[str, Any]],
    rerank_scores: list[float],
    dominant_style: str | None,
    compatibility: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    styles: list[str] = list(item.styles)
    if not styles:
        styles = [dominant_style] if dominant_style else list(plan.styles)
    ranked: list[dict[str, Any]] = []
    for candidate, raw_score in zip(candidates, rerank_scores, strict=True):
        metadata = candidate.get("metadata") or {}
        rerank = normalize_rerank_score(float(raw_score))
        style = style_score(metadata, styles, compatibility)
        mood = mood_score(metadata, list(plan.moods))
        confidence = float(metadata.get("confidence") or 0)
        final = (
            W_RERANK * rerank
            + W_STYLE * style
            + W_MOOD * mood
            + W_CONFIDENCE * confidence
        )
        ranked.append(
            {
                **candidate,
                "scores": {
                    "final": round(final, 4),
                    "rerank": round(rerank, 4),
                    "style": round(style, 3),
                    "mood": round(mood, 3),
                    "confidence": round(confidence, 3),
                    "vector_similarity": round(
                        float(candidate.get("cosine_similarity") or 0), 4
                    ),
                },
            }
        )
    return sorted(ranked, key=lambda row: row["scores"]["final"], reverse=True)
