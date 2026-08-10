// 房屋 3D 場景外殼 — 純函式幾何層。
//
// 依 docs/3D房屋場景建置流程.md 實作:幾何運算全在本模組(可用 node 單測,
// 見 tests/test_scene_shell_geometry.py)。scene_viewer.js 已改回內聯外殼
// 管線(feat/scene3d-modeling-swap),本模組目前僅由 node 測試消費,保留
// 為文件化的參考實作。所有數值常數集中在 DEFAULT_SCENE_CONFIG。
//
// 座標約定(對映文件 §1):本 repo 前端已是公分制、{x, z} 世界對齊座標
// (z 已於後端邊界翻轉一次)。文件的平面 (x,y) → 世界 [x,0,-y] 在此等價於
// (x,z) → [x,0,z],線段方向角 atan2(dy,dx) ≡ atan2(-dz,dx)。
//
// 本模組不 import three;多邊形牆以描述 {region, heightCm} 交由 viewer 擠出。
import {
  doorOpeningForWallTopology,
  openingWallInterval,
  wallSectionSpan,
} from "./scene_architecture.js?v=sha256-7932d83e3afd";
import { windowOpeningMetrics } from "./scene_window_types.js?v=sha256-990e2abb3240";

export const DEFAULT_SCENE_CONFIG = Object.freeze({
  wallHeightCm: 280,
  wallThicknessCm: 12,
  window: Object.freeze({ sillCm: 90, headCm: 210 }),
  door: Object.freeze({ sillCm: 0, headCm: 210 }),
  glassThicknessCm: 2,
  epsilonCm: 0.2,
  frameAllowanceCm: 0.6,
  minWindowWidthCm: 30,
  minOpeningIntervalWidthCm: Object.freeze({ door: 68, window: 50 }),
  clusterDistanceCm: 30,
  clusterAngleDeg: 10,
  profile: Object.freeze({
    normalSpreadMaxCm: 40,
    endDistanceMaxCm: 50,
    minThicknessCm: 3,
  }),
  floorMarginCm: 50,
  floorThicknessCm: 5,
  topCapHeightCm: 2.5,
  minSegmentLengthCm: 4,
  junction: Object.freeze({ minGapCm: 0.8, maxGapFactor: 2, maxGapFloorCm: 36 }),
  minCameraSpanCm: 100,
  cameraDistFactor: 1.2,
  axesSizeCm: 200,
});

export function shellConfig(overrides = {}) {
  const wallHeightCm = Number(overrides.wallHeightCm);
  return Object.freeze({
    ...DEFAULT_SCENE_CONFIG,
    ...overrides,
    wallHeightCm: Number.isFinite(wallHeightCm)
      ? Math.max(wallHeightCm, 210)
      : DEFAULT_SCENE_CONFIG.wallHeightCm,
    window: Object.freeze({ ...DEFAULT_SCENE_CONFIG.window, ...overrides.window }),
    door: Object.freeze({ ...DEFAULT_SCENE_CONFIG.door, ...overrides.door }),
    minOpeningIntervalWidthCm: Object.freeze({
      ...DEFAULT_SCENE_CONFIG.minOpeningIntervalWidthCm,
      ...overrides.minOpeningIntervalWidthCm,
    }),
    profile: Object.freeze({ ...DEFAULT_SCENE_CONFIG.profile, ...overrides.profile }),
    junction: Object.freeze({ ...DEFAULT_SCENE_CONFIG.junction, ...overrides.junction }),
  });
}

export function worldFromPlan(x, z) {
  return [Number(x) || 0, 0, Number(z) || 0];
}

export function segmentRotationY(dx, dz) {
  return Math.atan2(-dz, dx);
}

const roundCm = (value) => Math.round(Number(value) * 100) / 100;

function segmentFrame(segment = {}) {
  const start = segment.start || {};
  const end = segment.end || {};
  const sx = Number(start.x) || 0;
  const sz = Number(start.z) || 0;
  const ex = Number(end.x) || 0;
  const ez = Number(end.z) || 0;
  const dx = ex - sx;
  const dz = ez - sz;
  const length = Math.hypot(dx, dz);
  const unitX = length ? dx / length : 1;
  const unitZ = length ? dz / length : 0;
  return {
    sx,
    sz,
    ex,
    ez,
    dx,
    dz,
    length,
    unitX,
    unitZ,
    // 法向 n = (-unitZ, unitX):沿段軸 u 逆時針轉 90°。
    normalX: -unitZ,
    normalZ: unitX,
    centerX: (sx + ex) / 2,
    centerZ: (sz + ez) / 2,
    rotationY: segmentRotationY(dx, dz),
  };
}

