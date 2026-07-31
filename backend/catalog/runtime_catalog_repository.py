"""Phase 4 SQL runtime catalogs for styles, surfaces, costs, and quarantine.

Versioned JSON remains the import/review source.  In strict PostgreSQL mode,
FastAPI reads these datasets only through this repository and never silently
falls back to scanning JSON files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from .postgres_repository import (
    borrow_catalog_connection,
    catalog_dict_cursor,
    catalog_provider_mode,
)


T = TypeVar("T")


class RuntimeCatalogUnavailable(RuntimeError):
    """Raised when a strict Phase 4 PostgreSQL catalog cannot be read."""

    def __init__(self, catalog_key: str, reason: Exception | str):
        self.catalog_key = catalog_key
        self.reason = reason
        super().__init__(f"{catalog_key}: {reason}")


def _env_file_value(project_dir: Path, name: str) -> str:
    path = project_dir / ".env"
    if not path.is_file():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def runtime_catalog_provider_mode(project_dir: Path) -> str:
    """Return strict postgres by default or explicit offline json."""
    value = os.getenv(
        "ROOMPILOT_RUNTIME_CATALOG_PROVIDER",
        _env_file_value(project_dir, "ROOMPILOT_RUNTIME_CATALOG_PROVIDER"),
    ).strip()
    if not value:
        return catalog_provider_mode(project_dir)
    lowered = value.casefold()
    if lowered in {"postgres", "postgresql", "sql", "database"}:
        return "postgres"
    if lowered in {"json", "local", "fallback"}:
        return "json"
    return "postgres"


def _json_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _provider_load(
    project_dir: Path,
    catalog_key: str,
    postgres_loader: Callable[[], T],
    json_loader: Callable[[], T],
) -> T:
    mode = runtime_catalog_provider_mode(project_dir)
    if mode == "json":
        return json_loader()
    try:
        return postgres_loader()
    except Exception as exc:
        if isinstance(exc, RuntimeCatalogUnavailable):
            raise
        raise RuntimeCatalogUnavailable(catalog_key, exc) from exc


def _metadata(cursor: Any, catalog_key: str) -> dict[str, Any]:
    cursor.execute(
        "SELECT metadata FROM roompilot.runtime_catalog_imports WHERE catalog_key = %s",
        (catalog_key,),
    )
    row = cursor.fetchone()
    if not row:
        raise RuntimeError(f"runtime_catalog_not_imported:{catalog_key}")
    payload = row["metadata"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return dict(payload or {})


def _postgres_style_cards(project_dir: Path) -> list[dict[str, Any]]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            _metadata(cursor, "style_cards")
            cursor.execute(
                """
                SELECT style_payload, card_payload
                FROM roompilot.style_cards_current
                ORDER BY style_order, card_order
                """
            )
            rows = cursor.fetchall()
    if not rows:
        raise RuntimeError("runtime_style_cards_empty")
    styles: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        style_payload = dict(row["style_payload"] or {})
        card_payload = dict(row["card_payload"] or {})
        style_id = str(style_payload["style_id"])
        style = by_id.get(style_id)
        if style is None:
            style = {**style_payload, "cards": []}
            by_id[style_id] = style
            styles.append(style)
        image_file = str(card_payload.get("image_file") or "").replace("\\", "/")
        style["cards"].append(
            {**card_payload, "image_url": f"/static/style_cards/{image_file}"}
        )
    return styles


def load_runtime_style_cards(project_dir: Path, source_path: Path) -> list[dict[str, Any]]:
    def load_json() -> list[dict[str, Any]]:
        payload = _json_payload(source_path)
        styles = payload.get("styles") or []
        result: list[dict[str, Any]] = []
        for style in styles:
            cards = []
            for card in style.get("cards") or []:
                image_file = str(card.get("image_file") or "").replace("\\", "/")
                cards.append({**card, "image_url": f"/static/style_cards/{image_file}"})
            result.append({**style, "cards": cards})
        return result

    return _provider_load(
        project_dir,
        "style_cards",
        lambda: _postgres_style_cards(project_dir),
        load_json,
    )


def _postgres_design_styles(project_dir: Path) -> list[dict[str, Any]]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            _metadata(cursor, "design_style_profiles")
            cursor.execute(
                """
                SELECT payload
                FROM roompilot.design_style_profiles_current
                ORDER BY style_order
                """
            )
            styles = [dict(row["payload"] or {}) for row in cursor.fetchall()]
    if not styles:
        raise RuntimeError("runtime_design_style_profiles_empty")
    return styles


def load_runtime_design_styles(project_dir: Path, source_path: Path) -> list[dict[str, Any]]:
    return _provider_load(
        project_dir,
        "design_style_profiles",
        lambda: _postgres_design_styles(project_dir),
        lambda: list(_json_payload(source_path).get("styles") or []),
    )


def _postgres_surface_catalog(project_dir: Path) -> dict[str, Any]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            payload = _metadata(cursor, "surface_materials")
            cursor.execute(
                "SELECT payload FROM roompilot.surface_materials_current ORDER BY surface_id"
            )
            surfaces = [dict(row["payload"] or {}) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT style_id, payload
                FROM roompilot.style_surface_profiles
                WHERE is_active
                ORDER BY style_id
                """
            )
            profiles = {
                str(row["style_id"]): dict(row["payload"] or {})
                for row in cursor.fetchall()
            }
    if not surfaces:
        raise RuntimeError("runtime_surface_materials_empty")
    return {**payload, "surfaces": surfaces, "style_surface_profiles": profiles}


