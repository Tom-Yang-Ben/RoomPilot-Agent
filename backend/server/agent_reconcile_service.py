"""step6 ↔ agent 管線的擺放對帳（資料轉接 + 重現 + 比對）。

同一批「step6 選定的家具」餵給兩條路徑,比對結果:

- Path A（正式 step6）:`scene_service.generate_layout` —— 逐件靠 backend.engine
  柵格擺位。
- Path B（agent 管線）:`PlaceFurnitureTool` → engine 逐件擺放,再 `EngineValidateTool`
  以 engine 重新驗證。

**資料轉接**:server 選件 dict（furniture_id / normalized_type / size_cm）→ agent
`FurnitureListDoc`（ChosenItem）。這是**選件層**轉接,不碰座標,所以不受兩邊座標系
差異影響。

**為何比覆蓋率＋合法性,不比座標**:兩條路徑座標系不同（step6 為房中心原點、
rotation 與引擎反向;引擎為角原點),且兩邊的合法性其實呼叫同一支
`backend.engine.clearance.check_placement_with_clearance` —— 直接比座標既脆弱又
多半是恆等式。真正有訊號的對帳是「同一批件,兩條路徑各自合法擺出的家族覆蓋是否一致」。

# ponytail: 以下三項刻意未做,需要時再補:
#  (1) 把 step6 已擺好的座標轉回引擎 placed row（角原點/中心原點/旋轉反向換算）
#      再交 agent 驗證 —— 脆弱且與 engine 檢查恆等,價值低。
#  (2) hint 邏輯完全對齊:step6 用 placement_hints 成組,本處 agent 走 free 擺放,
#      家族覆蓋通常仍一致（副件改靠牆而非貼主件),但位置會不同。
#  (3) 多房:目前逐房比對,多房由呼叫端迴圈。選件階段（RAG/LLM）不在此比較。
"""
from __future__ import annotations

from ..agent.documents import ChosenItem, FurnitureListDoc, LayoutDoc, LayoutRoom
from ..agent.knowledge import family_of
from ..agent.place import placement_hints
from ..agent.tools.engine_validate import EngineValidateTool
from ..agent.tools.place_furniture import PlaceFurnitureTool
from ..engine.models import Room
from .scene_service import generate_layout


def _clean_size(size: dict | None) -> tuple[float, float, float]:
    """型錄尺寸防禦性清洗（兩條路徑餵同一份 size_cm,缺欄才用同一組 fallback）。"""
    size = size or {}

    def pick(key: str, fallback: float) -> float:
        try:
            value = float(size.get(key))
        except (TypeError, ValueError):
            value = 0.0
        return value if value > 0 else fallback

    return pick("width", 120.0), pick("depth", 60.0), pick("height", 80.0)


def _to_furniture_list(room_id: str, items: list[dict]) -> FurnitureListDoc:
    """資料轉接:server 選件 dict → agent FurnitureListDoc（座標不轉,只轉選件語意）。"""
    chosen: list[ChosenItem] = []
    for index, item in enumerate(items):
        width, depth, height = _clean_size(item.get("size_cm"))
        clearance = item.get("clearance") if isinstance(item.get("clearance"), dict) else None
        chosen.append(
            ChosenItem(
                item_id=str(item.get("instance_id") or item.get("furniture_id") or f"{room_id}:{index + 1}"),
                catalog_id=str(item.get("catalog_furniture_id") or item.get("furniture_id") or ""),
                room_id=room_id,
                name=str(item.get("name_zh_raw") or item.get("furniture_id") or "家具"),
                category=str(item.get("normalized_type") or ""),
                width_cm=width,
                depth_cm=depth,
                height_cm=height,
                clearance=clearance,
            )
        )
    return FurnitureListDoc(variant="A", strategy="reconcile", items=chosen)


def _families(types) -> set[str]:
    return {family_of(t) for t in types if t}


def reconcile_room(room_id: str, width_cm: float, depth_cm: float, items: list[dict]) -> dict:
    """同一批件跑兩條路徑,回傳覆蓋率＋合法性對帳報告。"""
    width_cm = float(width_cm)
    depth_cm = float(depth_cm)
    items = [dict(it) for it in (items or [])]
    if not items:
        raise ValueError("items 不可為空（需要 step6 選定的家具清單，server 物件格式）")

    layout = LayoutDoc(
        rooms=[LayoutRoom(room_id=room_id, name=room_id, width_cm=width_cm, depth_cm=depth_cm)]
    )

    # Path B —— agent 管線：資料轉接 → 擺放 → 驗證
    furniture_list = _to_furniture_list(room_id, items)
    scene_b = PlaceFurnitureTool().run(layout, furniture_list)
    violations_b = EngineValidateTool().run(layout, scene_b)
    placed_b = scene_b.placed_in(room_id)
    failed_b = (scene_b.rooms.get(room_id) or {}).get("failed") or []

    # Path A —— 重現 step6：同一批件、同一房殼，走 generate_layout
    room_engine = Room(width=width_cm, depth=depth_cm, walls=[])
    objects_a = generate_layout(width_cm, depth_cm, items, room=room_engine, hints=placement_hints(items))
    placed_a = [o for o in objects_a if not o.get("placement_failed")]
    failed_a = [o for o in objects_a if o.get("placement_failed")]

    fam_a = _families(o.get("normalized_type") for o in placed_a)
    fam_b = _families(r.get("type") for r in placed_b)
    consistent = fam_a == fam_b and not violations_b

    return {
        "room_id": room_id,
        "item_count": len(items),
        "consistent": consistent,
        "step6": {
            "placed": len(placed_a),
            "failed": len(failed_a),
            "families": sorted(fam_a),
            "failed_items": [
                {
                    "id": o.get("furniture_id"),
                    "type": o.get("normalized_type"),
                    "reason": o.get("placement_reason"),
                }
                for o in failed_a
            ],
        },
        "agent": {
            "placed": len(placed_b),
            "failed": len(failed_b),
            "families": sorted(fam_b),
            "failed_items": [{"id": f.get("id"), "reason": f.get("reason")} for f in failed_b],
            "hard_violations": [
                {"item_id": v.item_id, "reason": v.reason} for v in violations_b
            ],
        },
        "divergence": {
            "families_only_in_step6": sorted(fam_a - fam_b),
            "families_only_in_agent": sorted(fam_b - fam_a),
        },
        "note": (
            "座標系不同（step6 房中心原點 vs 引擎角原點、旋轉反向），故對帳比"
            "『家族覆蓋＋合法性』，不比座標；選件階段（RAG/LLM）與 hint 成組邏輯"
            "不在此比較，見檔頭 ponytail 註記。"
        ),
    }