function box(kind, role, center, size, rotationY = 0, meta = {}) {
  return Object.freeze({
    kind,
    role,
    center: center.map(roundCm),
    size: size.map(roundCm),
    rotationY,
    meta: Object.freeze({ ...meta }),
  });
}

function boxAlongSegment(frame, role, kind, fromU, toU, bottom, top, thickness, offset = 0, meta = {}) {
  const midU = (fromU + toU) / 2;
  return box(
    kind,
    role,
    [
      frame.sx + frame.unitX * midU + frame.normalX * offset,
      (bottom + top) / 2,
      frame.sz + frame.unitZ * midU + frame.normalZ * offset,
    ],
    [toU - fromU, top - bottom, thickness],
    frame.rotationY,
    meta,
  );
}

function openingIsLocked(opening = {}) {
  return opening.confirmed === true
    || opening.source === "manual"
    || opening.opening_source === "manual_confirmed"
    || opening.host_wall_confirmed === true
    || opening.topology_gap === true;
}

function openingId(opening = {}) {
  return String(opening.id || "").trim();
}

// 文件 §5.3:Union-Find 群聚。DXF 窗常是多條平行線,必須群聚去重。
// 與文件的刻意偏離:兩開口 ID 皆非空且不同時永不合併(第 4 步擁有門窗身份),
// 丟棄 <minWindowWidthCm 不適用於已鎖定(confirmed/manual)開口。
// ponytail: ID 保護只做成對檢查;若兩個確認窗之間恰有一條 30cm 內的無主符號
// 線仍可能鏈結成群 —— 步驟 4 確認後的資料不會出現這種線,故不做分群後拆解。
export function clusterOpeningSegments(openings = [], cfg = DEFAULT_SCENE_CONFIG, kind = "window") {
  const items = openings
    .filter((opening) => opening && opening.start && opening.end)
    .map((opening) => {
      const frame = segmentFrame(opening);
      const angleDeg = ((Math.atan2(-frame.dz, frame.dx) * 180) / Math.PI % 180 + 180) % 180;
      return { opening, frame, angleDeg };
    });
  const parent = items.map((_, index) => index);
  const find = (index) => {
    let root = index;
    while (parent[root] !== root) root = parent[root];
    while (parent[index] !== root) {
      const next = parent[index];
      parent[index] = root;
      index = next;
    }
    return root;
  };
  const union = (left, right) => {
    parent[find(left)] = find(right);
  };

  for (let i = 0; i < items.length; i += 1) {
    for (let j = i + 1; j < items.length; j += 1) {
      const leftId = openingId(items[i].opening);
      const rightId = openingId(items[j].opening);
      if (leftId && rightId && leftId !== rightId) continue;
      const midDistance = Math.hypot(
        items[i].frame.centerX - items[j].frame.centerX,
        items[i].frame.centerZ - items[j].frame.centerZ,
      );
      if (midDistance > cfg.clusterDistanceCm) continue;
      const rawDiff = Math.abs(items[i].angleDeg - items[j].angleDeg);
      const angleDiff = Math.min(rawDiff, 180 - rawDiff);
      if (angleDiff > cfg.clusterAngleDeg) continue;
      union(i, j);
    }
  }

  const groups = new Map();
  items.forEach((item, index) => {
    const root = find(index);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(item);
  });

  return [...groups.values()]
    .map((members) => {
      const representative = [...members].sort((left, right) => (
        (openingIsLocked(right.opening) ? 1 : 0) - (openingIsLocked(left.opening) ? 1 : 0)
        || right.frame.length - left.frame.length
      ))[0];
      return representative;
    })
    .filter((item) => (
      kind !== "window"
      || item.frame.length >= cfg.minWindowWidthCm
      || openingIsLocked(item.opening)
    ))
    .sort((left, right) => (
      Math.round(left.frame.centerX * 10) - Math.round(right.frame.centerX * 10)
      || Math.round(left.frame.centerZ * 10) - Math.round(right.frame.centerZ * 10)
    ))
    .map((item) => item.opening);
}

