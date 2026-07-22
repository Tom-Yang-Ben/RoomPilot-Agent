import * as THREE from "three";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import {
  buildFloorPlanOverlay,
  buildSegmentWalls,
  buildWindowBoxes,
  createFloorMaterial,
  createWallMaterial,
  fitToTargetSize,
} from "../scene_builders.js?v=20260709a";

// 720° 提案漫遊頁:佈局與互動對標酷家樂分享頁(漫遊/平面戶型/三維戶型三模式、
// 左上戶型圖、房間選擇縮圖抽屜、自動導覽),程式碼與素材全部自製,品牌為 RoomPilot。

const STORAGE_KEY = "roompilot.panorama.scene";
const EYE_HEIGHT = 1.4;
const WALL_MARGIN = 0.45;

const TYPE_LABELS = {
  sofa: "沙發", "coffee-table": "茶几", "tv-bench": "電視櫃", armchair: "單椅",
  bookcase: "書櫃", bed: "床", "bedside-table": "床頭櫃", desk: "書桌",
  "office-chair": "辦公椅", "dining-table": "餐桌", "dining-chair": "餐椅", sideboard: "邊櫃",
};
const SPACE_LABELS = {
  living_room: "客廳", bedroom: "臥室", workspace: "工作空間", dining_room: "餐廳", studio: "套房",
};

const el = (id) => document.getElementById(id);
const elements = {
  canvasHost: el("pano-canvas"),
  chipLayer: el("chip-layer"),
  loading: el("pano-loading"),
  loadingBar: document.querySelector("#loading-track i"),
  loadingText: el("loading-text"),
  minimapCard: el("minimap-card"),
  minimapRoom: el("minimap-room"),
  minimap: el("pano-minimap"),
  minimapResize: el("minimap-resize"),
  heatCount: el("heat-count"),
  modeSwitch: el("mode-switch"),
  btnFullscreen: el("btn-fullscreen"),
  btnShare: el("btn-share"),
  btnLike: el("btn-like"),
  barRooms: el("bar-rooms"),
  barNav: el("bar-nav"),
  barMusic: el("bar-music"),
  musicLabel: el("music-label"),
  barMore: el("bar-more"),
  roomsDrawer: el("rooms-drawer"),
  roomsList: el("rooms-list"),
  moreMenu: el("more-menu"),
  moreTour: el("more-tour"),
  moreSpin: el("more-spin"),
  moreNight: el("more-night"),
  nightLabel: el("night-label"),
  moreClean: el("more-clean"),
  sharePop: el("share-pop"),
  shareUrl: el("share-url"),
  shareCopy: el("share-copy"),
  card: el("pano-card"),
  cardName: el("pano-card-name"),
  cardBody: el("pano-card-body"),
  cardClose: el("pano-card-close"),
  toast: el("pano-toast"),
  exitClean: el("exit-clean"),
};

let toastTimer = null;
function showToast(message, duration = 2400) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), duration);
}

function setProgress(ratio, text) {
  elements.loadingBar.style.width = `${Math.round(ratio * 100)}%`;
  if (text) elements.loadingText.textContent = text;
}

// ── 場景資料 ──
async function getSceneData() {
  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }
  setProgress(0.06, "沒有交棒場景,正在生成示範場景...");
  const response = await fetch("/api/scene/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      room_width_cm: 420,
      room_depth_cm: 360,
      space_type: "living_room",
      style_preference: "scandinavian",
      required_furniture: ["sofa", "coffee-table", "tv-bench", "armchair"],
      keep_window_clear: true,
      keep_door_clear: true,
      wall_option: "warm_white",
      floor_option: "light_oak",
    }),
  });
  if (!response.ok) throw new Error(`場景生成失敗 HTTP ${response.status}`);
  return response.json();
}

// ── three.js 基礎 ──
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.05, 160);
const orthoCamera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.1, 80);
orthoCamera.up.set(0, 0, -1);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
elements.canvasHost.appendChild(renderer.domElement);

if ("createImageBitmap" in globalThis) {
  globalThis.createImageBitmap = undefined; // 與 scene_viewer 相同:避開 Safari 貼圖解碼問題
}

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath("/static/vendor/draco/");
const loader = new GLTFLoader();
loader.setDRACOLoader(dracoLoader);

const roomGroup = new THREE.Group();
const furnitureGroup = new THREE.Group();
scene.add(roomGroup, furnitureGroup);

const ambientLight = new THREE.AmbientLight(0xffffff, 1.55);
const hemiLight = new THREE.HemisphereLight(0xffffff, 0xdac9b8, 1.2);
hemiLight.position.set(0, 8, 0);
const keyLight = new THREE.DirectionalLight(0xffffff, 1.7);
keyLight.position.set(6, 9, 5);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
const nightLamp = new THREE.PointLight(0xffd9a0, 0, 14, 1.6);
scene.add(ambientLight, hemiLight, keyLight, nightLamp);

const LIGHT_PRESETS = {
  day: { bg: new THREE.Color(0xe9eef2), ambient: 1.55, hemi: 1.2, key: 1.7, lamp: 0 },
  night: { bg: new THREE.Color(0x0e1220), ambient: 0.32, hemi: 0.18, key: 0.05, lamp: 2.4 },
};
const MODE_BG = { plan2d: new THREE.Color(0x333a4d), plan3d: new THREE.Color(0x000000) };
let nightMode = false;
let lightBlend = 0;
scene.background = LIGHT_PRESETS.day.bg.clone();

