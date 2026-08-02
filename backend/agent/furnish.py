"""逐房擺位主流程 —— 依 `docs/擺位計算邏輯.md` §6.2、§8、§9.4(公分版)。

核心紀律:**LLM 只決定「選哪些件」,所有座標由確定性演算法算出。**
本模組無隨機、無時間依賴、無並行;同輸入必得同輸出(複現條件見規格 §12)。
"""
from __future__ import annotations

from typing import Sequence

from ..engine.layout_model import Placement, RoomContext, Template
from ..engine.obb import Obb, facing_deg, front_vector
from ..engine.rules import (
    CHAIR_GAP_CM,
    RULE_KINDS_BY_LABEL,
    RULES,
    WALL_GAP_CM,
    anchor_ts,
    candidate_edges,
)
from .clearance import clearance_free

# ── §8.1 副件 → 可接受主件(依序取第一個已就位者)────────────────────
COMPANION_OF: dict[str, tuple[str, ...]] = {
    "nightstand": ("bed",),
    "coffee_table": ("sofa",),
    "tv": ("sofa",),
    "dining_chair": ("dining_table",),
    "office_chair": ("office_desk", "desk"),
}

# 房型規則的主件 —— §9.4 覆核時「保留,只記 log」的那一類
ANCHOR_KINDS = frozenset({"sofa", "bed", "dining_table"})


def _free_with_clearance(ctx: RoomContext, tpl: Template, obb: Obb, rotation: float, index: int) -> bool:
    """本體合法 ∧ 開合淨空合法。"""
    if not ctx.free(tpl, obb):
        return False
    probe = Placement(
        id=f"__probe-{tpl.kind}-{index}",
        kind=tpl.kind,
        cx=obb.cx,
        cy=obb.cy,
        w=tpl.w,
        d=tpl.d,
        rotation_deg=rotation,
        height=tpl.height,
        name=tpl.name,
    )
    return clearance_free(ctx.grid, ctx.masks.low, probe, ctx.placements)


def try_against_wall_clear(
    ctx: RoomContext,
    tpl: Template,
    index: int = 0,
) -> Placement | None:
    """§6.2 agent 版靠牆掃描:錨點序列與引擎版同源,但**逐點多驗開合淨空**。

    不能沿用引擎版再補驗 —— 它只回第一個點,淨空不過就沒有下一個候選可要。
    無開合需求的 kind,兩版行為完全一致(淨空檢查恆過)。
    """
    for edge in candidate_edges(ctx.edges, tpl.w):
        normal = edge.inward()
        rotation = facing_deg(normal)
        off = tpl.d / 2 + WALL_GAP_CM
        for t in anchor_ts(edge.length, tpl.w):
            px, py = edge.point_at(t)
            cx, cy = px + normal[0] * off, py + normal[1] * off
            obb = Obb.from_deg(cx, cy, tpl.w, tpl.d, rotation)
            if _free_with_clearance(ctx, tpl, obb, rotation, index):
                return Placement(
                    id=f"{ctx.room_id}-{tpl.kind}-{index}",
                    kind=tpl.kind,
                    cx=cx,
                    cy=cy,
                    w=tpl.w,
                    d=tpl.d,
                    rotation_deg=rotation,
                    height=tpl.height,
                    name=tpl.name,
                )
    return None


def try_facing_anchor(ctx: RoomContext, tpl: Template, anchor: Placement) -> Placement | None:
    """§8.1 主件正前方、面向主件。"""
    f = front_vector(anchor.rotation_deg)
    off = anchor.d / 2 + tpl.d / 2 + CHAIR_GAP_CM
    cx = anchor.cx + f[0] * off
    cy = anchor.cy + f[1] * off
    rotation = facing_deg((-f[0], -f[1]))       # 回頭面向主件(= anchor 角度 + 180°)
    obb = Obb.from_deg(cx, cy, tpl.w, tpl.d, rotation)
    if not _free_with_clearance(ctx, tpl, obb, rotation, 0):
        return None
    return Placement(
        id=f"{ctx.room_id}-{tpl.kind}-0",
        kind=tpl.kind,
        cx=cx,
        cy=cy,
        w=tpl.w,
        d=tpl.d,
        rotation_deg=rotation,
        height=tpl.height,
        name=tpl.name,
    )