function doorHeadCm(opening, cfg) {
  return Math.min(
    Number(opening.height_cm) || cfg.door.headCm,
    cfg.wallHeightCm - 8,
  );
}

// 門楣/門頂蓋所在的「牆縫線段」:沿用舊 buildConfirmedDoorLeaves 的
// headerSegment 優先序。回傳保留 id/height_cm 的線段物件;皆無回 null。
function doorWallSegment(opening = {}) {
  const gap = opening.wall_opening_segment || opening.closed_leaf_segment;
  if (!gap?.start || !gap?.end) return null;
  return {
    id: opening.id,
    height_cm: opening.height_cm,
    start: gap.start,
    end: gap.end,
  };
}

// 縫線段防呆:doorOpeningForWallTopology 對缺 swing 資料的門會合成出
// 離牆很遠的 closed leaf。門楣只能掛在貼近某條牆線(延長線容許縫寬)
// 的線段上,否則寧可不畫 —— 畫錯位置就是懸空牆塊。
function nearAnyWallLine(segment, walls, cfg) {
  const frame = segmentFrame(segment);
  const tolerance = cfg.wallThicknessCm * 2;
  return walls.some((wall) => {
    const line = segmentFrame(wall);
    if (line.length < cfg.minSegmentLengthCm) return false;
    const relX = frame.centerX - line.sx;
    const relZ = frame.centerZ - line.sz;
    const along = relX * line.unitX + relZ * line.unitZ;
    const perpendicular = Math.abs(relX * line.normalX + relZ * line.normalZ);
    return perpendicular <= tolerance
      && along >= -frame.length
      && along <= line.length + frame.length;
  });
}

// 文件 §5.4 路徑 A:線段牆的開口件。窗 = 玻璃 + 窗台下補實 + 窗頂上補實;
// 門(withGlass=false)= 只補門楣,底下留通行口。件全部落在開口自身線段上,
// 因此同時涵蓋 hosted(牆被切分)與 standalone(牆已留縫)兩種資料。
export function windowPieces(opening = {}, cfg = DEFAULT_SCENE_CONFIG, { kind = "window" } = {}) {
  const frame = segmentFrame(opening);
  if (frame.length < cfg.minSegmentLengthCm) return [];
  const infillThickness = cfg.wallThicknessCm - 2 * cfg.epsilonCm;
  const meta = { openingId: openingId(opening) || null };
  const pieces = [];

  if (kind === "door") {
    const head = doorHeadCm(opening, cfg);
    if (cfg.wallHeightCm - head > cfg.epsilonCm) {
      pieces.push(boxAlongSegment(
        frame, "door-lintel", "wall", 0, frame.length,
        head, cfg.wallHeightCm, infillThickness, 0, meta,
      ));
    }
    return pieces;
  }

  const metrics = windowOpeningMetrics(opening, cfg.wallHeightCm);
  const sill = metrics.sillHeightCm;
  const head = metrics.headHeightCm;
  if (head > sill) {
    pieces.push(boxAlongSegment(
      frame, "window-glass", "glass", 0, frame.length,
      sill, head, cfg.glassThicknessCm, 0, meta,
    ));
  }
  const sillTop = sill - cfg.frameAllowanceCm;
  if (sillTop > cfg.epsilonCm) {
    pieces.push(boxAlongSegment(
      frame, "window-sill-infill", "wall", 0, frame.length,
      0, sillTop, infillThickness, 0, meta,
    ));
  }
  const headBottom = head + cfg.frameAllowanceCm;
  if (cfg.wallHeightCm - headBottom > cfg.epsilonCm) {
    pieces.push(boxAlongSegment(
      frame, "window-head-infill", "wall", 0, frame.length,
      headBottom, cfg.wallHeightCm, infillThickness, 0, meta,
    ));
  }
  return pieces;
}

function polygonPoints(polygons = []) {
  return polygons.flatMap((region) => {
    const rings = [region?.exterior || [], ...(region?.holes || [])];
    return rings.flat().map((point) => ({
      x: Number(Array.isArray(point) ? point[0] : point?.x),
      z: Number(Array.isArray(point) ? point[1] : point?.z),
    })).filter((point) => Number.isFinite(point.x) && Number.isFinite(point.z));
  });
}

