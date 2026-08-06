"""設計知識 tool：節錄知識型 skill 文件，供選件提示與生圖措辭引用（deterministic）。

知識來源是 ``skills/`` 下兩份純宣告 SKILL.md（foundry-skills、Apache-2.0、
英文原文，只有宣告層、無 Python 流程層）：

- ``interior_designer``：風格矩陣、擺放通則、分房設計指南。
- ``interior_design_principles``：尺度/比例、色彩、照明、動線原則。

本 tool 只做 deterministic 節錄，不呼叫 LLM、不做幾何：

- ``selection_digest()``：擺放通則原文節錄，附在家具選件 user prompt 作語意參考。
- ``style_note()``：問卷風格 → 風格矩陣的材質/色彩/氛圍描述行，供生圖提示詞。

原文為英制單位，僅供語意判斷；座標與合法性仍只由 ``backend/engine/`` 判定。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .base import ToolContract

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# ponytail: 樸素關鍵字子字串對應；矩陣沒有的風格（如純日式）取最近似項，對不上回空字串
_STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "MINIMALIST": ("極簡", "簡約", "日式", "無印", "侘寂", "minimal", "muji", "japandi"),
    "SCANDINAVIAN": ("北歐", "斯堪地", "scandi", "nordic", "hygge"),
    "INDUSTRIAL": ("工業", "loft", "industrial"),
    "MID-CENTURY MODERN": ("中古", "復古", "mid-century", "midcentury"),
    "FARMHOUSE / MODERN FARMHOUSE": ("鄉村", "田園", "農舍", "farmhouse", "rustic"),
    "BOHEMIAN": ("波希米亞", "波西米亞", "boho", "bohemian"),
    "TRANSITIONAL": ("過渡", "新古典", "transitional"),
    "CONTEMPORARY": ("當代", "contemporary"),
    "MODERN": ("現代", "摩登", "modern"),
}
_STYLE_DETAIL_KEYS = ("Materials", "Colors", "Furniture", "Feel")


def _body(folder: str) -> str:
    """讀 SKILL.md 本文（去掉 frontmatter）。檔案缺失時直接丟例外（匯入期即發現）。"""
    text = (_SKILLS_DIR / folder / "SKILL.md").read_text(encoding="utf-8")
    end = text.find("\n---", 3) if text.startswith("---") else -1
    return text[end + 4 :] if end != -1 else text


def _section(body: str, title: str) -> str:
    match = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", body, re.S | re.M)
    return match.group(1) if match else ""


def _first_fence(text: str) -> str:
    match = re.search(r"```\n?(.*?)```", text, re.S)
    return match.group(1).strip() if match else ""


@lru_cache(maxsize=1)
def _style_blocks() -> dict[str, str]:
    """風格矩陣 → {風格名: 描述行}。風格名為頂格全大寫行，描述行縮排兩格。"""
    matrix = _first_fence(_section(_body("interior_designer"), "Design Style Guide"))
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in matrix.splitlines():
        if re.fullmatch(r"[A-Z][A-Z /\-]*", line):
            current = line
            blocks[current] = []
        elif current is not None and line.strip():
            blocks[current].append(line.strip())
    return {name: "\n".join(rows) for name, rows in blocks.items()}


@lru_cache(maxsize=1)
def selection_digest() -> str:
    """擺放通則精華（interior_designer「LAYOUT PRINCIPLES」原文節錄）。"""
    return _first_fence(_section(_body("interior_designer"), "Room Layout Principles"))


def style_note(styles: tuple[str, ...] | list[str]) -> str:
    """把第一個可對應的問卷風格翻成矩陣描述行；對不上回空字串（生圖端略過）。"""
    for style in styles:
        text = str(style).lower()
        for name, keywords in _STYLE_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                details = [
                    line
                    for line in _style_blocks().get(name, "").splitlines()
                    if line.split(":", 1)[0] in _STYLE_DETAIL_KEYS
                ]
                if details:
                    return f"風格參考（{name}）：" + "；".join(details)
    return ""


class DesignKnowledgeTool:
    contract = ToolContract(
        name="design_knowledge",
        description="節錄知識型 skill（室內設計原則/顧問）：選件擺放通則與風格矩陣描述。",
        input_schema={
            "type": "object",
            "properties": {"styles": {"type": "array", "items": {"type": "string"}}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "selection_digest": {"type": "string"},
                "style_note": {"type": "string"},
            },
        },
    )

    def run(self, styles: list[str] | None = None) -> dict:
        return {
            "selection_digest": selection_digest(),
            "style_note": style_note(tuple(styles or ())),
        }
