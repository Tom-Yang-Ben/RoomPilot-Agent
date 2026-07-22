import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { structurePreviewDescriptor } from "./scene_structure_geometry.js?v=20260721-column-resize3";

export function createStructurePreview(container) {
  if (!container) return { render() {} };

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf5f3ef);
  const camera = new THREE.PerspectiveCamera(48, 1, 0.05, 50);
  camera.position.set(3.6, 2.25, 3.8);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.target.set(0, 1.25, 0);
  controls.minDistance = 3.2;
  controls.maxDistance = 7;
  controls.minPolarAngle = Math.PI * 0.18;
  controls.maxPolarAngle = Math.PI * 0.46;

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb7aa98, 2.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(3, 5, 4);
  key.castShadow = true;
  scene.add(key);

  const context = new THREE.Group();
  const selected = new THREE.Group();
  scene.add(context, selected);

  const floorMaterial = new THREE.MeshStandardMaterial({
    color: 0xd7c2a4,
    roughness: 0.78,
  });
  const wallMaterial = new THREE.MeshStandardMaterial({
    color: 0xe9e6df,
    roughness: 0.9,
    transparent: true,
    opacity: 0.34,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  function clearGroup(group) {
    while (group.children.length) {
      const child = group.children[0];
      group.remove(child);
      child.geometry?.dispose();
      child.material?.dispose();
    }
  }

  function rebuildContext({ walls = [], planWidthM = 5.2, planDepthM = 4.2, ceilingHeightM = 2.7 }) {
    clearGroup(context);
    const width = Math.max(2.4, Number(planWidthM) || 5.2);
    const depth = Math.max(2.4, Number(planDepthM) || 4.2);
    const wallHeight = Math.max(2.1, Number(ceilingHeightM) || 2.7);
    const floor = new THREE.Mesh(new THREE.BoxGeometry(width, 0.06, depth), floorMaterial);
    floor.position.y = -0.03;
    floor.receiveShadow = true;
    context.add(floor);
    walls.forEach((wall) => {
      if (!wall?.start || !wall?.end) return;
      const startX = Number(wall.start.x || 0) - width / 2;
      const startZ = Number(wall.start.y ?? wall.start.z ?? 0) - depth / 2;
      const endX = Number(wall.end.x || 0) - width / 2;
      const endZ = Number(wall.end.y ?? wall.end.z ?? 0) - depth / 2;
      const dx = endX - startX;
      const dz = endZ - startZ;
      const length = Math.hypot(dx, dz);
      if (length < 0.04) return;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(length, wallHeight, Math.max(0.08, Number(wall.thickness_m || 0.12))),
        wallMaterial.clone(),
      );
      mesh.position.set((startX + endX) / 2, wallHeight / 2, (startZ + endZ) / 2);
      mesh.rotation.y = Math.atan2(-dz, dx);
      context.add(mesh);
    });
    const radius = Math.max(width, depth, 4);
    camera.position.set(radius * 0.68, Math.max(3, radius * 0.48), radius * 0.72);
    controls.target.set(0, Math.min(1.3, wallHeight / 2), 0);
    controls.minDistance = Math.max(2.5, radius * 0.45);
    controls.maxDistance = Math.max(8, radius * 1.8);
    controls.update();
  }

  function resize() {
    const width = Math.max(container.clientWidth, 1);
    const height = Math.max(container.clientHeight, 1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function clearSelected() {
    clearGroup(selected);
  }

  let activeKind = null;

  function render(item, kind, index = 0, previewContext = {}) {
    const descriptor = structurePreviewDescriptor(item, kind, previewContext);
    if (!descriptor) return;
    rebuildContext(previewContext);
    activeKind = kind;
    clearSelected();
    resize();
    const material = new THREE.MeshStandardMaterial({
      color: kind === "beam" ? 0x6b4d8a : 0x9b684b,
      roughness: 0.6,
      metalness: 0.02,
    });
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(
        descriptor.lengthM,
        descriptor.heightM,
        descriptor.widthM,
      ),
      material,
    );
    mesh.position.set(descriptor.centerX, descriptor.centerHeightM, descriptor.centerZ);
    mesh.rotation.y = -THREE.MathUtils.degToRad(descriptor.rotationDeg);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    selected.add(mesh);
    container.dataset.previewKind = kind;
    container.dataset.previewNumber = String(index + 1);
  }

  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();

  function animate() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  return { render };
}
