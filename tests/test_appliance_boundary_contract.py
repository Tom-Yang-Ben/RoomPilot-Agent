"""家電邊界契約：家電不進 2D/3D 自動配置。

契約原文（`AGENTS.md`）：

    冰箱、洗衣機等家電保留為問卷與 AI 生圖上下文，不能進入 2D/3D 自動配置或
    正式家具 API。

這支測試存在的原因是 2026-08-04 的檢視發現：後端唯一有寫的那條家電過濾，比對的
是 `refrigerator` / `washer` / `range-hood`——型錄從來沒有這三個名字（實際用語是
`fridge-freezer` / `washing-machine` / `extractor-hood`）。它之所以一直看起來有
效，是因為正式家具型錄本來就一件家電都沒有，不是因為它擋住了什麼；而第二條選件
路徑 `choose_furniture_items` 連那條寫錯用語的過濾都沒有。

所以這裡鎖的是**行為**（兩條路徑都要拒收）和**用語**（清單必須對得上型錄實況、
前後端必須同一份），不是原始碼字串。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.paths import STATIC_DIR
from backend.server.catalog_vocabulary import (
    APPLIANCE_MODEL_URL_MARKERS,
    APPLIANCE_TYPES,
    CATALOG_APPLIANCE_TYPES,
    is_appliance_item,
    is_appliance_type,
)
from backend.server.scene_service import (
    _WALL_ANCHORED_TYPES,
    _placement_candidates,
    choose_furniture_items,
    normalize_required_furniture,
    selected_furniture_items_from_questionnaire,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
APPLIANCE_CATALOG = PROJECT_DIR / "JSON" / "furniture" / "all_furniture_appliance_catalog.json"
VOCABULARY_SNAPSHOT = Path(__file__).resolve().parent / "data" / "catalog_vocabulary_snapshot.json"


def _furniture(furniture_id: str, normalized_type: str, **extra) -> dict:
    item = {
        "furniture_id": furniture_id,
        "normalized_type": normalized_type,
        "has_model": True,
        "model_url": f"https://cdn.example/models/{furniture_id}.glb",
        "primary_style": "scandinavian",
        "name_en": furniture_id,
        "name_zh_raw": furniture_id,
        "size_cm": {"width": 80, "depth": 60, "height": 80},
    }
    item.update(extra)
    return item


# --------------------------------------------------------------------------
# 用語：清單必須對得上型錄實況
# --------------------------------------------------------------------------


def test_appliance_vocabulary_covers_every_type_in_the_appliance_catalog() -> None:
    """`kind == "appliance"` 的每一種 type 都必須在清單裡。

    漏一種，那種家電就會靜靜地進到 2D/3D。
    """
    payload = json.loads(APPLIANCE_CATALOG.read_text(encoding="utf-8"))
    items = payload["items"]

    appliance_types = {item.get("type") for item in items if item.get("kind") == "appliance"}
    furniture_types = {item.get("type") for item in items if item.get("kind") == "furniture"}
    # `decoration` 與 `lamp` 在兩種 kind 底下都有大量資料，是標記重疊而不是家電。
    # 把它們當家電會整族踢掉擺飾與燈具，所以刻意排除——這也是為什麼這裡用差集，
    # 而不是直接拿 `kind == "appliance"` 當答案。
    unambiguous = {name for name in appliance_types if name and name not in furniture_types}

    assert unambiguous, "家電型錄讀不到任何 kind == appliance 的資料，測資可能換了 schema"
    missing = sorted(unambiguous - CATALOG_APPLIANCE_TYPES)
    assert not missing, f"家電型錄有這些型別，但過濾清單沒收：{missing}"


def test_no_official_furniture_type_is_treated_as_an_appliance() -> None:
    """反向保險：過濾不能吃掉任何一種正式家具。

    清單刻意收成超集（含舊 payload 的別名），所以這條必須跟著鎖，否則哪天型錄
    新增一種和家電同名的家具，選件會整族消失而且沒有任何訊號。
    """
    snapshot = json.loads(VOCABULARY_SNAPSHOT.read_text(encoding="utf-8"))
    catalog_types = set(snapshot["types"])

    assert catalog_types, "型錄快照是空的"
    overlap = sorted(catalog_types & APPLIANCE_TYPES)
    assert not overlap, f"這些正式家具型別會被家電過濾誤殺：{overlap}"


def test_appliance_cabinet_is_furniture_not_an_appliance() -> None:
    """電器櫃是櫃體家具。用語只差一個連字號，比對必須是精確的。"""
    assert is_appliance_type("appliance") is True
    assert is_appliance_type("appliance-cabinet") is False
    assert is_appliance_type("bathroom-vanity") is False
    assert is_appliance_type(" Fridge-Freezer ") is True
    assert is_appliance_type(None) is False


def test_appliances_are_recognised_by_delivery_url_when_the_type_is_missing() -> None:
    for marker in APPLIANCE_MODEL_URL_MARKERS:
        item = {"furniture_id": "x", "model_url": f"https://cdn.example{marker}whatever.glb"}
        assert is_appliance_item(item) is True, marker

    assert is_appliance_item({"furniture_id": "x", "model_url": "https://cdn.example/models/sofa.glb"}) is False
    assert is_appliance_item(None) is False


# --------------------------------------------------------------------------
# 行為：兩條選件路徑都要拒收
# --------------------------------------------------------------------------


def test_choose_furniture_items_never_returns_an_appliance() -> None:
    """第一條路徑。先前這條完全沒有家電過濾。"""
    furniture = [
        _furniture("sofa-1", "fabric-sofa"),
        _furniture("fridge-1", "fridge-freezer"),
        # 家電被標成家具型別、只有交付網址認得出來的情況。
        _furniture(
            "fridge-2",
            "sideboard",
            model_url="https://cdn.example/fi-fridges-freezers-500.glb",
        ),
    ]
    plan = {
        "style_id": "scandinavian",
        "required_furniture": ["fabric-sofa", "fridge-freezer", "refrigerator", "sideboard"],
    }

    chosen, unavailable = choose_furniture_items(plan, furniture)

    chosen_ids = {item["furniture_id"] for item in chosen}
    assert "sofa-1" in chosen_ids
    assert not any(is_appliance_item(item) for item in chosen)
    assert chosen_ids == {"sofa-1"}
    # 家電不是「缺貨」，不能混進 unavailable_types——那份清單會讓人以為補模型就好。
    assert "fridge-freezer" not in unavailable
    assert "refrigerator" not in unavailable
    # 但被家電佔用網址的 sideboard 確實是查無候選，這個要照實回報。
    assert "sideboard" in unavailable


def test_selected_furniture_from_questionnaire_drops_appliances() -> None:
    """第二條路徑。原本只認得舊名字，型錄實際用語會漏。"""
    catalog = [_furniture("sofa-1", "fabric-sofa")]
    questionnaire = {
        "selected_furniture": [
            {"furniture_id": "i-1", "catalog_furniture_id": "sofa-1", "normalized_type": "fabric-sofa"},
            # 型錄實際用語——修正前會通過。
            {"furniture_id": "i-2", "normalized_type": "fridge-freezer", "has_model": True,
             "model_url": "https://cdn.example/x.glb", "size_cm": {"width": 60, "depth": 60, "height": 180}},
            {"furniture_id": "i-3", "normalized_type": "washing-machine", "has_model": True,
             "model_url": "https://cdn.example/y.glb", "size_cm": {"width": 60, "depth": 60, "height": 85}},
            # 舊名字——修正前後都要擋住。
            {"furniture_id": "i-4", "normalized_type": "refrigerator", "has_model": True,
             "model_url": "https://cdn.example/z.glb", "size_cm": {"width": 60, "depth": 60, "height": 180}},
            # 只有交付網址認得出來。
            {"furniture_id": "i-5", "normalized_type": "sideboard", "has_model": True,
             "model_url": "https://cdn.example/models/ikea/appliance/foo.glb",
             "size_cm": {"width": 60, "depth": 60, "height": 85}},
        ]
    }

    selected = selected_furniture_items_from_questionnaire(questionnaire, catalog)

    assert [item["furniture_id"] for item in selected] == ["i-1"]


def test_user_confirmed_appliances_are_still_rejected() -> None:
    """使用者在 2D 手動放的家電也不能進 3D——契約沒有例外條款。"""
    questionnaire = {
        "selected_furniture": [
            {
                "furniture_id": "i-1",
                "normalized_type": "fridge-freezer",
                "position_locked": True,
                "user_specified": True,
                "source": "roompilot_2d",
                "size_cm": {"width": 60, "depth": 60, "height": 180},
            }
        ]
    }

    assert selected_furniture_items_from_questionnaire(questionnaire, []) == []


def test_normalize_required_furniture_drops_appliances() -> None:
    normalized = normalize_required_furniture(["fabric-sofa", "fridge-freezer", "refrigerator"], "living_room")

    assert normalized == ["fabric-sofa"]
    assert not any(is_appliance_type(name) for name in normalized)


def test_space_defaults_never_request_an_appliance() -> None:
    for space in ("living_room", "bedroom", "kitchen", "dining_room", "bathroom"):
        defaults = normalize_required_furniture([], space)
        offenders = [name for name in defaults if is_appliance_type(name)]
        assert not offenders, f"{space} 的預設家具含家電：{offenders}"


# --------------------------------------------------------------------------
# 擺放規則表不得再保留家電分支
# --------------------------------------------------------------------------


def test_wall_anchored_types_contain_no_appliance() -> None:
    offenders = sorted(name for name in _WALL_ANCHORED_TYPES if is_appliance_type(name))
    assert not offenders, f"_WALL_ANCHORED_TYPES 仍有家電殘留：{offenders}"


def test_placement_candidates_have_no_appliance_specific_branch() -> None:
    """家電不該有自己的擺放規則——有規則就代表某條路徑預期它會進來。"""
    args = (60.0, 60.0, 400.0, 320.0)
    baseline = _placement_candidates("__type_with_no_branch__", *args)

    for appliance in sorted(APPLIANCE_TYPES):
        assert _placement_candidates(appliance, *args) == baseline, (
            f"{appliance} 仍有專屬的擺放候選分支"
        )


# --------------------------------------------------------------------------
# 前後端同一份清單
# --------------------------------------------------------------------------


def _js_string_array(source: str, name: str) -> set[str]:
    match = re.search(rf"const {name} = (?:new Set\(\[|\[)(.*?)\]", source, re.DOTALL)
    assert match, f"scene_v2.js 找不到 {name}"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_frontend_appliance_list_matches_the_backend() -> None:
    """前端是使用者實際看到的最後一道防線，兩邊漏掉不同的名字比都沒有更難查。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert _js_string_array(source, "RETIRED_APPLIANCE_TYPES") == set(APPLIANCE_TYPES)
    assert _js_string_array(source, "RETIRED_APPLIANCE_MODEL_MARKERS") == set(APPLIANCE_MODEL_URL_MARKERS)
