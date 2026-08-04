function stringId(value) {
  return value == null || value === "" ? "" : String(value);
}

export function sceneObjectInstanceId(sceneObject) {
  return [
    sceneObject?.layout_furniture_id,
    sceneObject?.source_furniture_id,
    sceneObject?.id,
    sceneObject?.furniture_id,
  ].map(stringId).find(Boolean) || "";
}

function sceneObjectInstanceIds(sceneObject) {
  return new Set([
    sceneObject?.layout_furniture_id,
    sceneObject?.source_furniture_id,
    sceneObject?.id,
    sceneObject?.furniture_id,
  ].map(stringId).filter(Boolean));
}

function sceneObjectCatalogId(sceneObject) {
  return stringId(
    sceneObject?.catalog_furniture_id || sceneObject?.catalogFurnitureId,
  );
}

function sameValue(left, right) {
  return Boolean(stringId(left)) && stringId(left) === stringId(right);
}

function furnitureDistance(item, sceneObject) {
  const position = sceneObject?.position_cm || {};
  return Math.hypot(
    numeric(item?.xCm) - numeric(position.x),
    numeric(item?.yCm) - numeric(position.z),
  );
}

export function furniture2dIndexForSceneObject(furniture2d, sceneObject) {
  const items = furniture2d || [];
  const instanceIds = sceneObjectInstanceIds(sceneObject);
  const exactIndex = items.findIndex((item) => instanceIds.has(stringId(item?.id)));
  if (exactIndex >= 0) return exactIndex;

  // Some scene providers return the catalog product id in furniture_id and keep the
  // layout instance id separately. If the instance field is absent, narrow catalog
  // matches by room/type and finally by the nearest saved 2D position.
  const catalogId = sceneObjectCatalogId(sceneObject)
    || stringId(sceneObject?.furniture_id);
  let candidates = items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => sameValue(item?.catalogFurnitureId, catalogId));
  if (!candidates.length) return -1;

  const roomMatches = candidates.filter(({ item }) =>
    sameValue(item?.roomId, sceneObject?.placement_room_id)
  );
  if (roomMatches.length) candidates = roomMatches;

  const typeMatches = candidates.filter(({ item }) =>
    sameValue(item?.type, sceneObject?.normalized_type)
  );
  if (typeMatches.length) candidates = typeMatches;

  if (candidates.length === 1) return candidates[0].index;
  if (!candidates.length) return -1;
  return [...candidates]
    .sort((left, right) =>
      furnitureDistance(left.item, sceneObject)
      - furnitureDistance(right.item, sceneObject)
    )[0].index;
}

export function furniture2dItemForSceneObject(furniture2d, sceneObject) {
  const index = furniture2dIndexForSceneObject(furniture2d, sceneObject);
  return index >= 0 ? furniture2d[index] : null;
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
  const items = (furniture2d || []).map((item) => ({ ...item }));
  const index = furniture2dIndexForSceneObject(items, sceneObject);
  const current = index >= 0 ? items[index] : {};
  const id = stringId(current.id) || sceneObjectInstanceId(sceneObject);
  if (!id) return items;
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
    userRequired: "user_required" in sceneObject
      ? sceneObject.user_required === true
      : (current.userRequired ?? defaults.userRequired ?? false),
    userSpecified: "user_specified" in sceneObject
      ? sceneObject.user_specified === true
      : (current.userSpecified ?? defaults.userSpecified ?? false),
    modelLocked: "model_locked" in sceneObject
      ? sceneObject.model_locked === true
      : (current.modelLocked ?? defaults.modelLocked ?? false),
    // 檯面小物的宿主關係：3D↔2D 同步時不保留就會遺失。
    hostObjectId: "host_object_id" in sceneObject
      ? (sceneObject.host_object_id || null)
      : (current.hostObjectId ?? null),
    hostSurfaceHeightCm: "host_surface_height_cm" in sceneObject
      ? numeric(sceneObject.host_surface_height_cm)
      : numeric(current.hostSurfaceHeightCm),
  };

  if (index >= 0) items[index] = next;
  else items.push(next);
  return items;
}

export function removeFurniture2dBySceneObject(furniture2d, sceneObject) {
  const index = furniture2dIndexForSceneObject(furniture2d || [], sceneObject);
  if (index < 0) return (furniture2d || []).map((item) => ({ ...item }));
  return (furniture2d || [])
    .filter((_item, itemIndex) => itemIndex !== index)
    .map((item) => ({ ...item }));
}
