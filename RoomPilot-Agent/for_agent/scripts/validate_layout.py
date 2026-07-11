#!/usr/bin/env python3
"""validate_layout.py — 對 furniture.json 做確定性幾何 + 規則驗證，輸出 validation_report.json。

檢查項（由 rule.json 的 type 驅動）：
  no_overlap          家具兩兩不重疊（地毯等平面墊底物排除）
  within_room         家具完全落在 room_polygon 內
  min_walkway         用「自由空間侵蝕」判斷是否留得下指定寬度的走道（預設 60cm）
  clearance_zone      家具宣告的使用淨空區未被侵占且未超出房間
  door_swing          門開合扇形內無家具
  window_access       窗前保留操作淨空
  max_footprint_ratio 單件占地不超過房間面積比例
需求層（讀 requirement.json 的 constraints）：
  requirement_exclude 放了被排除類別 → 違規
  requirement_include 缺少必含類別   → 違規

用法：
  python validate_layout.py --furniture furniture.json --architecture architecture.json \
      --rules rule.json --requirement requirement.json --out validation_report.json \
      [--iteration 0]
"""
from __future__ import annotations
import argparse, json, sys
from typing import Dict, List

try:
    from shapely.geometry import Point
    from shapely.ops import unary_union
except ImportError:
    Point = None

import geometry as geo

FLAT_CATEGORIES = {"地毯", "rug", "掛畫", "壁飾"}  # 墊底/壁掛，不參與重疊/走道遮擋


def _is_flat(item: Dict) -> bool:
    return item.get("category") in FLAT_CATEGORIES or item.get("dimensions", {}).get("height", 99) <= 3


def _rule_map(rules: Dict) -> Dict[str, Dict]:
    return {r["type"]: r for r in rules.get("rules", []) if r.get("enabled", True)}


def check_no_overlap(furn, rule):
    tol = rule.get("params", {}).get("tolerance_cm", 1.0)
    out = []
    solids = [f for f in furn if not _is_flat(f)]
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            a, b = solids[i], solids[j]
            inter = geo.furniture_footprint(a).intersection(geo.furniture_footprint(b))
            area = inter.area
            if area > tol * tol:  # 以容差平方當面積門檻
                out.append({
                    "object_id": a["id"], "rule_id": rule["id"], "type": "rule",
                    "severity": rule.get("severity", "error"),
                    "message": f'{a["id"]} 與 {b["id"]} 重疊 {area:.0f} cm²',
                    "metrics": {"overlap_area_cm2": round(area, 1), "other_id": b["id"]},
                    "suggested_fix": {"action": "move", "min_delta_cm": 30},
                })
    return out


def check_within_room(furn, rule, room):
    out = []
    for f in furn:
        fp = geo.furniture_footprint(f)
        if not room.buffer(0.5).contains(fp):
            outside = fp.difference(room).area
            out.append({
                "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                "severity": rule.get("severity", "error"),
                "message": f'{f["id"]} 有 {outside:.0f} cm² 超出房間範圍',
                "metrics": {"overlap_area_cm2": round(outside, 1)},
                "suggested_fix": {"action": "move", "min_delta_cm": 20},
            })
    return out


