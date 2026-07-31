// 任何被呼叫的檢視器方法都回傳 resolved promise；getDiagnostics 給出「沒有載入失敗」的乾淨結果。
function createViewerDouble() {
  const cache = new Map();
  return new Proxy({}, {
    get(target, property) {
      if (property === "then") return undefined;
      if (property === "getDiagnostics") {
        return () => ({ failedFurniture: [], visibleFurnitureCount: 0 });
      }
      if (!cache.has(property)) cache.set(property, async () => undefined);
      return cache.get(property);
    },
  });
}

export function createSceneViewer() {
  return createViewerDouble();
}
