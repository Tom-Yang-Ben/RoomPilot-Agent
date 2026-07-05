import * as THREE from "three";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const cache = new Map();
let renderQueue = Promise.resolve();

if ("createImageBitmap" in globalThis) {
  globalThis.createImageBitmap = undefined;
}

const renderer = new THREE.WebGLRenderer({
  antialias: true,
  alpha: false,
  preserveDrawingBuffer: true,
});
renderer.setSize(720, 480, false);
renderer.setPixelRatio(1);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath("/static/vendor/draco/");

const loader = new GLTFLoader();
loader.setDRACOLoader(dracoLoader);

function isDarkFurniture(item) {
  const tokens = [item?.color, item?.name_en, item?.name_zh_raw, item?.material]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return ["black", "dark", "anthracite", "charcoal", "brown", "黑", "深灰", "深色"].some((keyword) =>
    tokens.includes(keyword)
  );
}

function createStage(theme = "light-stage") {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(theme === "dark-stage" ? 0x171311 : 0xfbf7f2);

  const camera = new THREE.PerspectiveCamera(34, 720 / 480, 0.1, 100);
  camera.position.set(3.4, 2.5, 3.6);

  const ambientLight = new THREE.AmbientLight(0xffffff, theme === "dark-stage" ? 1.9 : 2.2);
  const hemiLight = new THREE.HemisphereLight(
    theme === "dark-stage" ? 0xf8f4ef : 0xffffff,
    theme === "dark-stage" ? 0x6c5946 : 0xd8cbb9,
    theme === "dark-stage" ? 1.25 : 1.5
  );
  hemiLight.position.set(0, 6, 0);
  const keyLight = new THREE.DirectionalLight(0xffffff, theme === "dark-stage" ? 2.15 : 2.4);
  keyLight.position.set(4, 6, 4);
  const rimLight = new THREE.DirectionalLight(theme === "dark-stage" ? 0xf0d1aa : 0xdac4a8, theme === "dark-stage" ? 0.95 : 1.1);
  rimLight.position.set(-4, 4, -2);

  scene.add(ambientLight, hemiLight, keyLight, rimLight);

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(3.8, 64),
    new THREE.MeshStandardMaterial({
      color: theme === "dark-stage" ? 0x2a231f : 0xf6efe7,
      roughness: 0.98,
      metalness: 0.02,
    })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.045;
  scene.add(floor);

  const grid = new THREE.GridHelper(
    8,
    40,
    theme === "dark-stage" ? 0x6d5d50 : 0xcfb79d,
    theme === "dark-stage" ? 0x4e4137 : 0xe9ded1
  );
  grid.position.y = -0.03;
  scene.add(grid);

  return { scene, camera, floor, grid };
}

function disposeObject(root) {
  root.traverse((object) => {
    if (object.geometry) object.geometry.dispose();

    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      [
        "map",
        "normalMap",
        "roughnessMap",
        "metalnessMap",
        "alphaMap",
        "aoMap",
        "emissiveMap",
      ].forEach((key) => {
        if (material[key]) material[key].dispose();
      });
      material.dispose();
    });
  });
}

function fitModel(group, camera, floor, grid) {
  const box = new THREE.Box3().setFromObject(group);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  group.position.x -= center.x;
  group.position.z -= center.z;
  group.position.y -= box.min.y;

  const maxSide = Math.max(size.x, size.y, size.z);
  if (maxSide > 2.2) {
    const ratio = 2.2 / maxSide;
    group.scale.setScalar(ratio);
    group.updateMatrixWorld(true);
    const scaledBox = new THREE.Box3().setFromObject(group);
    group.position.y -= scaledBox.min.y;
  }

  group.updateMatrixWorld(true);
  const finalBox = new THREE.Box3().setFromObject(group);
  const finalSize = finalBox.getSize(new THREE.Vector3());
  const isFlatObject = finalSize.y <= Math.max(finalSize.x, finalSize.z) * 0.06;

  if (isFlatObject) {
    floor.visible = false;
    group.rotation.x = -0.25;
    group.position.y += 0.12;
    camera.position.set(
      Math.max(finalSize.x * 0.55, 0.95),
      Math.max(finalSize.x, finalSize.z) * 0.82 + 0.88,
      Math.max(finalSize.z * 0.9, 1.2)
    );
  } else {
    floor.visible = true;
    grid.visible = true;
    camera.position.set(finalSize.x * 1.7 + 1.2, finalSize.y * 1.3 + 0.9, finalSize.z * 1.8 + 1.45);
  }

  camera.lookAt(0, finalSize.y * 0.42, 0);
}

async function renderThumbnail(item) {
  const theme = isDarkFurniture(item) ? "light-stage" : "dark-stage";
  const cacheKey = `${item.model_url}::${theme}`;

  if (cache.has(cacheKey)) {
    return cache.get(cacheKey);
  }

  const { scene, camera, floor, grid } = createStage(theme);
  const gltf = await loader.loadAsync(item.model_url);
  const group = new THREE.Group();
  group.add(gltf.scene);
  scene.add(group);

  fitModel(group, camera, floor, grid);
  renderer.render(scene, camera);
  const imageUrl = renderer.domElement.toDataURL("image/png");
  cache.set(cacheKey, imageUrl);

  scene.remove(group);
  disposeObject(group);

  return imageUrl;
}

export function attachLibraryThumbnail(imageElement, item) {
  if (!imageElement || !item?.model_url) return;

  imageElement.dataset.modelUrl = item.model_url;

  renderQueue = renderQueue
    .then(async () => {
      const imageUrl = await renderThumbnail(item);
      if (imageElement.isConnected && imageElement.dataset.modelUrl === item.model_url) {
        imageElement.src = imageUrl;
      }
    })
    .catch((error) => {
      console.error("library thumbnail render failed", item.furniture_id, error);
    });
}