// 文件 §5.4 路徑 B:由開口線段兩端鄰近的牆多邊形頂點推定牆斷面。
// 只取法向 |dn| ≤ normalSpreadMaxCm 且距開口任一端點 ≤ endDistanceMaxCm 的頂點;
// spread < minThicknessCm(單一外框、開口離牆太遠)→ fallback 回 wallThicknessCm。
export function estimateProfile(opening = {}, polygons = [], cfg = DEFAULT_SCENE_CONFIG) {
  const frame = segmentFrame(opening);
  const fallback = Object.freeze({
    thicknessCm: cfg.wallThicknessCm,
    offsetCm: 0,
    startU: 0,
    endU: frame.length,
    fallback: true,
  });
  const kept = polygonPoints(polygons)
    .map((point) => {
      const relX = point.x - frame.sx;
      const relZ = point.z - frame.sz;
      return {
        du: relX * frame.unitX + relZ * frame.unitZ,
        dn: relX * frame.normalX + relZ * frame.normalZ,
        endDistance: Math.min(
          Math.hypot(point.x - frame.sx, point.z - frame.sz),
          Math.hypot(point.x - frame.ex, point.z - frame.ez),
        ),
      };
    })
    .filter((point) => (
      Math.abs(point.dn) <= cfg.profile.normalSpreadMaxCm
      && point.endDistance <= cfg.profile.endDistanceMaxCm
    ));
  if (!kept.length) return fallback;

  const dnValues = kept.map((point) => point.dn);
  const duValues = kept.map((point) => point.du);
  const spread = Math.max(...dnValues) - Math.min(...dnValues);
  if (spread < cfg.profile.minThicknessCm) return fallback;
  return Object.freeze({
    thicknessCm: roundCm(spread),
    offsetCm: roundCm((Math.max(...dnValues) + Math.min(...dnValues)) / 2),
    startU: roundCm(Math.min(0, ...duValues)),
    endU: roundCm(Math.max(frame.length, ...duValues)),
    fallback: false,
  });
}

// 文件 §5.4 路徑 B:多邊形牆的洞由資料自帶,不引入 CSG。補一段與左右鄰牆
// 同厚同心的連續牆跨過開口縫(窗 = 全高連續牆 + 玻璃貼片;門 = 只補門楣),
// 玻璃厚 profile + 2·epsilon 兩面各微露,避免與牆共面閃爍。
export function openingInfill(opening = {}, profile, cfg = DEFAULT_SCENE_CONFIG, { kind = "window" } = {}) {
  const frame = segmentFrame(opening);
  if (frame.length < cfg.minSegmentLengthCm) return [];
  const meta = { openingId: openingId(opening) || null };
  const withGlass = kind !== "door";
  const metrics = withGlass ? windowOpeningMetrics(opening, cfg.wallHeightCm) : null;
  const wallBottom = withGlass ? 0 : doorHeadCm(opening, cfg);
  const boxes = [];
  if (cfg.wallHeightCm - wallBottom > cfg.epsilonCm) {
    boxes.push(boxAlongSegment(
      frame, "opening-infill-wall", "wall", profile.startU, profile.endU,
      wallBottom, cfg.wallHeightCm, profile.thicknessCm, profile.offsetCm, meta,
    ));
  }
  if (withGlass && metrics.headHeightCm > metrics.sillHeightCm) {
    boxes.push(boxAlongSegment(
      frame, "window-glass", "glass", 0, frame.length,
      metrics.sillHeightCm, metrics.headHeightCm,
      profile.thicknessCm + 2 * cfg.epsilonCm, profile.offsetCm, meta,
    ));
  }
  return boxes;
}

// 文件 §3.4:bbox 只由結構幾何決定(牆/多邊形牆/窗/門),文字或家具不參與。
export function structureBbox(plan = {}) {
  let minX = Infinity;
  let minZ = Infinity;
  let maxX = -Infinity;
  let maxZ = -Infinity;
  let seen = false;
  const take = (x, z) => {
    if (!Number.isFinite(x) || !Number.isFinite(z)) return;
    seen = true;
    minX = Math.min(minX, x);
    minZ = Math.min(minZ, z);
    maxX = Math.max(maxX, x);
    maxZ = Math.max(maxZ, z);
  };
  [...(plan.walls || []), ...(plan.windows || []), ...(plan.doors || [])]
    .forEach((segment) => {
      take(Number(segment?.start?.x), Number(segment?.start?.z));
      take(Number(segment?.end?.x), Number(segment?.end?.z));
    });
  polygonPoints(plan.wallPolygons || []).forEach((point) => take(point.x, point.z));
  return seen ? [minX, minZ, maxX, maxZ] : null;
}

