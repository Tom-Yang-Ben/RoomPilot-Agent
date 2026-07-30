from __future__ import annotations

from .knowledge import JsonEngineeringKnowledgeRepository
from .models import (
    EstimateLine,
    EstimateResult,
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
)


class CostService:
    """Calculate from structured PriceRecord only; never ask an LLM for prices."""

    def __init__(
        self,
        knowledge: JsonEngineeringKnowledgeRepository,
        *,
        demo_mode: bool = False,
    ) -> None:
        self.knowledge = knowledge
        self.demo_mode = demo_mode

    def estimate(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
    ) -> EstimateResult:
        del quantities
        lines: list[EstimateLine] = []
        for room in retrieval.rooms:
            for work_item in room.work_items:
                record = self._select_price_record(
                    work_item.work_item_code, snapshot.region
                )
                pricing_quantity = round(
                    work_item.quantity * (1 + work_item.waste_rate), 4
                )
                material = record.get("material_unit_price") if record else None
                labor = record.get("labor_unit_price") if record else None
                other = record.get("other_unit_price") if record else None
                unit_prices = [material, labor, other]
                priced = record is not None and all(
                    value is not None for value in unit_prices
                )
                subtotal = (
                    round(
                        pricing_quantity
                        * sum(float(value) for value in unit_prices),
                        2,
                    )
                    if priced
                    else None
                )
                lines.append(
                    EstimateLine(
                        room_id=room.room_id,
                        work_item_code=work_item.work_item_code,
                        trade=work_item.trade,
                        name=work_item.name,
                        unit=work_item.unit,
                        raw_quantity=work_item.quantity,
                        waste_rate=work_item.waste_rate,
                        pricing_quantity=pricing_quantity,
                        material_unit_price=material,
                        labor_unit_price=labor,
                        other_unit_price=other,
                        subtotal=subtotal,
                        price_record_id=(record or {}).get("price_record_id"),
                        price_source=(record or {}).get("source"),
                        price_effective_date=(record or {}).get("effective_date"),
                        price_region=(record or {}).get("region"),
                        status="priced" if priced else "pending_quote",
                        confidence=(record or {}).get("confidence", "low"),
                    )
                )

        known_subtotal = round(sum(item.subtotal or 0 for item in lines), 2)
        pending_quote_count = sum(item.subtotal is None for item in lines)
        if self.demo_mode:
            disclaimer = (
                "示範資料，非正式報價。ROOMPILOT_DEMO_MODE=true，金額使用 DEMO_ONLY "
                "合成單價，只供公式、畫面與文件流程驗證。"
            )
        else:
            disclaimer = (
                "正式模式只接受所在地、版本化且非合成的 PriceRecord；缺價工項為 "
                "pending_quote，subtotal=null，絕不補猜或形成假總價。"
            )
        return EstimateResult(
            lines=lines,
            known_subtotal=known_subtotal,
            estimated_total=(
                known_subtotal if lines and pending_quote_count == 0 else None
            ),
            pending_quote_count=pending_quote_count,
            disclaimer=disclaimer,
        )

    def _select_price_record(
        self, work_item_code: str, region: str
    ) -> dict | None:
        records = [
            item
            for item in self.knowledge.price_records()
            if item.get("work_item_code") == work_item_code
        ]
        exact = [
            item
            for item in records
            if item.get("region") == region
            and item.get("status") not in {"pending_quote", "disabled"}
            and item.get("is_synthetic") is not True
        ]
        if exact:
            return sorted(exact, key=lambda item: item.get("effective_date", ""))[-1]
        if self.demo_mode:
            demo = [
                item
                for item in records
                if item.get("region") == "DEMO_ONLY"
                and item.get("status") == "demo_reference"
                and item.get("is_synthetic") is True
            ]
            if demo:
                return sorted(
                    demo, key=lambda item: item.get("effective_date", "")
                )[-1]
        return None

