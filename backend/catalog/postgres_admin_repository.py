"""Transactional PostgreSQL administration for Kai's furniture catalog.

The public catalog stays read-only.  This module owns the write transaction,
reference validation, activation gate, optimistic concurrency check and audit
record used by the protected FastAPI adapter.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .postgres_repository import (
    _borrow_connection,
    _connection_pool,
    _dict_cursor,
    _setting,
    catalog_provider_mode,
)


_READY_UPLOAD_STATUSES = (
    "already_exists",
    "complete",
    "completed",
    "skipped_existing",
    "success",
    "uploaded",
)
_READY_VALIDATION_STATUSES = ("", "ready", "success", "valid")


class CatalogAdminError(RuntimeError):
    """Expected catalog administration failure safe to map to an API code."""

    def __init__(
        self,
        code: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.context = dict(context or {})


class CatalogAdminNotFound(CatalogAdminError):
    pass


class CatalogAdminConflict(CatalogAdminError):
    pass


class CatalogAdminReferenceError(CatalogAdminError):
    pass


class CatalogAdminActivationError(CatalogAdminError):
    pass


def catalog_admin_token(project_dir: Path) -> str:
    """Read the admin token from process environment or the ignored .env file."""
    return _setting(project_dir, "ROOMPILOT_CATALOG_ADMIN_TOKEN")


def catalog_admin_writes_enabled(project_dir: Path) -> bool:
    """Writes are deliberately disabled in JSON and implicit auto modes."""
    return catalog_provider_mode(project_dir) == "postgres"


@contextmanager
def _transaction(project_dir: Path) -> Iterator[Any]:
    pool = _connection_pool(project_dir)
    connection = pool.getconn()
    try:
        connection.autocommit = False
        yield connection
        connection.commit()
    except Exception:
        if not getattr(connection, "closed", True):
            connection.rollback()
        raise
    finally:
        pool.putconn(connection, close=bool(getattr(connection, "closed", False)))


def _json_adapter(value: Any) -> Any:
    try:
        from psycopg2.extras import Json
    except ImportError as exc:  # pragma: no cover - deployment extra
        raise RuntimeError("postgres_driver_unavailable") from exc
    return Json(value)


_ADMIN_RECORD_SQL = """
SELECT jsonb_build_object(
    'schema_version', 'catalog.admin.v1',
    'coordinate_unit', 'cm',
    'item_id', i.item_id,
    'category_code', c.category_code,
    'source', i.source,
    'source_group', i.source_group,
    'catalog', i.catalog,
    'kind', i.kind,
    'source_type', i.source_type,
    'name_en', i.name_en,
    'name_zh', i.name_zh,
    'primary_color', i.primary_color,
    'colors', i.colors,
    'primary_material', i.primary_material,
    'materials', i.materials,
    'width_cm', i.width_cm,
    'depth_cm', i.depth_cm,
    'height_cm', i.height_cm,
    'price_twd', i.price_twd,
    'price_is_estimated', i.price_is_estimated,
    'product_url', i.product_url,
    'is_active', i.is_active,
    'styles', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'style_code', s.style_code,
                'rank', fs.style_rank,
                'confidence', fs.confidence
            ) ORDER BY fs.style_rank
        )
        FROM roompilot.furniture_styles AS fs
        JOIN roompilot.styles AS s ON s.style_id = fs.style_id
        WHERE fs.item_id = i.item_id
    ), '[]'::jsonb),
    'room_codes', COALESCE((
        SELECT jsonb_agg(r.room_code ORDER BY r.room_code)
        FROM roompilot.furniture_rooms AS fr
        JOIN roompilot.rooms AS r ON r.room_id = fr.room_id
        WHERE fr.item_id = i.item_id
    ), '[]'::jsonb),
    'annotation', (
        SELECT jsonb_build_object(
            'annotation_hash', a.annotation_hash,
            'model_name', a.model_name,
            'model_version', a.model_version,
            'prompt_version', a.prompt_version,
            'object_type_zh', a.object_type_zh,
            'description', a.description,
            'role', a.role,
            'visual_weight', a.visual_weight,
            'height_zone', a.height_zone,
            'size_class', a.size_class,
            'pattern', a.pattern,
            'mood_tags', a.mood_tags,
            'shape_tags', a.shape_tags,
            'features', a.features,
            'search_keywords', a.search_keywords,
            'rag_text', a.rag_text,
            'confidence', a.confidence,
            'description_source', a.description_source,
            'raw_response', a.raw_response
        )
        FROM roompilot.furniture_vlm_annotations AS a
        WHERE a.item_id = i.item_id AND a.is_current
    ),
    'assets', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'asset_type', asset.asset_type,
                'view_role', asset.view_role,
                'delivery_url', asset.delivery_url,
                'upload_status', asset.upload_status,
                'validation_status', asset.validation_status
            ) ORDER BY asset.asset_type, asset.view_role NULLS FIRST
        )
        FROM roompilot.furniture_assets AS asset
        WHERE asset.item_id = i.item_id
    ), '[]'::jsonb),
    'raw_data', i.raw_data,
    'created_at', i.created_at,
    'updated_at', i.updated_at
) AS record
FROM roompilot.furniture_items AS i
LEFT JOIN roompilot.furniture_categories AS c
    ON c.category_id = i.category_id
