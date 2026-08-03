"""逐房牆材質要在三條牆路徑都生效（2026-08-03 Ben：牆的顏色不一樣）。

根因是主路徑（連續牆體 buildWallMass、門窗補牆 buildStandaloneOpeningAssemblies）
呼叫端傳全域 wallMaterial，surface_overrides 的逐房材質只剩逐段 fallback 在用；
另有硬編碼奶油白踢腳板與端帽中點材質的接縫。解法移植自 bella-test1 的
wallMaterialResolver 改良，但她掛在逐段 BoxGeometry 路線，連續牆體改用
逐三角形採樣分材質 group。外牆固定材質是既有契約
（test_exterior_walls_keep_fixed_material...），她的「外牆繼承房間材質」不搬。
"""

from backend.paths import STATIC_DIR


VIEWER = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

RESOLVER = VIEWER.split("function wallMaterialResolver", 1)[1].split(
    "function wallSegmentPoint", 1
)[0]
MASS_BUILDER = VIEWER.split("function assignRoomFacesToWallMass", 1)[1].split(
    "function buildWallMassTopCaps", 1
)[0]
STANDALONE = VIEWER.split("function buildStandaloneOpeningAssemblies", 1)[1].split(
    "function buildStructuralMembers", 1
)[0]
WALL_BUILDER = VIEWER.split("function buildSegmentWalls", 1)[1].split(
    "function buildOpeningAssembly", 1
)[0]


def test_resolver_dedupes_autosaved_room_overrides_keeping_latest() -> None:
    # 問卷自動存檔會讓同一房間出現多筆 surface_overrides，只有最新那筆算數。
    assert "const canonicalOverrides = new Map();" in RESOLVER
    assert "canonicalOverrides.set(roomId, override);" in RESOLVER
    assert "const overrides = [...canonicalOverrides.values()];" in RESOLVER


def test_resolver_falls_back_to_nearest_room_instead_of_default_material() -> None:
    # 牆面貼在房界上、辨識多邊形會漂移幾公分；找不到就取最近房界 28cm 內的
    # 房間。掉回預設材質就是「這面牆顏色跟鄰居不一樣」的來源。
    assert "const distanceToRoomBoundary = (point, override)" in RESOLVER
    assert "const containedOverrideAtPoint" in RESOLVER
    assert "nearest.distance <= 28" in RESOLVER


def test_resolver_carries_side_finishes_onto_wall_end_caps() -> None:
    # BoxGeometry slots 0/1 是端帽；留在中點材質會在房角露出淡色接縫。
    assert (
        "positiveSide.clone(), negativeSide.clone(), interior.clone(),\n"
        "        interior.clone(), positiveSide.clone(), negativeSide.clone(),"
    ) in RESOLVER


def test_wall_mass_assigns_room_materials_per_face() -> None:
    # 連續牆體一團鄰接多個房間，逐三角形沿法線採樣 16cm 分材質 group；
    # 只認「點真的在房間裡」（materialAtPoint 不帶 28cm 容錯），外牆側與
    # 頂/底蓋維持全屋預設。幾何仍是後端開槽的 wall_polys。
    assert "resolveWallMaterial.materialAtPoint" in RESOLVER
    assert "resolveWallMaterial.defaultMaterial = defaultMaterial;" in RESOLVER
    assert "materialAtPoint(sample)" in MASS_BUILDER
    assert "geometry.clearGroups();" in MASS_BUILDER
    assert "geometry.addGroup(runStart * 3" in MASS_BUILDER
    assert "resolver.defaultMaterial" in MASS_BUILDER
    # 呼叫端傳 resolver，三條路徑共用同一份逐房材質快取。
    assert "const roomWallMaterial = wallMaterialResolver(" in VIEWER
    assert VIEWER.count("roomWallMaterial,") >= 3


def test_opening_infill_walls_resolve_per_side_like_their_host_wall() -> None:
    # 門楣/窗台補牆按面解析：外牆側固定外牆材質、室內側採樣所屬房間，
    # 不再整塊套全域材質。
    assert "const openingSectionMaterials = ()" in STANDALONE
    assert "exteriorWallOutwardSideSign(" in STANDALONE
    assert "wallMaterial.faceMaterials(opening, sign)" in STANDALONE
    assert "openingSectionMaterials()," in STANDALONE


def test_baseboard_follows_wall_finish_instead_of_hardcoded_cream() -> None:
    # 踢腳板原本硬編碼 0xf5f1ea 且外凸 1.1cm，每面牆腳掛一條異色帶。
    assert "0xf5f1ea" not in VIEWER
    assert "wallThickness + 2.2" not in WALL_BUILDER
    assert "wallThickness + 0.2" in WALL_BUILDER
    assert "wallMaterial.faceMaterials(segment, exteriorSideSign)\n          : material.clone();" in WALL_BUILDER
