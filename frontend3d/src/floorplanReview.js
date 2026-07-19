export const DEFAULT_ROOM_TYPE_OPTIONS = [
  { value: 'living_room', label_zh: '客廳' },
  { value: 'dining_room', label_zh: '餐廳' },
  { value: 'bedroom', label_zh: '臥室' },
  { value: 'study', label_zh: '書房' },
  { value: 'kitchen', label_zh: '廚房' },
  { value: 'bathroom', label_zh: '浴室' },
  { value: 'toilet', label_zh: '廁所' },
  { value: 'entry', label_zh: '玄關' },
  { value: 'corridor', label_zh: '走廊' },
  { value: 'balcony', label_zh: '陽台／露台' },
  { value: 'storage', label_zh: '儲藏室' },
  { value: 'laundry', label_zh: '洗衣間' },
  { value: 'other', label_zh: '其他空間' },
]

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

function canonicalSegments(raw = []) {
  return raw
    .map((segment) => {
      const start = segment.start || segment[0] || segment
      const end = segment.end || segment[1] || segment
      return {
        x1: Number(start.x ?? start.x1),
        z1: Number(start.z ?? start.y ?? start.z1),
        x2: Number(end.x ?? end.x2),
        z2: Number(end.z ?? end.y ?? end.z2),
      }
    })
    .filter((segment) => Object.values(segment).every(Number.isFinite))
}

function canonicalWallSegments(raw = [], bbox = null) {
  const segments = canonicalSegments(raw)
  if (!segments.length || !bbox) return segments

  const planSpanM = Math.max(
    Number(bbox.maxx) - Number(bbox.minx),
    Number(bbox.maxz) - Number(bbox.minz),
  )
  const xs = segments.flatMap((segment) => [segment.x1, segment.x2])
  const zs = segments.flatMap((segment) => [segment.z1, segment.z2])
  const segmentSpan = Math.max(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...zs) - Math.min(...zs),
  )
  if (!(planSpanM > 0) || segmentSpan <= planSpanM * 10) return segments

  // dxf_parser 的歷史 client segment 以公分輸出，但 bbox / wall_polys 是公尺。
  // 在辨識邊界正規化，避免使用者明明點在牆上卻吸附到放大 100 倍的座標。
  return segments.map((segment) => ({
    x1: segment.x1 / 100,
    z1: segment.z1 / 100,
    x2: segment.x2 / 100,
    z2: segment.z2 / 100,
  }))
}

function wallPolygonSegments(wallPolys = []) {
  const segments = []
  wallPolys.forEach((wall) => {
    const rings = [wall.exterior, ...(wall.holes || [])]
    rings.filter((ring) => ring?.length >= 2).forEach((ring) => {
      for (let index = 0; index < ring.length - 1; index += 1) {
        const [x1, z1] = ring[index]
        const [x2, z2] = ring[index + 1]
        segments.push({ x1: Number(x1), z1: Number(z1), x2: Number(x2), z2: Number(z2) })
      }
      const first = ring[0]
      const last = ring.at(-1)
      if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
        segments.push({
          x1: Number(last[0]),
          z1: Number(last[1]),
          x2: Number(first[0]),
          z2: Number(first[1]),
        })
      }
    })
  })
  return canonicalSegments(segments)
}

export function wallSnapSegments(draft = {}) {
  return [
    ...canonicalWallSegments(draft.wall_segments || [], draft.bbox),
    ...wallPolygonSegments(draft.wall_polys || []),
  ]
}