WHERE i.item_id = %s
"""


def _select_record(cursor: Any, item_id: str) -> dict[str, Any] | None:
    cursor.execute(_ADMIN_RECORD_SQL, (item_id,))
    row = cursor.fetchone()
    return dict(row["record"]) if row else None


def _response_record(
    record: Mapping[str, Any], *, include_raw_data: bool
) -> dict[str, Any]:
    response = dict(record)
    if not include_raw_data:
        response.pop("raw_data", None)
        annotation = response.get("annotation")
        if isinstance(annotation, dict):
            annotation = dict(annotation)
            annotation.pop("raw_response", None)
            response["annotation"] = annotation
    return response


def get_admin_furniture(
    project_dir: Path,
    item_id: str,
    *,
    include_raw_data: bool = False,
) -> dict[str, Any] | None:
    """Fetch active or inactive furniture for a protected administration route."""
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            record = _select_record(cursor, item_id)
    return (
        _response_record(record, include_raw_data=include_raw_data)
        if record
        else None
    )


def _category_id(cursor: Any, category_code: str) -> int:
    cursor.execute(
        """
        SELECT category_id
        FROM roompilot.furniture_categories
        WHERE category_code = %s AND is_active
        """,
        (category_code,),
    )
    row = cursor.fetchone()
    if not row:
        raise CatalogAdminReferenceError(
            "catalog_category_unknown",
            context={"category_code": category_code},
        )
    return int(row["category_id"])


def _reference_ids(
    cursor: Any,
    *,
    table: str,
    id_column: str,
    code_column: str,
    codes: Sequence[str],
    error_code: str,
) -> list[int]:
    unique_codes = list(dict.fromkeys(codes))
    if not unique_codes:
        return []
    cursor.execute(
        f"SELECT {id_column}, {code_column} FROM {table} "
        f"WHERE {code_column} = ANY(%s::TEXT[]) AND is_active",
        (unique_codes,),
    )
    rows_by_code = {str(row[code_column]): int(row[id_column]) for row in cursor.fetchall()}
    missing = [code for code in unique_codes if code not in rows_by_code]
    if missing:
        raise CatalogAdminReferenceError(error_code, context={"unknown_codes": missing})
    return [rows_by_code[code] for code in unique_codes]


def _replace_styles(
    cursor: Any,
    item_id: str,
    assignments: Sequence[Mapping[str, Any]],
) -> None:
    if len(assignments) > 2:
        raise CatalogAdminReferenceError("catalog_style_limit_exceeded")
    codes = [str(assignment["style_code"]) for assignment in assignments]
    style_ids = _reference_ids(
        cursor,
        table="roompilot.styles",
        id_column="style_id",
        code_column="style_code",
        codes=codes,
        error_code="catalog_style_unknown",
    )
    cursor.execute(
        "DELETE FROM roompilot.furniture_styles WHERE item_id = %s",
        (item_id,),
    )
    for rank, (style_id, assignment) in enumerate(
        zip(style_ids, assignments, strict=True), start=1
    ):
        cursor.execute(
            """
            INSERT INTO roompilot.furniture_styles
                (item_id, style_id, style_rank, confidence)
            VALUES (%s, %s, %s, %s)
            """,
            (item_id, style_id, rank, assignment.get("confidence")),
        )


def _replace_rooms(cursor: Any, item_id: str, room_codes: Sequence[str]) -> None:
    room_ids = _reference_ids(
        cursor,
        table="roompilot.rooms",
        id_column="room_id",
        code_column="room_code",
        codes=room_codes,
        error_code="catalog_room_unknown",
    )
    cursor.execute(
        "DELETE FROM roompilot.furniture_rooms WHERE item_id = %s",
        (item_id,),
    )
    for room_id in room_ids:
        cursor.execute(
            "INSERT INTO roompilot.furniture_rooms (item_id, room_id) VALUES (%s, %s)",
            (item_id, room_id),
        )


_ANNOTATION_COLUMNS = (
    "model_name",
    "model_version",
    "prompt_version",
    "object_type_zh",
    "description",
    "role",
    "visual_weight",
    "height_zone",
    "size_class",
    "pattern",
    "mood_tags",
    "shape_tags",
    "features",
    "search_keywords",
    "rag_text",
    "confidence",
    "description_source",
)
_ANNOTATION_ARRAY_COLUMNS = {
    "mood_tags",
    "shape_tags",
    "features",
    "search_keywords",
    "rag_text",
}


def _replace_annotation(
    cursor: Any,
    item_id: str,
    annotation: Mapping[str, Any] | None,
) -> None:
    cursor.execute(
        """
        UPDATE roompilot.furniture_vlm_annotations
        SET is_current = FALSE
        WHERE item_id = %s AND is_current
        """,
        (item_id,),
    )
    if annotation is None:
        return

    normalized = {
        key: annotation.get(key, [] if key in _ANNOTATION_ARRAY_COLUMNS else None)
        for key in _ANNOTATION_COLUMNS
    }
    raw_response = dict(annotation.get("raw_response") or {})
    hash_payload = {**normalized, "raw_response": raw_response}
    annotation_hash = hashlib.sha256(
        json.dumps(
            hash_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    cursor.execute(
        f"""
        INSERT INTO roompilot.furniture_vlm_annotations (
            item_id, annotation_hash, {', '.join(_ANNOTATION_COLUMNS)},
            raw_response, is_current
        )
        VALUES (
            %s, %s, {', '.join(['%s'] * len(_ANNOTATION_COLUMNS))}, %s, TRUE
        )
        ON CONFLICT (item_id, annotation_hash) DO UPDATE SET
            {', '.join(f'{column} = EXCLUDED.{column}' for column in _ANNOTATION_COLUMNS)},
            raw_response = EXCLUDED.raw_response,
            is_current = TRUE
        """,
        (
            item_id,
            annotation_hash,
            *(normalized[column] for column in _ANNOTATION_COLUMNS),
            _json_adapter(raw_response),
        ),
    )


def _activation_gaps(cursor: Any, item_id: str) -> list[str]:
    cursor.execute(
        """
        SELECT
            i.kind = 'furniture' AS furniture_kind,
            i.name_en IS NOT NULL AND BTRIM(i.name_en) <> '' AS named,
            i.width_cm IS NOT NULL
                AND i.depth_cm IS NOT NULL
                AND i.height_cm IS NOT NULL AS dimensions,
            c.category_id IS NOT NULL AND c.is_active AS category,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_styles AS fs
                WHERE fs.item_id = i.item_id
            ) AS styles,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_rooms AS fr
                WHERE fr.item_id = i.item_id
            ) AS rooms,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_vlm_annotations AS annotation
                WHERE annotation.item_id = i.item_id AND annotation.is_current
            ) AS annotation,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_assets AS asset
                WHERE asset.item_id = i.item_id
                  AND asset.asset_type = 'glb'
                  AND asset.delivery_url ~* '^https?://'
                  AND LOWER(COALESCE(asset.upload_status, '')) = ANY(%s::TEXT[])
                  AND LOWER(COALESCE(asset.validation_status, 'ready')) = ANY(%s::TEXT[])
            ) AS glb,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_assets AS asset
                WHERE asset.item_id = i.item_id
                  AND asset.asset_type = 'image'
                  AND asset.view_role = 'front'
                  AND asset.delivery_url ~* '^https?://'
                  AND LOWER(COALESCE(asset.upload_status, '')) = ANY(%s::TEXT[])
                  AND LOWER(COALESCE(asset.validation_status, 'ready')) = ANY(%s::TEXT[])
            ) AS front_image,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_assets AS asset
                WHERE asset.item_id = i.item_id
                  AND asset.asset_type = 'image'
                  AND asset.view_role = 'side'
                  AND asset.delivery_url ~* '^https?://'
                  AND LOWER(COALESCE(asset.upload_status, '')) = ANY(%s::TEXT[])
                  AND LOWER(COALESCE(asset.validation_status, 'ready')) = ANY(%s::TEXT[])
            ) AS side_image,
            EXISTS (
                SELECT 1 FROM roompilot.furniture_assets AS asset
                WHERE asset.item_id = i.item_id
                  AND asset.asset_type = 'image'
                  AND asset.view_role = 'angle-45'
                  AND asset.delivery_url ~* '^https?://'
                  AND LOWER(COALESCE(asset.upload_status, '')) = ANY(%s::TEXT[])
                  AND LOWER(COALESCE(asset.validation_status, 'ready')) = ANY(%s::TEXT[])
            ) AS angle_45_image
        FROM roompilot.furniture_items AS i
        LEFT JOIN roompilot.furniture_categories AS c
            ON c.category_id = i.category_id
        WHERE i.item_id = %s
        """,
        (
            list(_READY_UPLOAD_STATUSES),
            list(_READY_VALIDATION_STATUSES),
            list(_READY_UPLOAD_STATUSES),
            list(_READY_VALIDATION_STATUSES),
            list(_READY_UPLOAD_STATUSES),
            list(_READY_VALIDATION_STATUSES),
            list(_READY_UPLOAD_STATUSES),
            list(_READY_VALIDATION_STATUSES),
            item_id,
        ),
    )
    row = cursor.fetchone()
    if not row:
        raise CatalogAdminNotFound("catalog_item_not_found")
    return [key for key, value in row.items() if not bool(value)]


def _lock_item(cursor: Any, item_id: str) -> datetime:
    cursor.execute(
        """
        SELECT updated_at
        FROM roompilot.furniture_items
        WHERE item_id = %s
        FOR UPDATE
        """,
        (item_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise CatalogAdminNotFound("catalog_item_not_found")
    return row["updated_at"]


def _as_utc(value: datetime | str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise CatalogAdminConflict("catalog_expected_updated_at_timezone_required")
    return parsed.astimezone(timezone.utc)


def _check_revision(current: datetime, expected: datetime | str | None) -> None:
    if expected is None:
        return
    if current.astimezone(timezone.utc) != _as_utc(expected):
        raise CatalogAdminConflict(
            "catalog_item_version_conflict",
            context={"current_updated_at": current.isoformat()},
        )


def _write_audit(
    cursor: Any,
    *,
    item_id: str,
    action: str,
    actor: str,
    changed_fields: Sequence[str],
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
) -> None:
    cursor.execute(
        """
        INSERT INTO roompilot.furniture_admin_audit (
            item_id, action, actor, changed_fields, before_data, after_data
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            item_id,
            action,
            actor,
            list(changed_fields),
            _json_adapter(dict(before)) if before is not None else None,
            _json_adapter(dict(after)),
        ),
    )


