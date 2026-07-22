function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

export function polygonPath(region = {}) {
  return [region.exterior, ...(region.holes || [])]
    .filter((ring) => ring?.length)
    .map((ring) => `M ${ring.map(([x, z]) => `${x} ${z}`).join(' L ')} Z`)
    .join(' ')
}

export function layoutView(floorplan = {}) {
  const bbox = floorplan.bbox
  if (!bbox) return null
  const width = Math.max(0.1, Number(bbox.maxx) - Number(bbox.minx))
  const depth = Math.max(0.1, Number(bbox.maxz) - Number(bbox.minz))
  const padding = Math.max(width, depth) * 0.06
  return {
    minx: Number(bbox.minx) - padding,
    minz: Number(bbox.minz) - padding,
    width: width + padding * 2,
    depth: depth + padding * 2,
  }
}

export function clientPointToLayout(clientPoint, rect, view) {
  const scale = Math.min(rect.width / view.width, rect.height / view.depth)
  if (!(scale > 0)) return null
  const offsetX = (rect.width - view.width * scale) / 2
  const offsetY = (rect.height - view.depth * scale) / 2
  return {
    x_cm: (view.minx + (Number(clientPoint.x) - rect.left - offsetX) / scale) * 100,
    z_cm: (view.minz + (Number(clientPoint.y) - rect.top - offsetY) / scale) * 100,
  }
}

export function moveLayoutObject(objects, instanceId, positionCm) {
  return objects.map((item) => item.instance_id === instanceId
    ? {
        ...item,
        position_cm: { x: Number(positionCm.x_cm), z: Number(positionCm.z_cm) },
        position_locked: true,
      }
    : item)
}

export function rotateLayoutObject(objects, instanceId) {
  return objects.map((item) => {
    if (item.instance_id !== instanceId) return item
    const rotation = (Number(item.rotation_y_deg || 0) + 90) % 360
    const size = item.size_cm || {}
    return {
      ...item,
      rotation_y_deg: rotation,
      position_locked: true,
      footprint_cm: rotation % 180 === 90
        ? { width: Number(size.depth), depth: Number(size.width) }
        : { width: Number(size.width), depth: Number(size.depth) },
    }
  })
}

export function layoutValidationPayload(objects, instanceId, expectedRevision) {
  const item = objects.find((entry) => entry.instance_id === instanceId)
  if (!item) throw new Error('找不到要驗證的家具。')
  return {
    expected_revision: expectedRevision,
    item: clone(item),
    others: objects.filter((entry) => entry.instance_id !== instanceId).map(clone),
  }
}

export function layoutConfirmationPayload(proposal, objects, expectedRevision) {
  return {
    expected_revision: expectedRevision,
    user_reviewed: true,
    proposal_source: proposal?.source === 'openrouter' ? 'openrouter' : 'local_rules',
    openrouter: clone(proposal?.openrouter || {}),
    scene_objects: objects.map(clone),
  }
}

export function layoutObjectsToThreeItems(objects = []) {
  return objects
    .filter((item) => !item.placement_failed)
    .map((item) => ({
      id: item.instance_id,
      file: item.model_url || null,
      modelUrl: item.model_url || null,
      furnitureId: item.furniture_id,
      name: item.name_zh_raw || item.furniture_id,
      normalizedType: item.normalized_type || null,
      sizeCm: {
        width: Number(item.size_cm?.width),
        depth: Number(item.size_cm?.depth),
        height: Number(item.size_cm?.height),
      },
      placementRoomId: item.placement_room_id,
      userRequired: Boolean(item.user_required),
      selectionSource: item.selection_source || 'local_rules',
      userSelectedModel: Boolean(
        item.user_required || item.selection_source === 'user' || item.user_selected_model
      ),
      x: Number(item.position_cm?.x || 0) / 100,
      z: -Number(item.position_cm?.z || 0) / 100,
      yaw: Number(item.rotation_y_deg || 0) * Math.PI / 180,
      autoLayout: true,
      renderState: 'white_model',
    }))
}
