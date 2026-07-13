"""DXF -> 3D floor-plan JSON.

ezdxf flattens CAD entities into 2D segments tagged wall/window/door by layer;
shapely buffers the wall centrelines into a solid wall-mass polygon (this both
bridges the small corner gaps in real CAD and merges double-line walls), so the
frontend extrudes real solid walls and the polygon's holes fall out as rooms.
Units in DXF files are unreliable (scan: INSUNITS mostly 'feet' but extents imply
inches/mm), so proportions are preserved exactly and real-world metres are a
guess with a manual override (`scale_m`). Wall thickness is the second knob:
raise it to merge wider double-line walls (and thus close rooms).
"""
from __future__ import annotations
import os, glob, tempfile
import ezdxf
from ezdxf import path as ez_path
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

# Layer-name keyword classifiers (multilingual incl. CJK), matched as substrings
# of the lowercased layer name. Order matters: window/door checked before wall.
WIN_KW  = ("window", "win", "glaz", "glass", "窗", "fenetre", "fenster", "ventana")
DOOR_KW = ("door", "門", "门", "porte", "tur", "puerta", "porta")
WALL_KW = ("wall", "牆", "墙", "mur", "wand", "muro", "pared", "parede", "стен")

# DXF $INSUNITS code -> metres-per-unit. None where unitless/unknown.
INSUNITS_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 8: 2.54e-8}

WALL_HEIGHT = 2.7    # default storey height (m)
WALL_THICK  = 0.18   # default wall thickness (m); the merge/calibration knob
DEFAULT_SPAN = 12.0  # fallback: normalize plan's longer side to this many metres
MIN_ROOM_M2 = 1.5    # drop wall-mass holes smaller than a real room


def classify(layer: str) -> str | None:
    l = (layer or "").lower()
    if any(k in l for k in WIN_KW):  return "window"
    if any(k in l for k in DOOR_KW): return "door"
    if any(k in l for k in WALL_KW): return "wall"
    return None


