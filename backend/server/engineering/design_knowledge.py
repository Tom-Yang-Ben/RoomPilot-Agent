"""設計語彙知識庫的讀取與契約驗證。

與 :mod:`knowledge`（工程知識）平行但刻意分開：工程知識決定數字，設計知識
只決定論述語言。兩者的來源登錄、可信度標示與驗證規則各自獨立。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonDesignKnowledgeRepository:
    """版本化的設計語彙 seed 讀取器。"""

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

    def source_registry(self) -> list[dict[str, Any]]:
        return self._load_array("design_source_registry.json")

    def style_vocabulary(self) -> list[dict[str, Any]]:
        return self._load_array("style_vocabulary.json")

    def color_strategy(self) -> list[dict[str, Any]]:
        return self._load_array("color_strategy.json")

    def material_vocabulary(self) -> list[dict[str, Any]]:
        return self._load_array("material_vocabulary.json")

    def room_design_principles(self) -> list[dict[str, Any]]:
        return self._load_array("room_design_principles.json")

    def style_entry(self, style_id: str | None) -> dict[str, Any] | None:
        if not style_id:
            return None
        for item in self.style_vocabulary():
            if item.get("style_id") == style_id:
                return item
        return None

    def color_entry(self, style_id: str | None) -> dict[str, Any] | None:
        if not style_id:
            return None
        for item in self.color_strategy():
            if item.get("style_id") == style_id:
                return item
        return None

    def material_entry(self, style_id: str | None) -> dict[str, Any] | None:
        if not style_id:
            return None
        for item in self.material_vocabulary():
            if item.get("style_id") == style_id:
                return item
        return None

    def room_entry(self, room_type: str | None) -> dict[str, Any] | None:
        if not room_type:
            return None
        for item in self.room_design_principles():
            if item.get("room_type") == room_type:
                return item
        return None


def validate_design_knowledge(
    repository: JsonDesignKnowledgeRepository,
) -> dict[str, int]:
    """確認來源引用完整、鍵值不重複，且沒有偽裝成外部權威的內部編纂。"""
    sources = repository.source_registry()
    source_ids = {item.get("source_id") for item in sources}
    if None in source_ids or len(source_ids) != len(sources):
        raise ValueError("design_source_registry source_id 必須存在且不可重複")
    for source in sources:
        if source.get("external_reference") is True and not source.get("url"):
            raise ValueError(
                f"{source.get('source_id')} 標為外部引用就必須附上可查證 url"
            )

    style_ids: set[str] = set()
    for filename, records, key in (
        ("style_vocabulary", repository.style_vocabulary(), "style_id"),
        ("color_strategy", repository.color_strategy(), "style_id"),
        ("material_vocabulary", repository.material_vocabulary(), "style_id"),
        ("room_design_principles", repository.room_design_principles(), "room_type"),
    ):
        keys = [item.get(key) for item in records]
        if None in keys:
            raise ValueError(f"{filename} 每筆都必須有 {key}")
        if len(keys) != len(set(keys)):
            raise ValueError(f"{filename} 的 {key} 不可重複")
        missing_sources = {item.get("source_id") for item in records} - source_ids
        if missing_sources:
            raise ValueError(f"{filename} 缺少來源登錄: {missing_sources}")
        for item in records:
            confidence = item.get("confidence")
            if confidence not in {"low", "medium", "high", "contractor_confirmed"}:
                raise ValueError(f"{filename} 的 confidence 值不合法: {confidence}")
            source = next(
                candidate
                for candidate in sources
                if candidate.get("source_id") == item.get("source_id")
            )
            if (
                confidence == "high"
                and source.get("external_reference") is not True
            ):
                # 內部編纂不得標成 high；那會讓報告看起來有外部背書。
                raise ValueError(
                    f"{filename} 的 {item.get(key)} 標為 high，"
                    f"但來源 {source.get('source_id')} 不是外部引用"
                )
        if key == "style_id":
            style_ids.update(keys)

    # 三份風格檔必須覆蓋同一組 style_id，否則報告會缺章節。
    for filename, records in (
        ("color_strategy", repository.color_strategy()),
        ("material_vocabulary", repository.material_vocabulary()),
    ):
        covered = {item.get("style_id") for item in records}
        vocabulary = {item.get("style_id") for item in repository.style_vocabulary()}
        if covered != vocabulary:
            raise ValueError(
                f"{filename} 的 style_id 與 style_vocabulary 不一致: "
                f"缺少 {vocabulary - covered}，多出 {covered - vocabulary}"
            )

    return {
        "sources": len(sources),
        "styles": len(repository.style_vocabulary()),
        "color_strategies": len(repository.color_strategy()),
        "material_vocabularies": len(repository.material_vocabulary()),
        "room_principles": len(repository.room_design_principles()),
    }
