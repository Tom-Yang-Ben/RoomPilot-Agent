from pathlib import Path

import pytest

from scripts.sql.sync_catalog_embeddings_to_postgres import (
    catalog_visibility,
    vector_literal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAG_SCHEMA = PROJECT_ROOT / "docker_postgresql" / "init" / "002_roompilot_rag.sql"
DOCKER_COMPOSE = PROJECT_ROOT / "docker_postgresql" / "docker-compose.yml"
VISIBILITY_MIGRATION = (
    PROJECT_ROOT / "scripts" / "sql" / "migrate_catalog_visibility.py"
)


def test_public_rag_schema_is_generic_and_data_free() -> None:
    sql = RAG_SCHEMA.read_text(encoding="utf-8").casefold()

    assert "create extension if not exists vector" in sql
    assert "create extension if not exists pgcrypto" in sql
    assert "create table if not exists roompilot.furniture_embeddings" in sql
    assert "create or replace view roompilot.furniture_embedding_source_current" in sql
    assert "create or replace function roompilot.search_furniture_embeddings_filtered" in sql
    assert "roompilot.furniture_catalog_current" in sql
    assert "roompilot.furniture_items" not in sql
    assert "8,076" not in sql
    assert "8,675" not in sql
    assert "insert into roompilot.furniture_catalog" not in sql


def test_full_profile_database_mounts_rag_schema_after_catalog_schema() -> None:
    compose = DOCKER_COMPOSE.read_text(encoding="utf-8")
    catalog_position = compose.index("001_roompilot.sql")
    rag_position = compose.index("002_roompilot_rag.sql")

    assert catalog_position < rag_position


def test_embedding_vector_literal_validates_shape_and_finite_values() -> None:
    assert vector_literal([1, 0.5, -0.25], 3) == "[1,0.5,-0.25]"

    with pytest.raises(ValueError, match="dimension mismatch"):
        vector_literal([1, 2], 3)
    with pytest.raises(ValueError, match="NaN or Infinity"):
        vector_literal([1, float("nan"), 3], 3)


def test_embedding_sync_visibility_defaults_public_and_allows_private(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DB_PASSWORD=example\n", encoding="utf-8")
    assert catalog_visibility(env_path) == "public"

    env_path.write_text(
        "DB_PASSWORD=example\nROOMPILOT_CATALOG_VISIBILITY=private\n",
        encoding="utf-8",
    )
    assert catalog_visibility(env_path) == "private"
    assert catalog_visibility(env_path, "public") == "public"


def test_catalog_visibility_migration_is_reversible_and_data_preserving() -> None:
    source = VISIBILITY_MIGRATION.read_text(encoding="utf-8")

    assert "catalog_visibility_migration_backup" in source
    assert "--rollback" in source
    assert "--dry-run" in source
    assert "catalog_license_migration_backup_%" in source
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE" not in source.upper()
