from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STYLE_CARDS_PATH = Path(__file__).resolve().parents[1] / "catalog" / "data" / "taiwan_style_cards.json"


def load_taiwan_style_cards() -> list[dict[str, Any]]:
    """載入台灣住宅版 6 種風格與 18 組色卡，並補上前端資產 URL。"""
    payload = json.loads(STYLE_CARDS_PATH.read_text(encoding="utf-8"))
    styles = payload.get("styles", [])
    if len(styles) != 6 or any(len(style.get("cards", [])) != 3 for style in styles):
        raise ValueError("台灣住宅風格色卡必須是 6 種風格、每種 3 組色卡。")

    normalized: list[dict[str, Any]] = []
    for style in styles:
        cards = []
        for card in style["cards"]:
            cards.append(
                {
                    **card,
                    "image_url": "/static/style_cards/" + card["image_file"].replace("\\", "/"),
                }
            )
        normalized.append({**style, "cards": cards})
    return normalized


def find_taiwan_style_card(cards: list[dict[str, Any]], card_id: str | None) -> dict[str, Any] | None:
    if not card_id:
        return None
    return next(
        (card for style in cards for card in style.get("cards", []) if card.get("card_id") == card_id),
        None,
    )
