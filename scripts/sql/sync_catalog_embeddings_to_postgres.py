#!/usr/bin/env python3
"""Safely generate and UPSERT RAG vectors for the active PostgreSQL catalog.

The script never deletes vectors or catalog rows. It derives pending work from
``roompilot.furniture_embedding_source_current`` and writes only vectors whose
model/text hash is not current. Model weights must already be present in the
configured local cache; this operational script never silently downloads them.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = PROJECT_ROOT / ".env"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "docker_postgresql" / "init" / "002_roompilot_rag.sql"
)
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DIMENSION = 1024


@dataclass(frozen=True)
class EmbeddingSource:
    item_id: str
    annotation_id: int | None
    embedded_text: str
    text_hash: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="同步 full-profile catalog 的 BGE-M3 PostgreSQL/pgvector 向量。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dimension", type=int, default=DEFAULT_DIMENSION)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--visibility",
        choices=("public", "private"),
        help="Override ROOMPILOT_CATALOG_VISIBILITY for this sync only.",
    )
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="先套用通用、data-free RAG schema；僅供目前公開 generic catalog schema。",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _env_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"environment file does not exist: {path}")
    try:
        from dotenv import dotenv_values
    except ImportError as exc:  # pragma: no cover - postgres extra owns this
        raise RuntimeError("install the postgres extra before syncing embeddings") from exc
    return {key: str(value or "") for key, value in dotenv_values(path).items()}


def db_config(path: Path) -> dict[str, Any]:
    values = _env_values(path)
    return {
        "host": values.get("DB_HOST", "127.0.0.1"),
        "port": int(values.get("DB_PORT", "5432")),
        "dbname": values.get("DB_NAME", "roompilot_db"),
        "user": values.get("DB_USER", "roompilot"),
        "password": values.get("DB_PASSWORD", ""),
        "sslmode": values.get("DB_SSLMODE", "disable"),
        "connect_timeout": int(values.get("DB_CONNECT_TIMEOUT", "10")),
        "application_name": "roompilot_embedding_sync",
    }


def catalog_visibility(env_path: Path, override: str | None = None) -> str:
    value = (override or _env_values(env_path).get(
        "ROOMPILOT_CATALOG_VISIBILITY", "public"
    )).strip().casefold()
    if value not in {"public", "private"}:
        raise ValueError("catalog visibility must be public or private")
    return value


def connect_db(env_path: Path, visibility: str):
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - postgres extra owns this
        raise RuntimeError("install the postgres extra before syncing embeddings") from exc
    connection = psycopg2.connect(**db_config(env_path))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('roompilot.catalog_visibility', %s, false)",
            (visibility,),
        )
    return connection


def apply_schema(connection: Any, schema_path: Path) -> None:
    if not schema_path.is_file():
        raise FileNotFoundError(f"schema does not exist: {schema_path}")
    with connection.cursor() as cursor:
        cursor.execute(schema_path.read_text(encoding="utf-8"))


def embedding_status(cursor: Any, model: str) -> dict[str, int]:
    cursor.execute("SELECT COUNT(*) FROM roompilot.furniture_embedding_source_current")
    source_count = int(cursor.fetchone()[0])
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM roompilot.furniture_embeddings AS embedding
        INNER JOIN roompilot.furniture_embedding_source_current AS source
          ON source.item_id = embedding.item_id
         AND source.text_hash = embedding.text_hash
        WHERE embedding.embedding_model = %s
        """,
        (model,),
    )
    current_count = int(cursor.fetchone()[0])
    return {
        "source_count": source_count,
        "current_count": current_count,
        "pending_count": max(0, source_count - current_count),
    }


def load_pending_sources(
    cursor: Any,
    model: str,
    *,
    limit: int | None = None,
) -> list[EmbeddingSource]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    sql = """
        SELECT source.item_id, source.annotation_id, source.embedded_text, source.text_hash
        FROM roompilot.furniture_embedding_source_current AS source
        LEFT JOIN roompilot.furniture_embeddings AS embedding
          ON embedding.item_id = source.item_id
         AND embedding.embedding_model = %s
         AND embedding.text_hash = source.text_hash
        WHERE embedding.embedding_id IS NULL
        ORDER BY source.item_id
    """
    parameters: list[Any] = [model]
    if limit is not None:
        sql += " LIMIT %s"
        parameters.append(limit)
    cursor.execute(sql, tuple(parameters))
    return [
        EmbeddingSource(
            item_id=str(row[0]),
            annotation_id=int(row[1]) if row[1] is not None else None,
            embedded_text=str(row[2]),
            text_hash=str(row[3]).lower(),
        )
        for row in cursor.fetchall()
    ]


def vector_literal(values: Iterable[float], expected_dimension: int) -> str:
    vector = tuple(float(value) for value in values)
    if len(vector) != expected_dimension:
        raise ValueError(
            f"embedding dimension mismatch: {len(vector)} != {expected_dimension}"
        )
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("embedding contains NaN or Infinity")
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"


