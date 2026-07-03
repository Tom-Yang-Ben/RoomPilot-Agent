import * as THREE from "three";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const statusElement = document.getElementById("probe-status");
const resultsElement = document.getElementById("probe-results");

if ("createImageBitmap" in globalThis) {
  globalThis.createImageBitmap = undefined;
}

const params = new URLSearchParams(window.location.search);
const limit = Number(params.get("limit") || "0");
const concurrency = Math.max(1, Number(params.get("concurrency") || "4"));

function setStatus(text) {
  statusElement.textContent = text;
}

function render(results) {
  resultsElement.textContent = JSON.stringify(results, null, 2);
  window.__probeResults = results;
  window.__probeDone = true;
}

async function parseModel(item) {
  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath("https://unpkg.com/three@0.165.0/examples/jsm/libs/draco/");
  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);
  const response = await fetch(item.model_url);
  if (!response.ok) {
    throw new Error(`http-${response.status}`);
  }
  const arrayBuffer = await response.arrayBuffer();
  const gltf = await new Promise((resolve, reject) => {
    loader.parse(arrayBuffer, window.location.origin + "/", resolve, reject);
  });
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const size = box.getSize(new THREE.Vector3());
  return { size: [size.x, size.y, size.z] };
}

async function run() {
  setStatus("讀取資料中...");
  const siteData = await fetch("/api/site-data").then((response) => response.json());
  const allItems = siteData.furniture.filter((item) => item.has_model && item.model_url);
  const items = limit > 0 ? allItems.slice(0, limit) : allItems;

  const results = {
    checked: items.length,
    failures: [],
  };

  let currentIndex = 0;

  async function worker() {
    while (currentIndex < items.length) {
      const index = currentIndex;
      currentIndex += 1;
      const item = items[index];
      setStatus(`檢查中 ${index + 1} / ${items.length}：${item.name_zh_raw || item.name_en}`);
      try {
        await parseModel(item);
      } catch (error) {
        results.failures.push({
          furniture_id: item.furniture_id,
          name_en: item.name_en,
          name_zh_raw: item.name_zh_raw,
          model_url: item.model_url,
          error: error?.message || String(error),
        });
      }
    }
  }

  await Promise.all(Array.from({ length: concurrency }, () => worker()));

  const finalResults = {
    checked: results.checked,
    failure_count: results.failures.length,
    failures: results.failures,
  };
  setStatus(`完成：檢查 ${results.checked} 件，失敗 ${results.failures.length} 件`);
  render(finalResults);
}

window.__probeDone = false;
window.__probeResults = null;
run().catch((error) => {
  const result = {
    checked: 0,
    failure_count: 1,
    failures: [{ furniture_id: "__probe__", error: error?.message || String(error) }],
  };
  setStatus(`探針失敗：${error?.message || String(error)}`);
  render(result);
});