def _entity_segments(e, dist):
    """Flatten a single LEAF entity to ((x,y),(x,y)) segments. Best-effort.
    Container types (INSERT/POLYLINE/MLINE) are exploded by `_collect`, not here,
    so that each leaf is classified by its own layer."""
    t = e.dxftype()
    try:
        if t == "LINE":
            s, en = e.dxf.start, e.dxf.end
            return [((s.x, s.y), (en.x, en.y))]
        if t in ("LWPOLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
            # ez_path.make_path handles bulges/curves and closes polylines; use it
            # uniformly because LWPolyline lost its own .flattening() in ezdxf 1.4.
            pts = [(v.x, v.y) for v in ez_path.make_path(e).flattening(dist)]
            return list(zip(pts, pts[1:]))
    except Exception:
        return []
    return []


def _hatch_rings(e, dist):
    """Boundary loops of a HATCH as point rings — the filled (solid) wall outline
    that LINE/LWPOLYLINE extraction misses."""
    out = []
    try:
        for p in ez_path.from_hatch(e):
            pts = [(v.x, v.y) for v in p.flattening(dist)]
            if len(pts) >= 3:
                out.append(pts)
    except Exception:
        pass
    return out


def _collect(msp, dist):
    """Walk modelspace, classifying each LEAF entity by ITS OWN layer — so window
    lines inside a block placed on another layer (e.g. on DIM1) are still found.
    Returns (segs, rings): line segments and HATCH boundary rings, each keyed by
    wall/window/door + 'all'."""
    segs = {"wall": [], "window": [], "door": [], "all": []}
    rings = {"wall": [], "window": [], "door": [], "all": []}

    def leaf(e):
        cat = classify(e.dxf.layer)
        if e.dxftype() == "HATCH":
            grp = _hatch_rings(e, dist)        # all loops of THIS hatch, kept grouped
            if grp:                            # so holes (inner loops) can be XOR-ed
                rings["all"].append(grp)
                if cat:
                    rings[cat].append(grp)
            return
        s = _entity_segments(e, dist)
        if not s:
            return
        segs["all"] += s
        if cat:
            segs[cat] += s

    def walk(e):
        if e.dxftype() in ("INSERT", "POLYLINE", "MLINE"):
            try:
                for ve in e.virtual_entities():
                    walk(ve)
            except Exception:
                pass
        else:
            leaf(e)

    for e in msp:
        walk(e)
    return segs, rings


def _symbol_tol(thickness, span_m=None):
    """符號聚類容差。窗/門符號的內部線距隨「圖的整體比例」縮放——固定容差在
    小跨距模型(如 mm 版 config 比例的 4m 圖)會把相鄰兩個符號黏成一個。
    以跨距/60 近似該圖的實際牆厚(典型 10~12m 圖 ≈ 0.18m 牆),與 thickness 取小。"""
    t_eff = thickness if not span_m else min(thickness, span_m / 60.0)
    return max(0.75 * t_eff, 0.02)


def _cluster_seg_groups(segs, tol):
    """以「膨脹外包框相交」把線段聚類成群,回傳 index 群清單。"""
    boxes = []
    for s in segs:
        x0, x1 = sorted((s["x1"], s["x2"]))
        z0, z1 = sorted((s["z1"], s["z2"]))
        boxes.append((x0 - tol, z0 - tol, x1 + tol, z1 + tol))

    def hits(a, b):
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    n = len(segs)
    seen = [False] * n
    groups = []
    for i in range(n):
        if seen[i]:
            continue
        stack, grp = [i], []
        seen[i] = True
        while stack:
            k = stack.pop()
            grp.append(k)
            for j in range(n):
                if not seen[j] and hits(boxes[k], boxes[j]):
                    seen[j] = True
                    stack.append(j)
        groups.append(grp)
    return groups


def _merge_window_segs(segs, thickness, span_m=None):
    """一扇窗在 CAD 裡常是多條平行玻璃線+端封口(PNG 管線輸出固定為 4+2 條),
    逐段各畫一個盒會重疊 z-fighting。聚類後每群(=一扇窗)輸出一條沿長邊的
    中心線段。單段自成一群 → 原樣輸出,原生單線窗不受影響。"""
    if not segs:
        return segs
    out = []
    for grp in _cluster_seg_groups(segs, _symbol_tol(thickness, span_m)):
        if len(grp) == 1:
            out.append(segs[grp[0]])         # 單段窗(含斜窗)原樣保留
            continue
        xs = [v for k in grp for v in (segs[k]["x1"], segs[k]["x2"])]
        zs = [v for k in grp for v in (segs[k]["z1"], segs[k]["z2"])]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        if (x1 - x0) >= (z1 - z0):           # 群外包框長邊 = 窗方向
            zc = (z0 + z1) / 2
            out.append({"x1": x0, "z1": zc, "x2": x1, "z2": zc})
        else:
            xc = (x0 + x1) / 2
            out.append({"x1": xc, "z1": z0, "x2": xc, "z2": z1})
    return out


def _process(doc, name, scale_m, thickness, height):
    msp = doc.modelspace()

    # Resolution for flattening curves: fine relative to drawing size.
    try:
        hmin, hmax = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        rough = max(abs(hmax[0] - hmin[0]), abs(hmax[1] - hmin[1])) if hmin and hmax else 1000
    except Exception:
        rough = 1000
    dist = min(max(rough / 2000.0, 0.02), 5.0)

    segs, rings = _collect(msp, dist)
    wall_segs = [s for s in (segs["wall"] or segs["all"]) if s[0] != s[1]]
    wall_rings = rings["wall"]
    fallback = not (segs["wall"] or wall_rings)
    if len(wall_segs) < 2 and not wall_rings:
        raise ValueError("no usable wall geometry in DXF")

    # --- scale: longer plan side -> metres (bbox over wall lines + hatch rings) -
    pts = ([p for s in wall_segs for p in s]
           + [p for grp in wall_rings for r in grp for p in r])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    longer_units = max(maxx - minx, maxy - miny) or 1.0
    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    factor = INSUNITS_M.get(insunits)

    if scale_m and scale_m > 0:
        unit, span_m, basis = scale_m / longer_units, scale_m, "manual"
    elif factor and 2.0 <= longer_units * factor <= 80.0:
        unit, span_m, basis = factor, longer_units * factor, f"insunits:{insunits}"
    else:
        unit, span_m, basis = DEFAULT_SPAN / longer_units, DEFAULT_SPAN, "normalized"

    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    def to_m(seglist):
        out = []
        for (x1, y1), (x2, y2) in seglist:
            d = {"x1": (x1 - cx) * unit, "z1": (y1 - cy) * unit,
                 "x2": (x2 - cx) * unit, "z2": (y2 - cy) * unit}
            if (d["x1"] - d["x2"]) ** 2 + (d["z1"] - d["z2"]) ** 2 > 1e-8:
                out.append(d)
        return out

    def group_segs(groups):                      # hatch loops -> closed segments
        out = []
        for grp in groups:
            for r in grp:
                out += list(zip(r, r[1:]))
                if len(r) > 2:
                    out.append((r[-1], r[0]))
        return out

    walls   = to_m(wall_segs)
    windows = _merge_window_segs(
        to_m(segs["window"] + group_segs(rings["window"])), thickness, span_m)
    doors   = to_m(segs["door"] + group_segs(rings["door"]))
    # 門符號(弧攤平後常是數十段)聚類成「幾組門」——stats 報組數才有意義,
    # doors 線段清單保留原樣供繪圖
    door_groups = len(_cluster_seg_groups(doors, _symbol_tol(thickness, span_m))) if doors else 0

    def ring(coords):
        return [[round(x, 3), round(z, 3)] for x, z in coords]

    def shoelace(r):
        a = 0.0
        for i in range(len(r) - 1):
            a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
        return abs(a)

    def hatch_region(grp):
        # even-odd fill: largest loop is the outline, inner loops are holes — XOR
        # them so a wall drawn as a frame (outer ring − room ring) stays hollow.
        region = None
        for r in sorted(grp, key=shoelace, reverse=True):
            if len(r) < 3:
                continue
            poly = Polygon([((x - cx) * unit, (y - cy) * unit) for x, y in r])
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            region = poly if region is None else region.symmetric_difference(poly)
        return region

    # solid wall mass = buffered wall centrelines  ∪  hatch fill regions.
    # Square caps (3) extend each segment by `half` so perpendicular walls overlap
    # into clean right-angle corners; mitre joins keep convex corners sharp.
    half = max(thickness, 0.04) / 2.0
    parts = []
    if walls:
        line_mass = unary_union(
            [LineString([(s["x1"], s["z1"]), (s["x2"], s["z2"])]) for s in walls]
        ).buffer(half, cap_style=3, join_style=2, mitre_limit=5.0)
        if not line_mass.is_empty:
            parts.append(line_mass)
    for grp in wall_rings:
        reg = hatch_region(grp)
        if reg is not None and not reg.is_empty and reg.area > 1e-6:
            parts.append(reg)
    if not parts:
        raise ValueError("no usable wall geometry in DXF")
    mass = unary_union(parts)
    if not mass.is_valid:
        mass = mass.buffer(0)
    geoms = list(mass.geoms) if mass.geom_type == "MultiPolygon" else (
        [] if mass.is_empty else [mass])
    wall_polys = [{"exterior": ring(g.exterior.coords),
                   "holes": [ring(r.coords) for r in g.interiors]} for g in geoms]

    bx0, bz0, bx1, bz1 = ((minx - cx) * unit, (miny - cy) * unit,
                          (maxx - cx) * unit, (maxy - cy) * unit)

    # The upload-preview API consumes centimetres and the browser draws
    # segments with `{ start: { x, z }, end: { x, z } }`.  Keep the parser's
    # internal metres-based representation, but expose a canonical client
    # representation here so `/api/upload` cannot silently fall back to a
    # default square when these fields are absent.
    def client_segments(seglist):
        return [
            {
                "start": {"x": round(s["x1"] * 100, 2), "z": round(s["z1"] * 100, 2)},
                "end": {"x": round(s["x2"] * 100, 2), "z": round(s["z2"] * 100, 2)},
            }
            for s in seglist
        ]

    wall_segments = client_segments(walls)
    door_segments = client_segments(doors)
    window_segments = client_segments(windows)
    # ponytail: floor is the bbox ground slab the frontend draws from `bbox`.
    # No room/footprint segmentation — robust per-room extraction from gappy CAD
    # needs a wall-graph solver, out of scope. `extent_area` is the plan's
    # bounding extent, not interior floor area.
    return {
        "name": name,
        "scale_basis": basis,
        "scale_m": round(span_m, 3),
        "wall_height": height,
        "wall_thickness": thickness,
        "fallback_all_walls": fallback,
        "width_cm": round((bx1 - bx0) * 100, 1),
        "depth_cm": round((bz1 - bz0) * 100, 1),
        "wall_segments": wall_segments,
        "plan_segments": wall_segments,
        "door_segments": door_segments,
        "window_segments": window_segments,
        "bbox": {"minx": bx0, "minz": bz0, "maxx": bx1, "maxz": bz1},
        "wall_polys": wall_polys,
        "windows": windows,
        "doors": doors,
        "stats": {"wall_segments": len(walls), "wall_hatches": len(wall_rings),
                  "wall_polys": len(wall_polys),
                  "windows": len(windows), "doors": door_groups,
                  "door_segments": len(doors),
                  "width_m": round(bx1 - bx0, 2), "depth_m": round(bz1 - bz0, 2),
                  "extent_area": round((bx1 - bx0) * (bz1 - bz0), 1)},
    }


def parse_dxf_file(path, scale_m=None, thickness=WALL_THICK, height=WALL_HEIGHT):
    doc = ezdxf.readfile(path)
    return _process(doc, os.path.basename(path), scale_m, thickness, height)


def parse_dxf_bytes(data: bytes, name, scale_m=None, thickness=WALL_THICK, height=WALL_HEIGHT):
    # round-trip through a temp file so ezdxf detects the DXF encoding itself
    with tempfile.NamedTemporaryFile("wb", suffix=".dxf", delete=False) as f:
        f.write(data); tmp = f.name
    try:
        return parse_dxf_file(tmp, scale_m, thickness, height)
    finally:
        os.unlink(tmp)


def list_plans(folder):
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.dxf")))


if __name__ == "__main__":
    # self-check: every bundled plan must yield walls; most must yield rooms.
    here = os.path.dirname(__file__)
    folder = os.path.normpath(os.path.join(here, "..", "..", "testdata", "pic", "temp"))
    files = list_plans(folder)
    assert files, f"no DXF files under {folder}"
    for name in files:
        r = parse_dxf_file(os.path.join(folder, name))
        s = r["stats"]
        assert s["wall_segments"] >= 2, f"{name}: no walls"
        assert s["wall_polys"] >= 1, f"{name}: wall buffering produced no solid"
        assert 1.0 <= r["scale_m"] <= 200.0, f"{name}: scale {r['scale_m']} m out of range"
        print(f"  OK  {name:46s} seg={s['wall_segments']:4d} poly={s['wall_polys']:3d} "
              f"win={s['windows']:3d} door={s['doors']:3d} "
              f"{s['width_m']:5.1f}x{s['depth_m']:4.1f}m span={r['scale_m']:5.1f}m {r['scale_basis']}")
    print(f"self-check passed: {len(files)} plans")
