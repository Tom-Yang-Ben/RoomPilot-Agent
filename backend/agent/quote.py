"""報價單資料層：把場景裡的家具整理成可報價的品項與合計。

邊界：這裡只做彙整與加總，不決定價格。單價一律來自型錄（``price``，由
``rag_furniture`` 對應 ``price_twd``），缺價就是缺價——標「待報價」，不用同類
中位數、不用預算回推，也不隱藏該品項。

金額只在報價單出現：設計手冊與提案 PDF 的內文（章節敘述、空間規格表）不帶
價格，避免屋主邊讀設計邊算錢，也避免價格被 LLM 潤稿寫進敘述裡。
"""
from __future__ import annotations

from dataclasses import dataclass, field

PENDING_TEXT = "待報價"


def merge_rows(rows: list[dict]) -> list[tuple[dict, int]]:
    """同款同尺寸的家具（例如四張一樣的餐椅）合併成一列＋數量。"""
    merged: dict[tuple, list] = {}
    for row in rows:
        key = (
            str(row.get("name") or ""),
            str(row.get("type") or ""),
            round(float(row.get("width") or 0)),
            round(float(row.get("depth") or 0)),
        )
        if key in merged:
            merged[key][1] += 1
        else:
            merged[key] = [row, 1]
    return [(row, count) for row, count in merged.values()]


def _price(row: dict) -> float | None:
    value = row.get("price")
    if value in (None, ""):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


@dataclass(frozen=True)
class QuoteLine:
    name: str
    spec: str  # 「180x90cm」
    count: int
    unit_price: float | None  # None＝型錄未標價，待報價

    @property
    def subtotal(self) -> float | None:
        return None if self.unit_price is None else self.unit_price * self.count

    @property
    def amount_text(self) -> str:
        if self.unit_price is None:
            return PENDING_TEXT
        return f"單價 {self.unit_price:,.0f} 元｜小計 {self.subtotal:,.0f} 元"


@dataclass(frozen=True)
class RoomQuote:
    room_name: str
    lines: list[QuoteLine]


@dataclass
class Quote:
    rooms: list[RoomQuote] = field(default_factory=list)
    budget_total: int | None = None

    @property
    def total(self) -> float:
        """已標價品項的小計總和；待報價品項不進總額，也不估算。"""
        return sum(
            line.subtotal or 0.0 for room in self.rooms for line in room.lines
        )

    @property
    def priced_count(self) -> int:
        return sum(
            line.count
            for room in self.rooms
            for line in room.lines
            if line.unit_price is not None
        )

    @property
    def pending_count(self) -> int:
        return sum(
            line.count
            for room in self.rooms
            for line in room.lines
            if line.unit_price is None
        )

    @property
    def is_empty(self) -> bool:
        return not any(room.lines for room in self.rooms)


def build_quote(
    rooms: list[tuple[str, list[dict]]], *, budget_total: int | None = None
) -> Quote:
    """``rooms``＝[(空間名, 該空間已擺放的 scene rows)]。

    只收已擺入場景的家具：engine 判定放不下的品項不成案，不報價。
    """
    quote = Quote(budget_total=budget_total)
    for room_name, rows in rooms:
        lines = [
            QuoteLine(
                name=str(row.get("name") or row.get("id") or "家具"),
                spec="{w:.0f}x{d:.0f}cm".format(
                    w=float(row.get("width") or 0), d=float(row.get("depth") or 0)
                ),
                count=count,
                unit_price=_price(row),
            )
            for row, count in merge_rows(rows)
        ]
        if lines:
            quote.rooms.append(RoomQuote(room_name=room_name, lines=lines))
    return quote


__all__ = [
    "PENDING_TEXT",
    "Quote",
    "QuoteLine",
    "RoomQuote",
    "build_quote",
    "merge_rows",
]
