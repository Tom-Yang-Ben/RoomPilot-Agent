"""家具採購明細：缺價不補猜、推估價要標示、與工程施工費分開。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.server.engineering.furniture_cost import (
    FurnitureEstimateService,
    JsonFurniturePriceProvider,
    UnavailableFurniturePriceProvider,
)
from backend.server.engineering.models import ProjectSnapshot


class StubPriceProvider:
    provider_name = "stub"

    def __init__(self, prices: dict[str, dict]) -> None:
        self.prices = prices
        self.calls: list[list[str]] = []

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict]:
        self.calls.append(list(furniture_ids))
        return {key: self.prices[key] for key in furniture_ids if key in self.prices}


class ExplodingPriceProvider:
    provider_name = "kai_postgresql"

    def prices_for(self, furniture_ids: list[str]) -> dict[str, dict]:
        raise RuntimeError("catalog offline")


def _snapshot(furniture: list[dict]) -> ProjectSnapshot:
    return ProjectSnapshot(
        project_id="p1",
        project_name="測試案",
        revision="R1",
        source_project_revision=1,
        approval_status="designer_confirmed",
        confirmed_by="tester",
        pricing_basis_date="2026-08-02",
        rooms=[
            {
                "room_id": "r1",
                "name": "客廳",
                "room_type": "living_room",
                "geometry": {"length_cm": 500, "width_cm": 400, "height_cm": 280},
                "furniture": furniture,
            }
        ],
    )


def _item(furniture_id: str, catalog_id: str | None, quantity: int = 1) -> dict:
    return {
        "furniture_id": furniture_id,
        "catalog_furniture_id": catalog_id,
        "name": f"品項 {furniture_id}",
        "category": "sofa",
        "width_cm": 200,
        "depth_cm": 90,
        "height_cm": 80,
        "quantity": quantity,
    }


def test_subtotal_multiplies_unit_price_by_quantity() -> None:
    service = FurnitureEstimateService(
        StubPriceProvider({"c1": {"price_twd": 12800, "price_is_estimated": False}})
    )

    result = service.estimate(_snapshot([_item("f1", "c1", quantity=3)]))

    line = result.lines[0]
    assert line.unit_price_twd == 12800
    assert line.subtotal_twd == 38400
    assert line.status == "priced"
    assert line.confidence == "high"
    assert result.known_subtotal_twd == 38400
    assert result.estimated_total_twd == 38400


def test_missing_price_leaves_subtotal_null_and_blocks_the_total() -> None:
    service = FurnitureEstimateService(
        StubPriceProvider({"c1": {"price_twd": 5000, "price_is_estimated": False}})
    )

    result = service.estimate(
        _snapshot([_item("f1", "c1"), _item("f2", "missing"), _item("f3", None)])
    )

    priced, unknown, no_catalog_id = result.lines
    assert priced.subtotal_twd == 5000
    assert unknown.subtotal_twd is None
    assert unknown.status == "price_unavailable"
    assert unknown.confidence == "low"
    assert no_catalog_id.status == "price_unavailable"
    assert result.known_subtotal_twd == 5000
    # 有任一項缺價就沒有可信總價，不能拿已知小計冒充。
    assert result.estimated_total_twd is None
    assert result.unpriced_count == 2
    assert "待詢價" in result.disclaimer or "詢價" in result.disclaimer


def test_estimated_prices_are_marked_and_downgraded() -> None:
    service = FurnitureEstimateService(
        StubPriceProvider({"c1": {"price_twd": 7500, "price_is_estimated": True}})
    )

    result = service.estimate(_snapshot([_item("f1", "c1")]))

    line = result.lines[0]
    assert line.price_is_estimated is True
    # 推估價不是牌價，信心必須低於實際牌價。
    assert line.confidence == "medium"
    assert result.estimated_price_count == 1
    assert "推估價" in result.disclaimer


def test_catalog_outage_still_produces_the_line_items() -> None:
    service = FurnitureEstimateService(ExplodingPriceProvider())

    result = service.estimate(_snapshot([_item("f1", "c1"), _item("f2", "c2")]))

    assert len(result.lines) == 2
    assert all(line.status == "price_unavailable" for line in result.lines)
    assert result.estimated_total_twd is None
    assert result.catalog_provider.endswith("_unavailable")


def test_unavailable_provider_reports_no_prices() -> None:
    service = FurnitureEstimateService(UnavailableFurniturePriceProvider())

    result = service.estimate(_snapshot([_item("f1", "c1")]))

    assert result.priced_count == 0
    assert result.unpriced_count == 1


def test_prices_are_fetched_in_one_batch() -> None:
    provider = StubPriceProvider({})
    service = FurnitureEstimateService(provider)

    service.estimate(
        _snapshot([_item(f"f{index}", f"c{index}") for index in range(12)])
    )

    # 一次查完；逐項查會在大案子上打爆型錄連線。
    assert len(provider.calls) == 1
    assert len(provider.calls[0]) == 12


@pytest.mark.parametrize(
    "raw_price", [None, "", "not-a-number", -100, True]
)
def test_unusable_price_values_are_treated_as_missing(raw_price) -> None:
    service = FurnitureEstimateService(
        StubPriceProvider({"c1": {"price_twd": raw_price, "price_is_estimated": False}})
    )

    result = service.estimate(_snapshot([_item("f1", "c1")]))

    assert result.lines[0].status == "price_unavailable"
    assert result.lines[0].subtotal_twd is None


def test_disclaimer_separates_furniture_from_construction_cost() -> None:
    service = FurnitureEstimateService(
        StubPriceProvider({"c1": {"price_twd": 1000, "price_is_estimated": False}})
    )

    result = service.estimate(_snapshot([_item("f1", "c1")]))

    assert "工程施工費" in result.disclaimer


def test_json_provider_reads_the_shipped_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {"id": "a", "price_twd": 3200, "price_is_estimated": False},
                {"id": "b", "price_twd": 990, "price_is_estimated": True},
                {"id": "c"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    provider = JsonFurniturePriceProvider(catalog)

    prices = provider.prices_for(["a", "b", "c", "d"])

    assert prices["a"] == {"price_twd": 3200, "price_is_estimated": False}
    assert prices["b"]["price_is_estimated"] is True
    assert prices["c"]["price_twd"] is None
    assert "d" not in prices


def test_json_provider_survives_a_broken_catalog_file(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    assert JsonFurniturePriceProvider(broken).prices_for(["a"]) == {}
