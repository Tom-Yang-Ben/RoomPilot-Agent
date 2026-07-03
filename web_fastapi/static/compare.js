import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const FURNITURE_LIBRARY = {
  chair: {
    id: "chair",
    name: "椅子",
    sourceImage: "/assets/chair-source.png",
    sourceAlt: "椅子原圖",
    sourceTitle: "椅子原圖",
    sourceDescription: "使用 chair.png 作為目前比對來源。右側會同步切換成椅子的 TripoSR 與 SF3D 模型。",
    menuDescription: "chair.png 的比對組合",
    sourceFileLabel: "chair.png",
    panels: {
      triposr: {
        url: "/static/models/chair.glb",
        rotationDegrees: { x: -90, y: 0, z: 0 },
        orientationPresetDegrees: { x: 0, y: 0, z: 0 },
        colorSource: "頂點色 COLOR_0",
        fileName: "chair.glb",
      },
      sf3d: {
        url: "/static/models/chair_sf3d.glb",
        rotationDegrees: { x: 0, y: 0, z: 0 },
        orientationPresetDegrees: { x: 0, y: -90, z: 0 },
        colorSource: "2 張 UV 貼圖",
        fileName: "chair_sf3d.glb",
      },
    },
  },
  sofa: {
    id: "sofa",
    name: "沙發",
    sourceImage: "/assets/sofa-source.jpg",
    sourceAlt: "沙發原圖",
    sourceTitle: "沙發原圖",
    sourceDescription: "使用 sofa.jpg 作為目前比對來源。右側會同步切換成沙發的 TripoSR 與 SF3D 模型。",
    menuDescription: "sofa.jpg 的比對組合",
    sourceFileLabel: "sofa.jpg",
    panels: {
      triposr: {
        url: "/static/models/sofa_raw.glb",
        rotationDegrees: { x: -90, y: 0, z: 0 },
        orientationPresetDegrees: { x: 0, y: 0, z: 0 },
        colorSource: "頂點色 / 原始材質",
        fileName: "sofa_raw.glb",
      },
      sf3d: {
        url: "/static/models/sofa_sf3d.glb",
        rotationDegrees: { x: 0, y: 0, z: 0 },
        orientationPresetDegrees: { x: 0, y: 0, z: 0 },
        colorSource: "2 張 UV 貼圖",
        fileName: "sofa_sf3d.glb",
      },
    },
  },
};

const PANEL_CONFIGS = [
  {
    id: "triposr",
    title: "TripoSR",
    viewportId: "triposr-viewport",
    statusId: "triposr-status",
    loadingId: "triposr-loading",
    panelLabel: "TripoSR",
  },
  {
    id: "sf3d",
    title: "Stable Fast 3D",
    viewportId: "sf3d-viewport",
    statusId: "sf3d-status",
    loadingId: "sf3d-loading",
    panelLabel: "SF3D",
  },
];

const STORAGE_KEY = "compare-furniture";
const ORIENTATION_STORAGE_KEY = "compare-orientation";
const initialView = "iso";
const comparisonHeightMeters = 1;
const loader = new GLTFLoader();
const viewers = new Map();

const furnitureMenu = document.getElementById("furniture-menu");
const sourceImage = document.getElementById("source-image");
const sourceTitle = document.getElementById("source-title");
const sourceCopy = document.getElementById("source-copy");
const sidebarSourceName = document.getElementById("sidebar-source-name");
const sidebarTripoSrName = document.getElementById("sidebar-triposr-name");
const sidebarSf3dName = document.getElementById("sidebar-sf3d-name");
const orientationSwitchButtons = Array.from(document.querySelectorAll("[data-orientation-target]"));
const orientationAxisButtons = Array.from(document.querySelectorAll("[data-orientation-axis]"));
const orientationResetButton = document.getElementById("orientation-reset");
const orientationValueNodes = {
  x: document.getElementById("orientation-x"),
  y: document.getElementById("orientation-y"),
  z: document.getElementById("orientation-z"),
};
let activeFurnitureId = getStoredFurnitureId();
let activeOrientationTarget = "triposr";
let orientationState = loadOrientationState();

function getStoredFurnitureId() {
  try {
    const storedValue = localStorage.getItem(STORAGE_KEY);
    return storedValue && FURNITURE_LIBRARY[storedValue] ? storedValue : "chair";
  } catch {
    return "chair";
  }
}

function storeFurnitureId(furnitureId) {
  try {
    localStorage.setItem(STORAGE_KEY, furnitureId);
  } catch {
    // localStorage may be unavailable in some contexts; ignore safely.
  }
}

function createRotationDegrees(x = 0, y = 0, z = 0) {
  return { x, y, z };
}

