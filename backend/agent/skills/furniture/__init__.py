"""家具 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ...documents import (
    CandidateListDoc,
    ChosenItem,
    FurnitureListDoc,
    LayoutDoc,
    RequirementDoc,
    SceneDoc,
    ValidationReportDoc,
)
from ...llm import LLMGateway
from ...tools.design_knowledge import selection_digest
from ...tools.pick_furniture import PickFurnitureTool, default_hint
from ...tools.place_furniture import PlaceFurnitureTool
from ...tools.rag_furniture import RagFurnitureTool
from ..base import ask_llm_json, load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)
SELECT_SPEC = DOC.spec("select")
REPAIR_SPEC = DOC.spec("repair")


@dataclass(frozen=True)
class Strategy:
    variant: str
    key: str
    label: str
    directive: str


STRATEGIES: dict[str, Strategy] = {
    "A": Strategy(
        variant="A",
        key="circulation",
        label="動線優先",
        directive="留出開闊走道與活動空間；家具數量精簡、靠牆配置，優先保證動線流暢。",
    ),
    "B": Strategy(
        variant="B",
        key="storage",
        label="收納優先",
        directive="優先納入收納量體（衣櫃、櫃體、層架）；配件緊湊配置，最大化收納容量。",
    ),
}


class FurnitureSkill:
    def __init__(
        self,
        gateway: LLMGateway | None,
        *,
        rag_tool: RagFurnitureTool,
        pick_tool: PickFurnitureTool | None = None,
        place_tool: PlaceFurnitureTool | None = None,
    ) -> None:
        self._gateway = gateway
        self._rag = rag_tool
        self._pick = pick_tool or PickFurnitureTool()
        self._place = place_tool or PlaceFurnitureTool()

    # -- 候選（RAG 邊界） --

    def build_candidates(
        self, requirements: RequirementDoc, layout: LayoutDoc
    ) -> CandidateListDoc:
        return self._rag.run(requirements, layout)

    # -- 選件（白名單紀律＋補位） --

    def choose(
        self,
        requirements: RequirementDoc,
        candidates: CandidateListDoc,
        *,
        strategy: Strategy,
    ) -> FurnitureListDoc:
        llm_out = ask_llm_json(
            self._gateway,
            SELECT_SPEC,
            self._select_prompt(requirements, candidates, strategy),
            required=("selections",),
        )
        if llm_out is not None:
            outcome = self._pick.validate_selections(
                candidates,
                llm_out.get("selections") or [],
                variant=strategy.variant,
                strategy=strategy.label,
            )
            doc = outcome.doc
            if doc.items:
                self._cover_missing_musts(doc, requirements, candidates)
                return doc
        return self._pick.fallback_pick(
            requirements,
            candidates,
            variant=strategy.variant,
            strategy=strategy.label,
            extra_categories=("rug", "lighting")
            if strategy.key == "circulation"
            else ("storage", "rug", "lighting"),
        )

    # -- 擺放（engine 邊界） --

    def place(self, layout: LayoutDoc, furniture_list: FurnitureListDoc) -> SceneDoc:
        return self._place.run(layout, furniture_list)

    # -- 修復（迴圈次數由 Master 控制） --

    def repair(
        self,
        furniture_list: FurnitureListDoc,
        report: ValidationReportDoc,
        scene: SceneDoc,
        candidates: CandidateListDoc,
    ) -> FurnitureListDoc:
        targets = {violation.item_id for violation in report.hard_violations}
        targets.update(row["id"] for row in scene.failures())
        if not targets:
            return furniture_list
        actions = self._llm_repair_actions(furniture_list, report, scene, candidates, targets)
        if actions is None:
            actions = self._fallback_repair_actions(furniture_list, candidates, targets)
        return self._apply_actions(furniture_list, candidates, actions)

    # -- 內部：提示詞 --

    def _select_prompt(
        self,
        requirements: RequirementDoc,
        candidates: CandidateListDoc,
        strategy: Strategy,
    ) -> str:
        musts = [
            {
                "req_id": item.req_id,
                "room_id": item.room_id,
                "text": item.text,
                "category": item.category,
                "quantity": item.quantity,
            }
            for item in requirements.must_have()
        ]
        prefs = [item.text for item in requirements.soft][:8]
        pool = {
            room_id: [
                {
                    "catalog_id": c.catalog_id,
                    "name": c.name,
                    "category": c.category,
                    "width_cm": c.width_cm,
                    "depth_cm": c.depth_cm,
                    "price": c.price,
                    "style": c.style,
                    "score": c.score,
                }
                for c in rows
            ]
            for room_id, rows in candidates.by_room.items()
        }
        return (
            f"策略：{strategy.label}——{strategy.directive}\n"
            f"硬需求：{json.dumps(musts, ensure_ascii=False)}\n"
            f"偏好：{json.dumps(prefs, ensure_ascii=False)}\n"
            f"候選白名單：{json.dumps(pool, ensure_ascii=False)}\n"
            "設計知識參考（英制原文，僅供選件與擺位意圖的語意判斷；"
            "不得輸出座標，幾何一律由 engine 以公分計算）：\n"
            f"{selection_digest()}"
        )

    # -- 內部：補足未覆蓋的硬需求 --

    def _cover_missing_musts(
        self,
        doc: FurnitureListDoc,
        requirements: RequirementDoc,
        candidates: CandidateListDoc,
    ) -> None:
        fallback = self._pick.fallback_pick(
            requirements, candidates, variant=doc.variant, strategy=doc.strategy,
            extra_categories=(),
        )
        used_ids = {item.item_id for item in doc.items}
        used_catalog = {(item.room_id, item.catalog_id) for item in doc.items}
        for req in requirements.must_have():
            covered = any(
                item.room_id == (req.room_id or item.room_id)
                and (req.req_id in item.matched_requirements or item.category == req.category)
                for item in doc.items
            )
            if covered:
                continue
            for candidate_item in fallback.items:
                if req.req_id not in candidate_item.matched_requirements:
                    continue
                if (candidate_item.room_id, candidate_item.catalog_id) in used_catalog:
                    continue
                new_item = candidate_item
                while new_item.item_id in used_ids:
                    prefix, _, tail = new_item.item_id.rpartition("_")
                    new_item.item_id = f"{prefix}_{int(tail) + 100}"
                used_ids.add(new_item.item_id)
                used_catalog.add((new_item.room_id, new_item.catalog_id))
                new_item.reason = (new_item.reason + "（補足未覆蓋硬需求）").strip()
                doc.items.append(new_item)

    # -- 內部：修復動作 --

    def _llm_repair_actions(
        self,
        furniture_list: FurnitureListDoc,
        report: ValidationReportDoc,
        scene: SceneDoc,
        candidates: CandidateListDoc,
        targets: set[str],
    ) -> list[dict] | None:
        items_by_id = {item.item_id: item for item in furniture_list.items}
        problem_rows = [
            {
                "item_id": violation.item_id,
                "room_id": violation.room_id,
                "reason": violation.reason,
                "is_must": bool(
                    items_by_id.get(violation.item_id)
                    and items_by_id[violation.item_id].matched_requirements
                ),
            }
            for violation in report.hard_violations
        ] + [
            {
                "item_id": row["id"],
                "room_id": row["room_id"],
                "reason": row["reason"],
                "is_must": bool(row.get("matched_requirements")),
            }
            for row in scene.failures()
        ]
        pool = {
            room_id: [
                {
                    "catalog_id": c.catalog_id,
                    "name": c.name,
                    "category": c.category,
                    "width_cm": c.width_cm,
                    "depth_cm": c.depth_cm,
                }
                for c in rows
            ]
            for room_id, rows in candidates.by_room.items()
        }
        llm_out = ask_llm_json(
            self._gateway,
            REPAIR_SPEC,
            f"問題清單：{json.dumps(problem_rows, ensure_ascii=False)}\n"
            f"候選白名單：{json.dumps(pool, ensure_ascii=False)}",
            required=("actions",),
        )
        if llm_out is None:
            return None
        actions = [
            row
            for row in llm_out.get("actions") or []
            if isinstance(row, dict) and row.get("item_id") in targets
        ]
        return actions or None

    def _fallback_repair_actions(
        self,
        furniture_list: FurnitureListDoc,
        candidates: CandidateListDoc,
        targets: set[str],
    ) -> list[dict]:
        actions: list[dict] = []
        used = {(item.room_id, item.catalog_id) for item in furniture_list.items}
        for item in furniture_list.items:
            if item.item_id not in targets:
                continue
            replacement = self._next_smaller(item, candidates, used)
            if replacement is not None:
                actions.append(
                    {
                        "item_id": item.item_id,
                        "action": "swap",
                        "replacement_catalog_id": replacement,
                        "reason": "換成更小的同類候選（deterministic 修復）",
                    }
                )
            elif not item.matched_requirements:
                actions.append(
                    {"item_id": item.item_id, "action": "remove", "reason": "非必要件，移除以釋放空間"}
                )
        return actions

    def _next_smaller(
        self,
        item: ChosenItem,
        candidates: CandidateListDoc,
        used: set[tuple[str, str]],
    ) -> str | None:
        area = item.width_cm * item.depth_cm
        pool = [
            c
            for c in candidates.by_room.get(item.room_id, [])
            if c.category == item.category
            and (item.room_id, c.catalog_id) not in used
            and c.width_cm * c.depth_cm < area
        ]
        if not pool:
            return None
        best = max(pool, key=lambda c: c.width_cm * c.depth_cm)  # 最接近原尺寸的較小者
        return best.catalog_id

    def _apply_actions(
        self,
        furniture_list: FurnitureListDoc,
        candidates: CandidateListDoc,
        actions: list[dict],
    ) -> FurnitureListDoc:
        by_id = {item.item_id: item for item in furniture_list.items}
        catalog_pool = {
            (room_id, c.catalog_id): c
            for room_id, rows in candidates.by_room.items()
            for c in rows
        }
        removed: set[str] = set()
        for action in actions:
            item = by_id.get(str(action.get("item_id")))
            if item is None:
                continue
            if action.get("action") == "remove":
                if not item.matched_requirements:
                    removed.add(item.item_id)
                continue
            if action.get("action") == "swap":
                replacement = catalog_pool.get(
                    (item.room_id, str(action.get("replacement_catalog_id")))
                )
                if replacement is None or replacement.category != item.category:
                    continue
                item.catalog_id = replacement.catalog_id
                item.name = replacement.name
                item.width_cm = replacement.width_cm
                item.depth_cm = replacement.depth_cm
                item.height_cm = replacement.height_cm
                item.style = replacement.style
                item.price = replacement.price
                item.clearance = replacement.clearance
                item.reason = (item.reason + "（修復：換更小尺寸）").strip()
        furniture_list.items = [
            item for item in furniture_list.items if item.item_id not in removed
        ]
        for item in furniture_list.items:
            if item.hint.anchor_item_id in removed:
                item.hint = default_hint(item.category)
        return furniture_list
