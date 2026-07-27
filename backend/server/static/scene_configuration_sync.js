function sceneObjectId(sceneObject) {
  return String(sceneObject?.furniture_id || "");
}

function numeric(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function upsertFurniture2dFromSceneObject(
  furniture2d,
  sceneObject,
  defaults = {},
) {
  const id = sceneObjectId(sceneObject);
  if (!id) return (furniture2d || []).map((item) => ({ ...item }));

  const items = (furniture2d || []).map((item) => ({ ...item }));
  const index = items.findIndex((item) => String(item.id) === id);
  const current = index >= 0 ? items[index] : {};
  const size = sceneObject.size_cm || {};
  const position = sceneObject.position_cm || {};
  const next = {
    ...current,
    id,
    roomId: sceneObject.placement_room_id
      || current.roomId
      || defaults.roomId
      || null,
    type: sceneObject.normalized_type
      || current.type
      || defaults.type
      || "furniture",
    variantId: sceneObject.variant_id
      || current.variantId
      || defaults.variantId
      || "standard",
    label: sceneObject.name_zh
      || sceneObject.name_zh_raw
      || current.label
      || defaults.label
      || sceneObject.normalized_type
      || "家具",
    iconPath: current.iconPath || defaults.iconPath || "",
    widthCm: numeric(size.width, numeric(current.widthCm, 80)),
    depthCm: numeric(size.depth, numeric(current.depthCm, 80)),
    heightCm: numeric(size.height, numeric(current.heightCm, 80)),
    xCm: numeric(position.x, numeric(current.xCm)),
    yCm: numeric(position.z, numeric(current.yCm)),
    rotationDeg: numeric(sceneObject.rotation_y_deg, numeric(current.rotationDeg)),
    catalogFurnitureId: sceneObject.catalog_furniture_id
      || current.catalogFurnitureId
      || defaults.catalogFurnitureId
      || null,
    model_url: sceneObject.model_url || current.model_url || defaults.model_url || null,
    placementFailed: sceneObject.placement_failed === true,
    placementReason: sceneObject.placement_reason || "",
    reason: current.reason || defaults.reason || "",
    userRequired: current.userRequired ?? defaults.userRequired ?? false,
  };

  if (index >= 0) items[index] = next;
  else items.push(next);
  return items;
}

export function removeFurniture2dBySceneObject(furniture2d, sceneObject) {
  const id = sceneObjectId(sceneObject);
  if (!id) return (furniture2d || []).map((item) => ({ ...item }));
  return (furniture2d || [])
    .filter((item) => String(item.id) !== id)
    .map((item) => ({ ...item }));
}