// ── 狀態 ──
let mode = "roam"; // roam | plan2d | plan3d
const view = { yaw: 0, pitch: 0, fov: 75, position: new THREE.Vector3(0, EYE_HEIGHT, 0) };
const orbit = { theta: Math.PI / 4, phi: 0.95, radius: 9 }; // 三維戶型
const plan = { zoom: 1, panX: 0, panZ: 0 };                 // 平面戶型
let moveTween = null;
let sceneData = null;
let bounds = { minX: -2.1, maxX: 2.1, minZ: -1.8, maxZ: 1.8 };
let viewpoints = [];
let activeViewpoint = 0;
let ceilingMesh = null;
const furnitureWrappers = [];
const roamState = { tour: false, spin: false, nextMoveAt: 0, resumeDelay: 6000, dwell: 8200 };
let lastInteraction = performance.now();

function markInteraction() {
  lastInteraction = performance.now();
}

function roomCenter() {
  return { x: (bounds.minX + bounds.maxX) / 2, z: (bounds.minZ + bounds.maxZ) / 2 };
}

function clampToRoom(x, z, margin = WALL_MARGIN) {
  return {
    x: THREE.MathUtils.clamp(x, bounds.minX + margin, bounds.maxX - margin),
    z: THREE.MathUtils.clamp(z, bounds.minZ + margin, bounds.maxZ - margin),
  };
}

// ── 建房間 ──
function computeBounds(floorplan) {
  const segments = floorplan?.wall_segments || [];
  if (segments.length >= 2) {
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    segments.forEach(({ start, end }) => {
      [start, end].filter(Boolean).forEach((point) => {
        minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x);
        minZ = Math.min(minZ, point.z); maxZ = Math.max(maxZ, point.z);
      });
    });
    if (Number.isFinite(minX)) return { minX, maxX, minZ, maxZ };
  }
  const halfW = Math.max((Number(floorplan?.width_cm) || 420) / 200, 1.2);
  const halfD = Math.max((Number(floorplan?.depth_cm) || 360) / 200, 1.2);
  return { minX: -halfW, maxX: halfW, minZ: -halfD, maxZ: halfD };
}

function buildRoom() {
  const floorplan = sceneData.floorplan || {};
  const widthM = Math.max((Number(floorplan.width_cm) || 420) / 100, 2.4);
  const depthM = Math.max((Number(floorplan.depth_cm) || 360) / 100, 2.4);
  const wallHeight = 2.7;
  bounds = computeBounds(floorplan);

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(widthM, depthM), createFloorMaterial(renderer, sceneData.design_choices?.floor_option || "auto"));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  floor.userData.isFloor = true;
  roomGroup.add(floor);

  ceilingMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(widthM, depthM),
    new THREE.MeshStandardMaterial({ color: 0xf6f1e9, roughness: 0.98, side: THREE.DoubleSide })
  );
  ceilingMesh.rotation.x = Math.PI / 2;
  ceilingMesh.position.y = wallHeight;
  roomGroup.add(ceilingMesh);

  const wallMaterial = createWallMaterial(renderer, sceneData.design_choices?.wall_option || "auto");
  const registerWall = (mesh) => {
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  };
  const wallSegments = floorplan.wall_segments || [];
  const rect = [
    { start: { x: bounds.minX, z: bounds.minZ }, end: { x: bounds.maxX, z: bounds.minZ } },
    { start: { x: bounds.maxX, z: bounds.minZ }, end: { x: bounds.maxX, z: bounds.maxZ } },
    { start: { x: bounds.maxX, z: bounds.maxZ }, end: { x: bounds.minX, z: bounds.maxZ } },
    { start: { x: bounds.minX, z: bounds.maxZ }, end: { x: bounds.minX, z: bounds.minZ } },
  ];
  const useSegments = sceneData.design_choices?.single_room_mode === false && wallSegments.length >= 2;
  buildSegmentWalls(roomGroup, useSegments ? wallSegments : rect, wallMaterial, wallHeight, 0.06, registerWall);

  if (floorplan.source === "dxf") {
    buildFloorPlanOverlay(roomGroup, floorplan.door_segments || [], 0xb9773f, 0.82, 0.02);
    buildWindowBoxes(roomGroup, floorplan.window_segments || [], wallHeight);
  }

  const center = roomCenter();
  nightLamp.position.set(center.x, wallHeight - 0.35, center.z);
  orbit.radius = Math.max(widthM, depthM) * 1.5 + 2;
}

async function loadFurniture() {
  const objects = (sceneData.scene_objects || []).filter((item) => !item.placement_failed && item.model_url);
  let loaded = 0;
  await Promise.all(
    objects.map(async (item) => {
      try {
        const gltf = await loader.loadAsync(item.model_url);
        gltf.scene.traverse((object) => {
          if (object.isMesh) {
            object.castShadow = true;
            object.receiveShadow = true;
          }
        });
        const wrapper = new THREE.Group();
        wrapper.add(gltf.scene);
        fitToTargetSize(wrapper, item.size_cm || {});
        wrapper.position.set((item.position_cm?.x || 0) / 100, 0, (item.position_cm?.z || 0) / 100);
        wrapper.rotation.y = THREE.MathUtils.degToRad(item.rotation_y_deg || 0);
        wrapper.userData.sceneObject = item;
        furnitureGroup.add(wrapper);
        furnitureWrappers.push(wrapper);
      } catch (error) {
        console.warn("家具載入失敗", item.name_zh_raw, error);
      } finally {
        loaded += 1;
        setProgress(0.2 + (loaded / Math.max(objects.length, 1)) * 0.6, `努力載入中... ${loaded}/${objects.length}`);
      }
    })
  );
}

// ── 視點:候選點被家具擋住時就近找空位(矩形感知,含旋轉後的外接框) ──
function furnitureRects(buffer = 0.28) {
  return furnitureWrappers.map((wrapper) => {
    const item = wrapper.userData.sceneObject;
    const size = item.size_cm || {};
    const radians = THREE.MathUtils.degToRad(item.rotation_y_deg || 0);
    const cos = Math.abs(Math.cos(radians));
    const sin = Math.abs(Math.sin(radians));
    const width = (size.width || 80) / 100;
    const depth = (size.depth || 60) / 100;
    return {
      x: wrapper.position.x,
      z: wrapper.position.z,
      halfX: (width * cos + depth * sin) / 2 + buffer,
      halfZ: (width * sin + depth * cos) / 2 + buffer,
    };
  });
}