def create_furniture(
    project_dir: Path,
    payload: Mapping[str, Any],
    *,
    actor: str,
    include_raw_data: bool = False,
) -> dict[str, Any]:
    """Create one inactive furniture draft and all supplied metadata atomically."""
    data = dict(payload)
    item_id = str(data["item_id"])
    style_assignments = list(data.pop("styles", []))
    room_codes = list(data.pop("room_codes", []))
    annotation = data.pop("annotation", None)
    raw_data = dict(data.pop("raw_data", {}) or {})

    try:
        with _transaction(project_dir) as connection:
            with _dict_cursor(connection) as cursor:
                cursor.execute(
                    "SELECT 1 FROM roompilot.furniture_items WHERE item_id = %s",
                    (item_id,),
                )
                if cursor.fetchone():
                    raise CatalogAdminConflict("catalog_item_already_exists")
                category_id = _category_id(cursor, str(data["category_code"]))
                cursor.execute(
                    """
                    INSERT INTO roompilot.furniture_items (
                        item_id, category_id, source, source_group, catalog, kind,
                        source_type, name_en, name_zh, primary_color, colors,
                        primary_material, materials, width_cm, depth_cm, height_cm,
                        price_twd, price_is_estimated, product_url, is_active, raw_data
                    ) VALUES (
                        %s, %s, 'admin_api', %s, %s, 'furniture',
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, FALSE, %s
                    )
                    """,
                    (
                        item_id,
                        category_id,
                        data.get("source_group"),
                        data.get("catalog"),
                        data.get("source_type"),
                        data["name_en"],
                        data.get("name_zh"),
                        data.get("primary_color"),
                        data.get("colors", []),
                        data.get("primary_material"),
                        data.get("materials", []),
                        data.get("width_cm"),
                        data.get("depth_cm"),
                        data.get("height_cm"),
                        data.get("price_twd"),
                        data.get("price_is_estimated", False),
                        data.get("product_url"),
                        _json_adapter(raw_data),
                    ),
                )
                _replace_styles(cursor, item_id, style_assignments)
                _replace_rooms(cursor, item_id, room_codes)
                if annotation is not None:
                    _replace_annotation(cursor, item_id, annotation)
                record = _select_record(cursor, item_id)
                assert record is not None
                _write_audit(
                    cursor,
                    item_id=item_id,
                    action="create",
                    actor=actor,
                    changed_fields=sorted(payload.keys()),
                    before=None,
                    after=record,
                )
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise CatalogAdminConflict("catalog_item_already_exists") from exc
        raise
    return _response_record(record, include_raw_data=include_raw_data)


