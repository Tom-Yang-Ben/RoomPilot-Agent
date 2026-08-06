const PRESET_SURFACE_IDS = Object.freeze({
  wall: {
    auto: "wall_json_ambientcg_wall_paint_plaster006",
    warm_white: "wall_json_ambientcg_wall_paint_paintedplaster017",
    mineral_beige: "wall_json_ambientcg_wall_paint_plaster004",
    limewash: "wall_json_ambientcg_wall_paint_plaster002",
    sage: "wall_json_ambientcg_wall_wallpaper_fabric018",
    sand: "wall_json_ambientcg_wall_paint_concrete012",
    greige: "wall_json_ambientcg_wall_paint_concrete008",
    clay: "wall_json_ambientcg_wall_paint_paintedbricks003",
    light_gray: "wall_json_ambientcg_wall_paint_concrete014",
    charcoal: "wall_json_ambientcg_wall_paint_concrete015",
  },
  floor: {
    auto: "wood_cc0_wood_textures_planks039",
    light_oak: "wood_cc0_wood_textures_planks039",
    herringbone_oak: "wood_cc0_wood_textures_planks033b",
    walnut: "wood_cc0_wood_textures_woodfloor039",
    // stone_gray 曾指到暖木色木紋磚 cal288001，選「灰石材」畫面看起來像沒換。
    // 部分 _processed 磚的 color_hex/名稱與圖檔實色不符（2026-08-06 盤點 93/239 張），
    // 這裡選 metadata 與圖檔實色皆為灰的 cng128380。
    stone_gray: "tile_ccity_tile_flooring_cng128380",
    marble: "tile_ccity_tile_flooring_cal330121",
    microcement: "tile_ccity_tile_flooring_cci12610",
  },
});

// bella-test1 catalogMaterialOptionsForPack 的不變式：材質卡縮圖、色票與 3D 貼圖
// 必須沿用同一筆 catalog 資料。這裡把精選選項先解析成 3D 實際會載入的 surface，
// 縮圖改用它的 preview_url，卡片看到的就是 3D 貼上的那張圖。
// color 保留手寫精選值（部分 _processed 磚的 color_hex 與圖檔實色不符，見上），
// 只有選項沒給 color 時才退回 catalog 的 color_hex。catalog 未載入時原樣返回。
export function alignOptionWithCatalogSurface(surfaceCatalog, usage, option) {
  if (!option?.id) return option;
  const resolved = resolveSurfaceOption(surfaceCatalog, usage, option.id);
  const surface = (surfaceCatalog?.surfaces || []).find(
    (item) => item.surface_id === resolved && item.preview_url,
  );
  if (!surface) return option;
  return {
    ...option,
    materialPreview: surface.preview_url,
    color: option.color || surface.color_hex || null,
  };
}

export function resolveSurfaceOption(surfaceCatalog, usage, option) {
  const requested = String(option || "auto");
  const surfaces = surfaceCatalog?.surfaces || [];
  const supportsUsage = (surface) =>
    surface?.surface_id && surface.usage?.includes(usage) && surface.texture_url;

  const direct = surfaces.find(
    (surface) => surface.surface_id === requested && supportsUsage(surface),
  );
  if (direct) return direct.surface_id;

  const mappedId = PRESET_SURFACE_IDS[usage]?.[requested];
  const mapped = surfaces.find(
    (surface) => surface.surface_id === mappedId && supportsUsage(surface),
  );
  return mapped?.surface_id || requested;
}