def load_runtime_surface_catalog(project_dir: Path, source_path: Path) -> dict[str, Any]:
    return _provider_load(
        project_dir,
        "surface_materials",
        lambda: _postgres_surface_catalog(project_dir),
        lambda: _json_payload(source_path),
    )


def _postgres_cost_catalog(project_dir: Path) -> dict[str, Any]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            payload = _metadata(cursor, "renovation_costs")
            cursor.execute(
                """
                SELECT payload
                FROM roompilot.renovation_cost_rates
                WHERE is_active
                ORDER BY work_code
                """
            )
            rates = [dict(row["payload"] or {}) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT payload
                FROM roompilot.renovation_cost_sources
                WHERE is_active
                ORDER BY source_id
                """
            )
            sources = [dict(row["payload"] or {}) for row in cursor.fetchall()]
    if not rates or not sources:
        raise RuntimeError("runtime_renovation_costs_empty")
    return {**payload, "rates": rates, "sources": sources}


def load_runtime_cost_catalog(project_dir: Path, source_path: Path) -> dict[str, Any]:
    return _provider_load(
        project_dir,
        "renovation_costs",
        lambda: _postgres_cost_catalog(project_dir),
        lambda: _json_payload(source_path),
    )


def _postgres_quarantine_index(project_dir: Path, source_kind: str) -> dict[str, Any]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            payload = _metadata(cursor, source_kind)
            cursor.execute(
                """
                SELECT raw_payload
                FROM roompilot.external_import_quarantine
                WHERE source_kind = %s AND is_current
                ORDER BY record_id
                """,
                (source_kind,),
            )
            items = [dict(row["raw_payload"] or {}) for row in cursor.fetchall()]
    return {**payload, "items": items}


def load_runtime_external_import_index(
    project_dir: Path,
    source_path: Path,
) -> dict[str, Any]:
    return _provider_load(
        project_dir,
        "external_import",
        lambda: _postgres_quarantine_index(project_dir, "external_import"),
        lambda: _json_payload(source_path),
    )


def get_runtime_quarantine_record(
    project_dir: Path,
    source_kind: str,
    record_id: str,
    *,
    source_path: Path | None = None,
) -> dict[str, Any] | None:
    def load_postgres() -> dict[str, Any] | None:
        with borrow_catalog_connection(project_dir) as connection:
            with catalog_dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT raw_payload
                    FROM roompilot.external_import_quarantine
                    WHERE source_kind = %s AND record_id = %s AND is_current
                    """,
                    (source_kind, record_id),
                )
                row = cursor.fetchone()
        return dict(row["raw_payload"] or {}) if row else None

    def load_json() -> dict[str, Any] | None:
        if source_path is None:
            return None
        payload = _json_payload(source_path)
        return next(
            (
                dict(item)
                for item in payload.get("items") or []
                if str(item.get("furniture_id")) == record_id
            ),
            None,
        )

    return _provider_load(project_dir, source_kind, load_postgres, load_json)


