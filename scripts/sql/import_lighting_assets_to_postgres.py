"""把 lighting_assets_manifest.csv 匯入 `roompilot.lighting_assets`。

與家具匯入分開的理由和分表相同：燈具透過 `scene_json.surface_overrides.lighting_ids`
引用，不參與第 6 步家具自動選件；共用匯入流程會讓兩者的驗證門檻互相牽制。

冪等：以 item_id upsert，重跑不會產生重複列。不刪除 manifest 之外的既有列——
真要清空請用 --replace-existing。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extras

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.catalog.lighting_classification import (  # noqa: E402
    LIGHTING_TYPES,
    is_contract_fixture,
)

DEFAULT_MANIFEST = (
    PROJECT_ROOT / "backend/catalog/data/manifests/lighting_assets_manifest.csv"
)
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_postgresql_schema.sql")

_UPSERT = """
INSERT INTO roompilot.lighting_assets (
    item_id, lighting_type, classification_basis, source, source_group, catalog,
    canonical_category_zh, name_en, name_zh, width_cm, depth_cm, height_cm,
    glb_url, thumbnail_url, object_key, checksum, checksum_algo, license,
    style_primary, style_secondary, style_tags, verification_status, raw_data
) VALUES %s
ON CONFLICT (item_id) DO UPDATE SET
    lighting_type        = EXCLUDED.lighting_type,
    classification_basis = EXCLUDED.classification_basis,
    source               = EXCLUDED.source,
    source_group         = EXCLUDED.source_group,
    catalog              = EXCLUDED.catalog,
    canonical_category_zh= EXCLUDED.canonical_category_zh,
    name_en              = EXCLUDED.name_en,
    name_zh              = EXCLUDED.name_zh,
    width_cm             = EXCLUDED.width_cm,
    depth_cm             = EXCLUDED.depth_cm,
    height_cm            = EXCLUDED.height_cm,
    glb_url              = EXCLUDED.glb_url,
    thumbnail_url        = EXCLUDED.thumbnail_url,
    object_key           = EXCLUDED.object_key,
    checksum             = EXCLUDED.checksum,
    checksum_algo        = EXCLUDED.checksum_algo,
    license              = EXCLUDED.license,
    style_primary        = EXCLUDED.style_primary,
    style_secondary      = EXCLUDED.style_secondary,
    style_tags           = EXCLUDED.style_tags,
    verification_status  = EXCLUDED.verification_status,
    raw_data             = EXCLUDED.raw_data,
    updated_at           = NOW()
"""


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config(env_path: Path) -> dict[str, object]:
    env = _read_env(env_path)

    def setting(name: str, default: str = "") -> str:
        return os.getenv(name) or env.get(name) or default

    return {
        "host": setting("DB_HOST", "localhost"),
        "port": int(setting("DB_PORT", "5432")),
        "dbname": setting("DB_NAME", "roompilot_db"),
        "user": setting("DB_USER", "postgres"),
        "password": setting("DB_PASSWORD"),
        "application_name": setting("DB_APPLICATION_NAME", "roompilot_lighting_import"),
    }


def _numeric(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _style_tags(row: dict[str, str]) -> list[str]:
    tags = [row.get("style_primary", ""), row.get("style_secondary", "")]
    return list(dict.fromkeys(tag for tag in tags if tag))


def _validate(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise SystemExit("manifest 沒有任何資料列。")
    problems: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        item_id = (row.get("item_id") or "").strip()
        if not item_id:
            problems.append(f"第 {index} 行缺 item_id")
            continue
        if item_id in seen:
            problems.append(f"第 {index} 行 item_id 重複：{item_id}")
        seen.add(item_id)
        if row.get("lighting_type") not in LIGHTING_TYPES:
            problems.append(f"{item_id} 的 lighting_type 不合法：{row.get('lighting_type')}")
        if not (row.get("glb_url") or "").startswith("https://"):
            problems.append(f"{item_id} 缺少 https 的 glb_url")
        if not (row.get("object_key") or "").strip():
            problems.append(f"{item_id} 缺少 object_key")
        expected = "verified" if is_contract_fixture(row.get("lighting_type", "")) else "needs_review"
        if row.get("verification_status") != expected:
            problems.append(
                f"{item_id} 的 verification_status 與 lighting_type 不一致："
                f"{row.get('verification_status')} vs 應為 {expected}"
            )
    if problems:
        for line in problems[:20]:
            print(f"  ! {line}")
        raise SystemExit(f"manifest 驗證失敗，共 {len(problems)} 項問題。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true", help="只驗證，不寫資料庫。")
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="不執行 schema SQL；表已存在時可加快重跑。",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="匯入前先 TRUNCATE roompilot.lighting_assets。",
    )
    args = parser.parse_args()

    with args.manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _validate(rows)

    counts = Counter(row["lighting_type"] for row in rows)
    verified = sum(1 for row in rows if row["verification_status"] == "verified")
    print(f"manifest：{len(rows)} 筆，verified {verified}，needs_review {len(rows) - verified}")
    for lighting_type, count in counts.most_common():
        print(f"  {lighting_type:<24} {count:>4}")

    if args.dry_run:
        print("\n--dry-run：驗證通過，未寫入資料庫。")
        return

    payload = [
        (
            row["item_id"],
            row["lighting_type"],
            row.get("classification_basis") or None,
            row.get("source") or "unknown",
            row.get("source_group") or None,
            row.get("catalog") or None,
            row.get("canonical_category_zh") or None,
            row.get("name_en") or row["item_id"],
            row.get("name_zh") or None,
            _numeric(row.get("width_cm", "")),
            _numeric(row.get("depth_cm", "")),
            _numeric(row.get("height_cm", "")),
            row["glb_url"],
            row.get("thumbnail_url") or None,
            row["object_key"],
            row.get("checksum") or None,
            row.get("checksum_algo") or None,
            row.get("license") or "catalog-origin",
            row.get("style_primary") or None,
            row.get("style_secondary") or None,
            _style_tags(row),
            row["verification_status"],
            json.dumps(row, ensure_ascii=False),
        )
        for row in rows
    ]

    config = _db_config(args.env)
    connection = psycopg2.connect(**config)
    try:
        connection.autocommit = False
        with connection.cursor() as cursor:
            if not args.skip_schema:
                cursor.execute(args.schema_sql.read_text(encoding="utf-8"))
            if args.replace_existing:
                cursor.execute("TRUNCATE roompilot.lighting_assets")
            psycopg2.extras.execute_values(
                cursor, _UPSERT, payload, page_size=args.page_size
            )
            cursor.execute("SELECT COUNT(*) FROM roompilot.lighting_assets")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM roompilot.lighting_assets_current")
            deliverable = cursor.fetchone()[0]
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"\n已匯入。lighting_assets 共 {total} 筆；")
    print(f"lighting_assets_current（可交付）{deliverable} 筆。")


if __name__ == "__main__":
    main()