def _place_companion(ctx: RoomContext, tpl: Template, rule_kinds: frozenset[str]) -> None:
    """§8.1 副件:只准相對主件擺,三種情形一律略過並記 log,**寧缺勿亂**。

    絕不退回泛用靠牆 —— 這是「床頭櫃不該流落到離床很遠的牆邊」的根治點。
    副件恆擺 1 件(count 不展開):現行唯一策略是「主件正前」,一個主件前只有一個位。
    """
    if tpl.kind in rule_kinds:
        # 2. 該 kind 已被房型規則試過 —— 規則失敗表示相對位不可行,重試只會得到錯位置
        ctx.notes.append(f"略過「{tpl.label}」:房型規則已試過相對位且失敗")
        return
    anchor = None
    for anchor_kind in COMPANION_OF.get(tpl.kind, ()):
        anchor = ctx.find(anchor_kind)
        if anchor is not None:
            break
    if anchor is None:
        # 1. 本房主件未就位
        ctx.notes.append(f"略過「{tpl.label}」:本房沒有可依附的主件")
        return
    placement = try_facing_anchor(ctx, tpl, anchor)
    if placement is None:
        # 3. 相對位本體或淨空不可行
        ctx.notes.append(f"略過「{tpl.label}」:「{anchor.label}」正前方放不下")
        return
    ctx.commit(placement)


def _place_generic(ctx: RoomContext, tpl: Template) -> None:
    """§8.2 泛用件:逐件靠牆(含淨空)×count,**放不下即止**。

    主件放不下時,自足泛用件仍獨立擺出 —— 整房清空對使用者更差。
    """
    for index in range(max(1, tpl.count)):
        placement = try_against_wall_clear(ctx, tpl, index)
        if placement is None:
            ctx.notes.append(f"略過「{tpl.label}」第 {index + 1} 件:找不到合法靠牆位")
            return
        ctx.commit(placement)


def _resolve_clearance(ctx: RoomContext, rule_consumed: tuple[str, ...]) -> list[Template]:
    """§9.4 房型規則產物的淨空覆核(``reverse=False``)。

    房型規則層不認得淨空,由本層收尾。回傳「被移除、需退回剩件分流」的 template。
    """
    requeue: list[Template] = []
    for placement in list(ctx.placements):
        conflict = clearance_conflict_for(ctx, placement)
        if conflict is None:
            continue
        if placement.kind in ANCHOR_KINDS:
            # 主件:保留,只記 log —— 整房沒了主件對使用者更差
            ctx.notes.append(f"保留「{placement.label}」但淨空不足:{conflict}")
            continue
        ctx.remove(placement.id)
        if placement.kind in COMPANION_OF:
            # 副件:相對主件是它唯一合法位,寧缺勿亂
            ctx.notes.append(f"移除「{placement.label}」:{conflict}")
            continue
        ctx.notes.append(f"移除「{placement.label}」改由靠牆掃描重擺:{conflict}")
        requeue.append(
            Template(
                kind=placement.kind,
                w=placement.w,
                d=placement.d,
                height=placement.height,
                count=1,
                name=placement.name,
            )
        )
    return requeue


def clearance_conflict_for(ctx: RoomContext, placement: Placement) -> str | None:
    """對既有配置逐件覆核(``reverse=False``,避免重複噪音)。"""
    from .clearance import clearance_conflict

    return clearance_conflict(
        ctx.grid,
        ctx.masks.low,
        placement,
        [p for p in ctx.placements if p.id != placement.id],
        reverse=False,
    )


def furnish_room(ctx: RoomContext, templates: Sequence[Template]) -> RoomContext:
    """一間房的完整擺位(規格 §1.2 的 ⑤⑥⑦ 步)。

    ``templates`` 的順序即擺放順序(規格 §12 第 3 點:選件順序即擺放順序)。
    """
    by_kind: dict[str, Template] = {}
    for tpl in templates:
        by_kind.setdefault(tpl.kind, tpl)

    rule = RULES.get(ctx.label)
    consumed: tuple[str, ...] = ()
    if rule is not None:
        consumed = rule(ctx, by_kind)

    requeue = _resolve_clearance(ctx, consumed)

    rule_kinds = RULE_KINDS_BY_LABEL.get(ctx.label, frozenset())
    rest = [tpl for tpl in templates if tpl.kind not in consumed] + requeue
    # §8 非副件先擺 —— 副件的主件可能還在剩件裡(辦公椅在等它的書桌)
    rest.sort(key=lambda tpl: tpl.kind in COMPANION_OF)

    for tpl in rest:
        if tpl.kind in COMPANION_OF:
            _place_companion(ctx, tpl, rule_kinds)
        else:
            _place_generic(ctx, tpl)
    return ctx