export function snapPointToWall(draft, point, maxDistanceM = Number.POSITIVE_INFINITY) {
  const target = { x: Number(point?.x), z: Number(point?.z) }
  if (!Number.isFinite(target.x) || !Number.isFinite(target.z)) return null

  let nearest = null
  wallSnapSegments(draft).forEach((segment, wallIndex) => {
    const dx = segment.x2 - segment.x1
    const dz = segment.z2 - segment.z1
    const squaredLength = dx * dx + dz * dz
    if (squaredLength <= Number.EPSILON) return
    const ratio = Math.max(0, Math.min(1,
      ((target.x - segment.x1) * dx + (target.z - segment.z1) * dz) / squaredLength,
    ))
    const x = segment.x1 + ratio * dx
    const z = segment.z1 + ratio * dz
    const distanceM = Math.hypot(target.x - x, target.z - z)
    if (!nearest || distanceM < nearest.distance_m) {
      nearest = { x, z, wall_index: wallIndex, distance_m: distanceM }
    }
  })
  return nearest && nearest.distance_m <= maxDistanceM ? nearest : null
}

export function clientPointToViewBox(clientPoint, rect, view) {
  const scale = Math.min(rect.width / view.width, rect.height / view.depth)
  if (!(scale > 0)) return null
  const offsetX = (rect.width - view.width * scale) / 2
  const offsetY = (rect.height - view.depth * scale) / 2
  return {
    x: view.minx + (Number(clientPoint.x) - rect.left - offsetX) / scale,
    z: view.minz + (Number(clientPoint.y) - rect.top - offsetY) / scale,
  }
}

export function makeFloorplanReviewDraft(floorplan = {}) {
  const options = floorplan.room_type_options?.length
    ? clone(floorplan.room_type_options)
    : clone(DEFAULT_ROOM_TYPE_OPTIONS)
  const optionValues = new Set(options.map((option) => option.value))
  const rooms = (floorplan.room_regions || []).map((room) => {
    const suggestedType = room.room_type || room.value || 'other'
    return {
      ...clone(room),
      room_type: optionValues.has(suggestedType) ? suggestedType : 'other',
    }
  })
  return {
    bbox: clone(floorplan.bbox || null),
    wall_polys: clone(floorplan.wall_polys || []),
    wall_segments: canonicalWallSegments(
      floorplan.wall_segments || floorplan.plan_segments,
      floorplan.bbox,
    ),
    rooms,
    doors: canonicalSegments(floorplan.doors),
    windows: canonicalSegments(floorplan.windows),
    room_type_options: options,
  }
}

export function updateDraftRoomType(draft, roomId, roomType) {
  return {
    ...draft,
    rooms: draft.rooms.map((room) => (
      room.room_id === roomId ? { ...room, room_type: roomType } : room
    )),
  }
}

export function addDraftSegment(draft, feature, start, end) {
  if (!['doors', 'windows'].includes(feature)) return draft
  const segment = {
    x1: Number(start.x),
    z1: Number(start.z),
    x2: Number(end.x),
    z2: Number(end.z),
  }
  if (!Object.values(segment).every(Number.isFinite)) return draft
  if (Math.hypot(segment.x2 - segment.x1, segment.z2 - segment.z1) < 0.05) return draft
  return { ...draft, [feature]: [...draft[feature], segment] }
}

export function removeDraftSegment(draft, feature, index) {
  if (!['doors', 'windows'].includes(feature)) return draft
  return {
    ...draft,
    [feature]: draft[feature].filter((_segment, segmentIndex) => segmentIndex !== index),
  }
}

export function confirmationPayload(draft, expectedRevision) {
  return {
    expected_revision: expectedRevision,
    rooms: draft.rooms.map((room) => ({
      room_id: room.room_id,
      room_type: room.room_type,
    })),
    doors: canonicalSegments(draft.doors),
    windows: canonicalSegments(draft.windows),
  }
}

export function calibrationPayload(reference, actualLengthCm, expectedRevision) {
  const cm = (valueM) => Number((Number(valueM) * 100).toFixed(2))
  return {
    expected_revision: expectedRevision,
    reference_cm: {
      x1_cm: cm(reference.start.x),
      z1_cm: cm(reference.start.z),
      x2_cm: cm(reference.end.x),
      z2_cm: cm(reference.end.z),
    },
    actual_length_cm: Number(actualLengthCm),
  }
}
