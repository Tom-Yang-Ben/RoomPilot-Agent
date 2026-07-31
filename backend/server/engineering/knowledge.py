from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonEngineeringKnowledgeRepository:
    """Versioned MVP engineering seed repository.

    This repository is separate from the formal furniture catalog. DEMO_ONLY
    price/productivity rows are filtered by their consuming services.
    """

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def _load_array(self, filename: str) -> list[dict[str, Any]]:
        if filename not in self._cache:
            path = self.knowledge_dir / filename
            with path.open("r", encoding="utf-8") as file:
                value = json.load(file)
            if not isinstance(value, list) or not all(
                isinstance(item, dict) for item in value
            ):
                raise ValueError(f"{filename} 必須是 JSON object array")
            self._cache[filename] = value
        return self._cache[filename]

    def material_catalog(self) -> list[dict[str, Any]]:
        return self._load_array("material_catalog.json")

    def work_items(self) -> list[dict[str, Any]]:
        return self._load_array("work_items.json")

    def material_work_mappings(self) -> list[dict[str, Any]]:
        return self._load_array("material_work_mappings.json")

    def equipment_mep_mappings(self) -> list[dict[str, Any]]:
        return self._load_array("equipment_mep_mappings.json")

    def price_records(self) -> list[dict[str, Any]]:
        return self._load_array("price_records.json")

    def productivity_records(self) -> list[dict[str, Any]]:
        return self._load_array("productivity_records.json")

    def task_dependencies(self) -> list[dict[str, Any]]:
        return self._load_array("task_dependencies.json")

    def source_registry(self) -> list[dict[str, Any]]:
        return self._load_array("source_registry.json")

    def production_material_price_templates(self) -> list[dict[str, Any]]:
        return self._load_array(
            "production_templates/material_prices.pending_quote.json"
        )

    def production_price_templates(self) -> list[dict[str, Any]]:
        return self._load_array(
            "production_templates/price_records.pending_quote.json"
        )

    def production_productivity_templates(self) -> list[dict[str, Any]]:
        return self._load_array(
            "production_templates/productivity_records.pending_confirmation.json"
        )

    def construction_knowledge(self) -> list[dict[str, Any]]:
        filename = "construction_knowledge.jsonl"
        if filename not in self._cache:
            rows: list[dict[str, Any]] = []
            path = self.knowledge_dir / filename
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{filename}:{number} 必須是 JSON object")
                rows.append(value)
            self._cache[filename] = rows
        return self._cache[filename]


def validate_engineering_knowledge(
    repository: JsonEngineeringKnowledgeRepository,
) -> dict[str, int]:
    work_items = repository.work_items()
    work_codes = {item["work_item_code"] for item in work_items}
    if len(work_codes) != len(work_items):
        raise ValueError("work_item_code 不可重複")
    for mapping in repository.material_work_mappings():
        missing = set(mapping.get("work_item_codes") or []) - work_codes
        if missing:
            raise ValueError(f"{mapping.get('mapping_id')} 引用不存在工項: {missing}")
    for mapping in repository.equipment_mep_mappings():
        missing = {
            item.get("code") for item in mapping.get("direct_work_items") or []
        } - work_codes
        if missing:
            raise ValueError(f"{mapping.get('mapping_id')} 引用不存在工項: {missing}")
    for filename, records in (
        ("price_records", repository.price_records()),
        ("productivity_records", repository.productivity_records()),
        ("production_price_templates", repository.production_price_templates()),
        (
            "production_productivity_templates",
            repository.production_productivity_templates(),
        ),
    ):
        missing = {item.get("work_item_code") for item in records} - work_codes
        if missing:
            raise ValueError(f"{filename} 引用不存在工項: {missing}")
    sources = repository.source_registry()
    source_ids = {item.get("source_id") for item in sources}
    if None in source_ids or len(source_ids) != len(sources):
        raise ValueError("source_registry source_id 必須存在且不可重複")
    missing_sources = {
        item.get("source_id") for item in repository.construction_knowledge()
    } - source_ids
    if missing_sources:
        raise ValueError(f"construction_knowledge 缺少來源登錄: {missing_sources}")
    material_templates = repository.production_material_price_templates()
    if any(
        item.get(field) is not None
        for item in material_templates
        for field in ("price_low", "price_typical", "price_high")
    ):
        raise ValueError("Production 材料模板不得預填價格")
    price_templates = repository.production_price_templates()
    if any(
        item.get("is_synthetic") is not False
        or item.get("status") != "pending_quote"
        or any(
            item.get(field) is not None
            for field in (
                "material_unit_price",
                "labor_unit_price",
                "other_unit_price",
            )
        )
        for item in price_templates
    ):
        raise ValueError("Production 單價模板必須為非合成 pending_quote 且價格為 null")
    productivity_templates = repository.production_productivity_templates()
    if any(
        item.get("is_synthetic") is not False
        or any(
            item.get(field) is not None
            for field in (
                "daily_productivity",
                "crew_count",
                "preparation_days",
                "waiting_days",
            )
        )
        for item in productivity_templates
    ):
        raise ValueError("Production 工率模板必須為非合成且數值為 null")
    return {
        "materials": len(repository.material_catalog()),
        "work_items": len(work_items),
        "material_mappings": len(repository.material_work_mappings()),
        "equipment_mappings": len(repository.equipment_mep_mappings()),
        "price_records": len(repository.price_records()),
        "productivity_records": len(repository.productivity_records()),
        "task_dependencies": len(repository.task_dependencies()),
        "construction_documents": len(repository.construction_knowledge()),
        "sources": len(sources),
        "production_material_templates": len(material_templates),
        "production_price_templates": len(price_templates),
        "production_productivity_templates": len(productivity_templates),
    }
