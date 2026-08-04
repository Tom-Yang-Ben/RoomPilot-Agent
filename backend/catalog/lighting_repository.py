"""燈具資產讀取層：把 ``roompilot.lighting_assets_current`` 轉成家具 payload 形狀。

2026-07-30 的型錄切換把燈具從 ``furniture_items`` 移走，2026-08-02 以獨立表接
回（637 筆，``lighting_type`` 用 pendant/track/downlight/wall/table/floor 一套
自己的詞彙）。但沒有任何 payload 管道，於是
``main._AUTO_DECOR_TYPES["light"]`` 掃的還是家具型錄——正式型錄一盞燈都沒有，
第 7 步的自動裝飾照樣請求燈具角色，卻永遠拿不到東西（離線 JSON 型錄剛好殘留
``lamp``，所以預設測試模式下看不出來）。

這裡只接落地燈（``lighting_type = 'floor'``，128 筆）。其餘燈種不進自動擺放：

  table       檯燈要有桌面宿主，屬於檯面吸附 lane（scene_tabletop_hosts）。
  pendant / downlight / track / wall
              天花與壁掛燈具不佔地板，屬於第 8 步的 render_context 與天花層，
              不是 2D/3D 落地擺設。

輸出刻意做成與 ``postgres_repository._payload_from_row`` 同形狀，讓
``_auto_decor_catalog_item`` 與 ``generate_layout`` 不必分兩套解析。風格代碼共用
``_STYLE_ID_MAP``——燈具表的 10 種風格全都在那張表裡，不需要第二套對照。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .postgres_repository import (
    _STYLE_ID_MAP,
    _repair_text,
    borrow_catalog_connection,
    catalog_dict_cursor,
    postgres_catalog_requested,
)


#: 自動擺放只收落地燈；其餘燈種見模組 docstring。
FLOOR_LIGHTING_TYPE = "floor"

#: 落地燈在 payload 裡的型別名。`placement_surface_for` 沒有把它列進壁掛或檯面，
#: 所以會被當成落地家具參與碰撞與淨空——正是落地燈該有的行為。
FLOOR_LAMP_TYPE = "floor-lamp"

_FLOOR_LAMP_SQL = """
SELECT
    item_id, name_en, name_zh, width_cm, depth_cm, height_cm,
    glb_url, thumbnail_url, style_primary, style_secondary
FROM roompilot.lighting_assets_current
WHERE lighting_type = %s
  AND glb_url IS NOT NULL
  AND BTRIM(glb_url) <> ''
ORDER BY item_id
"""


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    style_codes = [
        _STYLE_ID_MAP.get(code, code)
        for code in (row.get("style_primary"), row.get("style_secondary"))
        if code
    ]
    name_zh = _repair_text(row.get("name_zh")) or _repair_text(row.get("name_en"))
    return {
        "furniture_id": row.get("item_id"),
        "name_en": _repair_text(row.get("name_en")),
        "name_zh": name_zh,
        "name_zh_raw": name_zh,
        "normalized_type": FLOOR_LAMP_TYPE,
        "category_label": "落地燈",
        "taxonomy_group": "soft_decor",
        "taxonomy_group_zh": "軟裝與燈飾",
        "taxonomy_type_zh": "落地燈",
        "catalog_scope": "kai_lighting_assets",
        "size_cm": {
            "width": _number(row.get("width_cm")),
            "depth": _number(row.get("depth_cm")),
            "height": _number(row.get("height_cm")),
        },
        "primary_style": style_codes[0] if style_codes else None,
        "style_primary": style_codes[0] if style_codes else None,
        "style_secondary": style_codes[1] if len(style_codes) > 1 else None,
        # 燈具表沒有逐筆信心值；給 1.0 讓風格相符的候選能穩定勝出，
        # 與 `_auto_decor_catalog_item` 的排序方式一致。
        "style_candidates": [
            {"style_id": code, "score": 1.0} for code in style_codes
        ],
        "style_confidence": 1.0,
        "style_assignment_source": "kai_lighting_assets",
        # glb_url 一律是 https（匯入時就驗過），前端的 GLTFLoader 直接載得動，
        # 不必繞 /api/furniture/{id}/model。
        "model_url": _repair_text(row.get("glb_url")),
        "glb_url": _repair_text(row.get("glb_url")),
        "has_model": True,
        "image_urls": (
            {"front": row["thumbnail_url"]} if row.get("thumbnail_url") else {}
        ),
        "placement_surface": "floor",
        "role": "lighting",
    }


def load_floor_lamps(project_dir: Path) -> list[dict[str, Any]]:
    """回傳可用於自動擺放的落地燈 payload。

    燈具只存在於 PostgreSQL，沒有離線 JSON 對應檔。型錄切成 json 或資料庫讀不到
    時回空清單——呼叫端（``main._auto_decor_candidates``）會退回家具型錄，用它
    殘留的 ``lamp`` 頂著；兩邊都沒有才把燈具角色記進 ``decor_summary.skipped``。

    讀取失敗刻意不往外丟：少一盞燈不該讓整間房的軟裝一起中止，那正是
    ``_auto_decor_catalog_item`` 回 None 的設計理由。
    """
    if not postgres_catalog_requested(project_dir):
        return []
    try:
        with borrow_catalog_connection(project_dir) as connection:
            with catalog_dict_cursor(connection) as cursor:
                cursor.execute(_FLOOR_LAMP_SQL, (FLOOR_LIGHTING_TYPE,))
                rows = cursor.fetchall()
    except Exception:
        return []
    return [_payload_from_row(dict(row)) for row in rows]
