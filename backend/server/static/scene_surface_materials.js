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
    stone_gray: "wood_tile_ccity_tile_flooring_cal288001",
    marble: "tile_ccity_tile_flooring_cal330121",
    microcement: "tile_ccity_tile_flooring_cci12610",
  },
});

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