function isFreeSpot(x, z, rects) {
  return !rects.some((rect) => Math.abs(x - rect.x) < rect.halfX && Math.abs(z - rect.z) < rect.halfZ);
}

function findFreeNear(x, z, rects, maxRadius = 1.5) {
  const clamped = clampToRoom(x, z);
  if (isFreeSpot(clamped.x, clamped.z, rects)) return clamped;
  for (let radius = 0.2; radius <= maxRadius; radius += 0.2) {
    for (let step = 0; step < 12; step += 1) {
      const angle = (step / 12) * Math.PI * 2;
      const candidate = clampToRoom(x + Math.cos(angle) * radius, z + Math.sin(angle) * radius);
      if (isFreeSpot(candidate.x, candidate.z, rects)) return candidate;
    }
  }
  return null;
}

function furnitureCentroid() {
  if (!furnitureWrappers.length) return roomCenter();
  let x = 0, z = 0;
  furnitureWrappers.forEach((wrapper) => {
    x += wrapper.position.x;
    z += wrapper.position.z;
  });
  return { x: x / furnitureWrappers.length, z: z / furnitureWrappers.length };
}

function computeViewpoints() {
  const center = roomCenter();
  const focus = furnitureCentroid(); // 每個視點都看向家具重心,開場就有東西看
  const spanX = (bounds.maxX - bounds.minX) / 2;
  const spanZ = (bounds.maxZ - bounds.minZ) / 2;
  const spaceLabel = SPACE_LABELS[sceneData.questionnaire?.space_type] || SPACE_LABELS.living_room;
  const rects = furnitureRects();

  const candidates = [
    { name: `${spaceLabel}中心`, x: center.x, z: center.z, always: true },
    { name: "入口", x: center.x, z: bounds.maxZ - WALL_MARGIN - 0.15 },
    { name: `${spaceLabel}左前`, x: center.x - spanX * 0.5, z: center.z + spanZ * 0.5 },
    { name: `${spaceLabel}右前`, x: center.x + spanX * 0.5, z: center.z + spanZ * 0.5 },
    { name: `${spaceLabel}左後`, x: center.x - spanX * 0.5, z: center.z - spanZ * 0.5 },
    { name: `${spaceLabel}右後`, x: center.x + spanX * 0.5, z: center.z - spanZ * 0.5 },
  ];

  const placed = [];
  candidates.forEach((candidate) => {
    const spot = findFreeNear(candidate.x, candidate.z, rects) || (candidate.always ? clampToRoom(candidate.x, candidate.z) : null);
    if (!spot) return;
    if (placed.some((other) => Math.hypot(other.x - spot.x, other.z - spot.z) < 0.6)) return;
    placed.push({ name: candidate.name, x: spot.x, z: spot.z });
  });

  viewpoints = placed.map((viewpoint) => {
    const distance = Math.hypot(focus.x - viewpoint.x, focus.z - viewpoint.z);
    const target = distance > 0.4 ? focus : center;
    return { ...viewpoint, yaw: Math.atan2(target.x - viewpoint.x, target.z - viewpoint.z) };
  });
}

function nearestViewpointIndex(x, z) {
  let best = 0;
  let bestDistance = Infinity;
  viewpoints.forEach((viewpoint, index) => {
    const distance = Math.hypot(viewpoint.x - x, viewpoint.z - z);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = index;
    }
  });
  return best;
}

// ── 房間選擇抽屜:離線渲染每個視點的縮圖 ──
function buildRoomThumbnails() {
  const thumbRenderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  thumbRenderer.setSize(216, 156);
  thumbRenderer.outputColorSpace = THREE.SRGBColorSpace;
  const thumbCamera = new THREE.PerspectiveCamera(78, 216 / 156, 0.05, 160);

  const thumbnails = viewpoints.map((viewpoint) => {
    thumbCamera.position.set(viewpoint.x, EYE_HEIGHT, viewpoint.z);
    thumbCamera.lookAt(viewpoint.x + Math.sin(viewpoint.yaw), EYE_HEIGHT - 0.06, viewpoint.z + Math.cos(viewpoint.yaw));
    thumbRenderer.render(scene, thumbCamera);
    return thumbRenderer.domElement.toDataURL("image/jpeg", 0.72);
  });
  thumbRenderer.dispose();

  elements.roomsList.innerHTML = "";
  viewpoints.forEach((viewpoint, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `room-thumb${index === activeViewpoint ? " active" : ""}`;
    button.innerHTML = `<img alt="${viewpoint.name}" src="${thumbnails[index]}" /><span>${viewpoint.name}</span>`;
    button.addEventListener("click", () => {
      setMode("roam");
      goToViewpoint(index);
    });
    elements.roomsList.appendChild(button);
  });
}

function setActiveViewpoint(index) {
  activeViewpoint = index;
  elements.roomsList.querySelectorAll(".room-thumb").forEach((button, buttonIndex) => {
    button.classList.toggle("active", buttonIndex === index);
  });
  elements.minimapRoom.textContent = viewpoints[index]?.name || "戶型圖";
}

// ── 移動 ──
function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function glideTo(x, z, targetYaw = null, duration = 950) {
  const clamped = clampToRoom(x, z);
  moveTween = {
    from: view.position.clone(),
    to: new THREE.Vector3(clamped.x, EYE_HEIGHT, clamped.z),
    fromYaw: view.yaw,
    toYaw: targetYaw ?? view.yaw,
    start: performance.now(),
    duration,
  };
  setActiveViewpoint(nearestViewpointIndex(clamped.x, clamped.z));
}

