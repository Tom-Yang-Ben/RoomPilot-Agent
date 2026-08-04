"""`frontend/geometry_core.js` 的契約，以及它取代的三份實作的差分驗證。

統一前，point-in-polygon 在前端有三份各自獨立的實作：

- `scene_plan_geometry.js` 的 `pointInPolygonCm`——`{x, y}`、有輸入守衛
- `scene_camera.js` 的 `pointInPolygon`——`{x, y}`、邊界含入（逐房鏡頭需要）
- `engineering.js` 的 `pointInPolygon`——`{x_cm, y_cm}`、成果報告頁的獨立 bundle

三者的射線法公式其實逐項等價，差別只在邊界處理與守衛。這裡把三份原始碼原樣嵌進
測試，對同一組多邊形與取樣點逐點比對——重構宣稱「行為零變更」，就必須由這支測試
證明，而不是由閱讀者相信。

差分測試的另一個作用是防止反向漂移：將來若有人「順手優化」核心的射線法，這裡會
立刻紅，因為原始實作是寫死的基準。
"""

from __future__ import annotations

import json
import re

from test_scene_workflow import run_workflow_script
from backend.paths import STATIC_DIR


CORE_MODULE = STATIC_DIR / "geometry_core.js"


# 統一前的三份實作，原樣保留作為差分基準。不要「順手」跟著核心一起改。
LEGACY_IMPLEMENTATIONS = """
function legacyPlanGeometry(point, polygon) {
  if (!point || !Array.isArray(polygon) || polygon.length < 3) return false;
  let inside = false;
  for (let index = 0, previousIndex = polygon.length - 1; index < polygon.length; previousIndex = index, index += 1) {
    const current = polygon[index];
    const previous = polygon[previousIndex];
    const intersects = (
      (Number(current.y) > point.y) !== (Number(previous.y) > point.y)
      && point.x < (
        ((Number(previous.x) - Number(current.x)) * (point.y - Number(current.y)))
        / ((Number(previous.y) - Number(current.y)) || 1e-9)
        + Number(current.x)
      )
    );
    if (intersects) inside = !inside;
  }
  return inside;
}

function legacyPointOnSegment(point, start, end, tolerance = 0.01) {
  const cross = (point.y - start.y) * (end.x - start.x)
    - (point.x - start.x) * (end.y - start.y);
  if (Math.abs(cross) > tolerance) return false;
  const dot = (point.x - start.x) * (end.x - start.x)
    + (point.y - start.y) * (end.y - start.y);
  if (dot < -tolerance) return false;
  const lengthSquared = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
  return dot <= lengthSquared + tolerance;
}

function legacyCamera(point, polygon) {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const start = polygon[previous];
    const end = polygon[index];
    if (legacyPointOnSegment(point, start, end)) return true;
    const crosses = (end.y > point.y) !== (start.y > point.y)
      && point.x < ((start.x - end.x) * (point.y - end.y)) / (start.y - end.y) + end.x;
    if (crosses) inside = !inside;
  }
  return inside;
}

function legacyEngineering(point, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
    const xi = polygon[i].x_cm; const yi = polygon[i].y_cm;
    const xj = polygon[j].x_cm; const yj = polygon[j].y_cm;
    const intersects = ((yi > point.y_cm) !== (yj > point.y_cm))
      && (point.x_cm < ((xj - xi) * (point.y_cm - yi)) / ((yj - yi) || 1e-9) + xi);
    if (intersects) inside = !inside;
  }
  return inside;
}

function legacyCameraDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx ** 2 + dy ** 2;
  if (!lengthSquared) return Math.hypot(point.x - start.x, point.y - start.y);
  const ratio = Math.max(0, Math.min(1,
    ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return Math.hypot(point.x - (start.x + ratio * dx), point.y - (start.y + ratio * dy));
}

function legacyStructureDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared <= 1e-9) return Math.hypot(point.x - start.x, point.y - start.y);
  const t = Math.max(0, Math.min(
    1,
    ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared,
  ));
  return Math.hypot(point.x - (start.x + dx * t), point.y - (start.y + dy * t));
}
"""


# 凸四邊形、L 形凹多邊形、含斜邊的梯形。取樣網格會踩到頂點、邊上與內外。
POLYGONS = {
    "square": [(0, 0), (200, 0), (200, 200), (0, 200)],
    "l_shape": [(0, 0), (300, 0), (300, 100), (100, 100), (100, 300), (0, 300)],
    "trapezoid": [(0, 0), (400, 0), (300, 250), (50, 250)],
}


