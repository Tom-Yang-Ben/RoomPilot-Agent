function createPreviewDouble() {
  const cache = new Map();
  return new Proxy({}, {
    get(target, property) {
      if (property === "then") return undefined;
      if (!cache.has(property)) cache.set(property, async () => undefined);
      return cache.get(property);
    },
  });
}

export function createStructurePreview() {
  return createPreviewDouble();
}