function goToViewpoint(index) {
  const viewpoint = viewpoints[index];
  if (!viewpoint) return;
  const yawDelta = ((viewpoint.yaw - view.yaw) % (Math.PI * 2) + Math.PI * 3) % (Math.PI * 2) - Math.PI;
  glideTo(viewpoint.x, viewpoint.z, view.yaw + yawDelta);
}

function updateMoveTween(now) {
  if (!moveTween) return;
  const t = Math.min((now - moveTween.start) / moveTween.duration, 1);
  const eased = easeInOut(t);
  view.position.lerpVectors(moveTween.from, moveTween.to, eased);
  view.yaw = moveTween.fromYaw + (moveTween.toYaw - moveTween.fromYaw) * eased;
  if (t >= 1) moveTween = null;
}

// ── 模式切換 ──
function setMode(next) {
  mode = next;
  elements.modeSwitch.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === next);
  });
  const inRoam = next === "roam";
  if (ceilingMesh) ceilingMesh.visible = inRoam;
  elements.minimapCard.style.display = inRoam && minimapOpen ? "" : "none";
  elements.barRooms.hidden = !inRoam;
  elements.barNav.hidden = !inRoam;
  elements.roomsDrawer.classList.remove("show");
  elements.barRooms.classList.remove("active");
  if (next === "plan2d") {
    plan.zoom = 1;
    plan.panX = 0;
    plan.panZ = 0;
    planLabelNodes = buildPlanLabels();
  }
  markInteraction();
}

elements.modeSwitch.querySelectorAll("button").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

// ── 相機套用 ──
function applyCamera() {
  if (mode === "roam") {
    camera.position.copy(view.position);
    const direction = new THREE.Vector3(
      Math.sin(view.yaw) * Math.cos(view.pitch),
      Math.sin(view.pitch),
      Math.cos(view.yaw) * Math.cos(view.pitch)
    );
    camera.lookAt(view.position.clone().add(direction));
    if (Math.abs(camera.fov - view.fov) > 0.01) {
      camera.fov = view.fov;
      camera.updateProjectionMatrix();
    }
    return camera;
  }

  const center = roomCenter();
  if (mode === "plan3d") {
    const target = new THREE.Vector3(center.x, 1.0, center.z);
    camera.position.set(
      target.x + orbit.radius * Math.cos(orbit.phi) * Math.sin(orbit.theta),
      target.y + orbit.radius * Math.sin(orbit.phi),
      target.z + orbit.radius * Math.cos(orbit.phi) * Math.cos(orbit.theta)
    );
    camera.lookAt(target);
    if (Math.abs(camera.fov - 50) > 0.01) {
      camera.fov = 50;
      camera.updateProjectionMatrix();
    }
    return camera;
  }

  // plan2d:正交俯視,北朝上
  const spanX = (bounds.maxX - bounds.minX) / 2 + 1.2;
  const spanZ = (bounds.maxZ - bounds.minZ) / 2 + 1.2;
  const aspect = innerWidth / innerHeight;
  let halfW = spanX;
  let halfH = spanZ;
  if (halfW / halfH < aspect) halfW = halfH * aspect;
  else halfH = halfW / aspect;
  orthoCamera.left = -halfW / plan.zoom;
  orthoCamera.right = halfW / plan.zoom;
  orthoCamera.top = halfH / plan.zoom;
  orthoCamera.bottom = -halfH / plan.zoom;
  orthoCamera.position.set(center.x + plan.panX, 40, center.z + plan.panZ);
  orthoCamera.lookAt(center.x + plan.panX, 0, center.z + plan.panZ);
  orthoCamera.updateProjectionMatrix();
  return orthoCamera;
}

// ── 拖曳 / 滾輪 / 點擊 ──
const raycaster = new THREE.Raycaster();
const pointerNdc = new THREE.Vector2();
let dragging = null;

renderer.domElement.addEventListener("pointerdown", (event) => {
  dragging = { x: event.clientX, y: event.clientY, moved: false };
  elements.canvasHost.classList.add("dragging");
  markInteraction();
});

window.addEventListener("pointermove", (event) => {
  if (!dragging) return;
  const dx = event.clientX - dragging.x;
  const dy = event.clientY - dragging.y;
  if (Math.abs(dx) + Math.abs(dy) > 4) dragging.moved = true;

  if (mode === "roam") {
    const speed = 0.0034 * (view.fov / 75);
    view.yaw += dx * speed;
    view.pitch = THREE.MathUtils.clamp(view.pitch + dy * speed, -1.25, 1.25);
  } else if (mode === "plan3d") {
    orbit.theta -= dx * 0.005;
    orbit.phi = THREE.MathUtils.clamp(orbit.phi + dy * 0.004, 0.25, 1.45);
  } else {
    const worldPerPixel = (orthoCamera.right - orthoCamera.left) / innerWidth;
    plan.panX -= dx * worldPerPixel;
    plan.panZ -= dy * worldPerPixel;
  }
  dragging.x = event.clientX;
  dragging.y = event.clientY;
  markInteraction();
});

window.addEventListener("pointerup", (event) => {
  const wasDragging = dragging;
  dragging = null;
  elements.canvasHost.classList.remove("dragging");
  if (!wasDragging || wasDragging.moved || event.target !== renderer.domElement) return;

  const rect = renderer.domElement.getBoundingClientRect();
  pointerNdc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointerNdc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointerNdc, mode === "plan2d" ? orthoCamera : camera);

  const furnitureHits = raycaster.intersectObjects(furnitureGroup.children, true);
  if (furnitureHits.length) {
    let node = furnitureHits[0].object;
    while (node && node.parent !== furnitureGroup) node = node.parent;
    if (node?.userData.sceneObject) {
      showFurnitureCard(node.userData.sceneObject);
      return;
    }
  }

  if (mode === "roam") {
    const floorHits = raycaster.intersectObjects(roomGroup.children, false).filter((hit) => hit.object.userData.isFloor);
    if (floorHits.length) {
      glideTo(floorHits[0].point.x, floorHits[0].point.z);
    }
  }
});

