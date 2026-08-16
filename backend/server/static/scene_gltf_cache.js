import * as THREE from "three";

// ── GLB 模型快取（頁面級，所有 viewer 共用）──
// 同一 model_url 只下載＋解析一次；之後每次使用都 clone，幾何與貼圖沿用
// 快取持有的共用資源。共用資源只在 LRU 淘汰時統一釋放：場景清除時以
// roompilotCachedAsset 旗標跳過（見 disposeObjectTree），避免弄壞其他
// clone；淘汰時 dispose 則安全——若仍有 clone 在畫面上，three 會在下一幀
// 惰性重新上傳，只有一次重傳成本。無上限快取會讓每個 WebGL context 的
// GPU 記憶體只增不減，最終 context 遺失（Shader Error 1282、白畫面）。
// ponytail: 以「整棟房子的相異 model_url 數」抓的粗上限；GPU 吃緊再調小
const GLTF_CACHE_LIMIT = 48;
const gltfPromiseCache = new Map();

function disposeGltfResources(gltf) {
  gltf?.scene?.traverse((object) => {
    object.geometry?.dispose?.();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      ["map", "normalMap", "roughnessMap", "metalnessMap", "alphaMap", "aoMap", "emissiveMap", "bumpMap"].forEach((key) => {
        material[key]?.dispose?.();
      });
      material.dispose();
    });
  });
}

function loadGltfCached(loader, url) {
  if (gltfPromiseCache.has(url)) {
    const cached = gltfPromiseCache.get(url);
    gltfPromiseCache.delete(url);   // LRU：重新插入成最新
    gltfPromiseCache.set(url, cached);
    return cached;
  }
  const promise = loader.loadAsync(url).catch((error) => {
    gltfPromiseCache.delete(url);   // 失敗不留快取，下次可重試
    throw error;
  });
  gltfPromiseCache.set(url, promise);
  while (gltfPromiseCache.size > GLTF_CACHE_LIMIT) {
    const oldestUrl = gltfPromiseCache.keys().next().value;
    const oldest = gltfPromiseCache.get(oldestUrl);
    gltfPromiseCache.delete(oldestUrl);
    oldest.then(disposeGltfResources).catch(() => {});
  }
  return promise;
}

function cloneCachedGltfScene(gltf) {
  const root = gltf.scene.clone(true);
  root.traverse((object) => {
    object.userData = { ...object.userData, roompilotCachedAsset: true };
  });
  return root;
}

export { cloneCachedGltfScene, loadGltfCached };
