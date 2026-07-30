#!/usr/bin/env python3
"""Validate RoomPilot BGE-M3 embedding input and UPSERT real vectors into PostgreSQL.

The official furniture JSON currently contains ``embedded_text`` and
``text_hash`` for every item, but no numeric embedding arrays. Running this
script uses the repaired 8,076-row BGE-M3 delivery in ``JSON/RAG`` by default.

An embedding JSON/JSONL record may contain only ``item_id`` and ``embedding``;
model, dimension, text, and hash default to the official catalog contract.
Optional explicit fields are validated rather than trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.sql import import_official_catalog_to_postgres as catalog_import
except ModuleNotFoundError:  # Direct execution with scripts/sql on sys.path.
    import import_official_catalog_to_postgres as catalog_import


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = PROJECT_ROOT / "JSON" / "furniture" / "furniture_official_catagory.json"
DEFAULT_EMBEDDINGS = PROJECT_ROOT / "JSON" / "RAG" / "furniture_embeddings_bge_m3.jsonl"
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_furniture_embeddings_schema.sql")
EXPECTED_CATALOG_COUNT = 8_675
EXPECTED_SOURCE_COUNT = 8_076


@dataclass(frozen=True)
class EmbeddingSource:
    item_id: str
    embedded_text: str
    text_hash: str


@dataclass(frozen=True)
class EmbeddingRow:
    item_id: str
    embedding_model: str
    embedding_dimension: int
    embedded_text: str
    text_hash: str
    vector: tuple[float, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="建立家具向量 SQL 契約，並在有實際向量時安全 UPSERT。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=DEFAULT_EMBEDDINGS,
        help="含 item_id 與 embedding array 的 JSON 或 JSONL。",
    )
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--model", help="覆寫 embedding_model；未提供時使用資料列或 catalog embedding_target。")
    parser.add_argument("--dimension", type=int, help="覆寫並驗證向量維度；不會固定 SQL VECTOR 維度。")
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-schema", action="store_true")
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="要求 8,076 件 active/RAG-indexable 家具都有向量；正式完整批次建議啟用。",
    )
    parser.add_argument(
        "--allow-unnormalized",
        action="store_true",
        help="略過 catalog 對目標模型宣告 normalized=true 時的單位長度檢查。",
    )
    return parser.parse_args(argv)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_catalog(
    path: Path,
) -> tuple[dict[str, Any], dict[str, EmbeddingSource], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("官方 catalog 必須是含 items array 的 JSON object。")
    items = payload["items"]
    if payload.get("count") != len(items) or len(items) != EXPECTED_CATALOG_COUNT:
        raise ValueError(
            f"官方 catalog 必須是 {EXPECTED_CATALOG_COUNT:,} 筆，"
            f"metadata.count={payload.get('count')!r}，實際={len(items):,}。"
        )

    sources: dict[str, EmbeddingSource] = {}
    seen_item_ids: set[str] = set()
    errors: list[str] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] 不是 object")
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id or item_id in seen_item_ids:
            errors.append(f"item_id 缺漏或重複：{item_id!r}")
            continue
        seen_item_ids.add(item_id)
        if not bool(item.get("is_active", True)) or not bool(
            item.get("rag_indexable", True)
        ):
            continue
        text = str(item.get("embedded_text") or "").strip()
        text_hash = str(item.get("text_hash") or "").strip().lower()
        if not item_id or not text or len(text_hash) != 64:
            errors.append(f"items[{index}] 缺少 id／embedded_text／SHA-256 text_hash")
            continue
        if sha256_text(text) != text_hash:
            errors.append(f"text_hash 與 embedded_text 不一致：{item_id}")
            continue
        sources[item_id] = EmbeddingSource(item_id, text, text_hash)
    if errors or len(sources) != EXPECTED_SOURCE_COUNT:
        raise ValueError("；".join(errors[:10]) or "embedding source 筆數不符")
    return payload, sources, items


def load_records(path: Path | None, catalog_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if path is None:
        return [item for item in catalog_items if item.get("embedding") is not None]
    if not path.is_file():
        raise FileNotFoundError(f"找不到 embedding 檔：{path}")
    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    else:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get("embeddings") or payload.get("items") or []
        else:
            records = []
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("embedding 檔必須是 object array、embeddings/items array 或 JSONL。")
    return records


def _vector_values(value: Any, item_id: str) -> tuple[float, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"embedding 必須是非空數值 array：{item_id}")
    vector: list[float] = []
    for entry in value:
        if isinstance(entry, bool):
            raise ValueError(f"embedding 含非數值：{item_id}")
        try:
            number = float(entry)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"embedding 含非數值：{item_id}") from exc
        if not math.isfinite(number):
            raise ValueError(f"embedding 含 NaN／Infinity：{item_id}")
        vector.append(number)
    return tuple(vector)


def prepare_embedding_rows(
    records: Iterable[dict[str, Any]],
    sources: dict[str, EmbeddingSource],
    target: dict[str, Any],
    *,
    model_override: str | None = None,
    dimension_override: int | None = None,
    allow_unnormalized: bool = False,
) -> list[EmbeddingRow]:
    rows: list[EmbeddingRow] = []
    seen: set[tuple[str, str, str]] = set()
    target_model = str(target.get("embedding_model") or "").strip()
    target_dimension = target.get("embedding_dimension")
    target_normalized = bool(target.get("normalized"))

    for record in records:
        item_id = str(record.get("item_id") or record.get("id") or "").strip()
        if item_id not in sources:
            raise ValueError(
                f"embedding item_id 不在官方 {EXPECTED_SOURCE_COUNT:,} 筆 active/RAG-indexable 家具中：{item_id!r}"
            )
        source = sources[item_id]
        text = str(record.get("embedded_text") or source.embedded_text).strip()
        text_hash = str(record.get("text_hash") or source.text_hash).strip().lower()
        if text != source.embedded_text or text_hash != source.text_hash:
            raise ValueError(f"embedding 使用過期或非官方 embedded_text/text_hash：{item_id}")
        if sha256_text(text) != text_hash:
            raise ValueError(f"embedding text_hash 驗證失敗：{item_id}")

        vector = _vector_values(record.get("embedding"), item_id)
        model = str(
            model_override or record.get("embedding_model") or target_model
        ).strip()
        if not model:
            raise ValueError(f"缺少 embedding_model：{item_id}")
        raw_dimension = dimension_override or record.get("embedding_dimension") or len(vector)
        try:
            dimension = int(raw_dimension)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"embedding_dimension 不合法：{item_id}") from exc
        if dimension != len(vector):
            raise ValueError(
                f"向量維度不符：{item_id} 宣告 {dimension}，實際 {len(vector)}"
            )
        if dimension_override is None and model == target_model and target_dimension is not None:
            if dimension != int(target_dimension):
                raise ValueError(
                    f"向量維度不符合 catalog embedding_target：{item_id} "
                    f"{dimension} != {target_dimension}"
                )
        if target_normalized and model == target_model and not allow_unnormalized:
            norm = math.sqrt(sum(number * number for number in vector))
            if not 0.98 <= norm <= 1.02:
                raise ValueError(f"目標模型向量未正規化：{item_id}，L2 norm={norm:.6f}")

        unique_key = (item_id, model, text_hash)
        if unique_key in seen:
            raise ValueError(f"embedding 重複：{unique_key}")
        seen.add(unique_key)
        rows.append(
            EmbeddingRow(
                item_id=item_id,
                embedding_model=model,
                embedding_dimension=dimension,
                embedded_text=text,
                text_hash=text_hash,
                vector=vector,
            )
        )
    return rows


def vector_literal(values: tuple[float, ...]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in values) + "]"


def validate_database_sources(cursor, sources: dict[str, EmbeddingSource]) -> dict[str, int]:
    cursor.execute(
        "SELECT item_id, annotation_id, embedded_text, text_hash "
        "FROM roompilot.furniture_embedding_source_current"
    )
    database_rows = cursor.fetchall()
    database_sources = {
        str(item_id): (annotation_id, str(text), str(text_hash).lower())
        for item_id, annotation_id, text, text_hash in database_rows
    }
    missing = set(sources) - set(database_sources)
    extra = set(database_sources) - set(sources)
    mismatched = {
        item_id
        for item_id in set(sources) & set(database_sources)
        if (
            database_sources[item_id][1] != sources[item_id].embedded_text
            or database_sources[item_id][2] != sources[item_id].text_hash
        )
    }
    if missing or extra or mismatched:
        raise RuntimeError(
            "SQL embedding source view 與官方 JSON 不一致："
            f"missing={len(missing)}, extra={len(extra)}, mismatched={len(mismatched)}"
        )
    return {
        "source_rows": len(database_sources),
        "annotation_links": sum(row[0] is not None for row in database_sources.values()),
    }


def validate_database_contract(cursor) -> dict[str, int | str]:
    cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    extension_row = cursor.fetchone()
    if extension_row is None:
        raise RuntimeError("PostgreSQL 尚未啟用 pgvector extension。")

    cursor.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'roompilot.furniture_embeddings'::regclass"
    )
    constraints = {str(row[0]) for row in cursor.fetchall()}
    required_constraints = {
        "furniture_embeddings_dimension_positive",
        "furniture_embeddings_dimension_matches",
        "furniture_embeddings_text_hash_sha256",
    }
    missing_constraints = required_constraints - constraints
    if missing_constraints:
        raise RuntimeError(f"家具向量表缺少 constraints：{sorted(missing_constraints)}")

    cursor.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'roompilot' AND tablename = 'furniture_embeddings'"
    )
    indexes = [(str(name), str(definition)) for name, definition in cursor.fetchall()]
    if not any(name == "idx_furniture_embeddings_item_model" for name, _ in indexes):
        raise RuntimeError("家具向量表缺少 item/model B-tree index。")
    hnsw_indexes = [name for name, definition in indexes if " using hnsw " in definition.lower()]
    if hnsw_indexes:
        raise RuntimeError(f"模型／維度尚未定案，不應先建立 HNSW：{hnsw_indexes}")

    cursor.execute(
        "SELECT COUNT(*) FROM roompilot.search_furniture_embeddings("
        "'[1,0,0]'::vector, '__roompilot_contract_probe__', 1)"
    )
    probe_rows = int(cursor.fetchone()[0])
    if probe_rows != 0:
        raise RuntimeError("向量搜尋契約 probe 不應命中正式資料。")
    return {
        "pgvector_version": str(extension_row[0]),
        "embedding_constraints": len(required_constraints),
        "hnsw_indexes": len(hnsw_indexes),
        "search_probe_rows": probe_rows,
    }


def upsert_embeddings(cursor, rows: list[EmbeddingRow], page_size: int) -> None:
    if not rows:
        return
    from psycopg2.extras import execute_batch

    cursor.execute(
        "SELECT item_id, annotation_id FROM roompilot.furniture_embedding_source_current"
    )
    annotation_ids = dict(cursor.fetchall())
    statement = """
        INSERT INTO roompilot.furniture_embeddings (
            item_id, annotation_id, embedding_model, embedding_dimension,
            embedded_text, text_hash, embedding
        ) VALUES (%s,%s,%s,%s,%s,%s,%s::vector)
        ON CONFLICT (item_id, embedding_model, text_hash) DO UPDATE SET
            annotation_id = EXCLUDED.annotation_id,
            embedding_dimension = EXCLUDED.embedding_dimension,
            embedded_text = EXCLUDED.embedded_text,
            embedding = EXCLUDED.embedding,
            created_at = NOW()
    """
    values = [
        (
            row.item_id,
            annotation_ids.get(row.item_id),
            row.embedding_model,
            row.embedding_dimension,
            row.embedded_text,
            row.text_hash,
            vector_literal(row.vector),
        )
        for row in rows
    ]
    execute_batch(cursor, statement, values, page_size=page_size)


def run_import(
    args: argparse.Namespace,
    sources: dict[str, EmbeddingSource],
    rows: list[EmbeddingRow],
) -> dict[str, int | str]:
    psycopg = catalog_import.require_psycopg()
    with psycopg.connect(**catalog_import.db_config(args.env)) as connection:
        with connection.cursor() as cursor:
            if not args.skip_schema:
                cursor.execute(args.schema_sql.read_text(encoding="utf-8-sig"))
            database_counts = validate_database_contract(cursor)
            database_counts.update(validate_database_sources(cursor, sources))
            upsert_embeddings(cursor, rows, args.page_size)
            cursor.execute("SELECT COUNT(*) FROM roompilot.furniture_embeddings")
            database_counts["all_embedding_rows"] = int(cursor.fetchone()[0])
            if rows:
                expected_keys = {
                    (row.item_id, row.embedding_model, row.text_hash) for row in rows
                }
                cursor.execute(
                    "SELECT item_id, embedding_model, text_hash "
                    "FROM roompilot.furniture_embeddings "
                    "WHERE item_id = ANY(%s) AND embedding_model = ANY(%s)",
                    (
                        sorted({row.item_id for row in rows}),
                        sorted({row.embedding_model for row in rows}),
                    ),
                )
                actual_keys = {
                    (str(item_id), str(model), str(text_hash))
                    for item_id, model, text_hash in cursor.fetchall()
                }
                missing_keys = expected_keys - actual_keys
                if missing_keys:
                    raise RuntimeError(
                        "向量 UPSERT 驗證失敗，缺少 "
                        f"{len(missing_keys)} 筆，例如：{sorted(missing_keys)[:3]}"
                    )
                database_counts["imported_embedding_rows"] = len(expected_keys)
            else:
                database_counts["imported_embedding_rows"] = 0
    return database_counts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.page_size <= 0:
        raise ValueError("--page-size 必須大於 0。")
    if args.dimension is not None and args.dimension <= 0:
        raise ValueError("--dimension 必須大於 0。")
    if not args.schema_sql.is_file() and not args.skip_schema:
        raise FileNotFoundError(f"找不到 embedding schema：{args.schema_sql}")

    payload, sources, catalog_items = load_catalog(args.catalog)
    records = load_records(args.embeddings, catalog_items)
    target = payload.get("embedding_target") or {}
    rows = prepare_embedding_rows(
        records,
        sources,
        target,
        model_override=args.model,
        dimension_override=args.dimension,
        allow_unnormalized=args.allow_unnormalized,
    )
    if args.require_all and len(rows) != len(sources):
        raise ValueError(
            f"--require-all 需要 {len(sources):,} 筆向量，實際只有 {len(rows):,}。"
        )

    print("家具 embedding 來源驗證完成")
    print(f"- embedded_text／text_hash：{len(sources):,}")
    print(
        "- catalog target："
        f"{target.get('embedding_model')}／{target.get('embedding_dimension')} 維／"
        f"{target.get('distance_metric')}／normalized={target.get('normalized')}"
    )
    print(f"- 實際向量：{len(rows):,}")
    if args.dry_run:
        print("Dry Run 完成；未連線 PostgreSQL，也未寫入資料庫。")
        return 0

    counts = run_import(args, sources, rows)
    print(f"- pgvector：{counts['pgvector_version']}")
    print(f"- SQL constraints：{counts['embedding_constraints']}")
    print(f"- HNSW indexes：{counts['hnsw_indexes']}")
    print(f"- search probe rows：{counts['search_probe_rows']}")
    print(f"- SQL source view：{counts['source_rows']:,}")
    print(f"- current annotation links：{counts['annotation_links']:,}")
    print(f"- 本批 UPSERT 向量：{counts['imported_embedding_rows']:,}")
    print(f"- furniture_embeddings 總筆數：{counts['all_embedding_rows']:,}")
    if not rows:
        print("目前來源沒有數值向量；已建立／驗證空表，等待 RAG embedding 檔。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"家具向量匯入失敗：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