renderer.domElement.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    if (mode === "roam") {
      view.fov = THREE.MathUtils.clamp(view.fov + event.deltaY * 0.03, 35, 95);
    } else if (mode === "plan3d") {
      orbit.radius = THREE.MathUtils.clamp(orbit.radius + event.deltaY * 0.012, 3, 30);
    } else {
      plan.zoom = THREE.MathUtils.clamp(plan.zoom - event.deltaY * 0.0016, 0.5, 4);
    }
    markInteraction();
  },
  { passive: false }
);

let pinchDistance = null;
renderer.domElement.addEventListener("touchmove", (event) => {
  if (event.touches.length !== 2) return;
  const distance = Math.hypot(
    event.touches[0].clientX - event.touches[1].clientX,
    event.touches[0].clientY - event.touches[1].clientY
  );
  if (pinchDistance && mode === "roam") {
    view.fov = THREE.MathUtils.clamp(view.fov + (pinchDistance - distance) * 0.18, 35, 95);
  }
  pinchDistance = distance;
  markInteraction();
});
renderer.domElement.addEventListener("touchend", () => {
  pinchDistance = null;
});

// ── 場景內房間膠囊(漫遊)與房名標籤(平面戶型) ──
const projectVector = new THREE.Vector3();

function projectToScreen(x, y, z, cam) {
  projectVector.set(x, y, z).project(cam);
  if (projectVector.z > 1) return null;
  return {
    x: (projectVector.x * 0.5 + 0.5) * innerWidth,
    y: (-projectVector.y * 0.5 + 0.5) * innerHeight,
  };
}

function shoelaceArea(ring) {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return Math.abs(sum) / 2;
}

function ringCentroid(ring) {
  let x = 0, z = 0;
  ring.forEach(([px, pz]) => { x += px; z += pz; });
  return { x: x / ring.length, z: z / ring.length };
}

// 膠囊與標籤是持久 DOM,每幀只更新位置(重建會吃掉 click 事件)
const chipsBox = document.createElement("div");
const planBox = document.createElement("div");
elements.chipLayer.appendChild(chipsBox);
elements.chipLayer.appendChild(planBox);
let chipNodes = [];

function buildChips() {
  chipsBox.innerHTML = "";
  chipNodes = viewpoints.map((viewpoint, index) => {
    const chip = document.createElement("div");
    chip.className = "room-chip";
    chip.style.display = "none";
    chip.innerHTML = `
      <span class="chip-label">${viewpoint.name}</span>
      <svg class="chip-arrow" width="30" height="12" viewBox="0 0 30 12" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M3 10L15 3l12 7"/></svg>
    `;
    chip.addEventListener("click", () => goToViewpoint(index));
    chipsBox.appendChild(chip);
    return chip;
  });
}

function buildPlanLabels() {
  const regions = sceneData.floorplan?.room_regions || [];
  const spaceLabel = SPACE_LABELS[sceneData.questionnaire?.space_type] || "空間";
  const entries = regions.length
    ? regions.map((region, index) => {
        const centroid = ringCentroid(region.exterior || []);
        return { name: regions.length > 1 ? `空間 ${index + 1}` : spaceLabel, area: shoelaceArea(region.exterior || []), ...centroid };
      })
    : [{ name: spaceLabel, area: (bounds.maxX - bounds.minX) * (bounds.maxZ - bounds.minZ), ...roomCenter() }];

  planBox.innerHTML = "";
  return entries.map((entry) => {
    const label = document.createElement("div");
    label.className = "plan-label";
    label.innerHTML = `<strong>${entry.name}</strong><small>${entry.area.toFixed(2)}㎡</small>`;
    planBox.appendChild(label);
    return { node: label, entry };
  });
}
let planLabelNodes = [];

function updateChips() {
  const clean = document.body.classList.contains("clean");
  chipsBox.style.display = mode === "roam" && !clean ? "" : "none";
  planBox.style.display = mode === "plan2d" && !clean ? "" : "none";

  if (mode === "roam" && !clean) {
    viewpoints.forEach((viewpoint, index) => {
      const chip = chipNodes[index];
      if (!chip) return;
      const distance = Math.hypot(viewpoint.x - view.position.x, viewpoint.z - view.position.z);
      const screen = distance < 0.8 ? null : projectToScreen(viewpoint.x, 1.45, viewpoint.z, camera);
      if (!screen || screen.x < -40 || screen.x > innerWidth + 40 || screen.y < 0 || screen.y > innerHeight) {
        chip.style.display = "none";
        return;
      }
      chip.style.display = "";
      chip.style.left = `${screen.x}px`;
      chip.style.top = `${screen.y}px`;
    });
    return;
  }

  if (mode === "plan2d" && !clean) {
    planLabelNodes.forEach(({ node, entry }) => {
      const screen = projectToScreen(entry.x, 0, entry.z, orthoCamera);
      if (!screen) {
        node.style.display = "none";
        return;
      }
      node.style.display = "";
      node.style.left = `${screen.x}px`;
      node.style.top = `${screen.y}px`;
    });
  }
}

// ── 平面戶型的外圍尺寸標註(畫在 chip layer 的 canvas 上) ──
const dimCanvas = document.createElement("canvas");
dimCanvas.style.cssText = "position:absolute;inset:0;pointer-events:none;";
elements.chipLayer.appendChild(dimCanvas);
const dimContext = dimCanvas.getContext("2d");

