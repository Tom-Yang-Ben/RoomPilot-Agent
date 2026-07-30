"""以具來源的單價區間產生概念設計工程概算。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..catalog.runtime_catalog_repository import load_runtime_cost_catalog


DISCLAIMER_ZH = "網路公開行情概算；施工前須現場丈量並取得正式報價。"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "data" / "taiwan_renovation_price_seed.json"
PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_default_cost_catalog() -> dict[str, Any]:
    """由 Phase 4 provider 讀取具來源的台灣裝修行情。"""
    return load_runtime_cost_catalog(PROJECT_DIR, DEFAULT_CATALOG_PATH)


def _validate_catalog(catalog: Mapping[str, Any]) -> None:
    sources = {str(item.get("id")): item for item in catalog.get("sources", [])}
    for source in sources.values():
        if not source.get("url") or not source.get("retrieved_on"):
            raise ValueError("cost_source_provenance_required")
    for rate in catalog.get("rates", []):
        required = (rate.get("work_code"), rate.get("unit"), rate.get("range_twd"), rate.get("source_ids"))
        if not all(required) or "inclusions" not in rate or "exclusions" not in rate:
            raise ValueError("cost_rate_contract_invalid")
        if any(str(source_id) not in sources for source_id in rate["source_ids"]):
            raise ValueError("cost_rate_source_missing")


def estimate_project_cost(
    work_items: Iterable[Mapping[str, Any]],
    *,
    catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """計算低／基準／高區間；缺少數量證據或費率時保留待詢價。"""
    _validate_catalog(catalog)
    rates = {str(rate["work_code"]): rate for rate in catalog.get("rates", [])}
    sources = {str(source["id"]): source for source in catalog.get("sources", [])}
    estimated: list[dict[str, Any]] = []
    needs_quote: list[dict[str, Any]] = []
    raw_totals = {"low": 0.0, "base": 0.0, "high": 0.0}

    for raw_item in work_items:
        item = dict(raw_item)
        evidence = list(item.get("quantity_evidence") or [])
        if not evidence:
            raise ValueError("cost_quantity_evidence_required")
        quantity = item.get("quantity") or {}
        try:
            value = float(quantity["value"])
            unit = str(quantity["unit"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("cost_quantity_invalid") from exc
        if value <= 0:
            raise ValueError("cost_quantity_invalid")
        rate = rates.get(str(item.get("work_code")))
        if rate is None or str(rate.get("unit")) != unit:
            needs_quote.append(
                {
                    "id": item.get("id"),
                    "work_code": item.get("work_code"),
                    "description": item.get("description"),
                    "reason": "rate_missing" if rate is None else "unit_mismatch",
                }
            )
            continue

        estimate = {
            key: round(value * float(rate["range_twd"][key]))
            for key in ("low", "base", "high")
        }
        for key in raw_totals:
            raw_totals[key] += value * float(rate["range_twd"][key])
        source_ids = [str(source_id) for source_id in rate["source_ids"]]
        estimated.append(
            {
                "id": item.get("id"),
                "work_code": item.get("work_code"),
                "description": item.get("description"),
                "quantity": {"value": value, "unit": unit},
                "quantity_evidence": evidence,
                "rate_twd": deepcopy(rate["range_twd"]),
                "estimate_twd": estimate,
                "source_ids": source_ids,
                "sources": [deepcopy(sources[source_id]) for source_id in source_ids],
                "price_date": rate.get("valid_as_of"),
                "inclusions": deepcopy(rate["inclusions"]),
                "exclusions": deepcopy(rate["exclusions"]),
                "assumptions": deepcopy(item.get("assumptions") or []),
                "status": "concept_estimate",
            }
        )

    return {
        "schema_version": "1.0",
        "catalog_version": catalog.get("catalog_version"),
        "currency": catalog.get("currency", "TWD"),
        "region": catalog.get("region", "台灣"),
        "items": estimated,
        "needs_quote": needs_quote,
        "totals_twd": {key: round(value) for key, value in raw_totals.items()},
        "status": "concept_estimate",
        "disclaimer_zh": DISCLAIMER_ZH,
    }
