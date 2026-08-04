"""把 Kai 型錄實際存在的 ``normalized_type`` 匯出成快照，供詞彙契約測試使用。

為什麼要快照而不是讓測試直接查資料庫：``tests/conftest.py`` 預設把
``ROOMPILOT_CATALOG_PROVIDER`` 設成 ``json``，所以整套測試平常看到的是離線 JSON
型錄——而它與 PostgreSQL 的詞彙**並不相同**（JSON 多出 ``cabinets-cupboard``、
``planter``、``lamp`` 三型）。`FAMILY_OF` 那條複數 ``cabinets-cupboard`` 映射在
JSON 模式下查得到東西、在正式的 PostgreSQL 模式下永遠 0 筆，正是因此躲過了測試。

所以契約要對「正式來源」而不是「測試預設來源」斷言。這支腳本從
``roompilot.furniture_catalog_api_current`` 匯出快照，測試對快照跑（離線、快、
CI 不需要資料庫），另有一條 postgres 標記的測試負責檢查快照是否過期。

型錄變動後重新產生：

    python scripts/dump_catalog_vocabulary.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.catalog.postgres_repository import (  # noqa: E402
    borrow_catalog_connection,
)

SNAPSHOT_PATH = REPO_ROOT / "tests" / "data" / "catalog_vocabulary_snapshot.json"

COUNT_SQL = """
SELECT
    COALESCE({column}, category_code, source_type, 'furniture') AS catalog_type,
    COUNT(*) FILTER (
        WHERE glb_url IS NOT NULL AND BTRIM(glb_url) <> ''
    ) AS with_model,
    COUNT(*) AS total
FROM roompilot.furniture_catalog_api_current
GROUP BY 1
ORDER BY 1
"""


def _counts(cursor: object, column: str) -> dict[str, dict[str, int]]:
    cursor.execute(COUNT_SQL.format(column=column))
    return {
        str(catalog_type): {"with_model": int(with_model), "total": int(total)}
        for catalog_type, with_model, total in cursor.fetchall()
    }


def collect_vocabulary() -> dict[str, object]:
    with borrow_catalog_connection(REPO_ROOT) as connection:
        cursor = connection.cursor()
        # 兩個鍵空間都要：`scene_service` 比對 payload 的 normalized_type，
        # `spatial_data/rag/shortlist` 查的是 furniture_catalog_current 的
        # category_code。目前兩者只差 planter → flower-pots-planter 一列，
        # 但沒有任何機制保證它們會一直只差一列。
        types = _counts(cursor, "normalized_type")
        category_codes = _counts(cursor, "category_code")
        # 燈具在獨立表，用自己的 lighting_type 詞彙。自動裝飾的燈具角色從這裡
        # 取候選（`backend/catalog/lighting_repository.py`），所以契約也要看得到。
        cursor.execute(
            """
            SELECT lighting_type,
                   COUNT(*) FILTER (
                       WHERE glb_url IS NOT NULL AND BTRIM(glb_url) <> ''
                   ) AS with_model,
                   COUNT(*) AS total
            FROM roompilot.lighting_assets_current
            GROUP BY 1 ORDER BY 1
            """
        )
        lighting_types = {
            str(lighting_type): {"with_model": int(with_model), "total": int(total)}
            for lighting_type, with_model, total in cursor.fetchall()
        }

    return {
        "source": "roompilot.furniture_catalog_api_current",
        "note": (
            "由 scripts/dump_catalog_vocabulary.py 產生，請勿手改。"
            "with_model 為 0 的型別無法被第 6 步選用。"
        ),
        "types": types,
        "category_codes": category_codes,
        "lighting_source": "roompilot.lighting_assets_current",
        "lighting_types": lighting_types,
    }


def main() -> int:
    vocabulary = collect_vocabulary()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(vocabulary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    types = vocabulary["types"]
    usable = sum(1 for entry in types.values() if entry["with_model"])
    print(f"寫入 {SNAPSHOT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(types)} 型，其中 {usable} 型有可用模型")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