// 文件 §5.6:地板 = 結構 bbox 各向外擴 floorMarginCm 的薄盒,y ∈ [-厚, 0]。
export function floorBox(bbox, cfg = DEFAULT_SCENE_CONFIG) {
  if (!bbox) return null;
  const [minX, minZ, maxX, maxZ] = bbox;
  const thickness = cfg.floorThicknessCm;
  return box(
    "floor",
    "floor",
    [(minX + maxX) / 2, -thickness / 2, (minZ + maxZ) / 2],
    [
      maxX - minX + 2 * cfg.floorMarginCm,
      thickness,
      maxZ - minZ + 2 * cfg.floorMarginCm,
    ],
  );
}

// 文件 §5.7:相機依 bbox 推算,45° 俯視、對角斜看,不寫死。
export function fitCameraPose(bbox, cfg = DEFAULT_SCENE_CONFIG) {
  const span = cfg.minCameraSpanCm;
  const [minX, minZ, maxX, maxZ] = bbox || [-span / 2, -span / 2, span / 2, span / 2];
  const targetX = (minX + maxX) / 2;
  const targetZ = (minZ + maxZ) / 2;
  const distance = Math.max(maxX - minX, maxZ - minZ, cfg.minCameraSpanCm)
    * cfg.cameraDistFactor;
  return Object.freeze({
    position: [
      roundCm(targetX + distance * 0.7),
      roundCm(distance * 0.9),
      roundCm(targetZ + distance * 0.7),
    ],
    target: [roundCm(targetX), 0, roundCm(targetZ)],
  });
}

// step4_skip_wall_cut 的語意是「牆體幾何已由第 4 步處理,不得再切牆」——
// 不是「不畫補實件」。hosted 窗照切照補;縫內窗帶旗標才整組略過
// (沿用舊 missingWindows 行為);門楣一律要有(舊 buildConfirmedDoorLeaves
// 對每扇有牆縫線段的門都補 header,旗標從不參與)。
function pieceWindowsOf(windows, walls, cfg) {
  return windows.filter((opening) => (
    opening.step4_skip_wall_cut !== true
    || walls.some((wall) => openingWallInterval(
      wall, opening, cfg.wallThicknessCm, cfg.minOpeningIntervalWidthCm.window,
    ))
  ));
}

