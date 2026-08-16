const ROLE_PATTERNS = Object.freeze({
  fabric: /fabric|cloth|textile|upholstery|seat|cushion|布|皮革|leather/i,
  wood: /wood|oak|walnut|ash|beech|frame|木|橡木|胡桃/i,
  metal: /metal|steel|iron|brass|chrome|leg|金屬|鐵|鋼|銅/i,
  glass: /glass|玻璃/i,
  stone: /stone|marble|granite|quartz|top|石|大理石/i,
});

export function classifyMaterialSlot(name = "") {
  return Object.entries(ROLE_PATTERNS).find(([, pattern]) => pattern.test(name))?.[0] || "unknown";
}