function addRotationDegrees(base, extra) {
  return createRotationDegrees(
    (base?.x || 0) + (extra?.x || 0),
    (base?.y || 0) + (extra?.y || 0),
    (base?.z || 0) + (extra?.z || 0)
  );
}

function createDefaultOrientationState() {
  return Object.fromEntries(
    Object.keys(FURNITURE_LIBRARY).map((furnitureId) => [
      furnitureId,
      {
        triposr: createRotationDegrees(),
        sf3d: createRotationDegrees(),
      },
    ])
  );
}

function sanitizeRotationDegrees(rotation) {
  return createRotationDegrees(
    Number(rotation?.x) || 0,
    Number(rotation?.y) || 0,
    Number(rotation?.z) || 0
  );
}

function loadOrientationState() {
  const defaults = createDefaultOrientationState();

  try {
    const raw = localStorage.getItem(ORIENTATION_STORAGE_KEY);
    if (!raw) return defaults;

    const parsed = JSON.parse(raw);
    Object.keys(defaults).forEach((furnitureId) => {
      const storedFurniture = parsed?.[furnitureId];
      if (!storedFurniture) return;

      Object.keys(defaults[furnitureId]).forEach((panelId) => {
        if (storedFurniture[panelId]) {
          defaults[furnitureId][panelId] = sanitizeRotationDegrees(storedFurniture[panelId]);
        }
      });
    });
  } catch {
    return defaults;
  }

  return defaults;
}

function persistOrientationState() {
  try {
    localStorage.setItem(ORIENTATION_STORAGE_KEY, JSON.stringify(orientationState));
  } catch {
    // localStorage may be unavailable in some contexts; ignore safely.
  }
}

function ensureOrientationBucket(furnitureId) {
  if (!orientationState[furnitureId]) {
    orientationState[furnitureId] = {
      triposr: createRotationDegrees(),
      sf3d: createRotationDegrees(),
    };
  }

  return orientationState[furnitureId];
}

function getOrientationForPanel(furnitureId, panelId) {
  const bucket = ensureOrientationBucket(furnitureId);
  if (!bucket[panelId]) {
    bucket[panelId] = createRotationDegrees();
  }

  return bucket[panelId];
}

function normalizeQuarterTurnAngle(value) {
  let normalized = Math.round(value / 90) * 90;
  normalized %= 360;
  if (normalized > 180) normalized -= 360;
  if (normalized <= -180) normalized += 360;
  return normalized;
}

function renderOrientationPanel() {
  orientationSwitchButtons.forEach((button) => {
    const isActive = button.dataset.orientationTarget === activeOrientationTarget;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  const currentOrientation = getOrientationForPanel(activeFurnitureId, activeOrientationTarget);
  orientationValueNodes.x.textContent = `${currentOrientation.x}°`;
  orientationValueNodes.y.textContent = `${currentOrientation.y}°`;
  orientationValueNodes.z.textContent = `${currentOrientation.z}°`;
}

function rerenderCurrentOrientationViewer() {
  const viewer = viewers.get(activeOrientationTarget);
  if (!viewer) return;
  loadViewerModel(viewer, getActiveFurniture());
}

function setOrientationTarget(panelId) {
  if (!viewers.has(panelId)) return;
  activeOrientationTarget = panelId;
  renderOrientationPanel();
}

function adjustOrientation(axis, delta) {
  const currentOrientation = getOrientationForPanel(activeFurnitureId, activeOrientationTarget);
  currentOrientation[axis] = normalizeQuarterTurnAngle(currentOrientation[axis] + delta);
  persistOrientationState();
  renderOrientationPanel();
  rerenderCurrentOrientationViewer();
}

function resetOrientation() {
  ensureOrientationBucket(activeFurnitureId)[activeOrientationTarget] = createRotationDegrees();
  persistOrientationState();
  renderOrientationPanel();
  rerenderCurrentOrientationViewer();
}

function resizeViewer(viewer) {
  const width = Math.max(viewer.viewport.clientWidth, 1);
  const height = Math.max(viewer.viewport.clientHeight, 1);
  viewer.camera.aspect = width / height;
  viewer.camera.updateProjectionMatrix();
  viewer.renderer.setSize(width, height, false);
}

function disposeMaterial(material) {
  if (!material) return;

  Object.values(material).forEach((value) => {
    if (value && value.isTexture) {
      value.dispose();
    }
  });

  material.dispose?.();
}

function disposeModel(model) {
  model.traverse((object) => {
    if (!object.isMesh) return;
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach(disposeMaterial);
  });
}

function clearViewerModel(viewer) {
  if (!viewer.model) return;
  viewer.scene.remove(viewer.model);
  disposeModel(viewer.model);
  viewer.model = null;
}

function prepareModel(model, baseRotationDegrees, correctionDegrees = createRotationDegrees()) {
  const rotationDegrees = addRotationDegrees(baseRotationDegrees, correctionDegrees);

  model.rotation.set(
    THREE.MathUtils.degToRad(rotationDegrees.x),
    THREE.MathUtils.degToRad(rotationDegrees.y),
    THREE.MathUtils.degToRad(rotationDegrees.z)
  );
  model.updateWorldMatrix(true, true);

  model.traverse((object) => {
    if (!object.isMesh) return;
    object.castShadow = true;
    object.receiveShadow = true;

    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      if (material.map) material.map.anisotropy = 8;
      material.needsUpdate = true;
    });
  });

  const sourceBox = new THREE.Box3().setFromObject(model);
  const sourceSize = sourceBox.getSize(new THREE.Vector3());
  const sourceHeight = Math.max(sourceSize.y, 0.001);
  model.scale.setScalar(comparisonHeightMeters / sourceHeight);
  model.updateWorldMatrix(true, true);

  const scaledBox = new THREE.Box3().setFromObject(model);
  const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
  model.position.x -= scaledCenter.x;
  model.position.y -= scaledBox.min.y;
  model.position.z -= scaledCenter.z;
  model.updateWorldMatrix(true, true);

  return new THREE.Box3().setFromObject(model);
}

