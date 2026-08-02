"""型錄標記錯誤在讀取邊界攔下（QA 2026-08-01 #11）。

實測資料：92 筆配件（滑鼠墊／椅墊／層板）被標成家具型、abo-beds-19 是一個
468cm 寬的六斗櫃卻標成 bed、781 筆 style_codes 內部重複。normalized_type 由
匯入層決定且會被下次匯入覆寫，所以修在讀取邊界而不是改資料列。
"""

from __future__ import annotations

import pytest

from backend.catalog.placement_surface import (
    FLOOR,
    TABLETOP,
    WALL,
    is_floor_furniture,
    placement_surface_for,
)
from backend.paths import SERVER_DIR, STATIC_DIR
from backend.server.main import _normalize_catalog_payload


@pytest.mark.parametrize(
    ("normalized_type", "name", "expected"),
    [
        ("desk", "AmazonBasics 亞馬遜倍思遊戲滑鼠墊 小", TABLETOP),
        ("stool-bench", "Mouse Pad Large", TABLETOP),
        ("childrens-table", "BÖNSYRSA - 桌墊, 動物圖案", TABLETOP),
        ("bookcase", "BILLY 層板，橡木紋，76x26 公分", WALL),
        ("shelving-unit", "HEJNE 層板，針葉木，77x28 公分", WALL),
        ("flower-pots-planter", "鉚釘圓形壁掛式花盆", WALL),
        # 真的家具不能被誤降級。
        ("stool-bench", "橡木長凳", FLOOR),
        ("fabric-sofa", "三人座布沙發", FLOOR),
    ],
)
def test_accessory_names_are_demoted_off_the_floor(
    normalized_type: str, name: str, expected: str
) -> None:
    assert placement_surface_for(normalized_type, name) == expected
    assert is_floor_furniture(normalized_type, name) is (expected == FLOOR)


@pytest.mark.parametrize(
    "name",
    [
        "UTVISNING 附層板電競桌，黑色，120x60 公分",
        "GULLABERG 床邊桌，附 1 抽屜附層板/白色，53x43x69 公分",
        "EKET 附2門1層板收納櫃，白色，70x35x70 公分",
        "LÅDMAKARE - 收納組合, 附層板/橡木紋, 159x35x212 公分",
    ],
)
def test_a_shelf_mentioned_as_a_feature_does_not_demote_the_furniture(name: str) -> None:
    """「附層板」的主體是桌子或櫃子，層板只是配備。"""
    assert placement_surface_for("desk", name) == FLOOR


@pytest.mark.parametrize(
    ("normalized_type", "name"),
    [
        ("sofa", "Stone & Beam Alaina 坐墊餐椅"),
        ("stool-bench", "AmazonBasics 現代皮革軟辦公椅，超大坐墊, 象牙色"),
        ("coffee-table", "方形茶几配四個坐墊 - Solimo Andro Solid Sheesham Wood"),
        ("fabric-sofa", "Ravenna Home Amanda 曲線臂坐墊椅"),
        ("armchair", "記憶棉椅墊扶手椅"),
    ],
)
def test_cushion_words_never_demote_real_furniture(normalized_type: str, name: str) -> None:
    """實測型錄裡「坐墊／椅墊」共 40 筆全是真家具的配備描述。

    拿它當配件判準會把餐椅、辦公椅、茶几踢出配置——誤刪一張餐椅比留下一個
    滑鼠墊糟糕得多，所以這兩個詞刻意不列入判準。
    """
    assert placement_surface_for(normalized_type, name) == FLOOR


def test_type_table_still_wins_over_the_name_hint() -> None:
    """型別表已經判定的不看品名，避免兩套規則互相打架。"""
    assert placement_surface_for("large-medium-rug", "滑鼠墊造型地毯") == "floor_covering"
    assert placement_surface_for("mirror", "壁掛鏡") == WALL


def test_placement_surface_without_a_name_keeps_the_old_behaviour() -> None:
    assert placement_surface_for("sofa") == FLOOR
    assert placement_surface_for("vase") == TABLETOP


def test_style_codes_are_deduped_at_the_read_boundary() -> None:
    normalized = _normalize_catalog_payload((
        {
            "furniture_id": "a",
            "normalized_type": "sofa",
            "style_codes": ["scandinavian", "scandinavian", "japanese", "scandinavian"],
        },
    ))

    assert normalized[0]["style_codes"] == ["scandinavian", "japanese"]


def test_a_468cm_bed_is_flagged_as_implausible() -> None:
    normalized = _normalize_catalog_payload((
        {
            "furniture_id": "abo-beds-19",
            "normalized_type": "bed",
            "name_zh": "六斗櫃",
            "size_cm": {"width": 468.0, "depth": 225.1, "height": 76.5},
        },
        {
            "furniture_id": "real-bed",
            "normalized_type": "bed",
            "name_zh": "雙人床",
            "size_cm": {"width": 152.0, "depth": 200.0, "height": 55.0},
        },
    ))

    by_id = {item["furniture_id"]: item for item in normalized}
    assert by_id["abo-beds-19"]["size_is_implausible"] is True
    assert "size_is_implausible" not in by_id["real-bed"]


def test_types_without_a_size_rule_are_left_alone() -> None:
    normalized = _normalize_catalog_payload((
        {
            "furniture_id": "long-counter",
            "normalized_type": "kitchen-counter",
            "size_cm": {"width": 900.0, "depth": 60.0},
        },
    ))

    assert "size_is_implausible" not in normalized[0]


def test_implausible_rows_are_kept_out_of_automatic_selection() -> None:
    # 佇列 7 第五批：isFloorPlacedCatalogItem 純搬家到 scene_questionnaire_data.js，
    # 過濾條件改掃新檔；scene_v2.js 仍 import 它供自動選件使用。
    source = (
        STATIC_DIR / "scene_questionnaire_data.js"
    ).read_text(encoding="utf-8")

    # 前端自動選件與後端換小款兩條路徑都要濾掉。
    assert "candidate.size_is_implausible === true" in source
    # 換小款候選池在 /api/scene/layout；佇列 7 拆分第三批把它搬進 scene_api.py。
    scene_api = (SERVER_DIR / "scene_api.py").read_text(encoding="utf-8")
    assert 'not candidate.get("size_is_implausible")' in scene_api
