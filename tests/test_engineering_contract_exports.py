from __future__ import annotations

import json
from pathlib import Path

from backend.server.engineering.export_contracts import (
    ENGINEERING_API_PATHS,
    export_contracts,
)


CONTRACT_DIR = Path("docs/contracts")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_exported_engineering_contracts_are_current(tmp_path: Path) -> None:
    generated = export_contracts(tmp_path)
    for path in generated.values():
        assert _json(path) == _json(CONTRACT_DIR / path.name)


def test_exported_contracts_follow_roompilot_cm_and_api_boundaries() -> None:
    snapshot = _json(CONTRACT_DIR / "project_snapshot.schema.json")
    geometry = snapshot["$defs"]["RoomGeometry"]["properties"]
    assert {"length_cm", "width_cm", "height_cm", "polygon_cm"} <= set(geometry)
    assert not {"length_m", "width_m", "height_m"} & set(geometry)
    assert snapshot["properties"]["coordinate_unit"]["const"] == "cm"

    report = _json(CONTRACT_DIR / "report_payload.schema.json")
    assert {"demo_mode", "demo_disclaimer", "exclusions"} <= set(
        report["properties"]
    )
    risk = _json(CONTRACT_DIR / "risk_results.schema.json")
    assert "engine_adapter" in risk["required"]

    openapi = _json(CONTRACT_DIR / "engineering_openapi.yaml")
    assert set(openapi["paths"]) == ENGINEERING_API_PATHS
    serialized = json.dumps(openapi).lower()
    assert "neo4j" not in serialized
    assert "openai.com" not in serialized