# 取樣網格在 JS 內生成——`run_workflow_script` 是 `node --eval`，腳本走命令列，
# 兩千多個點序列化成 JSON 會撞上 Windows 的命令列長度上限（WinError 206）。
SAMPLE_GRID = """
const coordinates = [];
for (let step = 0; step <= 16; step += 1) {
  const base = step * 25;               // 25 的倍數會踩到頂點與邊上
  coordinates.push(base, base + 0.01, base - 0.01);   // 掃過邊界兩側
}
const points = coordinates.flatMap((x) => coordinates.map((y) => [x, y]));
"""


def _run(script: str) -> dict:
    return run_workflow_script(
        f"import * as core from {json.dumps(CORE_MODULE.as_uri())};\n"
        f"{LEGACY_IMPLEMENTATIONS}\n{script}"
    )


def test_core_matches_all_three_legacy_point_in_polygon_implementations() -> None:
    polygons = {
        name: [{"x": x, "y": y} for x, y in points]
        for name, points in POLYGONS.items()
    }

    result = _run(
        f"""
        const polygons = {json.dumps(polygons)};
        {SAMPLE_GRID}
        const mismatches = {{ plan: [], camera: [], engineering: [] }};
        let compared = 0;

        for (const [name, polygon] of Object.entries(polygons)) {{
          const cmPolygon = polygon.map((p) => ({{ x_cm: p.x, y_cm: p.y }}));
          for (const [x, y] of points) {{
            compared += 1;
            const point = {{ x, y }};

            // 邊界關閉：對應 scene_plan_geometry 與 engineering 的原始語意。
            const plain = core.pointInPolygon(point, polygon);
            if (plain !== legacyPlanGeometry(point, polygon)) {{
              mismatches.plan.push([name, x, y]);
            }}
            if (plain !== legacyEngineering({{ x_cm: x, y_cm: y }}, cmPolygon)) {{
              mismatches.engineering.push([name, x, y]);
            }}

            // 邊界含入：對應 scene_camera 的原始語意。
            const bounded = core.pointInPolygon(point, polygon, {{ includeBoundary: true }});
            if (bounded !== legacyCamera(point, polygon)) {{
              mismatches.camera.push([name, x, y]);
            }}
          }}
        }}

        console.log(JSON.stringify({{
          compared,
          plan: mismatches.plan.slice(0, 5),
          camera: mismatches.camera.slice(0, 5),
          engineering: mismatches.engineering.slice(0, 5),
          counts: {{
            plan: mismatches.plan.length,
            camera: mismatches.camera.length,
            engineering: mismatches.engineering.length,
          }},
        }}));
        """
    )

    assert result["compared"] > 7000, "取樣點太少，差分測試沒有說服力"
    assert result["counts"] == {"plan": 0, "camera": 0, "engineering": 0}, (
        f"核心與原始實作不一致：{result}"
    )


def test_boundary_flag_is_the_only_difference_between_the_two_modes() -> None:
    """關閉 includeBoundary 時，邊上的點依標準射線法判定（可能內可能外）；
    開啟時一律算室內。這是 scene_camera 與其餘兩者唯一的語意差。"""
    result = _run(
        """
        const square = [
          { x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 200 }, { x: 0, y: 200 },
        ];
        const onEdge = [
          { x: 0, y: 100 }, { x: 200, y: 100 },
          { x: 100, y: 0 }, { x: 100, y: 200 },
          { x: 0, y: 0 }, { x: 200, y: 200 },
        ];
        console.log(JSON.stringify({
          bounded: onEdge.map((p) => core.pointInPolygon(p, square, { includeBoundary: true })),
          plain: onEdge.map((p) => core.pointInPolygon(p, square)),
          interior: core.pointInPolygon({ x: 100, y: 100 }, square),
          exterior: core.pointInPolygon({ x: 300, y: 100 }, square),
        }));
        """
    )

    assert result["bounded"] == [True] * 6, "邊界含入模式下，邊上與角上都必須算室內"
    assert result["interior"] is True
    assert result["exterior"] is False
    assert any(value is False for value in result["plain"]), (
        "預設模式若把所有邊界點都算室內，就不是標準射線法了"
    )


