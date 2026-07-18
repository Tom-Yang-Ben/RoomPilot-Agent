const PRESET_SURFACE_IDS = Object.freeze({
  wall: {
    auto: "wall_ambientcg_plaster006",
    warm_white: "wall_ambientcg_plaster006",
    mineral_beige: "wall_ambientcg_plaster006",
    limewash: "wall_ambientcg_plaster006",
    sage: "wall_ambientcg_plaster006",
    sand: "wall_ambientcg_plaster006",
    greige: "wall_ambientcg_plaster006",
    clay: "wall_ambientcg_plaster006",
    light_gray: "wall_ambientcg_tiles008",
    charcoal: "wall_ambientcg_tiles009",
  },
  floor: {
    auto: "wood_cc0_wood_textures_planks039",
    light_oak: "wood_cc0_wood_textures_planks039",
    herringbone_oak: "wood_cc0_wood_textures_planks033b",
    walnut: "wood_cc0_wood_textures_woodfloor039",
    stone_gray: "tile_ccity_tile_flooring_cwo111101",
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
