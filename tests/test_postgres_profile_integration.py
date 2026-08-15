from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[1]
ITEM_ID = "public-ci-chair"


def test_full_profile_reads_a_developer_supplied_postgres_catalog() -> None:
    if os.getenv("ROOMPILOT_POSTGRES_TEST") != "1":
        pytest.skip("set ROOMPILOT_POSTGRES_TEST=1 with a disposable PostgreSQL service")

    import psycopg2

    from backend.catalog.postgres_repository import (
        catalog_provider_status,
        close_catalog_pools,
        load_catalog,
    )

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "roompilot_db"),
        user=os.getenv("DB_USER", "roompilot"),
        password=os.getenv("DB_PASSWORD", ""),
        sslmode=os.getenv("DB_SSLMODE", "disable"),
    )
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                (ROOT / "docker_postgresql" / "init" / "001_roompilot.sql").read_text(
                    encoding="utf-8"
                )
            )
            cursor.execute(
                """
                INSERT INTO roompilot.furniture_catalog (
                    item_id, name_en, name_zh, normalized_type,
                    taxonomy_group, width_cm, depth_cm, height_cm,
                    style_codes, room_codes, source_license, is_active
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE
                )
                ON CONFLICT (item_id) DO UPDATE SET
                    name_en = EXCLUDED.name_en,
                    updated_at = NOW()
                """,
                (
                    ITEM_ID,
                    "Public CI Chair",
                    "公開 CI 椅",
                    "dining-chair",
                    "dining_kitchen",
                    48,
                    52,
                    82,
                    ["scandinavian"],
                    ["dining_room"],
                    "GPL-3.0-only; generated test record",
                ),
            )

        close_catalog_pools()
        catalog = load_catalog(ROOT)
        item = next(row for row in catalog if row["furniture_id"] == ITEM_ID)
        assert item["normalized_type"] == "dining-chair"
        assert item["size_cm"] == {"width": 48.0, "depth": 52.0, "height": 82.0}
        assert item["has_model"] is False

        status = catalog_provider_status(ROOT)
        assert status["provider"] == "kai_postgresql"
        assert status["available"] is True
        assert status["ready"] is True
        assert status["strict"] is True
    finally:
        close_catalog_pools()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM roompilot.furniture_catalog WHERE item_id = %s",
                (ITEM_ID,),
            )
        connection.close()
