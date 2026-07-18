const ROLE_PATTERNS = Object.freeze({
  fabric: /fabric|cloth|textile|upholstery|seat|cushion|布|皮革|leather/i,
  wood: /wood|oak|walnut|ash|beech|frame|木|橡木|胡桃/i,
  metal: /metal|steel|iron|brass|chrome|leg|金屬|鐵|鋼|銅/i,
  glass: /glass|玻璃/i,
  stone: /stone|marble|granite|quartz|top|石|大理石/i,
});

const SCHEME_NAMES = ["明亮自然", "溫潤層次", "沉穩對比"];
const COMPATIBLE_FINISHES = Object.freeze({
  fabric: ["fabric", "leather"],
  wood: ["wood", "paint"],
  metal: ["matte_metal", "brushed_metal"],
  glass: ["transparent_glass"],
  stone: ["stone", "wood"],
});

export function classifyMaterialSlot(name = "") {
  return Object.entries(ROLE_PATTERNS).find(([, pattern]) => pattern.test(name))?.[0] || "unknown";
}

function paletteFor(scene) {
  const palette = scene.style_card?.palette_hex || scene.style?.palette_hex || [];
  return [...palette, "#f3eee7", "#b58b63", "#59636a", "#d7c9b8"].slice(0, 4);
}

function surfaceChoices(scene, catalog) {
  const styleId = scene.style?.style_id || "scandinavian";
  const profile = catalog.style_surface_profiles?.[styleId] || {};
  const surfaces = new Map((catalog.surfaces || []).map((item) => [item.surface_id, item]));
  const preferred = (profile.floor_surface_ids || []).map((id) => surfaces.get(id)).filter(Boolean);
  const fallback = (catalog.surfaces || []).filter((item) => !item.suitable_styles?.length || item.suitable_styles.includes(styleId));
  return preferred.length ? preferred : fallback;
}

function overrideForSlot(slot, palette, variant) {
  const role = classifyMaterialSlot(slot);
  const colorByRole = {
    fabric: palette[variant % palette.length],
    wood: palette[(variant + 1) % palette.length],
    metal: palette[(variant + 2) % palette.length],
    stone: palette[(variant + 3) % palette.length],
    glass: "#dce8e8",
  };
  if (role === "unknown") return { role, preserveOriginal: true };
  return {
    role,
    colorHex: colorByRole[role],
    preserveOriginal: false,
    transparent: role === "glass",
    opacity: role === "glass" ? 0.32 : 1,
    roughness: role === "metal" || role === "glass" ? 0.28 : role === "fabric" ? 0.88 : 0.62,
    metalness: role === "metal" ? 0.72 : 0,
  };
}

export function generateMaterialSchemes(scene, catalog) {
  const palette = paletteFor(scene);
  const surfaces = surfaceChoices(scene, catalog);
  return ["A", "B", "C"].map((id, index) => {
    const wallColorHex = palette[index % palette.length];
    const floorSurfaceId = surfaces[index % Math.max(surfaces.length, 1)]?.surface_id || null;
    const furnitureRoles = [...new Set((scene.scene_objects || []).flatMap((item) =>
      (item.material_slots || []).map(classifyMaterialSlot).filter((role) => role !== "unknown")
    ))];
    return {
      id,
      name: SCHEME_NAMES[index],
      wallColorHex,
      floorSurfaceId,
      changeSummary: {
        wall: { before: scene.design_choices?.wall_option || "原始牆面", after: wallColorHex },
        floor: { before: scene.design_choices?.floor_option || "原始地板", after: floorSurfaceId || "保留原材質" },
        furnitureCount: (scene.scene_objects || []).length,
        furnitureRoles,
      },
      roleOverrides: Object.fromEntries(["fabric", "wood", "metal", "glass", "stone"].map((role) => [role, overrideForSlot(role, palette, index)])),
      furniture: Object.fromEntries((scene.scene_objects || []).map((item) => [
        item.furniture_id,
        Object.fromEntries((item.material_slots || ["default"]).map((slot) => [slot, overrideForSlot(slot, palette, index)])),
      ])),
    };
  });
}

export function applyMaterialScheme(scene, scheme) {
  const next = structuredClone(scene);
  next.original_design_choices ||= structuredClone(scene.design_choices || {});
  next.design_choices = {
    ...(next.design_choices || {}),
    wall_color_hex: scheme.wallColorHex,
    floor_option: scheme.floorSurfaceId || next.design_choices?.floor_option || "auto",
    material_scheme_id: scheme.id,
  };
  next.material_role_overrides = structuredClone(scheme.roleOverrides || {});
  next.use_original_materials = false;
  next.scene_objects = (next.scene_objects || []).map((item) => ({
    ...item,
    original_material_overrides: item.original_material_overrides || structuredClone(item.material_overrides || {}),
    material_overrides: structuredClone(scheme.furniture[item.furniture_id] || {}),
  }));
  return next;
}

export function restoreOriginalMaterials(scene) {
  const next = structuredClone(scene);
  if (next.original_design_choices) next.design_choices = structuredClone(next.original_design_choices);
  next.scene_objects = (next.scene_objects || []).map((item) => ({
    ...item,
    material_overrides: structuredClone(item.original_material_overrides || {}),
  }));
  next.material_role_overrides = {};
  next.use_original_materials = true;
  return next;
}

export function updateFurnitureMaterialOverride(scene, { furnitureId, slot, finish, colorHex }) {
  const role = classifyMaterialSlot(slot);
  if (role === "unknown") throw new Error("未知材質欄位只能保留原始材質");
  if (!COMPATIBLE_FINISHES[role].includes(finish)) throw new Error(`${role} 不相容材質：${finish}`);
  const next = structuredClone(scene);
  const item = (next.scene_objects || []).find((candidate) => candidate.furniture_id === furnitureId);
  if (!item) throw new Error(`找不到家具：${furnitureId}`);
  const base = overrideForSlot(slot, [colorHex || "#d7c9b8"], 0);
  item.material_overrides ||= {};
  item.material_overrides[`role:${role}`] = {
    ...base,
    finish,
    colorHex: role === "glass" ? "#dce8e8" : colorHex || base.colorHex,
    roughness: finish === "leather" ? 0.48 : finish === "paint" ? 0.35 : finish === "brushed_metal" ? 0.25 : finish === "matte_metal" ? 0.55 : base.roughness,
  };
  next.use_original_materials = false;
  return next;
}
