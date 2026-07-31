// scene_v2.js 會載入 Three.js 的檢視器模組；jsdom 沒有 WebGL，也不需要真的算 3D。
// 這裡在模組解析階段把它們換成不做事的替身，讓測試專注在 DOM 事件與使用者回饋上。
const STUBS = new Map([
  ["scene_viewer.js", "./scene_viewer_stub.mjs"],
  ["scene_structure_preview.js", "./scene_structure_preview_stub.mjs"],
]);

export async function resolve(specifier, context, nextResolve) {
  for (const [moduleName, stub] of STUBS) {
    const [pathPart] = specifier.split("?");
    if (pathPart.endsWith(`/${moduleName}`) || pathPart.endsWith(moduleName)) {
      return {
        url: new URL(stub, import.meta.url).href,
        shortCircuit: true,
      };
    }
  }
  return nextResolve(specifier, context);
}
