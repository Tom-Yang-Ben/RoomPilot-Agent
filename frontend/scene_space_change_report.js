const DISCLAIMER = "概念建議；施工前須現場丈量及專業確認。";

function rounded(value) {
  return Math.round((Number(value) + Number.EPSILON) * 1000) / 1000;
}

export function buildEmptyAffected() {
  return { doors: [], windows: [], furniture: [], mep: [] };
}

export function buildSceneWallSegment(comparison, floorplan, changeId) {
  const xs = comparison.afterPolygonM.map((point) => Number(point.x));
  const ys = comparison.afterPolygonM.map((point) => Number(point.y));
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const side = comparison.wallSide;
  const startM = side === "right" ? { x: maxX, y: minY }
    : side === "left" ? { x: minX, y: minY }
    : side === "top" ? { x: minX, y: maxY }
    : { x: minX, y: minY };
  const endM = side === "right" ? { x: maxX, y: maxY }
    : side === "left" ? { x: minX, y: maxY }
    : side === "top" ? { x: maxX, y: maxY }
    : { x: maxX, y: minY };
  const halfWidthM = Number(floorplan.width_cm || 0) / 200;
  const halfDepthM = Number(floorplan.depth_cm || 0) / 200;
  const toScenePointM = (point) => ({
    x: rounded(point.x - halfWidthM),
    z: rounded(point.y - halfDepthM),
  });
  return {
    start: toScenePointM(startM),
    end: toScenePointM(endM),
    change_id: changeId,
    source: "wall_boxing_geometry",
  };
}

function validateChange(change) {
  if (!change?.id || !(change.evidence || []).length || !change.confidence) {
    throw new Error("space_change_evidence_required");
  }
  if (!change.visualRefs?.plan || !change.visualRefs?.section || !change.visualRefs?.model3d) {
    throw new Error("space_change_visuals_required");
  }
}

export function buildWallBoxingComparison(change) {
  validateChange(change);
  const before = {
    width: Number(change.beforeDimensionsM?.width),
    depth: Number(change.beforeDimensionsM?.depth),
  };
  const thickness = Number(change.thicknessM);
  if (!Number.isFinite(before.width) || !Number.isFinite(before.depth) || !(thickness > 0)) {
    throw new Error("wall_boxing_geometry_required");
  }
  const after = { ...before };
  const side = change.wallSide || (change.axis === "depth" ? "top" : "right");
  if (side === "top" || side === "bottom") after.depth = rounded(after.depth - thickness);
  else after.width = rounded(after.width - thickness);
  const beforePolygonM = structuredClone(change.roomPolygonM || [
    { x: 0, y: 0 }, { x: before.width, y: 0 }, { x: before.width, y: before.depth }, { x: 0, y: before.depth },
  ]);
  const xs = beforePolygonM.map((point) => Number(point.x));
  const ys = beforePolygonM.map((point) => Number(point.y));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const afterPolygonM = beforePolygonM.map((point) => {
    const next = { x: Number(point.x), y: Number(point.y) };
    if (side === "right" && Math.abs(next.x - maxX) < 0.002) next.x = rounded(next.x - thickness);
    if (side === "left" && Math.abs(next.x - minX) < 0.002) next.x = rounded(next.x + thickness);
    if (side === "top" && Math.abs(next.y - maxY) < 0.002) next.y = rounded(next.y - thickness);
    if (side === "bottom" && Math.abs(next.y - minY) < 0.002) next.y = rounded(next.y + thickness);
    return next;
  });
  return {
    changeId: change.id,
    beforeDimensionsM: before,
    afterDimensionsM: after,
    lostAreaM2: rounded(Number(change.wallLengthM) * thickness),
    thicknessM: thickness,
    target: change.target,
    wallSide: side,
    beforePolygonM,
    afterPolygonM,
    affected: structuredClone(change.affected || {}),
    visualRefs: structuredClone(change.visualRefs),
  };
}

export function buildSpaceChangeReport(changes = [], { audience = "customer" } = {}) {
  const normalized = changes.map((change) => {
    validateChange(change);
    const comparison = buildWallBoxingComparison(change);
    const shared = {
      id: change.id,
      roomId: change.roomId,
      title: change.title,
      kind: change.kind,
      target: change.target,
      status: change.status || "concept_recommendation",
      beforeDimensionsM: comparison.beforeDimensionsM,
      afterDimensionsM: comparison.afterDimensionsM,
      beforePolygonM: comparison.beforePolygonM,
      afterPolygonM: comparison.afterPolygonM,
      lostAreaM2: comparison.lostAreaM2,
      risks: structuredClone(change.risks || []),
      costEstimateId: change.costEstimateId || null,
      visualRefs: structuredClone(change.visualRefs),
      confidence: structuredClone(change.confidence),
    };
    if (audience === "designer") {
      return {
        ...shared,
        thicknessM: comparison.thicknessM,
        wallLengthM: Number(change.wallLengthM),
        affected: structuredClone(change.affected || {}),
        evidence: structuredClone(change.evidence),
        assumptions: structuredClone(change.assumptions || []),
        constructionNotes: structuredClone(change.constructionNotes || []),
      };
    }
    return {
      ...shared,
      impactSummary: {
        spaceLostM2: comparison.lostAreaM2,
        furnitureAffected: (change.affected?.furniture || []).length,
        mepAffected: (change.affected?.mep || []).length,
      },
    };
  });
  return {
    schemaVersion: 1,
    audience,
    changes: normalized,
    disclaimer: DISCLAIMER,
  };
}
