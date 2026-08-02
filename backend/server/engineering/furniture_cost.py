"""家具採購明細與總價。

價格只從 Kai 型錄取得（PostgreSQL 優先，資料庫不可用時回退已驗證 JSON），
與工程施工費完全分開計算與呈現：一個是買家具的錢，一個是施工的錢，
合在一起會讓屋主誤判預算組成。

查無價格的品項一律 ``price_unavailable`` 且 ``subtotal_twd=null``，比照
:class:`CostService` 的 pending_quote，絕不補猜或形成假總價。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .models import (
    FurnitureEstimateLine,
    FurnitureEstimateResult,
    ProjectSnapshot,
)


class FurniturePriceProvider(Protocol):
    provider_name: str

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict[str, Any]]:
        ...


class PostgresFurniturePriceProvider:
    provider_name = "kai_postgresql"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict[str, Any]]:
        from ...catalog.postgres_repository import get_furniture_prices

        return get_furniture_prices(self.project_dir, furniture_ids)


class JsonFurniturePriceProvider:
    provider_name = "verified_json"

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path
        self._index: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._index is not None:
            return self._index
        index: dict[str, dict[str, Any]] = {}
        try:
            payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._index = {}
            return self._index
        items = payload if isinstance(payload, list) else payload.get("items") or []
        for item in items:
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            index[item_id] = {
                "price_twd": item.get("price_twd"),
                "price_is_estimated": bool(item.get("price_is_estimated")),
            }
        self._index = index
        return index

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict[str, Any]]:
        index = self._load()
        return {
            item_id: index[item_id] for item_id in furniture_ids if item_id in index
        }


class UnavailableFurniturePriceProvider:
    """型錄暫時取不到時使用；所有品項標為無價，而不是讓報告產生失敗。"""

    provider_name = "unavailable"

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict[str, Any]]:
        del furniture_ids
        return {}


def build_furniture_price_provider(project_dir: Path) -> FurniturePriceProvider:
    """依既有 catalog provider 設定選擇價格來源，語意與第 6 步一致。"""
    from ...catalog.postgres_repository import catalog_provider_mode

    try:
        if catalog_provider_mode(project_dir) == "postgres":
            return PostgresFurniturePriceProvider(project_dir)
    except Exception:  # noqa: BLE001 - provider 判定失敗不該讓報告產不出來
        pass
    return JsonFurniturePriceProvider(
        project_dir / "JSON" / "furniture" / "furniture_official_catagory.json"
    )


class FurnitureEstimateService:
    def __init__(self, price_provider: FurniturePriceProvider) -> None:
        self.price_provider = price_provider

    def estimate(self, snapshot: ProjectSnapshot) -> FurnitureEstimateResult:
        catalog_ids = [
            item.catalog_furniture_id
            for room in snapshot.rooms
            for item in room.furniture
            if item.catalog_furniture_id
        ]
        try:
            prices = self.price_provider.prices_for(catalog_ids)
            provider_name = self.price_provider.provider_name
        except Exception:  # noqa: BLE001 - 型錄不可用時仍要產出明細，只是沒有價格
            prices = {}
            provider_name = f"{self.price_provider.provider_name}_unavailable"

        lines: list[FurnitureEstimateLine] = []
        for room in snapshot.rooms:
            for item in room.furniture:
                record = prices.get(item.catalog_furniture_id or "")
                unit_price = self._as_int(
                    record.get("price_twd") if record else None
                )
                is_estimated = bool(record.get("price_is_estimated")) if record else False
                priced = unit_price is not None
                lines.append(
                    FurnitureEstimateLine(
                        room_id=room.room_id,
                        room_name=room.name,
                        furniture_id=item.furniture_id,
                        catalog_furniture_id=item.catalog_furniture_id,
                        name=item.name,
                        category=item.category,
                        width_cm=item.width_cm,
                        depth_cm=item.depth_cm,
                        height_cm=item.height_cm,
                        quantity=item.quantity,
                        unit_price_twd=unit_price,
                        subtotal_twd=(
                            unit_price * item.quantity if priced else None
                        ),
                        price_is_estimated=is_estimated,
                        price_source=(
                            provider_name if priced else "price_not_in_catalog"
                        ),
                        status="priced" if priced else "price_unavailable",
                        confidence=self._confidence(priced, is_estimated),
                    )
                )

        known_subtotal = sum(line.subtotal_twd or 0 for line in lines)
        unpriced = sum(line.subtotal_twd is None for line in lines)
        estimated_count = sum(
            line.price_is_estimated and line.subtotal_twd is not None
            for line in lines
        )
        return FurnitureEstimateResult(
            lines=lines,
            known_subtotal_twd=known_subtotal,
            # 有任何一項查不到價，就沒有可信的採購總價。
            estimated_total_twd=(
                known_subtotal if lines and unpriced == 0 else None
            ),
            priced_count=len(lines) - unpriced,
            unpriced_count=unpriced,
            estimated_price_count=estimated_count,
            catalog_provider=provider_name,
            disclaimer=self._disclaimer(unpriced, estimated_count),
        )

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = int(round(float(value)))
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    @staticmethod
    def _confidence(priced: bool, is_estimated: bool) -> str:
        if not priced:
            return "low"
        return "medium" if is_estimated else "high"

    @staticmethod
    def _disclaimer(unpriced: int, estimated: int) -> str:
        parts = [
            "家具採購金額為型錄牌價彙總，不含運送、安裝、組裝與稅金，"
            "亦不含工程施工費。"
        ]
        if unpriced:
            parts.append(
                f"其中 {unpriced} 項型錄查無價格，小計為空且不計入總價，"
                "採購前需個別詢價。"
            )
        if estimated:
            parts.append(
                f"另有 {estimated} 項為型錄推估價（price_is_estimated），"
                "非實際牌價，僅供預算抓感覺。"
            )
        return "".join(parts)