def check_min_walkway(furn, rule, room, doors):
    """自由空間侵蝕法：能否在家具之間留下寬度 >= min_distance 的通行區。

    做法：自由空間 = 房間 - 實體家具；把自由空間向內侵蝕 min_distance/2。
    若侵蝕後為空 → 完全沒有足夠寬的走道。
    若侵蝕後裂成多塊 → 有被切斷、走不到的孤立區。
    這自然容許「座位圍桌」這類緊鄰群組（它們只是障礙，只要繞得過去即通過）。
    """
    min_d = rule.get("params", {}).get("min_distance_cm", 60.0)
    solids = [geo.furniture_footprint(f) for f in furn if not _is_flat(f)]
    free = room
    if solids:
        free = room.difference(unary_union(solids))
    passages = free.buffer(-min_d / 2.0)
    out = []
    if passages.is_empty:
        out.append({
            "object_id": "__circulation__", "rule_id": rule["id"], "type": "rule",
            "severity": rule.get("severity", "error"),
            "message": f"房間內留不出寬度 {min_d:.0f}cm 的走道",
            "metrics": {"required_cm": min_d},
            "suggested_fix": {"action": "remove"},
        })
        return out
    # 侵蝕後元件數 > 1 表示走道被切斷
    parts = list(getattr(passages, "geoms", [passages]))
    parts = [p for p in parts if p.area > 25]  # 濾掉碎屑
    if len(parts) > 1:
        out.append({
            "object_id": "__circulation__", "rule_id": rule["id"], "type": "rule",
            "severity": rule.get("severity", "error"),
            "message": f"走道被切斷成 {len(parts)} 個區塊，存在無法以 {min_d:.0f}cm 走道到達的孤立區",
            "metrics": {"required_cm": min_d, "components": len(parts)},
            "suggested_fix": {"action": "move", "min_delta_cm": 20},
        })
    # 門口是否連到走道
    for d in doors:
        nx, ny = geo.inward_normal(d.get("rotation", 0.0)) if d.get("swing_in", True) \
            else geo.inward_normal(d.get("rotation", 0.0) + 180)
        pt = Point(d["position"]["x"] + nx * (min_d / 2 + 5),
                   d["position"]["y"] + ny * (min_d / 2 + 5))
        if passages.distance(pt) > min_d / 2:
            out.append({
                "object_id": d["id"], "rule_id": rule["id"], "type": "rule",
                "severity": rule.get("severity", "error"),
                "message": f'門 {d["id"]} 前方沒有連到 {min_d:.0f}cm 走道',
                "metrics": {"required_cm": min_d},
                "suggested_fix": {"action": "move", "min_delta_cm": 20},
            })
    return out


def check_clearance_zone(furn, rule, room):
    out = []
    solids = [(f, geo.furniture_footprint(f)) for f in furn if not _is_flat(f)]
    for f in furn:
        for zone in f.get("clearance_zones", []):
            zp = geo.clearance_zone_polygon(f, zone)
            if not room.buffer(0.5).contains(zp):
                out.append({
                    "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                    "severity": rule.get("severity", "error"),
                    "message": f'{f["id"]} 的 {zone["anchor"]} 淨空區超出房間',
                    "metrics": {"required_cm": zone["depth"]},
                    "suggested_fix": {"action": "move", "min_delta_cm": zone["depth"]},
                })
            for other, ofp in solids:
                if other["id"] == f["id"]:
                    continue
                inter = zp.intersection(ofp).area
                if inter > 25:
                    out.append({
                        "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                        "severity": rule.get("severity", "error"),
                        "message": f'{f["id"]} 的 {zone["anchor"]} 淨空區被 {other["id"]} 侵占',
                        "metrics": {"overlap_area_cm2": round(inter, 1), "other_id": other["id"]},
                        "suggested_fix": {"action": "move", "min_delta_cm": 20},
                    })
    return out


def check_door_swing(furn, rule, doors):
    out = []
    solids = [(f, geo.furniture_footprint(f)) for f in furn if not _is_flat(f)]
    for d in doors:
        swing = geo.door_swing_polygon(d)
        for f, fp in solids:
            inter = swing.intersection(fp).area
            if inter > 25:
                out.append({
                    "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                    "severity": rule.get("severity", "error"),
                    "message": f'{f["id"]} 擋住門 {d["id"]} 的開合範圍',
                    "metrics": {"overlap_area_cm2": round(inter, 1), "other_id": d["id"]},
                    "suggested_fix": {"action": "move", "min_delta_cm": 30},
                })
    return out


def check_window_access(furn, rule, windows):
    clr = rule.get("params", {}).get("clearance_cm", 40.0)
    out = []
    solids = [(f, geo.furniture_footprint(f)) for f in furn if not _is_flat(f)]
    for w in windows:
        # 窗前矩形淨空：沿窗法線向房間內 clr 深，寬=窗寬
        nx, ny = geo.inward_normal(w.get("rotation", 0.0))
        cx = w["position"]["x"] + nx * clr / 2.0
        cy = w["position"]["y"] + ny * clr / 2.0
        # 窗沿牆方向的寬 = width；垂直方向 = clr
        zone = geo.footprint(cx, cy, w["width"], clr, w.get("rotation", 0.0))
        for f, fp in solids:
            if fp.intersection(zone).area > 25:
                out.append({
                    "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                    "severity": rule.get("severity", "warning"),
                    "message": f'{f["id"]} 擋住窗 {w["id"]} 前方 {clr:.0f}cm 淨空',
                    "metrics": {"required_cm": clr, "other_id": w["id"]},
                    "suggested_fix": {"action": "move", "min_delta_cm": clr},
                })
    return out


