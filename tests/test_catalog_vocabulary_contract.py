"""家具族系詞彙的跨層一致性契約。

房型詞彙曾有同一種病，已由 ``tests/test_room_type_vocabulary.py`` 以「正典 ＋
鎖住各消費層」治好。家具族系是完全相同的病，但先前沒有任何測試把這些表綁到型錄
實況——`FAMILY_CATALOG_FALLBACKS` 只被檢查「不自映射、不鏈式」，Kai 改一個分類名
會讓全部測試照樣綠，而線上安靜地少一件家具（QA 2026-08-04 的電器櫃、浴櫃、
高收納櫃）。

本檔把詞彙表分成三類，各用不同的標準檢查：

1. **檢索表**——值會直接拿去比對型錄欄位。裡面出現型錄沒有的名字＝該查詢必然
   0 筆。這類一律要求「型錄真的有、而且有可用模型」。
2. **族系表**——問卷與 2D 型庫的使用者用語，容許不是型錄名（``lounge-chair``、
   ``storage-cabinet``），但必須能經 ``catalog_types_for_family`` 解析到真型別，
   或明確登記在 ``FAMILIES_WITHOUT_CATALOG_MODELS``。
3. **標籤表**——只做顯示（``REPLACEMENT_TYPE_LABELS`` 還要涵蓋不進 2D/3D 的家電），
   死鍵無害，不在本契約內。

型錄實況取自 ``tests/data/catalog_vocabulary_snapshot.json``，而不是當場查資料庫，
因為 ``conftest.py`` 預設把型錄切成離線 JSON，而 **JSON 與 PostgreSQL 的詞彙並不
相同**（JSON 另有 ``cabinets-cupboard``、``planter``、``lamp``）。對 JSON 斷言會
讓 ``FAMILY_OF`` 的複數 ``cabinets-cupboard`` 看起來是好的——它在正式的 PostgreSQL
路徑上永遠 0 筆。快照是否過期由檔尾那條 postgres 測試負責。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from backend.agent.knowledge import FAMILY_OF, family_of
from backend.paths import STATIC_DIR
from backend.server.catalog_vocabulary import (
    FAMILIES_WITHOUT_CATALOG_MODELS,
    FAMILY_CATALOG_FALLBACKS,
    PLACEMENT_FAMILY_FALLBACKS,
    PLACEMENT_FAMILY_UNMAPPED,
    catalog_types_for_family,
    placement_family_for_type,
)
from backend.server.main import _AUTO_DECOR_TYPES
from backend.server.scene_service import FURNITURE_ALIASES, SPACE_DEFAULTS
from backend.spatial_data.rag.shortlist import (
    FAMILY_CATEGORY_OVERRIDES,
    categories_for_family,
)


SNAPSHOT = json.loads(
    (Path(__file__).parent / "data" / "catalog_vocabulary_snapshot.json").read_text(
        encoding="utf-8"
    )
)
# 只有「有可用模型」才算數：型錄有這一列但沒有 glb 時，第 6 步照樣選不到。
USABLE_TYPES = {
    name for name, counts in SNAPSHOT["types"].items() if counts["with_model"]
}
USABLE_CATEGORY_CODES = {
    name for name, counts in SNAPSHOT["category_codes"].items() if counts["with_model"]
}


def _block(source: str, start: str, end: str, origin: str) -> str:
    assert start in source, f"{origin}：找不到起始標記 {start!r}，本測試的解析已過期"
    return source.split(start, 1)[1].split(end, 1)[0]


def _quoted(text: str) -> set[str]:
    """取出型錄型別字面值。房型鍵、用途 id 與中文標籤不會落在這個字元集。"""
    return set(re.findall(r'"([a-z][a-z0-9-]*)"', text))


def _inner_arrays(block: str) -> set[str]:
    """最內層陣列字面值的內容——巢狀結構裡真正裝型別清單的那一層。"""
    tokens: set[str] = set()
    for literal in re.findall(r"\[([^\[\]]*)\]", block):
        tokens |= _quoted(literal)
    return tokens


def _layout2d() -> str:
    return (STATIC_DIR / "scene_layout2d.js").read_text(encoding="utf-8")


def _questionnaire_data() -> str:
    return (STATIC_DIR / "scene_questionnaire_data.js").read_text(encoding="utf-8")


def _scene_v2() -> str:
    return (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")


def frontend_2d_library_types() -> set[str]:
    block = _block(
        _layout2d(),
        "export const FURNITURE_2D_LIBRARY = Object.freeze([",
        "\n]);",
        "scene_layout2d.js",
    )
    found = set(re.findall(r'^\s+type: "([a-z0-9-]+)"', block, re.MULTILINE))
    assert found, "FURNITURE_2D_LIBRARY 解析失敗"
    return found


def frontend_modelless_families() -> tuple[str, ...]:
    block = _block(
        _layout2d(),
        "export const FAMILIES_WITHOUT_CATALOG_MODELS = Object.freeze([",
        "\n]);",
        "scene_layout2d.js",
    )
    return tuple(re.findall(r'"([a-z0-9-]+)"', block))


def retrieval_tables() -> dict[str, set[str]]:
    """值會拿去比對型錄 ``normalized_type`` 的表。"""
    routes = _block(
        _questionnaire_data(),
        "const CATALOG_RETRIEVAL_ROUTES = {",
        "\n};",
        "scene_questionnaire_data.js",
    )
    fallback_rules = _block(
        _questionnaire_data(),
        "const QUESTIONNAIRE_FALLBACK_CATALOG_RULES = Object.freeze({",
        "\n});",
        "scene_questionnaire_data.js",
    )
    purposes = _block(
        _scene_v2(),
        "const QUESTIONNAIRE_CATALOG_PURPOSES = Object.freeze({",
        "\n});",
        "scene_v2.js",
    )
    purpose_types = _block(
        _scene_v2(),
        "const QUESTIONNAIRE_CATALOG_PURPOSE_TYPES = Object.freeze({",
        "\n});",
        "scene_v2.js",
    )

    tables = {
        "CATALOG_RETRIEVAL_ROUTES.type": set(
            re.findall(r'\btype:\s*"([a-z0-9-]+)"', routes)
        ),
        "CATALOG_RETRIEVAL_ROUTES.types": _inner_arrays(routes),
        "QUESTIONNAIRE_FALLBACK_CATALOG_RULES.types": {
            token
            for literal in re.findall(r"\btypes:\s*\[([^\]]*)\]", fallback_rules)
            for token in _quoted(literal)
        },
        # 第三欄是 PURPOSE_TYPES 缺項時的後備型別清單，同樣比對 normalized_type。
        "QUESTIONNAIRE_CATALOG_PURPOSES[2]": _inner_arrays(purposes),
        "QUESTIONNAIRE_CATALOG_PURPOSE_TYPES": _inner_arrays(purpose_types),
        # 後端：族系後備的目標、軟裝自動選件、以及 Yen 摺疊表的型錄側。
        "FAMILY_CATALOG_FALLBACKS.values": {
            target for targets in FAMILY_CATALOG_FALLBACKS.values() for target in targets
        },
        # light 角色的候選來自燈具表而不是家具型錄，鍵空間不同，由
        # test_auto_decor_light_lane_draws_from_the_lighting_table 單獨檢查。
        "_AUTO_DECOR_TYPES": {
            item
            for role, types in _AUTO_DECOR_TYPES.items()
            if role != "light"
            for item in types
        },
        "FAMILY_OF.keys": set(FAMILY_OF),
    }
    for name, tokens in tables.items():
        assert tokens, f"{name} 解析為空，本測試的解析已過期"
    return tables


def questionnaire_families() -> set[str]:
    """問卷與 2D 型庫會送進第 6 步的族系名。"""
    return (
        {family for families in SPACE_DEFAULTS.values() for family in families}
        | set(FURNITURE_ALIASES.values())
        | frontend_2d_library_types()
    )


def test_every_floor_furniture_type_has_a_placement_anchor_or_a_recorded_reason() -> None:
    """型錄的落地家具都要有類型錨點,否則會站在房間中央不貼牆。

    錨點鏈認的是族系粗分名;型錄用細分名。缺對照的型別不會擺放失敗、也不會缺件,
    只會安靜地停在房間正中心加 3×3 網格上,所以沒有測試盯著就不會有人發現。
    """
    from backend.catalog.placement_surface import placement_surface_for
    from backend.server.scene_service import _placement_candidates

    def has_type_anchor(name: str) -> bool:
        # 有專屬錨點的型別,候選會比「只有房間正中心 + 3×3 網格」多。
        generic = _placement_candidates("__no_such_type__", 60, 40, 600, 500)
        return len(_placement_candidates(name, 60, 40, 600, 500)) > len(generic)

    missing = sorted(
        name
        for name, counts in SNAPSHOT["category_codes"].items()
        if counts["with_model"]
        and placement_surface_for(name) == "floor"
        and not has_type_anchor(name)
        and name not in PLACEMENT_FAMILY_UNMAPPED
    )
    assert not missing, (
        f"這些落地家具型別沒有擺放錨點,會停在房間中央:{missing}。"
        "請在 PLACEMENT_FAMILY_FALLBACKS 補對照,或連同理由列進 PLACEMENT_FAMILY_UNMAPPED。"
    )


def test_placement_family_fallbacks_point_at_types_that_have_anchors() -> None:
    """對照表的目的地必須真的有錨點,否則等於沒對照。"""
    from backend.server.scene_service import _placement_candidates

    generic = len(_placement_candidates("__no_such_type__", 60, 40, 600, 500))
    for source, target in PLACEMENT_FAMILY_FALLBACKS.items():
        assert len(_placement_candidates(target, 60, 40, 600, 500)) > generic, (
            f"{source} 對到 {target},但 {target} 自己就沒有類型錨點"
        )
        assert placement_family_for_type(source) == target


def test_placement_family_fallbacks_only_map_types_the_catalog_has() -> None:
    """對照表只該收型錄真的存在的細分名,不然是在替不存在的資料做決定。"""
    unknown = sorted(set(PLACEMENT_FAMILY_FALLBACKS) - USABLE_CATEGORY_CODES - USABLE_TYPES)
    assert not unknown, f"這些型別不在型錄快照裡:{unknown}"


def test_retrieval_tables_only_reference_types_the_catalog_actually_has() -> None:
    """檢索表裡的型錄名必須真的存在且有模型，否則那條查詢必然 0 筆。"""
    offenders: list[str] = []
    for table, tokens in retrieval_tables().items():
        missing = sorted(tokens - USABLE_TYPES)
        if missing:
            offenders.append(f"{table}：{', '.join(missing)}")
    assert not offenders, "檢索表引用了型錄沒有的分類：\n" + "\n".join(offenders)


def test_auto_decor_light_lane_draws_from_the_lighting_table() -> None:
    """自動裝飾的燈具角色不能掃家具型錄——正式型錄一盞燈都沒有。

    燈具 2026-07-30 從 ``furniture_items`` 移走、2026-08-02 以
    ``roompilot.lighting_assets_current`` 接回，但一直沒有 payload 管道，於是
    ``scene_api`` 明明會請求 light 角色（``requested_roles.append("light")``、
    ``for role in ("rug", "plant", "light")``），卻永遠只在
    ``decor_summary.skipped`` 留下一行。離線 JSON 型錄剛好殘留 ``lamp``，所以
    預設測試模式下看不出來。

    這條鎖住三件事：型別名一致、候選確實走燈具表、而且家具型錄裡沒有它。
    """
    from backend.catalog.lighting_repository import FLOOR_LAMP_TYPE
    from backend.server.main import _auto_decor_candidates

    # `lamp` 是離線 JSON 型錄殘留的型別，正式型錄沒有；它只在資料庫不可用時
    # 頂替，所以刻意不列入 retrieval_tables 的型錄實況檢查。
    assert _AUTO_DECOR_TYPES["light"] == (FLOOR_LAMP_TYPE, "lamp")
    assert FLOOR_LAMP_TYPE not in USABLE_TYPES, (
        "落地燈進了家具型錄，請重新決定 light 角色的候選來源"
    )
    assert "lamp" not in USABLE_TYPES, (
        "家具型錄出現 lamp，請重新檢查燈具到底該由哪張表提供"
    )
    assert SNAPSHOT["lighting_types"]["floor"]["with_model"] > 0, (
        "燈具表沒有可用的落地燈，light 角色會整個落空"
    )


def test_auto_decor_lighting_types_stay_inside_the_lighting_vocabulary() -> None:
    """燈具表只接落地燈；其餘燈種各有歸屬，不該悄悄被拉進落地擺設。

    table 要桌面宿主（檯面吸附 lane）、pendant／downlight／track／wall 是天花與
    壁掛，屬於第 8 步的 render_context，不進 2D/3D 落地配置。
    """
    from backend.catalog.lighting_repository import (
        FLOOR_LIGHTING_TYPE,
        FLOOR_LAMP_TYPE,
    )

    assert FLOOR_LIGHTING_TYPE in SNAPSHOT["lighting_types"]
    assert FLOOR_LAMP_TYPE not in SNAPSHOT["lighting_types"], (
        "FLOOR_LAMP_TYPE 是 payload 用語，不該與燈具表的 lighting_type 混用"
    )


def test_shortlist_overrides_reference_category_codes_that_exist() -> None:
    """shortlist 查的是 ``furniture_catalog_current.category_code``，不是
    ``normalized_type``。兩者現在恆等（改名收在匯入層的
    ``CATEGORY_CODE_OVERRIDES``），但沒有任何機制保證它們會一直恆等——這條與
    ``test_retrieval_tables_only_reference_types_the_catalog_actually_has`` 分開
    檢查，就是為了在它們再度分岔時指出是哪一邊。"""
    targets = {
        target for targets in FAMILY_CATEGORY_OVERRIDES.values() for target in targets
    }
    missing = sorted(targets - USABLE_CATEGORY_CODES)
    assert not missing, f"FAMILY_CATEGORY_OVERRIDES 指向不存在的 category_code：{missing}"


def test_every_questionnaire_family_resolves_or_is_declared_modelless() -> None:
    """族系可以不是型錄名，但必須解析得到候選，否則 2D 有、3D 永遠缺席。"""
    unresolved: list[str] = []
    for family in sorted(questionnaire_families()):
        if family in FAMILIES_WITHOUT_CATALOG_MODELS:
            continue
        if not (set(catalog_types_for_family(family)) & USABLE_TYPES):
            unresolved.append(family)
    assert not unresolved, (
        "這些族系在型錄查無候選，且沒有登記在 FAMILIES_WITHOUT_CATALOG_MODELS："
        f"{unresolved}"
    )


def test_declared_modelless_families_really_have_no_catalog_models() -> None:
    """型錄補進模型之後，這張表要跟著縮小——留著會讓 UI 一直掛「無 3D」角標。"""
    resolved = sorted(
        family
        for family in FAMILIES_WITHOUT_CATALOG_MODELS
        if set(catalog_types_for_family(family)) & USABLE_TYPES
    )
    assert not resolved, (
        f"這些族系型錄已經有模型，請從 FAMILIES_WITHOUT_CATALOG_MODELS 移除：{resolved}"
    )


def test_frontend_and_backend_agree_on_modelless_families() -> None:
    """2D 型庫的「無 3D」角標與第 6 步的 unavailable_types 必須是同一份名單。"""
    assert frontend_modelless_families() == tuple(FAMILIES_WITHOUT_CATALOG_MODELS)


def test_both_backend_resolution_chains_reach_the_same_catalog_items() -> None:
    """同一個問卷字串，兩條後端路徑用的是不同的解析鏈：

    - ``scene_service.choose_furniture_items`` 走 ``catalog_types_for_family``，
      比對 payload 的 ``normalized_type``；
    - ``spatial_data/rag/shortlist`` 走 ``family_of`` → ``categories_for_family``，
      比對 ``category_code``。

    兩條今天答案一致是巧合，不是由構造保證。在統一之前，至少要讓分歧被抓到：
    每個族系在兩條鏈上都要解析得到候選，且候選必須有交集。
    """
    # 兩個鍵空間目前恆等，但這裡刻意保留換算層：它們曾經分岔（planter ↔
    # flower-pots-planter），再分岔時這條測試要能指出交集為空，而不是自己爆掉。
    to_normalized = {
        code: code
        for code in set(SNAPSHOT["category_codes"]) | set(SNAPSHOT["types"])
    }
    divergent: list[str] = []
    for family in sorted(questionnaire_families()):
        if family in FAMILIES_WITHOUT_CATALOG_MODELS:
            continue
        scene_types = set(catalog_types_for_family(family)) & USABLE_TYPES
        shortlist_codes = set(categories_for_family(family_of(family)))
        shortlist_types = {
            to_normalized.get(code, code)
            for code in shortlist_codes & USABLE_CATEGORY_CODES
        }
        if not shortlist_types:
            divergent.append(f"{family}：shortlist 解析為空（scene_service 得到 {sorted(scene_types)}）")
        elif not scene_types & shortlist_types:
            divergent.append(
                f"{family}：scene_service {sorted(scene_types)} 與 "
                f"shortlist {sorted(shortlist_types)} 沒有交集"
            )
    assert not divergent, "兩條解析鏈分歧：\n" + "\n".join(divergent)


def test_frontend_retrieval_routes_agree_with_the_backend_family_mapping() -> None:
    """前端 ``CATALOG_RETRIEVAL_ROUTES`` 與後端族系映射不得各說各話。

    兩邊語意刻意不同——後端 ``catalog_types_for_family`` 是「族系本身查無候選才
    退而求其次」，前端路由則是一次撈整個族系的所有成員（沙發要四種一起撈）——
    所以不能斷言相等。可以斷言的是：前端撈的每一型，都得是這個族系的後備目標，
    或是 ``family_of()`` 認定屬於這個族系的型別。否則兩邊會在同一個族系上取到
    不同的候選集，而使用者看到的是第 6 步與問卷推薦對不上。
    """
    routes = _block(
        _questionnaire_data(),
        "const CATALOG_RETRIEVAL_ROUTES = {",
        "\n};",
        "scene_questionnaire_data.js",
    )
    entries = re.findall(
        r'^  "?([a-z0-9-]+)"?:\s*\{(.*?)^  \},?$', routes, re.MULTILINE | re.DOTALL
    )
    assert entries, "CATALOG_RETRIEVAL_ROUTES 逐條解析失敗"

    offenders: list[str] = []
    for family, body in entries:
        # 只取 type/types 兩個欄位——`query: "wardrobe"` 這種單字查詢字串長得像
        # 型別，全文抓取會把它誤判成路由目標。
        wanted = set(re.findall(r'\btype:\s*"([a-z0-9-]+)"', body))
        for literal in re.findall(r"\btypes:\s*\[([^\]]*)\]", body):
            wanted |= _quoted(literal)
        allowed = set(catalog_types_for_family(family)) | {
            catalog_type
            for catalog_type in USABLE_TYPES
            if family_of(catalog_type) == family
        }
        if not wanted & USABLE_TYPES:
            offenders.append(f"{family}：路由查不到任何有模型的型別")
        elif not wanted <= allowed:
            offenders.append(f"{family}：路由撈 {sorted(wanted - allowed)}，不屬於這個族系")
    assert not offenders, "前端路由與後端族系映射分歧：\n" + "\n".join(offenders)


def test_every_catalog_type_with_models_is_reachable_or_declared() -> None:
    """型錄有貨、卻沒有任何路徑拿得到，是詞彙漂移的另一半。

    先前有 12 型（``display-cabinet`` 38 筆、``room-divider`` 17 筆、兒童家具三型
    等）不在任何一張表裡：使用者只有在 /library 逐頁翻才找得到。這條讓「新增型別
    卻忘了掛上任何 lane」不能靜悄悄地發生——要嘛接進某張表，要嘛明確登記為
    手動挑選。
    """
    from backend.catalog.placement_surface import (
        _FLOOR_COVERING_TYPES,
        _TABLETOP_TYPES,
        _WALL_TYPES,
    )
    from backend.server.catalog_vocabulary import MANUAL_ONLY_TYPES

    reachable: set[str] = set()
    for tokens in retrieval_tables().values():
        reachable |= tokens
    for family in questionnaire_families():
        reachable |= set(catalog_types_for_family(family))
    for types in _AUTO_DECOR_TYPES.values():
        reachable |= set(types)
    # 檯面小物、壁掛、地面覆蓋物走自己的擺放 lane，不經族系選件。
    surface_lanes = _TABLETOP_TYPES | _WALL_TYPES | _FLOOR_COVERING_TYPES

    orphans = sorted(
        USABLE_TYPES - reachable - surface_lanes - set(MANUAL_ONLY_TYPES)
    )
    assert not orphans, (
        "型錄有模型但沒有任何選件路徑拿得到，也沒登記在 MANUAL_ONLY_TYPES："
        f"{orphans}"
    )


def test_manual_only_types_are_not_already_reachable() -> None:
    """型別接上 lane 之後要從 MANUAL_ONLY_TYPES 移除，免得清單變成謊言。"""
    from backend.server.catalog_vocabulary import MANUAL_ONLY_TYPES

    reachable: set[str] = set()
    for tokens in retrieval_tables().values():
        reachable |= tokens
    for family in questionnaire_families():
        reachable |= set(catalog_types_for_family(family))
    already = sorted(set(MANUAL_ONLY_TYPES) & reachable)
    assert not already, f"這些型別已經接上選件路徑，請從 MANUAL_ONLY_TYPES 移除：{already}"


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_CATALOGS") != "1",
    reason="需要本機 PostgreSQL 型錄；設 ROOMPILOT_TEST_POSTGRES_CATALOGS=1 才跑",
)
def test_light_role_actually_returns_a_lamp_in_postgres_mode() -> None:
    """接上 lane 之後，正式模式下燈具角色必須真的選得出東西。

    預設測試模式走離線 JSON 型錄，`lamp` 那條退路會讓 light 角色看起來是通的；
    真正要驗的是 PostgreSQL 模式——那才是先前永遠落空的路徑。
    """
    from backend.catalog.lighting_repository import FLOOR_LAMP_TYPE
    from backend.server.main import _auto_decor_catalog_item

    selected = _auto_decor_catalog_item("light", "scandinavian")
    assert selected is not None, "PostgreSQL 模式下燈具角色仍然落空"
    assert selected["normalized_type"] == FLOOR_LAMP_TYPE
    assert selected["catalog_scope"] == "kai_lighting_assets"
    assert str(selected["model_url"]).startswith("https://")
    size = selected["size_cm"]
    assert all(size[key] for key in ("width", "depth", "height")), (
        f"落地燈缺尺寸，引擎會算不出佔位：{selected['furniture_id']}"
    )


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_CATALOGS") != "1",
    reason="需要本機 PostgreSQL 型錄；設 ROOMPILOT_TEST_POSTGRES_CATALOGS=1 才跑",
)
def test_snapshot_still_matches_the_live_catalog() -> None:
    """快照過期的話，上面每一條契約都是在對舊型錄斷言。

    重新產生：``python scripts/dump_catalog_vocabulary.py``
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.dump_catalog_vocabulary import collect_vocabulary

    live = collect_vocabulary()
    assert set(live["types"]) == set(SNAPSHOT["types"]), (
        "型錄的 normalized_type 集合已變動，請重新產生快照"
    )
    assert set(live["category_codes"]) == set(SNAPSHOT["category_codes"]), (
        "型錄的 category_code 集合已變動，請重新產生快照"
    )