// 現行 buildConfirmedWallJunctionFills 的純幾何部分:已確認牆端點間
// ≤ max(36, 2·牆厚) 的縫以橋接牆補上;橋的中點靠近任何開口時不得補
// (門縫/窗縫必須保留)。
function junctionFillBoxes(walls, protectedOpenings, cfg) {
  const tolerance = Math.max(cfg.junction.maxGapFloorCm, cfg.wallThicknessCm * cfg.junction.maxGapFactor);
  const openingTolerance = Math.max(cfg.wallThicknessCm * 0.6, 7);
  const frames = protectedOpenings.map((opening) => segmentFrame(
    opening.wall_opening_segment || opening,
  ));
  const distanceToOpening = (x, z, frame) => {
    const relX = x - frame.sx;
    const relZ = z - frame.sz;
    const along = Math.max(0, Math.min(frame.length, relX * frame.unitX + relZ * frame.unitZ));
    return Math.hypot(frame.sx + frame.unitX * along - x, frame.sz + frame.unitZ * along - z);
  };
  const touchesOpening = (start, end) => {
    const midX = (start.x + end.x) / 2;
    const midZ = (start.z + end.z) / 2;
    return frames.some((frame) => (
      distanceToOpening(midX, midZ, frame) <= openingTolerance
      && (
        distanceToOpening(start.x, start.z, frame) <= openingTolerance
        || distanceToOpening(end.x, end.z, frame) <= openingTolerance
      )
    ));
  };

  const endpoints = walls.flatMap((segment, segmentIndex) => {
    const frame = segmentFrame(segment);
    if (frame.length < cfg.minSegmentLengthCm) return [];
    return [
      { key: `${segmentIndex}:start`, segmentIndex, x: frame.sx, z: frame.sz },
      { key: `${segmentIndex}:end`, segmentIndex, x: frame.ex, z: frame.ez },
    ];
  });
  const used = new Set();
  const boxes = [];
  endpoints.forEach((endpoint, index) => {
    if (used.has(endpoint.key)) return;
    const neighbor = endpoints
      .slice(index + 1)
      .filter((candidate) => (
        candidate.segmentIndex !== endpoint.segmentIndex && !used.has(candidate.key)
      ))
      .map((candidate) => ({
        candidate,
        distance: Math.hypot(candidate.x - endpoint.x, candidate.z - endpoint.z),
      }))
      .filter(({ distance }) => distance > cfg.junction.minGapCm && distance <= tolerance)
      .sort((left, right) => left.distance - right.distance)[0];
    if (!neighbor) return;
    const start = { x: endpoint.x, z: endpoint.z };
    const end = { x: neighbor.candidate.x, z: neighbor.candidate.z };
    if (touchesOpening(start, end)) return;
    const bridge = segmentFrame({ start, end });
    if (bridge.length < cfg.junction.minGapCm) return;
    boxes.push(box(
      "wall",
      "junction-fill",
      [bridge.centerX, cfg.wallHeightCm / 2, bridge.centerZ],
      [bridge.length + cfg.wallThicknessCm, cfg.wallHeightCm, cfg.wallThicknessCm],
      bridge.rotationY,
      { detail: "confirmed-wall-junction-fill" },
    ));
    used.add(endpoint.key);
    used.add(neighbor.candidate.key);
  });
  return boxes;
}

function segmentWallBoxes(walls, windows, cfg) {
  const boxes = [];
  walls.forEach((segment, segmentIndex) => {
    const frame = segmentFrame(segment);
    if (frame.length < cfg.minSegmentLengthCm) return;
    const meta = {
      segmentIndex,
      segmentId: String(segment.id || "") || null,
    };
    // Step 4 已確認的牆段自帶門縫;只有 hosted 窗需要把牆切成上下段之間的
    // 空帶(玻璃與補實件由 windowPieces 供給)。
    const intervals = windows
      .map((opening) => openingWallInterval(
        segment,
        opening,
        cfg.wallThicknessCm,
        cfg.minOpeningIntervalWidthCm.window,
      ))
      .filter(Boolean)
      .map((interval) => ({
        from: Math.max(0, interval.from),
        to: Math.min(frame.length, interval.to),
      }))
      .filter((interval) => interval.to - interval.from >= 2.5)
      .sort((left, right) => left.from - right.from);

    let cursor = 0;
    const sections = [];
    intervals.forEach((interval) => {
      if (interval.from - cursor >= 2.5) sections.push({ from: cursor, to: interval.from });
      cursor = Math.max(cursor, interval.to);
    });
    if (frame.length - cursor >= 2.5) sections.push({ from: cursor, to: frame.length });

    sections.forEach((section) => {
      const span = wallSectionSpan(section.from, section.to, frame.length);
      boxes.push(boxAlongSegment(
        frame, "wall-section", "wall", span.from, span.to,
        0, cfg.wallHeightCm, cfg.wallThicknessCm, 0,
        { ...meta, from: span.from, to: span.to },
      ));
    });
    boxes.push(boxAlongSegment(
      frame, "top-cap", "wall", 0, frame.length,
      cfg.wallHeightCm, cfg.wallHeightCm + cfg.topCapHeightCm,
      cfg.wallThicknessCm, 0, meta,
    ));
  });
  return boxes;
}

