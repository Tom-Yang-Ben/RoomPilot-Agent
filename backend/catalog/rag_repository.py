"""Kai-owned PostgreSQL adapter for Django's furniture RAG runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .postgres_repository import borrow_catalog_connection, catalog_dict_cursor


EMBEDDING_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class RagFilters:
    room_type: str | None = None
    categories: tuple[str, ...] | None = None
    price_min: int | None = None
    price_max: int | None = None
    max_width_cm: float | None = None
    max_height_cm: float | None = None
    role: str | None = None
    size_class: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "RagFilters":
        categories = value.get("categories")
        return cls(
            room_type=value.get("room_type"),
            categories=tuple(categories) if categories else None,
            price_min=value.get("price_min"),
            price_max=value.get("price_max"),
            max_width_cm=value.get("max_width_cm"),
            max_height_cm=value.get("max_height_cm"),
            role=value.get("role"),
            size_class=value.get("size_class"),
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "room_type": self.room_type,
            "categories": list(self.categories) if self.categories else None,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "max_width_cm": self.max_width_cm,
            "max_height_cm": self.max_height_cm,
            "role": self.role,
            "size_class": self.size_class,
        }


def embedding_status(project_dir: Path) -> dict[str, Any]:
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS current_embeddings,
                    MIN(embedding.embedding_dimension) AS embedding_dimension
                FROM roompilot.furniture_embeddings AS embedding
                INNER JOIN roompilot.furniture_embedding_source_current AS source
                    ON source.item_id = embedding.item_id
                   AND source.text_hash = embedding.text_hash
                WHERE embedding.embedding_model = %s
                """,
                (EMBEDDING_MODEL,),
            )
            row = cursor.fetchone()
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_proc AS procedure
                    JOIN pg_namespace AS namespace
                      ON namespace.oid = procedure.pronamespace
                    WHERE namespace.nspname = 'roompilot'
                      AND procedure.proname = 'search_furniture_embeddings_filtered'
                ) AS available
                """
            )
            function_row = cursor.fetchone()
    return {
        "provider": "postgresql_pgvector",
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": int(row["embedding_dimension"] or 0),
        "current_embeddings": int(row["current_embeddings"] or 0),
        "search_function_available": bool(function_row["available"]),
    }


def load_group_price_stats(
    project_dir: Path,
    groups: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            for group_id, specification in groups.items():
                categories = list(specification.get("categories") or [])
                if not categories:
                    continue
                cursor.execute(
                    """
                    SELECT
                        percentile_cont(0.33) WITHIN GROUP (ORDER BY price_value) AS p33,
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY price_value) AS median,
                        percentile_cont(0.67) WITHIN GROUP (ORDER BY price_value) AS p67
                    FROM (
                        SELECT NULLIF(item.raw_data->'chroma_metadata'->>'price_twd', '')::NUMERIC
                            AS price_value
                        FROM roompilot.furniture_items AS item
                        WHERE item.kind = 'furniture'
                          AND item.is_active
                          AND item.raw_data->'chroma_metadata'->>'category' = ANY(%s::TEXT[])
                    ) AS prices
                    WHERE price_value IS NOT NULL
                    """,
                    (categories,),
                )
                row = cursor.fetchone()
                if row and row["median"] is not None:
                    stats[group_id] = {
                        "p33": float(row["p33"]),
                        "median": float(row["median"]),
                        "p67": float(row["p67"]),
                    }
    return stats


def search_embedding_candidates(
    project_dir: Path,
    query_embedding: list[float],
    filters: RagFilters,
    *,
    match_count: int = 50,
    embedding_model: str = EMBEDDING_MODEL,
) -> list[dict[str, Any]]:
    vector_text = "[" + ",".join(format(float(value), ".9g") for value in query_embedding) + "]"
    with borrow_catalog_connection(project_dir) as connection:
        with catalog_dict_cursor(connection) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM roompilot.search_furniture_embeddings_filtered(
                    %s::VECTOR, %s, %s, %s, %s::TEXT[], %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    vector_text,
                    embedding_model,
                    match_count,
                    filters.room_type,
                    list(filters.categories) if filters.categories else None,
                    filters.price_min,
                    filters.price_max,
                    filters.max_width_cm,
                    filters.max_height_cm,
                    filters.role,
                    filters.size_class,
                ),
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]
