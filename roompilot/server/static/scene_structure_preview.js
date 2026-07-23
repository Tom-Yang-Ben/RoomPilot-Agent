import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { structurePreviewDescriptor } from "./scene_structure_geometry.js?v=20260721-column-resize3";

export function createStructurePreview(container) {
  if (!container) return { render() {} };

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf5f3ef);
  const camera = new THREE.PerspectiveCamera(48, 1, 5, 5000);
  camera.position.set(360, 225, 380);

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
  controls.target.set(0, 125, 0);
  controls.minDistance = 320;
  controls.maxDistance = 700;
  controls.minPolarAngle = Math.PI * 0.18;
  controls.maxPolarAngle = Math.PI * 0.46;

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb7aa98, 2.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(300, 500, 400);
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
      child.traverse((node) => {
        node.geometry?.dispose();
        if (Array.isArray(node.material)) {
          node.material.forEach((material) => material.dispose());
        } else {
          node.material?.dispose();
        }
      });
    }
  }

  function rebuildContext({ walls = [], planWidthCm = 520, planDepthCm = 420, ceilingHeightCm = 270 }) {
    clearGroup(context);
    const width = Math.max(240, Number(planWidthCm) || 520);
    const depth = Math.max(240, Number(planDepthCm) || 420);
    const wallHeight = Math.max(210, Number(ceilingHeightCm) || 270);
    const floor = new THREE.Mesh(new THREE.BoxGeometry(width, 6, depth), floorMaterial);
    floor.position.y = -3;
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
      if (length < 4) return;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(length, wallHeight, Math.max(8, Number(wall.thickness_cm || 12))),
        wallMaterial.clone(),
      );
      mesh.position.set((startX + endX) / 2, wallHeight / 2, (startZ + endZ) / 2);
      mesh.rotation.y = Math.atan2(-dz, dx);
      context.add(mesh);
    });
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
  let activeDescriptor = null;
  let activeView = "perspective";
  let activeDimension = null;
  let activeObject = null;

  function renderDimensionGuide() {
    if (!activeObject || !activeDescriptor) return;
    const existing = activeObject.getObjectByName("dimension-guide");
    if (existing) {
      activeObject.remove(existing);
      existing.geometry?.dispose();
      existing.material?.dispose();
    }
    if (!activeDimension) return;
    const thickness = 3.5;
    const guideLength = 12;
    let geometry;
    let position;
    let color;
    if (activeDimension === "length") {
      geometry = new THREE.BoxGeometry(
        activeDescriptor.lengthCm + guideLength,
        thickness,
        thickness,
      );
      position = new THREE.Vector3(0, activeDescriptor.heightCm / 2 + 9, 0);
      color = 0xd98324;
    } else if (activeDimension === "width") {
      geometry = new THREE.BoxGeometry(
        thickness,
        thickness,
        activeDescriptor.widthCm + guideLength,
      );
      position = new THREE.Vector3(
        activeDescriptor.lengthCm / 2 + 9,
        activeDescriptor.heightCm / 2 + 9,
        0,
      );
      color = 0x26889a;
    } else {
      geometry = new THREE.BoxGeometry(
        thickness,
        activeDescriptor.heightCm + guideLength,
        thickness,
      );
      position = new THREE.Vector3(
        activeDescriptor.lengthCm / 2 + 9,
        0,
        activeDescriptor.widthCm / 2 + 9,
      );
      color = 0x2d8a67;
    }
    const guide = new THREE.Mesh(
      geometry,
      new THREE.MeshBasicMaterial({ color, depthTest: false }),
    );
    guide.name = "dimension-guide";
    guide.position.copy(position);
    guide.renderOrder = 10;
    activeObject.add(guide);
  }

  function setActiveDimension(dimension) {
    activeDimension = ["length", "width", "height"].includes(dimension)
      ? dimension
      : null;
    renderDimensionGuide();
  }

  function focusSelectedStructure(descriptor, view = activeView) {
    if (!descriptor) return;
    const rotation = THREE.MathUtils.degToRad(descriptor.rotationDeg);
    const along = new THREE.Vector3(Math.cos(rotation), 0, -Math.sin(rotation));
    const across = new THREE.Vector3(-along.z, 0, along.x);
    const target = new THREE.Vector3(
      descriptor.centerX,
      descriptor.centerHeightCm,
      descriptor.centerZ,
    );
    const visibleWidth = view === "side"
      ? Math.max(descriptor.widthCm, descriptor.heightCm)
      : Math.max(descriptor.lengthCm, descriptor.heightCm);
    const modelClearance = view === "side"
      ? descriptor.lengthCm / 2 + 100
      : descriptor.widthCm / 2 + 100;
    const distance = Math.max(220, visibleWidth * 1.35, modelClearance);
    let direction;
    if (view === "front") {
      direction = across;
    } else if (view === "side") {
      direction = along;
    } else {
      direction = across.clone().multiplyScalar(0.78)
        .add(along.clone().multiplyScalar(0.48))
        .setY(0.42)
        .normalize();
    }
    camera.position.copy(target).add(direction.multiplyScalar(distance));
    camera.near = Math.max(2, distance / 100);
    camera.far = Math.max(3000, distance * 8);
    camera.updateProjectionMatrix();
    controls.target.copy(target);
    controls.enabled = view === "perspective";
    controls.minDistance = Math.max(120, distance * 0.45);
    controls.maxDistance = Math.max(800, distance * 2.5);
    camera.lookAt(target);
    if (controls.enabled) controls.update();
  }

  function setView(view) {
    if (!["front", "side", "perspective"].includes(view)) return;
    activeView = view;
    context.visible = view === "perspective";
    focusSelectedStructure(activeDescriptor, activeView);
  }

  function render(item, kind, index = 0, previewContext = {}) {
    const descriptor = structurePreviewDescriptor(item, kind, previewContext);
    if (!descriptor) return;
    rebuildContext(previewContext);
    activeKind = kind;
    activeDescriptor = descriptor;
    clearSelected();
    activeObject = null;
    resize();
    const material = new THREE.MeshStandardMaterial({
      color: kind === "beam" ? 0x6b4d8a : 0x9b684b,
      roughness: 0.6,
      metalness: 0.02,
    });
    const object = new THREE.Group();
    object.position.set(descriptor.centerX, descriptor.centerHeightCm, descriptor.centerZ);
    object.rotation.y = -THREE.MathUtils.degToRad(descriptor.rotationDeg);
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(
        descriptor.lengthCm,
        descriptor.heightCm,
        descriptor.widthCm,
      ),
      material,
    );
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    object.add(mesh);
    selected.add(object);
    activeObject = object;
    renderDimensionGuide();
    container.dataset.previewKind = kind;
    container.dataset.previewNumber = String(index + 1);
    context.visible = activeView === "perspective";
    focusSelectedStructure(descriptor, activeView);
  }

  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();

  function animate() {
    if (controls.enabled) controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  return { render, setView, setActiveDimension };
}