function getViewDirection(view) {
  const directions = {
    iso: new THREE.Vector3(1, 0.68, 1),
    front: new THREE.Vector3(0, 0.12, 1),
    side: new THREE.Vector3(1, 0.12, 0),
    top: new THREE.Vector3(0, 1, 0.001),
  };

  return (directions[view] || directions.iso).clone().normalize();
}

function setViewerCamera(viewer, view) {
  const direction = getViewDirection(view);
  viewer.camera.position.copy(viewer.target).addScaledVector(direction, viewer.distance);
  viewer.camera.near = Math.max(viewer.distance / 100, 0.01);
  viewer.camera.far = viewer.distance * 20;
  viewer.camera.updateProjectionMatrix();
  viewer.controls.target.copy(viewer.target);
  viewer.controls.update();
}

function loadViewerModel(viewer, furniture) {
  const panelSpec = furniture.panels[viewer.id];
  const loadToken = (viewer.loadToken || 0) + 1;
  viewer.loadToken = loadToken;

  viewer.status.textContent = `${furniture.name} · ${viewer.panelLabel} 載入中`;
  delete viewer.status.dataset.state;
  viewer.loading.textContent = `載入 ${furniture.name} ${viewer.panelLabel} 模型`;
  viewer.loading.classList.remove("hidden");
  clearViewerModel(viewer);

  loader.load(
    panelSpec.url,
    (gltf) => {
      if (viewer.loadToken !== loadToken) return;

      viewer.model = gltf.scene;
      const correctionDegrees = addRotationDegrees(
        panelSpec.orientationPresetDegrees,
        getOrientationForPanel(furniture.id, viewer.id)
      );
      const box = prepareModel(viewer.model, panelSpec.rotationDegrees, correctionDegrees);
      viewer.scene.add(viewer.model);

      const size = box.getSize(new THREE.Vector3());
      viewer.target.copy(box.getCenter(new THREE.Vector3()));
      viewer.distance = Math.max(size.length() * 1.9, 2.7);
      viewer.controls.target.copy(viewer.target);
      setViewerCamera(viewer, initialView);

      viewer.status.textContent = `${furniture.name} · ${viewer.panelLabel}：X ${size.x.toFixed(2)}m · Y ${size.y.toFixed(2)}m · Z ${size.z.toFixed(2)}m · ${panelSpec.colorSource}`;
      viewer.status.dataset.state = "ready";
      viewer.loading.classList.add("hidden");
    },
    undefined,
    (error) => {
      if (viewer.loadToken !== loadToken) return;

      console.error(`${viewer.id} GLB 載入失敗`, error);
      viewer.status.textContent = `${furniture.name} · ${viewer.panelLabel} 載入失敗`;
      viewer.status.dataset.state = "error";
      viewer.loading.textContent = `${furniture.name} ${viewer.panelLabel} 載入失敗`;
    }
  );
}

