from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote


STYLE_CARDS_PATH = Path(__file__).resolve().parents[1] / "catalog" / "data" / "taiwan_style_cards.json"


def _palette_preview_url(palette: list[str]) -> str:
    colors = (palette or ["#f3eee5", "#c8b49b", "#766b60"])[:4]
    width = 600 / len(colors)
    rectangles = "".join(
        f'<rect x="{index * width:g}" width="{width:g}" height="360" fill="{color}"/>'
        for index, color in enumerate(colors)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 360">'
        f"{rectangles}</svg>"
    )
    return "data:image/svg+xml," + quote(svg, safe="")


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
                    "image_url": _palette_preview_url(card.get("palette_hex") or []),
                    "image_kind": "project_authored_palette",
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