_CORE_PATCH_COLUMNS = {
    "source_group",
    "catalog",
    "source_type",
    "name_en",
    "name_zh",
    "primary_color",
    "colors",
    "primary_material",
    "materials",
    "width_cm",
    "depth_cm",
    "height_cm",
    "price_twd",
    "price_is_estimated",
    "product_url",
    "is_active",
}


def patch_furniture(
    project_dir: Path,
    item_id: str,
    payload: Mapping[str, Any],
    *,
    actor: str,
    include_raw_data: bool = False,
) -> dict[str, Any]:
    """Patch one item under row lock and optionally enforce activation readiness."""
    data = dict(payload)
    expected_updated_at = data.pop("expected_updated_at", None)
    changed_fields = sorted(data.keys())
    if not changed_fields:
        raise CatalogAdminReferenceError("catalog_patch_empty")

    with _transaction(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            current_updated_at = _lock_item(cursor, item_id)
            _check_revision(current_updated_at, expected_updated_at)
            before = _select_record(cursor, item_id)
            assert before is not None

            if "category_code" in data:
                category_id = _category_id(cursor, str(data.pop("category_code")))
                cursor.execute(
                    "UPDATE roompilot.furniture_items SET category_id = %s WHERE item_id = %s",
                    (category_id, item_id),
                )

            if "styles" in data:
                _replace_styles(cursor, item_id, list(data.pop("styles") or []))
            if "room_codes" in data:
                _replace_rooms(cursor, item_id, list(data.pop("room_codes") or []))
            if "annotation" in data:
                _replace_annotation(cursor, item_id, data.pop("annotation"))
            if "raw_data" in data:
                raw_patch = dict(data.pop("raw_data") or {})
                cursor.execute(
                    """
                    UPDATE roompilot.furniture_items
                    SET raw_data = raw_data || %s::jsonb
                    WHERE item_id = %s
                    """,
                    (_json_adapter(raw_patch), item_id),
                )

            core_updates = {
                key: value for key, value in data.items() if key in _CORE_PATCH_COLUMNS
            }
            if core_updates:
                assignments = ", ".join(f"{key} = %s" for key in core_updates)
                cursor.execute(
                    f"UPDATE roompilot.furniture_items SET {assignments} WHERE item_id = %s",
                    (*core_updates.values(), item_id),
                )

            if payload.get("is_active") is True:
                gaps = _activation_gaps(cursor, item_id)
                if gaps:
                    raise CatalogAdminActivationError(
                        "catalog_item_not_ready_for_activation",
                        context={"missing": gaps},
                    )

            cursor.execute(
                "UPDATE roompilot.furniture_items SET updated_at = NOW() WHERE item_id = %s",
                (item_id,),
            )
            after = _select_record(cursor, item_id)
            assert after is not None
            _write_audit(
                cursor,
                item_id=item_id,
                action="update",
                actor=actor,
                changed_fields=changed_fields,
                before=before,
                after=after,
            )
    return _response_record(after, include_raw_data=include_raw_data)


def soft_delete_furniture(
    project_dir: Path,
    item_id: str,
    *,
    actor: str,
    expected_updated_at: datetime | str | None = None,
    include_raw_data: bool = False,
) -> dict[str, Any]:
    """Deactivate an item without removing its metadata, assets or audit trail."""
    with _transaction(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            current_updated_at = _lock_item(cursor, item_id)
            _check_revision(current_updated_at, expected_updated_at)
            before = _select_record(cursor, item_id)
            assert before is not None
            cursor.execute(
                """
                UPDATE roompilot.furniture_items
                SET is_active = FALSE, updated_at = NOW()
                WHERE item_id = %s
                """,
                (item_id,),
            )
            after = _select_record(cursor, item_id)
            assert after is not None
            _write_audit(
                cursor,
                item_id=item_id,
                action="soft_delete",
                actor=actor,
                changed_fields=("is_active",),
                before=before,
                after=after,
            )
    return _response_record(after, include_raw_data=include_raw_data)
