"""前端 2D 種子表不得含型錄 0 件死鍵——2026-08-02 假家具案回歸鎖。

種子表（recommendedFurnitureForRoom）生出的件若型錄 0 件，會是無 model_url、
無 catalogFurnitureId 的佔位假件：2D 照樣標「合法」（合法＝引擎擺放判定），
送 3D 前被 generate 合併剔除，全程零錯誤訊息。實案：專案 b2b2c83f 廚／儲／浴
三件假件（電器櫃、高收納櫃、浴櫃），2D 14 件 vs 3D 11 件。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT2D = REPO_ROOT / "backend" / "server" / "static" / "scene_layout2d.js"

# 2026-08-02 型錄實測 0 件（audit_furniture_vanish 關卡 3）；型錄補貨後方可移出
KNOWN_CATALOG_EMPTY = {
    "appliance-cabinet",
    "storage-cabinet",
    "bathroom-vanity",
    "cabinets-cupboard",
}


def seed_types() -> set[str]:
    text = LAYOUT2D.read_text(encoding="utf-8")
    match = re.search(
        r"recommendedFurnitureForRoom[\s\S]*?recommendations = \{([\s\S]*?)\n  \};",
        text,
    )
    assert match, "找不到 recommendedFurnitureForRoom 的 recommendations 表"
    return set(re.findall(r'\[\s*"([a-z0-9-]+)"\s*,', match.group(1)))


def test_seed_table_contains_no_dead_keys():
    dead = seed_types() & KNOWN_CATALOG_EMPTY
    assert not dead, f"種子表含型錄 0 件死鍵（會生 2D 假件）: {sorted(dead)}"


def test_seed_table_keeps_core_real_types():
    expected = {"bed", "wardrobe", "sofa", "shelving-unit", "mirror-cabinet"}
    missing = expected - seed_types()
    assert not missing, f"種子表缺少核心真身型別: {sorted(missing)}"


def test_shelving_unit_has_2d_variant():
    # 種子路徑不帶尺寸覆寫，型別若無 2D 變體會 throw unknown_furniture_type，
    # 儲藏室種子（v1: shelving-unit）就會整房消失。
    text = LAYOUT2D.read_text(encoding="utf-8")
    assert re.search(r'type:\s*"shelving-unit"', text), "shelving-unit 未登記 2D 類型定義"
