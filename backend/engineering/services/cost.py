"""Cost Service：只用結構化 PriceRecord 計價；LLM 不得補猜價格。

估價公式：
    計價量 = 工程量 × (1 + 損耗率)
    小計   = 計價量 × (材料單價 + 人工單價 + 其他單價)

demo_mode=False（正式模式）時不得使用 region=DEMO_ONLY 的合成價格；
找不到同地區有效單價 → subtotal=None、status=pending_quote。
"""
from __future__ import annotations

from ..contracts import (
    EstimateLine,
    EstimateResult,
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
)
from ..knowledge_repo import JsonKnowledgeRepository


class CostService:
    def __init__(
        self,
        knowledge: JsonKnowledgeRepository,
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
        del quantities  # 工程量已封裝在 retrieval work item。
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
                prices = [material, labor, other]
                priced = record is not None and all(
                    value is not None for value in prices
                )
                subtotal = (
                    round(pricing_quantity * sum(float(value) for value in prices), 2)
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
        pending_quote_count = sum(1 for item in lines if item.subtotal is None)
        uses_demo = any(item.price_region == "DEMO_ONLY" for item in lines)

        if uses_demo:
            disclaimer = (
                "目前啟用 DEMO_MODE，金額使用合成示範單價，只用於測試公式、畫面與文件流程；"
                "不得作為市場行情、正式報價、契約或施工依據。"
            )
        else:
            disclaimer = (
                "此為初步工程量與版本化單價計算。缺少單價的工項顯示待詢價；"
                "正式價格以所在地廠商現勘、工法、材料型號及書面報價為準。"
            )

        return EstimateResult(
            lines=lines,
            known_subtotal=known_subtotal,
            estimated_total=known_subtotal if pending_quote_count == 0 else None,
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
            and item.get("region") != "DEMO_ONLY"
            and item.get("status") not in {"pending_quote", "disabled"}
        ]
        if exact:
            return sorted(exact, key=lambda item: item.get("effective_date", ""))[-1]

        if self.demo_mode:
            demo = [
                item
                for item in records
                if item.get("region") == "DEMO_ONLY"
                and item.get("status") == "demo_reference"
            ]
            if demo:
                return sorted(demo, key=lambda item: item.get("effective_date", ""))[-1]
        return None