function drawDimensions() {
  if (dimCanvas.width !== innerWidth || dimCanvas.height !== innerHeight) {
    dimCanvas.width = innerWidth;
    dimCanvas.height = innerHeight;
  }
  dimContext.clearRect(0, 0, innerWidth, innerHeight);
  if (mode !== "plan2d") return;

  const corners = {
    tl: projectToScreen(bounds.minX, 0, bounds.minZ, orthoCamera),
    tr: projectToScreen(bounds.maxX, 0, bounds.minZ, orthoCamera),
    bl: projectToScreen(bounds.minX, 0, bounds.maxZ, orthoCamera),
    br: projectToScreen(bounds.maxX, 0, bounds.maxZ, orthoCamera),
  };
  if (!corners.tl || !corners.tr || !corners.bl || !corners.br) return;

  const widthMm = Math.round((bounds.maxX - bounds.minX) * 1000);
  const depthMm = Math.round((bounds.maxZ - bounds.minZ) * 1000);
  dimContext.strokeStyle = "rgba(255,255,255,0.72)";
  dimContext.fillStyle = "rgba(255,255,255,0.85)";
  dimContext.lineWidth = 1;
  dimContext.font = "11px 'Noto Sans TC', sans-serif";
  dimContext.textAlign = "center";

  const drawDim = (a, b, offsetX, offsetY, text) => {
    const ax = a.x + offsetX, ay = a.y + offsetY;
    const bx = b.x + offsetX, by = b.y + offsetY;
    dimContext.beginPath();
    dimContext.moveTo(ax, ay);
    dimContext.lineTo(bx, by);
    // 端點短刻線
    if (offsetY !== 0) {
      dimContext.moveTo(ax, ay - 4); dimContext.lineTo(ax, ay + 4);
      dimContext.moveTo(bx, by - 4); dimContext.lineTo(bx, by + 4);
    } else {
      dimContext.moveTo(ax - 4, ay); dimContext.lineTo(ax + 4, ay);
      dimContext.moveTo(bx - 4, by); dimContext.lineTo(bx + 4, by);
    }
    dimContext.stroke();
    dimContext.save();
    dimContext.translate((ax + bx) / 2, (ay + by) / 2);
    if (offsetX !== 0) dimContext.rotate(-Math.PI / 2);
    dimContext.fillText(text, 0, -5);
    dimContext.restore();
  };

  drawDim(corners.tl, corners.tr, 0, -26, `${widthMm}mm`);
  drawDim(corners.bl, corners.br, 0, 34, `${widthMm}mm`);
  drawDim(corners.tl, corners.bl, -30, 0, `${depthMm}mm`);
  drawDim(corners.tr, corners.br, 38, 0, `${depthMm}mm`);
}

// ── 左上戶型圖 ──
const minimapContext = elements.minimap.getContext("2d");
let minimapBase = null;
let minimapTransform = null;
let minimapOpen = true;
let minimapSize = 280;

function applyMinimapSize() {
  elements.minimap.style.width = `${minimapSize}px`;
  elements.minimap.style.height = `${minimapSize}px`;
}

function buildMinimapBase() {
  const canvas = document.createElement("canvas");
  canvas.width = elements.minimap.width;
  canvas.height = elements.minimap.height;
  const context = canvas.getContext("2d");

  const pad = 44;
  const spanX = bounds.maxX - bounds.minX;
  const spanZ = bounds.maxZ - bounds.minZ;
  const scale = Math.min((canvas.width - pad * 2) / spanX, (canvas.height - pad * 2) / spanZ);
  const offsetX = (canvas.width - spanX * scale) / 2;
  const offsetY = (canvas.height - spanZ * scale) / 2;
  minimapTransform = {
    toCanvas(x, z) {
      return [offsetX + (x - bounds.minX) * scale, offsetY + (bounds.maxZ - z) * scale];
    },
    toWorld(canvasX, canvasY) {
      return {
        x: bounds.minX + (canvasX - offsetX) / scale,
        z: bounds.maxZ - (canvasY - offsetY) / scale,
      };
    },
  };

  // 地板淡填色
  context.fillStyle = "rgba(235, 232, 226, 0.28)";
  const [fx, fy] = minimapTransform.toCanvas(bounds.minX, bounds.maxZ);
  context.fillRect(fx, fy, spanX * scale, spanZ * scale);

  const drawSegments = (segments, color, width) => {
    context.strokeStyle = color;
    context.lineWidth = width;
    context.lineCap = "round";
    segments.forEach(({ start, end }) => {
      if (!start || !end) return;
      context.beginPath();
      context.moveTo(...minimapTransform.toCanvas(start.x, start.z));
      context.lineTo(...minimapTransform.toCanvas(end.x, end.z));
      context.stroke();
    });
  };

  const floorplan = sceneData.floorplan || {};
  const wallSegments = floorplan.wall_segments?.length
    ? floorplan.wall_segments
    : [
        { start: { x: bounds.minX, z: bounds.minZ }, end: { x: bounds.maxX, z: bounds.minZ } },
        { start: { x: bounds.maxX, z: bounds.minZ }, end: { x: bounds.maxX, z: bounds.maxZ } },
        { start: { x: bounds.maxX, z: bounds.maxZ }, end: { x: bounds.minX, z: bounds.maxZ } },
        { start: { x: bounds.minX, z: bounds.maxZ }, end: { x: bounds.minX, z: bounds.minZ } },
      ];
  drawSegments(wallSegments, "rgba(255,255,255,0.95)", 7);
  drawSegments(floorplan.door_segments || [], "rgba(235, 200, 160, 0.95)", 5);
  drawSegments(floorplan.window_segments || [], "rgba(170, 205, 225, 0.95)", 5);

  // 視點水滴 pin
  viewpoints.forEach((viewpoint) => {
    const [x, y] = minimapTransform.toCanvas(viewpoint.x, viewpoint.z);
    context.save();
    context.translate(x, y);
    context.fillStyle = "#fff";
    context.strokeStyle = "rgba(60,60,60,0.4)";
    context.lineWidth = 1.4;
    context.beginPath();
    context.arc(0, -13, 9.5, Math.PI * 0.82, Math.PI * 0.18);
    context.lineTo(0, 0);
    context.closePath();
    context.fill();
    context.stroke();
    context.fillStyle = "#5b5b5e";
    context.beginPath();
    context.arc(0, -13, 3.6, 0, Math.PI * 2);
    context.fill();
    context.restore();
  });

  minimapBase = canvas;
}