def check_footprint_ratio(furn, rule, room):
    ratio = rule.get("params", {}).get("max_ratio", 0.35)
    ra = room.area
    out = []
    for f in furn:
        if _is_flat(f):
            continue
        a = geo.furniture_footprint(f).area
        if ra > 0 and a / ra > ratio:
            out.append({
                "object_id": f["id"], "rule_id": rule["id"], "type": "rule",
                "severity": rule.get("severity", "warning"),
                "message": f'{f["id"]} 占地 {a/ra*100:.0f}% 超過上限 {ratio*100:.0f}%',
                "metrics": {"measured_cm": round(a, 1)},
                "suggested_fix": {"action": "replace"},
            })
    return out


def check_requirements(furn, requirement):
    out = []
    if not requirement:
        return out
    c = requirement.get("constraints", {})
    exclude = set(c.get("exclude_categories", []))
    include = set(c.get("include_categories", []))
    present = {f.get("category") for f in furn}
    for f in furn:
        if f.get("category") in exclude:
            out.append({
                "object_id": f["id"], "rule_id": "requirement_exclude", "type": "requirement",
                "severity": "error",
                "message": f'{f["id"]} 屬於被排除類別「{f.get("category")}」',
                "metrics": {}, "suggested_fix": {"action": "remove"},
            })
    for cat in include:
        if cat not in present:
            out.append({
                "object_id": "__missing__", "rule_id": "requirement_include", "type": "requirement",
                "severity": "error",
                "message": f'缺少必含類別「{cat}」', "metrics": {},
                "suggested_fix": {"action": "replace"},
            })
    return out


def validate(furniture, architecture, rules, requirement, iteration=0):
    if Point is None:
        raise RuntimeError("需要 shapely：pip install shapely")
    furn = furniture["furniture"]
    room = geo.room_polygon(architecture)
    doors = architecture.get("doors", [])
    windows = architecture.get("windows", [])
    rmap = _rule_map(rules)

    violations: List[Dict] = []
    if "no_overlap" in rmap:
        violations += check_no_overlap(furn, rmap["no_overlap"])
    if "within_room" in rmap:
        violations += check_within_room(furn, rmap["within_room"], room)
    if "min_walkway" in rmap:
        violations += check_min_walkway(furn, rmap["min_walkway"], room, doors)
    if "clearance_zone" in rmap:
        violations += check_clearance_zone(furn, rmap["clearance_zone"], room)
    if "door_swing" in rmap:
        violations += check_door_swing(furn, rmap["door_swing"], doors)
    if "window_access" in rmap:
        violations += check_window_access(furn, rmap["window_access"], windows)
    if "max_footprint_ratio" in rmap:
        violations += check_footprint_ratio(furn, rmap["max_footprint_ratio"], room)
    violations += check_requirements(furn, requirement)

    errors = [v for v in violations if v.get("severity") == "error"]
    warnings = [v for v in violations if v.get("severity") == "warning"]
    return {
        "passed": len(errors) == 0,
        "iteration": iteration,
        "summary": {"total": len(violations), "errors": len(errors), "warnings": len(warnings)},
        "violations": violations,
    }


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description="家具布置幾何/規則驗證")
    ap.add_argument("--furniture", required=True)
    ap.add_argument("--architecture", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--requirement", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--iteration", type=int, default=0)
    args = ap.parse_args(argv)

    report = validate(_load(args.furniture), _load(args.architecture), _load(args.rules),
                      _load(args.requirement) if args.requirement else None, args.iteration)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    s = report["summary"]
    print(f"[validate] passed={report['passed']} errors={s['errors']} warnings={s['warnings']} "
          f"→ {args.out}")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