def search_runtime_rag_documents(
    project_dir: Path,
    query: str,
    *,
    document_types: tuple[str, ...] = (),
    limit: int = 20,
) -> tuple[dict[str, Any], ...]:
    """Search the formal Phase 4 RAG evidence view; quarantine is not in it."""
    term = query.strip()
    if not term:
        raise ValueError("runtime_rag_query_required")
    allowed_types = {"style_card", "surface_material", "renovation_cost"}
    if set(document_types) - allowed_types:
        raise ValueError("runtime_rag_document_type_invalid")
    safe_limit = max(1, min(int(limit), 100))
    predicates = [
        "(POSITION(LOWER(%s) IN LOWER(content)) > 0 OR similarity(content, %s) >= 0.08)"
    ]
    params: list[Any] = [term, term]
    if document_types:
        predicates.append("document_type = ANY(%s::TEXT[])")
        params.append(list(document_types))
    params.extend([term, term, safe_limit])
    sql = f"""
        SELECT document_id, document_type, title, content, metadata
        FROM roompilot.runtime_catalog_rag_documents
        WHERE {' AND '.join(predicates)}
        ORDER BY
            CASE WHEN POSITION(LOWER(%s) IN LOWER(content)) > 0 THEN 0 ELSE 1 END,
            similarity(content, %s) DESC,
            document_id
        LIMIT %s
    """
    try:
        with borrow_catalog_connection(project_dir) as connection:
            with catalog_dict_cursor(connection) as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeCatalogUnavailable("runtime_rag_documents", exc) from exc
    return tuple(
        {
            **dict(row),
            "metadata": dict(row.get("metadata") or {}),
        }
        for row in rows
    )


def runtime_catalog_status(project_dir: Path) -> dict[str, Any]:
    """Return SQL import counts without exposing any quarantined payload."""
    mode = runtime_catalog_provider_mode(project_dir)
    if mode == "json":
        return {
            "provider": "json_offline",
            "available": True,
            "ready": True,
            "strict": False,
            "source_of_truth": "versioned_files",
        }
    try:
        with borrow_catalog_connection(project_dir) as connection:
            with catalog_dict_cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM roompilot.style_cards_current) AS style_card_count,
                        (SELECT COUNT(*) FROM roompilot.design_style_profiles_current)
                            AS design_style_count,
                        (SELECT COUNT(*) FROM roompilot.surface_materials_current) AS surface_count,
                        (SELECT COUNT(*) FROM roompilot.surface_materials_current
                            WHERE 'wall' = ANY(usage)) AS wall_surface_count,
                        (SELECT COUNT(*) FROM roompilot.surface_materials_current
                            WHERE 'floor' = ANY(usage)) AS floor_surface_count,
                        (SELECT COUNT(*) FROM roompilot.renovation_cost_catalog_current) AS cost_rate_count,
                        (SELECT COUNT(*) FROM roompilot.external_import_quarantine WHERE is_current)
                            AS quarantine_count,
                        (SELECT COUNT(*) FROM roompilot.runtime_catalog_rag_documents) AS rag_count
                    """
                )
                row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT catalog_key, schema_version, catalog_version,
                           source_path, LEFT(source_sha256, 12) AS source_sha256,
                           record_count, imported_at
                    FROM roompilot.runtime_catalog_imports
                    ORDER BY catalog_key
                    """
                )
                imports = [
                    {
                        **dict(import_row),
                        "imported_at": import_row["imported_at"].isoformat(),
                    }
                    for import_row in cursor.fetchall()
                ]
        return {
            "provider": "kai_postgresql",
            "available": True,
            "ready": True,
            "strict": mode == "postgres",
            "source_of_truth": "postgresql",
            "imports": imports,
            **{key: int(value) for key, value in dict(row).items()},
        }
    except Exception as exc:
        return {
            "provider": "kai_postgresql",
            "available": False,
            "ready": False,
            "strict": mode == "postgres",
            "source_of_truth": "postgresql",
            "reason": type(exc).__name__,
        }
