from __future__ import annotations

import pytest

from scripts.sql import import_furniture_embeddings_to_postgres as embedding_import
from scripts.sql import import_official_catalog_to_postgres as catalog_import


def test_official_catalog_has_complete_embedding_sources_but_no_vectors() -> None:
    payload, sources, items = embedding_import.load_catalog(
        embedding_import.DEFAULT_CATALOG
    )

    assert len(items) == 8_675
    assert len(sources) == 8_076
    assert payload["embedding_target"] == {
        "embedding_model": "BAAI/bge-m3",
        "embedding_dimension": 1024,
        "distance_metric": "cosine",
        "normalized": True,
    }
    assert embedding_import.load_records(None, items) == []


def test_restored_floor_lamps_are_active_embedding_sources() -> None:
    _payload, sources, items = embedding_import.load_catalog(
        embedding_import.DEFAULT_CATALOG
    )

    floor_lamps = [
        item for item in items if item.get("canonical_category_zh") == "落地燈"
    ]
    assert len(floor_lamps) == 118
    assert all(item.get("is_active", True) for item in floor_lamps)
    assert all(item.get("rag_indexable", True) for item in floor_lamps)
    assert {item["id"] for item in floor_lamps} <= set(sources)


def test_embedding_schema_keeps_dimension_open_and_filters_stale_text() -> None:
    schema = embedding_import.DEFAULT_SCHEMA.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_embeddings" in schema
    assert "embedding            VECTOR NOT NULL" in schema
    assert "VECTOR(1024)" not in schema
    assert "vector_dims(embedding) = embedding_dimension" in schema
    assert "furniture_embeddings_text_hash_sha256" in schema
    assert "CREATE OR REPLACE VIEW roompilot.furniture_embedding_source_current" in schema
    assert "CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings" in schema
    assert "CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings_filtered" in schema
    assert "item.raw_data -> 'chroma_metadata' AS chroma_metadata" in schema
    assert "current_source.text_hash = embedding.text_hash" in schema
    assert "using hnsw" not in schema.lower()


def test_filtered_embedding_search_applies_all_hard_filters_without_returning_vectors() -> None:
    schema = embedding_import.DEFAULT_SCHEMA.read_text(encoding="utf-8")
    function = schema.split(
        "CREATE OR REPLACE FUNCTION roompilot.search_furniture_embeddings_filtered", 1
    )[1]

    for parameter in (
        "query_embedding VECTOR",
        "room_type VARCHAR",
        "category_values TEXT[]",
        "price_min INTEGER",
        "price_max INTEGER",
        "max_width_cm NUMERIC",
        "max_height_cm NUMERIC",
        "item_role VARCHAR",
        "item_size_class VARCHAR",
    ):
        assert parameter in function
    assert "current_source.chroma_metadata ->> 'category' = ANY(category_values)" in function
    assert "('room_' || room_type)" in function
    assert "current_source.text_hash = embedding.text_hash" in function
    assert "embedding.embedding_model = query_model" in function
    assert "vector_dims(embedding.embedding) = vector_dims(query_embedding)" in function
    assert "embedding.embedding <=> query_embedding" in function
    returns = function.split("RETURNS TABLE", 1)[1].split("LANGUAGE sql", 1)[0]
    assert "embedding VECTOR" not in returns


def test_embedding_rows_validate_hash_dimension_and_normalization() -> None:
    text = "測試家具｜現代風格｜木材"
    source = embedding_import.EmbeddingSource(
        item_id="chair-1",
        embedded_text=text,
        text_hash=embedding_import.sha256_text(text),
    )
    sources = {source.item_id: source}
    target = {
        "embedding_model": "test/model",
        "embedding_dimension": 2,
        "normalized": True,
    }

    rows = embedding_import.prepare_embedding_rows(
        [{"item_id": source.item_id, "embedding": [1, 0]}], sources, target
    )
    assert rows == [
        embedding_import.EmbeddingRow(
            item_id=source.item_id,
            embedding_model="test/model",
            embedding_dimension=2,
            embedded_text=text,
            text_hash=source.text_hash,
            vector=(1.0, 0.0),
        )
    ]

    with pytest.raises(ValueError, match="向量維度不符合"):
        embedding_import.prepare_embedding_rows(
            [{"item_id": source.item_id, "embedding": [1, 0, 0]}],
            sources,
            target,
        )
    with pytest.raises(ValueError, match="未正規化"):
        embedding_import.prepare_embedding_rows(
            [{"item_id": source.item_id, "embedding": [2, 0]}], sources, target
        )
    with pytest.raises(ValueError, match="過期或非官方"):
        embedding_import.prepare_embedding_rows(
            [
                {
                    "item_id": source.item_id,
                    "embedded_text": "舊文字",
                    "embedding": [1, 0],
                }
            ],
            sources,
            target,
        )


def test_catalog_reset_removes_embedding_dependencies_before_catalog_tables() -> None:
    reset_sql = catalog_import.RESET_CATALOG_SQL

    source_view = "DROP VIEW IF EXISTS roompilot.furniture_embedding_source_current"
    search_function = "DROP FUNCTION IF EXISTS roompilot.search_furniture_embeddings"
    filtered_function = (
        "DROP FUNCTION IF EXISTS roompilot.search_furniture_embeddings_filtered"
    )
    embedding_table = "DROP TABLE IF EXISTS roompilot.furniture_embeddings"
    furniture_table = "DROP TABLE IF EXISTS roompilot.furniture_items"
    assert source_view in reset_sql
    assert search_function in reset_sql
    assert filtered_function in reset_sql
    assert reset_sql.index(filtered_function) < reset_sql.index(source_view)
    assert reset_sql.index(search_function) < reset_sql.index(source_view)
    assert reset_sql.index(source_view) < reset_sql.index(embedding_table)
    assert reset_sql.index(embedding_table) < reset_sql.index(furniture_table)
