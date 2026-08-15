from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonKnowledgeRepository:
    """Structured knowledge（工項、對應、單價、工率、依賴）的唯一讀取入口。"""

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def _load(self, filename: str) -> list[dict[str, Any]]:
        if filename not in self._cache:
            path = self.knowledge_dir / filename
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, list):
                raise ValueError(f"{filename} must contain a JSON array")
            self._cache[filename] = data
        return self._cache[filename]

    def work_items(self) -> list[dict[str, Any]]:
        return self._load("work_items.json")

    def material_work_mappings(self) -> list[dict[str, Any]]:
        return self._load("material_work_mappings.json")

    def equipment_mep_mappings(self) -> list[dict[str, Any]]:
        return self._load("equipment_mep_mappings.json")

    def price_records(self) -> list[dict[str, Any]]:
        return self._load("price_records.json")

    def productivity_records(self) -> list[dict[str, Any]]:
        return self._load("productivity_records.json")

    def task_dependencies(self) -> list[dict[str, Any]]:
        return self._load("task_dependencies.json")
