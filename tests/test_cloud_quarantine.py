from __future__ import annotations

import json
from pathlib import Path

from backend.server.main import _furniture_payload_cache


ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_PATH = (
    ROOT
    / "backend"
    / "catalog"
    / "data"
    / "quarantine"
    / "unmatched_cloud_furniture"
    / "unmatched_catalog_items.json"
)


def test_unmatched_cloud_furniture_is_packaged_for_kai():
    payload = json.loads(QUARANTINE_PATH.read_text(encoding="utf-8"))

    assert payload["web_policy"] == "excluded_until_verified"
    assert payload["count"] == 1514
    assert len(payload["items"]) == 1514
    assert all(
        item["quarantine_reason"] == "no_verified_cloudfront_match"
        for item in payload["items"]
    )


def test_quarantined_furniture_is_not_in_the_web_model_set():
    payload = json.loads(QUARANTINE_PATH.read_text(encoding="utf-8"))
    quarantined_ids = {item["furniture_id"] for item in payload["items"]}
    web_model_ids = {
        item["furniture_id"]
        for item in _furniture_payload_cache()
        if item["has_model"] and item["model_url"]
    }

    assert quarantined_ids.isdisjoint(web_model_ids)
