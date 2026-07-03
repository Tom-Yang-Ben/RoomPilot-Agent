import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function createViewer(container, statusElement) {
  // Some embedded IKEA textures fail through createImageBitmap -> blob URLs
  // in this browser runtime. Forcing GLTFLoader to use HTMLImageElement loading
  // is slower but much more reliable for the current dataset.
  if ("createImageBitmap" in globalThis) {
    globalThis.createImageBitmap = undefined;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8f5f1);

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 100);
  camera.position.set(3.2, 2.4, 3.8);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0.8, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 1.8));

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.6);
  keyLight.position.set(4, 6, 4);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0xd9d6cf, 1.1);
  rimLight.position.set(-4, 3, -3);
  scene.add(rimLight);

  const grid = new THREE.GridHelper(8, 40, 0xc7b8a7, 0xe5ddd3);
  scene.add(grid);

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(3.8, 64),
    new THREE.MeshStandardMaterial({
      color: 0xf2ece5,
      roughness: 0.98,
      metalness: 0.02,
    })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.001;
  scene.add(floor);

  const axes = new THREE.AxesHelper(1.4);
  axes.position.set(-2.3, 0.01, 2.3);
  scene.add(axes);

  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath("https://unpkg.com/three@0.165.0/examples/jsm/libs/draco/");

  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);
  let currentModel = null;
  let spinSpeed = 0;
  let loadVersion = 0;

  function setStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
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

  function fitModel(group) {
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
    controls.target.set(0, finalSize.y * 0.45, 0);
    camera.position.set(finalSize.x * 1.8 + 1.3, finalSize.y * 1.4 + 0.8, finalSize.z * 1.8 + 1.6);
    controls.update();
  }

  function clear() {
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
    setStatus("載入模型中...");

    try {
      const gltf = await loader.loadAsync(url);
      if (requestVersion !== loadVersion) {
        return;
      }
      clear();

      currentModel = new THREE.Group();
      currentModel.add(gltf.scene);
      fitModel(currentModel);
      scene.add(currentModel);
      setStatus("模型已載入，可拖曳旋轉檢視。");
    } catch (error) {
      console.error(error);
      if (requestVersion !== loadVersion) {
        return;
      }
      clear();
      const reason = error?.message || String(error);
      setStatus(`模型載入失敗：${reason}`);
    }
  }

  function resetCamera() {
    camera.position.set(3.2, 2.4, 3.8);
    controls.target.set(0, 0.8, 0);
    controls.update();
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

  return { load, resetCamera, toggleSpin, clear };
}
