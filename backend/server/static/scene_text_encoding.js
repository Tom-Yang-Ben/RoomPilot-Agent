const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

function cjkCount(value) {
  return [...value].filter((character) => {
    const codePoint = character.codePointAt(0);
    return (codePoint >= 0x3400 && codePoint <= 0x9fff)
      || (codePoint >= 0xf900 && codePoint <= 0xfaff);
  }).length;
}

export function repairMojibake(value) {
  if (typeof value !== "string" || !value) return value;
  let repaired = value;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const codePoints = [...repaired].map((character) => character.codePointAt(0));
    if (codePoints.some((codePoint) => codePoint > 0xff)) break;
    try {
      const decoded = utf8Decoder.decode(Uint8Array.from(codePoints));
      if (cjkCount(decoded) <= cjkCount(repaired)) break;
      repaired = decoded;
    } catch {
      break;
    }
  }
  return repaired;
}

export function repairMojibakeDeep(value) {
  if (typeof value === "string") return repairMojibake(value);
  if (Array.isArray(value)) return value.map(repairMojibakeDeep);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [key, repairMojibakeDeep(entry)]),
  );
}
