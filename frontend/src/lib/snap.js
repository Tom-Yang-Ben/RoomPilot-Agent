// Pure 2D snap geometry for furniture placement, in world XZ coordinates
// (no three.js import so it can be unit-tested in plain node).
//
// Priority: wall face (aligns yaw to the wall, supports diagonal walls, plus a
// perpendicular second wall for corner snapping) → edge alignment against other
// furniture (axis-aligned AABBs: abut / flush / centre) → 0.1 m grid.

export const GRID = 0.1        // fallback grid pitch (m)
export const WALL_SNAP = 0.45  // wall face engages within this distance (m)
export const EDGE_SNAP = 0.18  // furniture edges align within this distance (m)
export const GAP = 0.005       // breathing room left against a snapped face (m)
const HALF_PI = Math.PI / 2

// Wall face segments in world coords from the backend payload.
// Plan (x,z) maps to world (x,-z) — same convention the wall extrusion uses.
export function wallSegments(data) {
  const segs = []
  for (const poly of data?.wall_polys ?? []) {
    for (const ring of [poly.exterior, ...(poly.holes ?? [])]) {
      for (let i = 0; i + 1 < ring.length; i++) {
        const [x1, z1] = ring[i]
        const [x2, z2] = ring[i + 1]
        if ((x1 - x2) ** 2 + (z1 - z2) ** 2 > 1e-8) {
          segs.push({ x1, z1: -z1, x2, z2: -z2 })
        }
      }
    }
  }
  return segs
}

// Half-extent of a yaw-rotated size.x × size.z footprint along unit direction
// (ux,uz), measured from the centre. Yaw follows three.js rotation.y, so the
// local X axis lands on (cos yaw, -sin yaw) and local Z on (sin yaw, cos yaw).
export function extentAlong(size, yaw, ux, uz) {
  const c = Math.cos(yaw)
  const s = Math.sin(yaw)
  return (Math.abs(ux * c - uz * s) * size.x + Math.abs(ux * s + uz * c) * size.z) / 2
}

function nearestOnSeg(px, pz, s) {
  const dx = s.x2 - s.x1
  const dz = s.z2 - s.z1
  const l2 = dx * dx + dz * dz
  let t = l2 ? ((px - s.x1) * dx + (pz - s.z1) * dz) / l2 : 0
  t = Math.max(0, Math.min(1, t))
  return { qx: s.x1 + t * dx, qz: s.z1 + t * dz, dx, dz }
}

// pos/yaw: proposed placement (cursor). size: {x,z} footprint of the item.
// others: [{x,z,yaw,size}] the rest of the placed furniture.
// Returns {x, z, yaw, kind: 'corner'|'wall'|'edge'|'grid'|null}.
export function snapPlacement({ x, z, yaw, size, walls = [], others = [], enabled = true }) {
  if (!enabled || !size) return { x, z, yaw, kind: null }

  // --- wall snap: nearest wall face within reach of the item's side ---------
  let best = null
  for (const s of walls) {
    const { qx, qz, dx, dz } = nearestOnSeg(x, z, s)
    const d = Math.hypot(x - qx, z - qz)
    if (!best || d < best.d) best = { d, qx, qz, dx, dz }
  }
  if (best) {
    const len = Math.hypot(best.dx, best.dz)
    const tx = best.dx / len
    const tz = best.dz / len
    let nx = -tz
    let nz = tx
    if ((x - best.qx) * nx + (z - best.qz) * nz < 0) { nx = -nx; nz = -nz }
    // keep the user's intended orientation, quantised into the wall's frame
    const wallYaw = Math.atan2(-tz, tx)
    const snapYaw = wallYaw + Math.round((yaw - wallYaw) / HALF_PI) * HALF_PI
    const half = extentAlong(size, snapYaw, nx, nz)
    if (best.d < half + WALL_SNAP) {
      let px = best.qx + nx * (half + GAP)
      let pz = best.qz + nz * (half + GAP)
      let kind = 'wall'
      // corner: a second, roughly perpendicular wall nearby slides the item
      // along the first wall until that face is flush too
      let corner = null
      for (const s of walls) {
        const { qx, qz, dx, dz } = nearestOnSeg(px, pz, s)
        const l2 = Math.hypot(dx, dz)
        if (!l2) continue
        if (Math.abs(tx * (dz / l2) - tz * (dx / l2)) < 0.7) continue // near-parallel
        let n2x = -(dz / l2)
        let n2z = dx / l2
        if ((px - qx) * n2x + (pz - qz) * n2z < 0) { n2x = -n2x; n2z = -n2z }
        const d2 = (px - qx) * n2x + (pz - qz) * n2z
        const err = extentAlong(size, snapYaw, n2x, n2z) + GAP - d2
        if (Math.abs(err) < WALL_SNAP && (!corner || Math.abs(err) < Math.abs(corner.err))) {
          corner = { err, n2x, n2z }
        }
      }
      if (corner) {
        // project the flush correction onto the first wall's tangent
        const along = corner.n2x * corner.err * tx + corner.n2z * corner.err * tz
        px += tx * along
        pz += tz * along
        kind = 'corner'
      }
      return { x: px, z: pz, yaw: snapYaw, kind }
    }
  }

  // --- edge snap vs other furniture (axis-aligned AABBs) --------------------
  const hx = extentAlong(size, yaw, 1, 0)
  const hz = extentAlong(size, yaw, 0, 1)
  let bx = null
  let bz = null
  for (const o of others) {
    if (!o.size) continue
    const ohx = extentAlong(o.size, o.yaw, 1, 0)
    const ohz = extentAlong(o.size, o.yaw, 0, 1)
    // only snap to neighbours: the perpendicular axis must be within reach
    if (Math.abs(z - o.z) - (hz + ohz) < 1.0) {
      for (const c of [o.x - ohx - hx, o.x + ohx + hx, o.x - ohx + hx, o.x + ohx - hx, o.x]) {
        const d = c - x
        if (Math.abs(d) < EDGE_SNAP && (bx === null || Math.abs(d) < Math.abs(bx))) bx = d
      }
    }
    if (Math.abs(x - o.x) - (hx + ohx) < 1.0) {
      for (const c of [o.z - ohz - hz, o.z + ohz + hz, o.z - ohz + hz, o.z + ohz - hz, o.z]) {
        const d = c - z
        if (Math.abs(d) < EDGE_SNAP && (bz === null || Math.abs(d) < Math.abs(bz))) bz = d
      }
    }
  }

  // --- grid on whichever axis nothing else claimed ---------------------------
  return {
    x: bx !== null ? x + bx : Math.round(x / GRID) * GRID,
    z: bz !== null ? z + bz : Math.round(z / GRID) * GRID,
    yaw,
    kind: bx !== null || bz !== null ? 'edge' : 'grid',
  }
}
