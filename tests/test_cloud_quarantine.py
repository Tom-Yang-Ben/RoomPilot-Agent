from __future__ import annotations

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


def test_private_quarantine_payload_is_not_distributed():
    assert not QUARANTINE_PATH.exists()


def test_portable_fixture_exposes_no_remote_model_set():
    assert all(
        item.get("render_mode") == "procedural_fixture" and not item.get("model_url")
        for item in _furniture_payload_cache()
    )