def test_guards_reject_malformed_input_instead_of_throwing() -> None:
    result = _run(
        """
        const square = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }];
        console.log(JSON.stringify({
          nullPoint: core.pointInPolygon(null, square),
          undefinedPolygon: core.pointInPolygon({ x: 1, y: 1 }, undefined),
          twoVertices: core.pointInPolygon({ x: 1, y: 1 }, [{ x: 0, y: 0 }, { x: 1, y: 1 }]),
          emptyPolygon: core.pointInPolygon({ x: 1, y: 1 }, []),
          stringCoordinates: core.pointInPolygon({ x: "5", y: "5" }, square),
          emptyArea: core.polygonArea([]),
          nullArea: core.polygonArea(null),
        }));
        """
    )

    assert result["nullPoint"] is False
    assert result["undefinedPolygon"] is False
    assert result["twoVertices"] is False
    assert result["emptyPolygon"] is False
    assert result["stringCoordinates"] is True, "座標一律經 Number() 轉型"
    assert result["emptyArea"] == 0
    assert result["nullArea"] == 0


def test_polygon_area_is_orientation_independent() -> None:
    result = _run(
        """
        const clockwise = [
          { x: 0, y: 0 }, { x: 0, y: 200 }, { x: 300, y: 200 }, { x: 300, y: 0 },
        ];
        const counterClockwise = [...clockwise].reverse();
        console.log(JSON.stringify({
          clockwise: core.polygonArea(clockwise),
          counterClockwise: core.polygonArea(counterClockwise),
          triangle: core.polygonArea([{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 0, y: 100 }]),
        }));
        """
    )

    assert result["clockwise"] == 60_000
    assert result["counterClockwise"] == 60_000
    assert result["triangle"] == 5_000


def test_distance_to_segment_matches_both_legacy_copies() -> None:
    """統一後的退化守衛採 `<= 1e-9`（原 scene_structure_geometry 的寫法）。

    scene_camera 原本是 `!lengthSquared`，只擋長度剛好為 0 的邊——所以兩者只在
    邊長介於 0 與約 3e-5 之間時分歧。這裡把一般情形釘成完全一致，並單獨標出那個
    亞微米級的角落，讓將來讀這段的人不必自己重推。
    """
    result = _run(
        """
        const cases = [
          [{ x: 50, y: 50 }, { x: 0, y: 0 }, { x: 100, y: 0 }],
          [{ x: -30, y: 40 }, { x: 0, y: 0 }, { x: 100, y: 0 }],
          [{ x: 150, y: 10 }, { x: 0, y: 0 }, { x: 100, y: 0 }],
          [{ x: 20, y: 20 }, { x: 0, y: 0 }, { x: 100, y: 100 }],
          [{ x: 5, y: 5 }, { x: 10, y: 10 }, { x: 10, y: 10 }],
        ];
        const degenerate = [{ x: 5, y: 0 }, { x: 0, y: 0 }, { x: 1e-6, y: 0 }];
        console.log(JSON.stringify({
          matchesCamera: cases.every(([p, a, b]) =>
            core.distanceToSegment(p, a, b) === legacyCameraDistance(p, a, b)),
          matchesStructure: cases.every(([p, a, b]) =>
            core.distanceToSegment(p, a, b) === legacyStructureDistance(p, a, b)),
          core: core.distanceToSegment(...degenerate),
          legacyCamera: legacyCameraDistance(...degenerate),
          legacyStructure: legacyStructureDistance(...degenerate),
        }));
        """
    )

    assert result["matchesCamera"] is True
    assert result["matchesStructure"] is True
    # 亞微米級退化邊：核心跟隨 structure 版，與 camera 版不同。
    assert result["core"] == result["legacyStructure"]
    assert result["core"] != result["legacyCamera"]


def test_geometry_core_has_no_imports_so_both_page_chains_can_share_it() -> None:
    """核心一旦 import 任何東西，engineering.js 就會被牽進對方的相依圖——
    共用它的前提就沒了。"""
    source = CORE_MODULE.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith(("//", "*", "/*"))
    )

    assert not re.search(r"^\s*import\b", code, re.MULTILINE), "geometry_core.js 必須零依賴"
    assert not re.search(r"\bimport\s*\(", code), "動態 import 同樣會拉進相依"
    assert "document" not in code and "window" not in code, "核心不得碰 DOM"
