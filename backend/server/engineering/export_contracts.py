from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import ProjectSnapshot, ReportPayload, RiskResult


ENGINEERING_API_PATHS = {
    "/api/v1/engineering/health",
    "/api/v1/projects/{project_id}/revisions/{revision}/snapshot",
    "/api/v1/projects/{project_id}/revisions/{revision}/lock",
    "/api/v1/projects/{project_id}/engineering-packages",
    "/api/v1/jobs/{job_id}",
    "/api/v1/packages/{package_id}",
    "/api/v1/documents/{document_id}/download",
}


def _schema_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        prefix = "#/components/schemas/"
        if isinstance(reference, str) and reference.startswith(prefix):
            names.add(reference.removeprefix(prefix))
        for item in value.values():
            names.update(_schema_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_schema_names(item))
    return names


def _engineering_openapi() -> dict[str, Any]:
    from backend.server.main import app

    full = app.openapi()
    paths = {
        path: value
        for path, value in full.get("paths", {}).items()
        if path in ENGINEERING_API_PATHS
    }
    all_schemas = full.get("components", {}).get("schemas", {})
    needed = _schema_names(paths)
    pending = list(needed)
    while pending:
        name = pending.pop()
        for reference in _schema_names(all_schemas.get(name, {})) - needed:
            needed.add(reference)
            pending.append(reference)
    return {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "RoomPilot Designer-Locked Engineering API",
            "version": "1.0.0",
            "description": (
                "由目前 FastAPI route 與 Pydantic 模型輸出的工程文件 API；"
                "前端不得直連 LLM、Vector Index 或資料庫。"
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {
                name: all_schemas[name]
                for name in sorted(needed)
                if name in all_schemas
            }
        },
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_contracts(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "project_snapshot": output_dir / "project_snapshot.schema.json",
        "report_payload": output_dir / "report_payload.schema.json",
        "risk_results": output_dir / "risk_results.schema.json",
        # JSON is valid YAML 1.2, while keeping generation dependency-free.
        "openapi": output_dir / "engineering_openapi.yaml",
    }
    _write_json(outputs["project_snapshot"], ProjectSnapshot.model_json_schema())
    _write_json(outputs["report_payload"], ReportPayload.model_json_schema())
    _write_json(outputs["risk_results"], RiskResult.model_json_schema())
    _write_json(outputs["openapi"], _engineering_openapi())
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export RoomPilot engineering JSON Schema and OpenAPI contracts."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/contracts"),
    )
    args = parser.parse_args()
    for name, path in export_contracts(args.output_dir).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