// 文件 §5:SceneModel = { boxes, polygonWalls, floor, cameraPose }。
// 切換開關 infill = 只有多邊形牆表示時走路徑 B(openingInfill);
// 有已確認線段牆時線段資料優先(第 4 步編輯結果是幾何權威)。
export function buildSceneModel(plan = {}, cfg = DEFAULT_SCENE_CONFIG) {
  const walls = plan.walls || [];
  const polygons = (plan.wallPolygons || []).filter(
    (region) => (region?.exterior?.length || 0) >= 3,
  );
  const windows = clusterOpeningSegments(plan.windows || [], cfg, "window");
  const doors = clusterOpeningSegments(
    (plan.doors || []).map((door) => doorOpeningForWallTopology(walls, door, cfg.wallThicknessCm)),
    cfg,
    "door",
  );
  const pieceWindows = pieceWindowsOf(windows, walls, cfg);
  const pieceDoors = doors;
  const infill = polygons.length > 0 && !walls.length;
  const boxes = [];
  const polygonWalls = infill
    ? polygons.map((region) => Object.freeze({ region, heightCm: cfg.wallHeightCm }))
    : [];

  if (infill) {
    pieceWindows.forEach((opening) => {
      const profile = estimateProfile(opening, polygons, cfg);
      boxes.push(...openingInfill(opening, profile, cfg, { kind: "window" }));
    });
    pieceDoors.forEach((opening) => {
      const doorSegment = doorWallSegment(opening) || opening;
      const profile = estimateProfile(doorSegment, polygons, cfg);
      boxes.push(...openingInfill(doorSegment, profile, cfg, { kind: "door" }));
    });
  } else if (walls.length) {
    boxes.push(...segmentWallBoxes(walls, pieceWindows, cfg));
    boxes.push(...junctionFillBoxes(walls, [...pieceDoors, ...pieceWindows], cfg));
    // 縫內開口(牆段在開口兩側斷開、未被任何牆段 host)的補實件只到牆高,
    // 左右牆的頂蓋卻到牆高 + topCapHeightCm —— 開口跨距會矮一截。
    // 補上開口自身的頂蓋,讓頂線跨過門窗連續;hosted 開口由牆段整段頂蓋涵蓋。
    const hostedOnAnyWall = (opening, minWidthCm) => walls.some((wall) => (
      openingWallInterval(wall, opening, cfg.wallThicknessCm, minWidthCm)
    ));
    const gapTopCap = (opening) => {
      const frame = segmentFrame(opening);
      if (frame.length < cfg.minSegmentLengthCm) return [];
      return [boxAlongSegment(
        frame, "top-cap", "wall", 0, frame.length,
        cfg.wallHeightCm, cfg.wallHeightCm + cfg.topCapHeightCm,
        cfg.wallThicknessCm, 0,
        { openingId: openingId(opening) || null },
      )];
    };
    pieceWindows.forEach((opening) => {
      boxes.push(...windowPieces(opening, cfg, { kind: "window" }));
      if (!hostedOnAnyWall(opening, cfg.minOpeningIntervalWidthCm.window)) {
        boxes.push(...gapTopCap(opening));
      }
    });
    // 門的 2D 線段是門扇符號(常平行牆線外偏 20cm+,開門葉甚至與牆垂直),
    // 不在牆平面上 —— 門楣/頂蓋畫在門段上會變成懸在門邊的牆塊。必須落在
    // 第 4 步的牆縫線段;兩種縫線皆無則不畫(與舊 buildConfirmedDoorLeaves
    // 的 headerSegment 同優先序、同缺省行為)。
    pieceDoors.forEach((opening) => {
      const doorSegment = doorWallSegment(opening);
      if (!doorSegment || !nearAnyWallLine(doorSegment, walls, cfg)) return;
      boxes.push(...windowPieces(doorSegment, cfg, { kind: "door" }));
      if (!hostedOnAnyWall(doorSegment, cfg.minOpeningIntervalWidthCm.door)) {
        boxes.push(...gapTopCap(doorSegment));
      }
    });
  }

  const bbox = structureBbox({ walls, windows, doors, wallPolygons: polygons })
    || fallbackBbox(plan);
  return Object.freeze({
    boxes,
    polygonWalls,
    floor: floorBox(bbox, cfg),
    cameraPose: fitCameraPose(bbox, cfg),
    bbox,
    openings: Object.freeze({ windows, doors }),
  });
}

function fallbackBbox(plan = {}) {
  const width = Number(plan.widthCm);
  const depth = Number(plan.depthCm);
  if (!Number.isFinite(width) || !Number.isFinite(depth) || width <= 0 || depth <= 0) {
    return null;
  }
  return [-width / 2, -depth / 2, width / 2, depth / 2];
}
