import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function createViewer(container, statusElement) {
  if ("createImageBitmap" in globalThis) {
    globalThis.createImageBitmap = undefined;
  }

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 100);
  camera.position.set(3.2, 2.4, 3.8);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0.8, 0);
  renderer.domElement.addEventListener("wheel", (event) => event.preventDefault(), { passive: false });

  const ambientLight = new THREE.AmbientLight(0xffffff, 2.1);
  scene.add(ambientLight);

  const hemiLight = new THREE.HemisphereLight(0xffffff, 0xd7cab7, 1.4);
  hemiLight.position.set(0, 6, 0);
  scene.add(hemiLight);

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
  keyLight.position.set(4, 6, 4);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0xdac4a8, 1.25);
  rimLight.position.set(-4, 4, -2);
  scene.add(rimLight);

  const grid = new THREE.GridHelper(8, 40, 0xc2ab90, 0xe8dccd);
  grid.position.y = -0.03;
  scene.add(grid);

  const floorMaterial = new THREE.MeshStandardMaterial({
    color: 0xf6efe7,
    roughness: 0.98,
    metalness: 0.02,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });

  const floor = new THREE.Mesh(new THREE.CircleGeometry(3.8, 64), floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.045;
  scene.add(floor);

  const axes = new THREE.AxesHelper(1.4);
  axes.position.set(-2.3, 0.01, 2.3);
  scene.add(axes);

  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath("/static/vendor/draco/");

  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);

  let currentModel = null;
  let currentOutline = null;
  let spinSpeed = 0;
  let loadVersion = 0;

  function setStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  function setTheme(theme) {
    if (theme === "dark-stage") {
      scene.background = new THREE.Color(0x171311);
      floorMaterial.color.set(0x2a231f);
      grid.material.color.set(0x6d5d50);
      grid.material.opacity = 0.58;
      grid.material.transparent = true;
      ambientLight.intensity = 1.85;
      hemiLight.intensity = 1.25;
      hemiLight.color.set(0xf8f4ef);
      hemiLight.groundColor.set(0x6c5946);
      keyLight.intensity = 2.4;
      rimLight.intensity = 1.05;
      rimLight.color.set(0xf0d1aa);
    } else {
      scene.background = new THREE.Color(0xfcfaf7);
      floorMaterial.color.set(0xf6efe7);
      grid.material.color.set(0xc2ab90);
      grid.material.opacity = 1;
      grid.material.transparent = false;
      ambientLight.intensity = 2.1;
      hemiLight.intensity = 1.4;
      hemiLight.color.set(0xffffff);
      hemiLight.groundColor.set(0xd7cab7);
      keyLight.intensity = 2.8;
      rimLight.intensity = 1.25;
      rimLight.color.set(0xdac4a8);
    }
  }

  function disposeModel(root) {
    if (!root) return;
    root.traverse((object) => {
      if (object.geometry) {
        object.geometry.dispose();
      }

      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => {
        ["map", "normalMap", "roughnessMap", "metalnessMap", "alphaMap", "aoMap", "emissiveMap"].forEach((key) => {
          if (material[key]) {
            material[key].dispose();
          }
        });
        material.dispose();
      });
    });
  }

  function clearOutline() {
    if (!currentOutline) return;
    scene.remove(currentOutline);
    currentOutline.geometry.dispose();
    currentOutline.material.dispose();
    currentOutline = null;
  }

  function fitModel(group) {
    floor.visible = true;
    grid.visible = true;
    group.rotation.set(0, 0, 0);

    const box = new THREE.Box3().setFromObject(group);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());

    group.position.x -= center.x;
    group.position.z -= center.z;
    group.position.y -= box.min.y;

    const maxSide = Math.max(size.x, size.y, size.z);
    if (maxSide > 2.4) {
      const ratio = 2.4 / maxSide;
      group.scale.setScalar(ratio);
      group.updateMatrixWorld(true);
      const scaledBox = new THREE.Box3().setFromObject(group);
      group.position.y -= scaledBox.min.y;
    }

    const finalBox = new THREE.Box3().setFromObject(group);
    const finalSize = finalBox.getSize(new THREE.Vector3());
    const flatThreshold = Math.max(finalSize.x, finalSize.z) * 0.06;
    const isFlatObject = finalSize.y <= flatThreshold;

    if (isFlatObject) {
      floor.visible = false;
      group.rotation.x = -0.28;
      group.position.y += 0.14;
      controls.target.set(0, finalSize.y * 0.2, 0);
      camera.position.set(
        Math.max(finalSize.x * 0.65, 0.9),
        Math.max(finalSize.x, finalSize.z) * 0.9 + 0.9,
        Math.max(finalSize.z * 0.95, 1.15)
      );

      group.updateMatrixWorld(true);
      const tiltedBox = new THREE.Box3().setFromObject(group);
      const helper = new THREE.Box3Helper(tiltedBox, 0xb98752);
      currentOutline = helper;
      scene.add(helper);
    } else {
      controls.target.set(0, finalSize.y * 0.45, 0);
      camera.position.set(finalSize.x * 1.8 + 1.3, finalSize.y * 1.4 + 0.8, finalSize.z * 1.8 + 1.6);
    }

    controls.update();
  }

  function resetCamera() {
    camera.position.set(3.2, 2.4, 3.8);
    controls.target.set(0, 0.8, 0);
    controls.update();
  }

  function clear() {
    clearOutline();
    if (currentModel) {
      scene.remove(currentModel);
      disposeModel(currentModel);
      currentModel = null;
    }
    spinSpeed = 0;
    resetCamera();
  }

  async function load(url) {
    const requestVersion = ++loadVersion;
    setStatus("模型載入中...");

    try {
      const gltf = await loader.loadAsync(url);
      if (requestVersion !== loadVersion) return;

      clear();
      currentModel = new THREE.Group();
      currentModel.add(gltf.scene);
      fitModel(currentModel);
      scene.add(currentModel);
      setStatus("模型已載入，可拖曳、縮放與旋轉檢視。");
    } catch (error) {
      console.error(error);
      if (requestVersion !== loadVersion) return;

      clear();
      const reason = error?.message || String(error);
      setStatus(`模型載入失敗，請確認這件家具的 GLB 是否可用。${reason}`);
    }
  }

  function toggleSpin() {
    spinSpeed = spinSpeed > 0 ? 0 : 0.01;
    return spinSpeed > 0;
  }

  function onResize() {
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  window.addEventListener("resize", onResize);

  renderer.setAnimationLoop(() => {
    if (currentModel && spinSpeed > 0) {
      currentModel.rotation.y += spinSpeed;
    }
    controls.update();
    renderer.render(scene, camera);
  });

  setTheme("light-stage");

  return { load, resetCamera, toggleSpin, clear, setTheme };
}