function createViewer(config) {
  const viewport = document.getElementById(config.viewportId);
  const status = document.getElementById(config.statusId);
  const loading = document.getElementById(config.loadingId);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xeef0eb);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.01, 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  viewport.prepend(renderer.domElement);

  const environment = new RoomEnvironment();
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  scene.environment = pmremGenerator.fromScene(environment, 0.04).texture;
  environment.dispose();
  pmremGenerator.dispose();

  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9ddd4, 1.7));

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
  keyLight.position.set(3, 5, 4);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xffffff, 1.1);
  fillLight.position.set(-4, 2.5, -2);
  scene.add(fillLight);

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(6, 6),
    new THREE.MeshStandardMaterial({ color: 0xe7e9e3, roughness: 0.92, metalness: 0 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.01;
  floor.receiveShadow = true;
  scene.add(floor);

  const grid = new THREE.GridHelper(6, 20, 0x6e746b, 0xc2c6bf);
  grid.position.y = 0.002;
  grid.material.transparent = true;
  grid.material.opacity = 0.78;
  scene.add(grid);

  const axes = new THREE.AxesHelper(1.2);
  axes.position.set(-1.35, 0.01, -1.35);
  scene.add(axes);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;
  controls.screenSpacePanning = true;
  controls.minDistance = 1.2;
  controls.maxDistance = 12;

  const viewer = {
    ...config,
    viewport,
    status,
    loading,
    scene,
    camera,
    renderer,
    controls,
    model: null,
    target: new THREE.Vector3(0, 0.8, 0),
    distance: 4,
    loadToken: 0,
  };

  const resizeObserver = new ResizeObserver(() => resizeViewer(viewer));
  resizeObserver.observe(viewport);
  viewer.resizeObserver = resizeObserver;
  resizeViewer(viewer);
  return viewer;
}

function getActiveFurniture() {
  return FURNITURE_LIBRARY[activeFurnitureId] || FURNITURE_LIBRARY.chair;
}

function renderFurnitureMenu() {
  furnitureMenu.innerHTML = "";

  Object.values(FURNITURE_LIBRARY).forEach((furniture) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "furniture-button";
    button.dataset.furnitureId = furniture.id;
    button.setAttribute("aria-pressed", String(furniture.id === activeFurnitureId));

    const image = document.createElement("img");
    image.src = furniture.sourceImage;
    image.alt = furniture.sourceAlt;

    const content = document.createElement("div");
    content.className = "furniture-button-copy";

    const title = document.createElement("div");
    title.className = "furniture-button-title";
    title.textContent = furniture.name;

    const subtitle = document.createElement("div");
    subtitle.className = "furniture-button-subtitle";
    subtitle.textContent = furniture.menuDescription;

    const status = document.createElement("div");
    status.className = "furniture-button-status";
    status.textContent = `${furniture.sourceFileLabel} · TripoSR / SF3D`;

    content.append(title, subtitle, status);
    button.append(image, content);

    button.addEventListener("click", () => {
      if (furniture.id === activeFurnitureId) return;
      setActiveFurniture(furniture.id);
    });

    furnitureMenu.appendChild(button);
  });
}

function updateFurnitureContext(furniture) {
  sourceImage.src = furniture.sourceImage;
  sourceImage.alt = furniture.sourceAlt;
  sourceTitle.textContent = furniture.sourceTitle;
  sourceCopy.textContent = furniture.sourceDescription;
  sidebarSourceName.textContent = `${furniture.name} / ${furniture.sourceFileLabel}`;
  sidebarTripoSrName.textContent = furniture.panels.triposr.fileName;
  sidebarSf3dName.textContent = furniture.panels.sf3d.fileName;
  document.title = `${furniture.name} 3D 比對`;
}

function setActiveFurniture(furnitureId) {
  if (!FURNITURE_LIBRARY[furnitureId]) return;

  activeFurnitureId = furnitureId;
  storeFurnitureId(furnitureId);

  const furniture = getActiveFurniture();
  updateFurnitureContext(furniture);
  renderFurnitureMenu();
  renderOrientationPanel();
  viewers.forEach((viewer) => loadViewerModel(viewer, furniture));
}

document.querySelectorAll("[data-shared-view]").forEach((button) => {
  button.addEventListener("click", () => {
    viewers.forEach((viewer) => setViewerCamera(viewer, button.dataset.sharedView));
  });
});

document.querySelectorAll("[data-reset-view]").forEach((button) => {
  button.addEventListener("click", () => {
    const viewer = viewers.get(button.dataset.resetView);
    if (viewer) setViewerCamera(viewer, initialView);
  });
});

orientationSwitchButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setOrientationTarget(button.dataset.orientationTarget);
  });
});

orientationAxisButtons.forEach((button) => {
  button.addEventListener("click", () => {
    adjustOrientation(button.dataset.orientationAxis, Number(button.dataset.step));
  });
});

orientationResetButton?.addEventListener("click", () => {
  resetOrientation();
});

PANEL_CONFIGS.forEach((config) => {
  viewers.set(config.id, createViewer(config));
});

setActiveFurniture(activeFurnitureId);

function animate() {
  requestAnimationFrame(animate);
  viewers.forEach((viewer) => {
    viewer.controls.update();
    viewer.renderer.render(viewer.scene, viewer.camera);
  });
}

animate();
