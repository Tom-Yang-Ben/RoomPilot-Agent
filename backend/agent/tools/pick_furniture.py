"""挑家具 tool：白名單驗證與 deterministic fallback 選件。

紀律沿用舊 ``select`` 模組的核心精神：LLM 只能從候選白名單挑選；
任何白名單外的 catalog_id 一律拒絕並記錄原因。LLM 的提示詞與語意判斷
在 ``skills/furniture.py``；本 tool 只負責驗證、補位與擺位意圖的
heuristic 預設值。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..documents import (
    CandidateItem,
    CandidateListDoc,
    ChosenItem,
    FurnitureListDoc,
    PlacementHint,
    RequirementDoc,
)
from .base import ToolContract

# 主件（free 擺放、先擺）；順序即 fallback 的擺放優先序。
ANCHOR_CATEGORIES = [
    "bed",
    "sofa",
    "dining_table",
    "desk",
    "wardrobe",
    "storage",
    "media",
]
# 配件：靠著哪類主件擺（method=adjacent）。
ADJACENT_PREFERENCE = {
    "side_table": ["bed", "sofa"],
    "coffee_table": ["sofa"],
    "lighting": ["sofa", "bed", "desk"],
    "armchair": ["sofa", "coffee_table"],
    "stool_bench": ["dining_table", "bed"],
    "dining_chair": ["dining_table"],
    "office_chair": ["desk"],
    "mirror": ["wardrobe", "storage"],
    "decor": ["storage", "media", "desk"],
    "kids": ["bed"],
}
# 地面覆蓋物：壓在哪類主件下（method=overlay）。
OVERLAY_PREFERENCE = {"rug": ["bed", "sofa"]}

_METHOD_ORDER = {"free": 0, "adjacent": 1, "overlay": 2}


def default_hint(category: str) -> PlacementHint:
    if category in OVERLAY_PREFERENCE:
        return PlacementHint(method="overlay", note="壓在主家具下方")
    if category in ADJACENT_PREFERENCE:
        return PlacementHint(method="adjacent", note="緊鄰主家具擺放")
    return PlacementHint(method="free", note="主件，優先取得空間")


def order_for_placement(items: list[ChosenItem]) -> list[ChosenItem]:
    """主件先擺、配件次之、覆蓋物最後；主件之間依 ANCHOR_CATEGORIES 排序。"""

    def sort_key(item: ChosenItem) -> tuple[int, int]:
        method_rank = _METHOD_ORDER.get(item.hint.method, 3)
        try:
            anchor_rank = ANCHOR_CATEGORIES.index(item.category)
        except ValueError:
            anchor_rank = len(ANCHOR_CATEGORIES)
        return (method_rank, anchor_rank)

    return sorted(items, key=sort_key)


def resolve_anchor(item: ChosenItem, chosen_in_room: list[ChosenItem]) -> str | None:
    """為 adjacent/overlay 配件找同房間的主件 item_id。"""
    preference = ADJACENT_PREFERENCE.get(item.category) or OVERLAY_PREFERENCE.get(
        item.category
    )
    if not preference:
        return None
    for anchor_category in preference:
        for other in chosen_in_room:
            if other.item_id != item.item_id and other.category == anchor_category:
                return other.item_id
    return None


@dataclass
class SelectionOutcome:
    doc: FurnitureListDoc
    rejected: list[dict] = field(default_factory=list)


class PickFurnitureTool:
    contract = ToolContract(
        name="pick_furniture",
        description=(
            "驗證選件（只允許候選白名單）並組成家具清單；"
            "或在無 LLM 時以排序分數 deterministic 補位。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "candidates": {"type": "object"},
                "selections": {"type": "array"},
                "variant": {"type": "string"},
                "strategy": {"type": "string"},
            },
            "required": ["candidates"],
        },
        output_schema={"type": "object", "description": "FurnitureListDoc dict＋rejected"},
    )

    # -- LLM 選件驗證（白名單紀律） --

    def validate_selections(
        self,
        candidates: CandidateListDoc,
        selections: list[dict],
        *,
        variant: str,
        strategy: str,
    ) -> SelectionOutcome:
        doc = FurnitureListDoc(variant=variant, strategy=strategy)
        rejected: list[dict] = []
        counters: dict[str, int] = {}
        whitelist: dict[tuple[str, str], CandidateItem] = {}
        for room_id, rows in candidates.by_room.items():
            for candidate in rows:
                whitelist[(room_id, candidate.catalog_id)] = candidate
        for row in selections or []:
            room_id = str(row.get("room_id", ""))
            catalog_id = str(row.get("catalog_id", ""))
            candidate = whitelist.get((room_id, catalog_id))
            if candidate is None:
                rejected.append(
                    {
                        "room_id": room_id,
                        "catalog_id": catalog_id,
                        "reason": "不在該房間候選白名單內",
                    }
                )
                continue
            hint_row = row.get("hint") or {}
            hint = PlacementHint(
                method=str(hint_row.get("method") or default_hint(candidate.category).method),
                anchor_item_id=hint_row.get("anchor_item_id"),
                note=str(hint_row.get("note", "")),
            )
            if hint.method not in _METHOD_ORDER:
                hint.method = default_hint(candidate.category).method
            doc.items.append(
                self._chosen_from_candidate(
                    candidate,
                    room_id,
                    counters,
                    matched=[str(r) for r in row.get("matched_requirements") or []],
                    hint=hint,
                    reason=str(row.get("reason", "")),
                )
            )
        self._fill_anchors(doc)
        return SelectionOutcome(doc=doc, rejected=rejected)

    # -- deterministic fallback：無 LLM 時依需求與分數補位 --

    def fallback_pick(
        self,
        requirements: RequirementDoc,
        candidates: CandidateListDoc,
        *,
        variant: str,
        strategy: str,
        extra_categories: tuple[str, ...] = ("rug", "lighting"),
    ) -> FurnitureListDoc:
        doc = FurnitureListDoc(variant=variant, strategy=strategy)
        counters: dict[str, int] = {}
        for room_id, rows in candidates.by_room.items():
            ranked = sorted(rows, key=lambda c: c.score, reverse=True)
            used: set[str] = set()
            for req in requirements.must_have(room_id):
                pool = [
                    c for c in ranked if c.category == req.category and c.catalog_id not in used
                ]
                for candidate in pool[: req.quantity]:
                    used.add(candidate.catalog_id)
                    doc.items.append(
                        self._chosen_from_candidate(
                            candidate,
                            room_id,
                            counters,
                            matched=[req.req_id],
                            hint=default_hint(candidate.category),
                            reason=f"對應需求「{req.text}」的最高排序候選",
                        )
                    )
            for category in extra_categories:
                if any(i.room_id == room_id and i.category == category for i in doc.items):
                    continue
                pool = [
                    c for c in ranked if c.category == category and c.catalog_id not in used
                ]
                if pool:
                    candidate = pool[0]
                    used.add(candidate.catalog_id)
                    doc.items.append(
                        self._chosen_from_candidate(
                            candidate,
                            room_id,
                            counters,
                            matched=[],
                            hint=default_hint(category),
                            reason="氛圍配件（軟潛規則建議）",
                        )
                    )
        self._fill_anchors(doc)
        return doc

    # -- 內部 --

    def _chosen_from_candidate(
        self,
        candidate: CandidateItem,
        room_id: str,
        counters: dict[str, int],
        *,
        matched: list[str],
        hint: PlacementHint,
        reason: str,
    ) -> ChosenItem:
        counters[candidate.category] = counters.get(candidate.category, 0) + 1
        item_id = f"{candidate.category}_{counters[candidate.category]}"
        return ChosenItem(
            item_id=item_id,
            catalog_id=candidate.catalog_id,
            room_id=room_id,
            name=candidate.name,
            category=candidate.category,
            width_cm=candidate.width_cm,
            depth_cm=candidate.depth_cm,
            height_cm=candidate.height_cm,
            style=candidate.style,
            price=candidate.price,
            matched_requirements=matched,
            hint=hint,
            clearance=candidate.clearance,
            reason=reason,
        )

    def _fill_anchors(self, doc: FurnitureListDoc) -> None:
        for item in doc.items:
            if item.hint.method in ("adjacent", "overlay") and not item.hint.anchor_item_id:
                anchor = resolve_anchor(item, doc.in_room(item.room_id))
                if anchor:
                    item.hint.anchor_item_id = anchor
                else:
                    item.hint.method = "free"
                    item.hint.note += "（找不到主件，改為自由擺放）"
