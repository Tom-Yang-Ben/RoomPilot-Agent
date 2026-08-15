const PRESET_SURFACE_IDS = Object.freeze({
  wall: {
    auto: "warm_white",
    warm_white: "warm_white",
    mineral_beige: "limewash",
    limewash: "limewash",
    sage: "limewash",
    sand: "limewash",
    greige: "light_gray",
    clay: "limewash",
    light_gray: "light_gray",
    charcoal: "charcoal",
  },
  floor: {
    auto: "light_oak",
    light_oak: "light_oak",
    herringbone_oak: "light_oak",
    walnut: "walnut",
    stone_gray: "stone_gray",
    marble: "marble",
    microcement: "microcement",
  },
});

export function resolveSurfaceOption(surfaceCatalog, usage, option) {
  const requested = String(option || "auto");
  const surfaces = surfaceCatalog?.surfaces || [];
  const supportsUsage = (surface) =>
    surface?.surface_id && surface.usage?.includes(usage);

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