function drawMinimap() {
  if (!minimapBase || !minimapTransform || mode !== "roam" || !minimapOpen) return;
  minimapContext.clearRect(0, 0, elements.minimap.width, elements.minimap.height);
  minimapContext.drawImage(minimapBase, 0, 0);

  const [x, y] = minimapTransform.toCanvas(view.position.x, view.position.z);
  const heading = Math.atan2(-Math.cos(view.yaw), Math.sin(view.yaw));
  const halfFov = THREE.MathUtils.degToRad(view.fov) / 2;
  const gradient = minimapContext.createRadialGradient(x, y, 3, x, y, 66);
  gradient.addColorStop(0, "rgba(90, 160, 255, 0.6)");
  gradient.addColorStop(1, "rgba(90, 160, 255, 0)");
  minimapContext.beginPath();
  minimapContext.moveTo(x, y);
  minimapContext.arc(x, y, 66, heading - halfFov, heading + halfFov);
  minimapContext.closePath();
  minimapContext.fillStyle = gradient;
  minimapContext.fill();

  minimapContext.beginPath();
  minimapContext.arc(x, y, 8, 0, Math.PI * 2);
  minimapContext.fillStyle = "#5aa0ff";
  minimapContext.strokeStyle = "#fff";
  minimapContext.lineWidth = 3;
  minimapContext.fill();
  minimapContext.stroke();
}

elements.minimap.addEventListener("click", (event) => {
  if (!minimapTransform) return;
  const rect = elements.minimap.getBoundingClientRect();
  const canvasX = ((event.clientX - rect.left) / rect.width) * elements.minimap.width;
  const canvasY = ((event.clientY - rect.top) / rect.height) * elements.minimap.height;
  const world = minimapTransform.toWorld(canvasX, canvasY);
  glideTo(world.x, world.z);
  markInteraction();
});

elements.minimapResize.addEventListener("click", () => {
  minimapSize = minimapSize === 280 ? 190 : 280;
  applyMinimapSize();
});

// ── 底部工具列 ──
elements.barRooms.addEventListener("click", () => {
  const showing = elements.roomsDrawer.classList.toggle("show");
  elements.barRooms.classList.toggle("active", showing);
  elements.moreMenu.classList.remove("show");
});

elements.barNav.addEventListener("click", () => {
  minimapOpen = !minimapOpen;
  elements.barNav.classList.toggle("active", minimapOpen);
  elements.minimapCard.style.display = mode === "roam" && minimapOpen ? "" : "none";
});

// 音樂:WebAudio 合成的低音量環境聲(不用任何外部音檔)
let audioContext = null;
let musicNodes = null;

function startMusic() {
  audioContext = audioContext || new (window.AudioContext || window.webkitAudioContext)();
  const gain = audioContext.createGain();
  gain.gain.value = 0.035;
  const lfo = audioContext.createOscillator();
  const lfoGain = audioContext.createGain();
  lfo.frequency.value = 0.09;
  lfoGain.gain.value = 0.018;
  lfo.connect(lfoGain).connect(gain.gain);
  const notes = [220, 277.18, 329.63];
  const oscillators = notes.map((frequency, index) => {
    const oscillator = audioContext.createOscillator();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    oscillator.detune.value = index * 4 - 4;
    oscillator.connect(gain);
    oscillator.start();
    return oscillator;
  });
  lfo.start();
  gain.connect(audioContext.destination);
  musicNodes = { gain, oscillators, lfo };
}

function stopMusic() {
  if (!musicNodes) return;
  musicNodes.oscillators.forEach((oscillator) => oscillator.stop());
  musicNodes.lfo.stop();
  musicNodes.gain.disconnect();
  musicNodes = null;
}

elements.barMusic.addEventListener("click", () => {
  if (musicNodes) {
    stopMusic();
    elements.musicLabel.textContent = "音樂關";
    elements.barMusic.classList.remove("active");
  } else {
    startMusic();
    elements.musicLabel.textContent = "音樂開";
    elements.barMusic.classList.add("active");
  }
});

elements.barMore.addEventListener("click", () => {
  elements.moreMenu.classList.toggle("show");
  elements.roomsDrawer.classList.remove("show");
  elements.barRooms.classList.remove("active");
});

// ── 更多選單 ──
elements.moreTour.addEventListener("click", () => {
  roamState.tour = !roamState.tour;
  roamState.spin = false;
  elements.moreTour.classList.toggle("active", roamState.tour);
  elements.moreSpin.classList.remove("active");
  if (roamState.tour) {
    setMode("roam");
    lastInteraction = performance.now() - roamState.resumeDelay;
    roamState.nextMoveAt = performance.now() + roamState.dwell;
    showToast("自動導覽中:拖曳畫面可隨時暫停");
  }
});

elements.moreSpin.addEventListener("click", () => {
  roamState.spin = !roamState.spin;
  roamState.tour = false;
  elements.moreSpin.classList.toggle("active", roamState.spin);
  elements.moreTour.classList.remove("active");
  if (roamState.spin) {
    setMode("roam");
    lastInteraction = performance.now() - roamState.resumeDelay;
  }
});

elements.moreNight.addEventListener("click", () => {
  nightMode = !nightMode;
  elements.moreNight.classList.toggle("active", nightMode);
  elements.nightLabel.textContent = nightMode ? "日間模式" : "夜間模式";
});

