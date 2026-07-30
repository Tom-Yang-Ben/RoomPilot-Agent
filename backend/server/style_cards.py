from __future__ import annotations

from pathlib import Path
from typing import Any

from ..catalog.runtime_catalog_repository import load_runtime_style_cards


STYLE_CARDS_PATH = Path(__file__).resolve().parents[1] / "catalog" / "data" / "taiwan_style_cards.json"
PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_taiwan_style_cards() -> list[dict[str, Any]]:
    """由 Phase 4 provider 載入台灣住宅版 6 種風格與 18 組色卡。"""
    styles = load_runtime_style_cards(PROJECT_DIR, STYLE_CARDS_PATH)
    if len(styles) != 6 or any(len(style.get("cards", [])) != 3 for style in styles):
        raise ValueError("台灣住宅風格色卡必須是 6 種風格、每種 3 組色卡。")
    return styles


def find_taiwan_style_card(cards: list[dict[str, Any]], card_id: str | None) -> dict[str, Any] | None:
    if not card_id:
        return None
    return next(
        (card for style in cards for card in style.get("cards", []) if card.get("card_id") == card_id),
        None,
    )