def _resolve_device(requested: str, torch: Any) -> str:
    if requested not in {"auto", "cpu", "cuda", "mps"}:
        raise ValueError(f"unsupported RAG model device: {requested}")
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(getattr(torch, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def load_embedder(env_path: Path, model: str):
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - rag extra owns this
        raise RuntimeError("install the rag extra before syncing embeddings") from exc

    values = _env_values(env_path)
    requested_device = values.get("ROOMPILOT_RAG_DEVICE", "auto").casefold()
    device = _resolve_device(requested_device, torch)
    cache_value = values.get("ROOMPILOT_RAG_MODEL_CACHE", "").strip()
    cache_dir = (
        Path(cache_value).expanduser()
        if cache_value
        else Path.home() / ".cache" / "huggingface"
    )
    hub_dir = cache_dir / "hub"
    cache_folder = hub_dir if hub_dir.is_dir() else cache_dir
    embedder = SentenceTransformer(
        model,
        device=device,
        cache_folder=str(cache_folder),
        local_files_only=True,
    )
    embedder.max_seq_length = 512
    return embedder, device


def upsert_sources(
    connection: Any,
    sources: list[EmbeddingSource],
    *,
    model: str,
    dimension: int,
    batch_size: int,
    env_path: Path,
) -> tuple[int, str]:
    if batch_size < 1:
        raise ValueError("batch-size must be at least 1")
    try:
        from psycopg2.extras import execute_values
    except ImportError as exc:  # pragma: no cover - postgres extra owns this
        raise RuntimeError("install the postgres extra before syncing embeddings") from exc

    embedder, device = load_embedder(env_path, model)
    written = 0
    with connection:
        with connection.cursor() as cursor:
            for offset in range(0, len(sources), batch_size):
                batch = sources[offset : offset + batch_size]
                vectors = embedder.encode(
                    [source.embedded_text for source in batch],
                    normalize_embeddings=True,
                    batch_size=batch_size,
                    show_progress_bar=False,
                )
                rows = []
                for source, vector in zip(batch, vectors, strict=True):
                    rows.append(
                        (
                            source.item_id,
                            source.annotation_id,
                            model,
                            dimension,
                            source.embedded_text,
                            source.text_hash,
                            vector_literal(vector, dimension),
                        )
                    )
                execute_values(
                    cursor,
                    """
                    INSERT INTO roompilot.furniture_embeddings (
                        item_id, annotation_id, embedding_model, embedding_dimension,
                        embedded_text, text_hash, embedding
                    ) VALUES %s
                    ON CONFLICT (item_id, embedding_model, text_hash) DO UPDATE SET
                        annotation_id = EXCLUDED.annotation_id,
                        embedding_dimension = EXCLUDED.embedding_dimension,
                        embedded_text = EXCLUDED.embedded_text,
                        embedding = EXCLUDED.embedding,
                        created_at = now()
                    """,
                    rows,
                    template="(%s, %s, %s, %s, %s, %s, %s::vector)",
                    page_size=batch_size,
                )
                written += len(rows)
    return written, device


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dimension < 1:
        raise ValueError("dimension must be at least 1")
    if args.batch_size < 1:
        raise ValueError("batch-size must be at least 1")

    visibility = catalog_visibility(args.env, args.visibility)
    connection = connect_db(args.env, visibility)
    rollback_schema_dry_run = False
    try:
        if args.create_schema:
            if args.dry_run:
                apply_schema(connection, args.schema_sql)
                rollback_schema_dry_run = True
            else:
                with connection:
                    apply_schema(connection, args.schema_sql)
        with connection.cursor() as cursor:
            before = embedding_status(cursor, args.model)
            pending = load_pending_sources(cursor, args.model, limit=args.limit)

        summary: dict[str, Any] = {
            "schema_version": "roompilot.embedding-sync.v1",
            "model": args.model,
            "dimension": args.dimension,
            "visibility": visibility,
            "source_count": before["source_count"],
            "current_count": before["current_count"],
            "pending_count": before["pending_count"],
            "selected_count": len(pending),
            "create_schema": bool(args.create_schema),
            "dry_run": bool(args.dry_run),
        }
        if args.dry_run or not pending:
            summary["written_count"] = 0
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0

        written, device = upsert_sources(
            connection,
            pending,
            model=args.model,
            dimension=args.dimension,
            batch_size=args.batch_size,
            env_path=args.env,
        )
        with connection.cursor() as cursor:
            after = embedding_status(cursor, args.model)
        summary.update(
            {
                "written_count": written,
                "device": device,
                "current_count_after": after["current_count"],
                "pending_count_after": after["pending_count"],
            }
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        if rollback_schema_dry_run:
            connection.rollback()
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