elements.moreClean.addEventListener("click", () => {
  document.body.classList.add("clean");
  elements.moreMenu.classList.remove("show");
});
elements.exitClean.addEventListener("click", () => document.body.classList.remove("clean"));

// ── 右上圓鈕 ──
elements.btnFullscreen.addEventListener("click", () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen?.();
});

elements.btnShare.addEventListener("click", () => {
  elements.shareUrl.textContent = location.href;
  elements.sharePop.classList.toggle("show");
});
elements.shareCopy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(location.href);
    showToast("已複製分享連結");
  } catch {
    showToast("複製失敗,請手動複製網址", 3200);
  }
  elements.sharePop.classList.remove("show");
});

elements.btnLike.addEventListener("click", () => {
  const liked = elements.btnLike.classList.toggle("liked");
  showToast(liked ? "已收藏這個提案" : "已取消收藏");
});

// 熱度:本機瀏覽次數
try {
  const heat = (Number(localStorage.getItem("roompilot.pano.heat")) || 0) + 1;
  localStorage.setItem("roompilot.pano.heat", String(heat));
  elements.heatCount.textContent = String(heat);
} catch { /* 無痕模式沒有 localStorage */ }

// ── 家具資訊卡 ──
function showFurnitureCard(item) {
  const size = item.size_cm || {};
  elements.cardName.textContent = item.name_zh_raw || TYPE_LABELS[item.normalized_type] || "家具";
  elements.cardBody.innerHTML = [
    `類型:${TYPE_LABELS[item.normalized_type] || item.normalized_type || "-"}`,
    `尺寸:${size.width || "-"} × ${size.depth || "-"} × ${size.height || "-"} cm`,
    item.primary_style ? `風格:${item.primary_style}` : "",
  ]
    .filter(Boolean)
    .join("<br />");
  elements.card.classList.add("show");
}
elements.cardClose.addEventListener("click", () => elements.card.classList.remove("show"));

// ── 自動導覽 / 自動旋轉 ──
function updateRoam(now) {
  if (mode !== "roam" || dragging) return;
  if (now - lastInteraction < roamState.resumeDelay) return;
  if (roamState.spin && !moveTween) {
    view.yaw += 0.0022;
    if (view.pitch !== 0) view.pitch *= 0.985;
    return;
  }
  if (roamState.tour && !moveTween) {
    view.yaw += 0.0016;
    if (view.pitch !== 0) view.pitch *= 0.985;
    if (now >= roamState.nextMoveAt) {
      goToViewpoint((activeViewpoint + 1) % viewpoints.length);
      roamState.nextMoveAt = now + roamState.dwell;
    }
  }
}

// ── 燈光 ──
function updateLights() {
  const target = nightMode ? 1 : 0;
  lightBlend += (target - lightBlend) * 0.06;
  const day = LIGHT_PRESETS.day;
  const night = LIGHT_PRESETS.night;
  ambientLight.intensity = THREE.MathUtils.lerp(day.ambient, night.ambient, lightBlend);
  hemiLight.intensity = THREE.MathUtils.lerp(day.hemi, night.hemi, lightBlend);
  keyLight.intensity = THREE.MathUtils.lerp(day.key, night.key, lightBlend);
  nightLamp.intensity = THREE.MathUtils.lerp(day.lamp, night.lamp, lightBlend);
  if (mode === "roam") {
    scene.background.copy(day.bg).lerp(night.bg, lightBlend);
  } else {
    scene.background.copy(MODE_BG[mode]);
  }
}

window.addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// ── 啟動 ──
let entryTween = null;

async function boot() {
  try {
    setProgress(0.04, "努力載入中...");
    sceneData = await getSceneData();
    setProgress(0.16, "努力載入中...");
    document.title = `RoomPilot 720° 提案漫遊 — ${sceneData.style?.style_name_zh || ""}`;

    buildRoom();
    await loadFurniture();
    computeViewpoints();
    buildChips();

    // 開場從「入口」視點看向室內;沒有入口就選離家具重心最遠的視點(看得最全)
    const focus = furnitureCentroid();
    let startIndex = viewpoints.findIndex((viewpoint) => viewpoint.name === "入口");
    if (startIndex < 0) {
      startIndex = viewpoints.reduce(
        (best, viewpoint, index) =>
          Math.hypot(viewpoint.x - focus.x, viewpoint.z - focus.z) >
          Math.hypot(viewpoints[best].x - focus.x, viewpoints[best].z - focus.z)
            ? index
            : best,
        0
      );
    }
    const start = viewpoints[startIndex];
    view.position.set(start.x, EYE_HEIGHT, start.z);
    view.yaw = start.yaw;

    setProgress(0.9, "正在準備房間縮圖...");
    if (ceilingMesh) ceilingMesh.visible = true;
    buildRoomThumbnails();
    buildMinimapBase();
    applyMinimapSize();
    setActiveViewpoint(startIndex);

    setProgress(1, "完成");
    elements.loading.classList.add("done");
    entryTween = { start: performance.now(), duration: 1400, fromFov: 96, toFov: 75 };
    showToast("拖曳環視 · 滾輪縮放 · 點擊地面或房間標籤移動", 4200);
  } catch (error) {
    console.error(error);
    setProgress(0, `載入失敗:${error.message}`);
  }
}

renderer.setAnimationLoop(() => {
  const now = performance.now();
  if (entryTween) {
    const t = Math.min((now - entryTween.start) / entryTween.duration, 1);
    view.fov = entryTween.fromFov + (entryTween.toFov - entryTween.fromFov) * easeInOut(t);
    if (t >= 1) entryTween = null;
  }
  updateMoveTween(now);
  updateRoam(now);
  updateLights();
  const activeCamera = applyCamera();
  updateChips();
  drawDimensions();
  drawMinimap();
  renderer.render(scene, activeCamera);
});

boot();
