function clamp01(value) {
  return Math.min(1, Math.max(0, Number(value) || 0));
}

function parseHex(value) {
  const text = String(value || "#ffffff").replace("#", "");
  const expanded = text.length === 3
    ? text.split("").map((part) => `${part}${part}`).join("")
    : text.padEnd(6, "f").slice(0, 6);
  return [
    Number.parseInt(expanded.slice(0, 2), 16),
    Number.parseInt(expanded.slice(2, 4), 16),
    Number.parseInt(expanded.slice(4, 6), 16),
  ].map((channel) => Number.isFinite(channel) ? channel : 255);
}

function toHex(channels) {
  return `#${channels
    .map((channel) => Math.round(channel).toString(16).padStart(2, "0"))
    .join("")}`;
}

function mixHex(from, to, amount) {
  const start = parseHex(from);
  const end = parseHex(to);
  const ratio = clamp01(amount);
  return toHex(start.map((channel, index) =>
    channel + (end[index] - channel) * ratio));
}

function distanceFromWhite(color) {
  const channels = parseHex(color);
  return Math.hypot(...channels.map((channel) => 255 - channel)) / Math.sqrt(3 * 255 ** 2);
}

export function surfaceTint(color, imageSurface, usage = "generic") {
  if (!imageSurface) return String(color || "#ffffff");
  const contrast = distanceFromWhite(color || "#ffffff");
  const base = usage === "wall" ? 0.52 : usage === "floor" ? 0.68 : 0.56;
  const strength = base + contrast * (usage === "wall" ? 0.28 : 0.2);
  return mixHex("#ffffff", color || "#ffffff", strength);
}

export function surfacePbrProfile(surface = {}, usage = "floor") {
  const category = String(surface.category || "").toLowerCase();
  const isWall = usage === "wall";
  const isWood = category.includes("wood") || category.includes("plank");
  const isTile = category.includes("tile") || category.includes("stone")
    || category.includes("marble");

  if (isWall) {
    return {
      roughness: 0.93,
      metalness: 0,
      bumpScale: 0.012,
      clearcoat: 0,
      clearcoatRoughness: 1,
      envMapIntensity: 0.42,
    };
  }
  if (isWood) {
    return {
      roughness: 0.56,
      metalness: 0,
      bumpScale: 0.028,
      clearcoat: 0.12,
      clearcoatRoughness: 0.62,
      envMapIntensity: 0.78,
    };
  }
  if (isTile) {
    return {
      roughness: category.includes("marble") ? 0.3 : 0.48,
      metalness: 0,
      bumpScale: 0.022,
      clearcoat: category.includes("marble") ? 0.42 : 0.24,
      clearcoatRoughness: category.includes("marble") ? 0.24 : 0.46,
      envMapIntensity: 0.96,
    };
  }
  return {
    roughness: 0.72,
    metalness: 0,
    bumpScale: 0.018,
    clearcoat: 0.08,
    clearcoatRoughness: 0.7,
    envMapIntensity: 0.68,
  };
}

const FURNITURE_PROFILES = Object.freeze({
  fabric: {
    roughness: 0.9,
    metalness: 0,
    sheen: 0.34,
    sheenRoughness: 0.78,
    envMapIntensity: 0.5,
  },
  wood: {
    roughness: 0.52,
    metalness: 0,
    clearcoat: 0.1,
    clearcoatRoughness: 0.62,
    envMapIntensity: 0.82,
  },
  metal: {
    roughness: 0.24,
    metalness: 0.88,
    clearcoat: 0.3,
    clearcoatRoughness: 0.2,
    envMapIntensity: 1.35,
  },
  glass: {
    roughness: 0.08,
    metalness: 0,
    transmission: 0.9,
    thickness: 0.012,
    ior: 1.5,
    transparent: true,
    opacity: 0.32,
    envMapIntensity: 1.45,
  },
  unknown: {
    roughness: 0.62,
    metalness: 0.02,
    envMapIntensity: 0.72,
  },
});

export function furniturePbrProfile(role) {
  return {
    ...(FURNITURE_PROFILES[role] || FURNITURE_PROFILES.unknown),
  };
}

// Keep architectural finishes separate from furniture material roles. Doors,
// frames and glazing must remain physically consistent when furniture changes.
const ARCHITECTURAL_PROFILES = Object.freeze({
  door_leaf: {
    roughness: 0.46,
    metalness: 0,
    clearcoat: 0.14,
    clearcoatRoughness: 0.58,
    envMapIntensity: 0.82,
  },
  window_frame: {
    roughness: 0.3,
    metalness: 0.18,
    clearcoat: 0.24,
    clearcoatRoughness: 0.36,
    envMapIntensity: 1.04,
  },
  glass: {
    roughness: 0.07,
    metalness: 0,
    transmission: 0.9,
    thickness: 1,
    ior: 1.48,
    transparent: true,
    opacity: 0.34,
    envMapIntensity: 1.38,
  },
});

export function architecturalPbrProfile(role) {
  return {
    ...(ARCHITECTURAL_PROFILES[role] || ARCHITECTURAL_PROFILES.door_leaf),
  };
}
