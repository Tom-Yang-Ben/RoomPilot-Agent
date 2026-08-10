import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { classifyMaterialSlot } from "./scene_material_schemes.js?v=20260712b";
import {
  architecturalPbrProfile,
  furniturePbrProfile,
  surfacePbrProfile,
  surfaceTint,
} from "./scene_pbr_contracts.js?v=sha256-e2a4e5e31adf";
import {
  doorOpeningForWallTopology,
  openingBelongsToWall,
  openingWallInterval,
  wallSectionSpan,
  wallSegmentForOpening,
} from "./scene_architecture.js?v=sha256-7932d83e3afd";
import { createViewModeState } from "./scene_view_modes.js?v=20260712b";
import { columnGeometryDescriptor } from "./scene_structure_geometry.js?v=sha256-4a2bf6282bb0";
import { windowOpeningMetrics } from "./scene_window_types.js?v=sha256-990e2abb3240";
import {
  clampWalkPosition,
  computeExactModelScale,
  fallbackMaterialRole,
  findNearestWalkablePosition,
  inferredWallThicknessCm,
  snapFurnitureToRoomSurface,
  synchronizedFloorRegions,
  viewPresentation,
} from "./scene_visual_contracts.js?v=sha256-21f70e95c7c9";
import { normalizedPlanarUvs } from "./scene_texture_uv.js?v=sha256-d6416b081798";

const CM_PER_METER = 100;

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

function normalizeSceneRotationDeg(rotationDeg = 0) {
  return ((Number(rotationDeg) % 360) + 360) % 360;
}

function architecturalOpeningVector(opening = {}) {
  const start = opening.start || {};
  const end = opening.end || {};
  const startX = Number(start.x || 0);
  const startZ = Number(start.z || 0);
  const endX = Number(end.x || 0);
  const endZ = Number(end.z || 0);
  const dx = endX - startX;
  const dz = endZ - startZ;
  const length = Math.hypot(dx, dz);
  return {
    startX,
    startZ,
    endX,
    endZ,
    centerX: (startX + endX) / 2,
    centerZ: (startZ + endZ) / 2,
    length,
    unitX: length ? dx / length : 0,
    unitZ: length ? dz / length : 0,
  };
}

function architecturalOpeningsOverlap(left = {}, right = {}) {
  if (left.topology_gap === true || right.topology_gap === true) {
    return left.topology_gap === true
      && right.topology_gap === true
      && Boolean(left.topology_gap_key)
      && left.topology_gap_key === right.topology_gap_key;
  }
  const leftVector = architecturalOpeningVector(left);
  const rightVector = architecturalOpeningVector(right);
  if (leftVector.length < 4 || rightVector.length < 4) return false;
  const parallel = Math.abs(
    leftVector.unitX * rightVector.unitX + leftVector.unitZ * rightVector.unitZ,
  );
  if (parallel < 0.82) return false;
  const centerDistance = Math.hypot(
    leftVector.centerX - rightVector.centerX,
    leftVector.centerZ - rightVector.centerZ,
  );
  const endpointDistance = Math.min(
    Math.hypot(leftVector.startX - rightVector.startX, leftVector.startZ - rightVector.startZ)
      + Math.hypot(leftVector.endX - rightVector.endX, leftVector.endZ - rightVector.endZ),
    Math.hypot(leftVector.startX - rightVector.endX, leftVector.startZ - rightVector.endZ)
      + Math.hypot(leftVector.endX - rightVector.startX, leftVector.endZ - rightVector.startZ),
  );
  const width = Math.min(
    Number(left.width_cm || left.width || leftVector.length) || leftVector.length,
    Number(right.width_cm || right.width || rightVector.length) || rightVector.length,
  );
  return centerDistance <= Math.max(18, width * 0.28) || endpointDistance <= 36;
}

function openingWallCoverage(opening = {}, wallSegments = [], wallThickness = 12) {
  if (opening.topology_gap) return null;
  const hostSegment = wallSegmentForOpening(wallSegments, opening, wallThickness);
  if (!hostSegment) return null;
  const interval = openingWallInterval(hostSegment, opening, wallThickness, 24);
  if (!interval) return null;
  return { hostSegment, interval };
}

function openingAnchorOnWall(segment, interval) {
  const start = segment?.start || {};
  const end = segment?.end || {};
  const dx = Number(end.x) - Number(start.x);
  const dz = Number(end.z) - Number(start.z);
  const length = Math.hypot(dx, dz);
  if (length < 0.001 || !interval) return null;
  const center = (Number(interval.from) + Number(interval.to)) / 2;
  return {
    x: Number(start.x) + (dx / length) * center,
    z: Number(start.z) + (dz / length) * center,
  };
}

function openingAnchorForWallTopology(opening = {}, wallSegments = [], wallThickness = 12) {
  const coverage = openingWallCoverage(opening, wallSegments, wallThickness);
  return coverage ? openingAnchorOnWall(coverage.hostSegment, coverage.interval) : null;
}

function openingsShareWallCoverage(left = {}, right = {}, wallSegments = [], wallThickness = 12) {
  const leftCoverage = openingWallCoverage(left, wallSegments, wallThickness);
  const rightCoverage = openingWallCoverage(right, wallSegments, wallThickness);
  if (!leftCoverage || !rightCoverage || leftCoverage.hostSegment !== rightCoverage.hostSegment) {
    return false;
  }
  const overlap = Math.min(leftCoverage.interval.to, rightCoverage.interval.to)
    - Math.max(leftCoverage.interval.from, rightCoverage.interval.from);
  const narrowerWidth = Math.min(
    leftCoverage.interval.to - leftCoverage.interval.from,
    rightCoverage.interval.to - rightCoverage.interval.from,
  );
  // A repeated recognition can be offset from the wall line, but still cuts the
  // same physical span. Do not collapse neighbouring, genuinely separate doors.
  return overlap >= Math.max(24, narrowerWidth * 0.55);
}

function architecturalOpeningScore(opening = {}, wallSegments = [], wallThickness = 12) {
  const coverage = openingWallCoverage(opening, wallSegments, wallThickness);
  const vector = architecturalOpeningVector(opening);
  const host = coverage ? architecturalOpeningVector(coverage.hostSegment) : null;
  const centerOffset = host
    ? Math.abs(
      (vector.centerX - host.startX) * -host.unitZ
      + (vector.centerZ - host.startZ) * host.unitX,
    )
    : 0;
  return (opening.topology_gap ? 100 : 0)
    + (opening.confirmed ? 18 : 0)
    + (opening.source === "manual" ? 14 : 0)
    + Math.min(12, Number(opening.confidence || 0) * 12)
    - Math.min(30, centerOffset * 0.25);
}

function dedupeArchitecturalOpeningsFor3d(openings = [], wallSegments = [], wallThickness = 12) {
  const result = [];
  openings.filter(Boolean).forEach((opening) => {
    const openingId = String(opening?.id || "").trim();
    const duplicateIndex = result.findIndex(
      (candidate) => {
        const candidateId = String(candidate?.id || "").trim();
        if (openingId && candidateId && openingId === candidateId) return true;
        // Step 4 owns door identity; Step 6 must never merge distinct doors.
        // Each persisted door ID represents a separately confirmed physical door.
        if (openingId && candidateId) return false;
        const samePhysicalSpan = architecturalOpeningsOverlap(candidate, opening)
          || openingsShareWallCoverage(candidate, opening, wallSegments, wallThickness);
        return samePhysicalSpan;
      },
    );
    if (duplicateIndex < 0) {
      result.push(opening);
      return;
    }
    if (
      architecturalOpeningScore(opening, wallSegments, wallThickness)
      > architecturalOpeningScore(result[duplicateIndex], wallSegments, wallThickness)
    ) {
      result[duplicateIndex] = opening;
    }
  });
  return result;
}

function sceneToWorldPosition(position = {}) {
  return {
    x: Number(position.x || 0),
    z: -Number(position.z || 0),
  };
}

function worldToScenePosition(position = {}) {
  return {
    x: Math.round(Number(position.x || 0) * 100) / 100,
    z: Math.round(-Number(position.z || 0) * 100) / 100,
  };
}

function sceneToWorldRotationDeg(rotationDeg = 0) {
  return normalizeSceneRotationDeg(-Number(rotationDeg || 0));
}

function worldToSceneRotationDeg(rotationDeg = 0) {
  return normalizeSceneRotationDeg(-Number(rotationDeg || 0));
}

function flipPointZ(point) {
  if (Array.isArray(point)) return [Number(point[0] || 0), -Number(point[1] || 0)];
  if (!point || typeof point !== "object") return point;
  const next = { ...point };
  if ("z" in next) next.z = -Number(next.z || 0);
  if ("y" in next && !("z" in next)) next.y = -Number(next.y || 0);
  return next;
}

function flipSegmentZ(segment) {
  if (!segment || typeof segment !== "object") return segment;
  return {
    ...segment,
    start: flipPointZ(segment.start),
    end: flipPointZ(segment.end),
    swing_end: segment.swing_end ? flipPointZ(segment.swing_end) : segment.swing_end,
    confirmed_wall_opening: segment.confirmed_wall_opening
      ? flipSegmentZ(segment.confirmed_wall_opening)
      : segment.confirmed_wall_opening,
    wall_opening_segment: segment.wall_opening_segment
      ? flipSegmentZ(segment.wall_opening_segment)
      : segment.wall_opening_segment,
    closed_leaf_segment: segment.closed_leaf_segment
      ? flipSegmentZ(segment.closed_leaf_segment)
      : segment.closed_leaf_segment,
    rotation_deg: "rotation_deg" in segment
      ? sceneToWorldRotationDeg(segment.rotation_deg)
      : segment.rotation_deg,
  };
}

function flipBoundsZ(bounds) {
  if (!bounds || typeof bounds !== "object") return bounds;
  const minZ = Number(bounds.minZ);
  const maxZ = Number(bounds.maxZ);
  if (!Number.isFinite(minZ) || !Number.isFinite(maxZ)) return { ...bounds };
  return { ...bounds, minZ: -maxZ, maxZ: -minZ };
}

function flipPolygonRegionZ(region) {
  if (!region || typeof region !== "object") return region;
  return {
    ...region,
    exterior: (region.exterior || []).map(flipPointZ),
    holes: (region.holes || []).map((ring) => (ring || []).map(flipPointZ)),
    polygon_cm: (region.polygon_cm || []).map(flipPointZ),
  };
}

function floorplanForWorld(sceneData) {
  const floorplan = JSON.parse(JSON.stringify(sceneData?.floorplan || {}));
  [
    "wall_segments",
    "door_segments",
    "window_segments",
    "door_openings",
    "beam_segments",
  ].forEach((key) => {
    if (Array.isArray(floorplan[key])) floorplan[key] = floorplan[key].map(flipSegmentZ);
  });
  if (Array.isArray(floorplan.columns)) {
    floorplan.columns = floorplan.columns.map((column) => ({
      ...column,
      center: flipPointZ(column.center),
      rotation_deg: "rotation_deg" in column
        ? sceneToWorldRotationDeg(column.rotation_deg)
        : column.rotation_deg,
    }));
  }
  if (Array.isArray(floorplan.wall_polys)) {
    floorplan.wall_polys = floorplan.wall_polys.map(flipPolygonRegionZ);
  }
  if (Array.isArray(floorplan.room_regions)) {
    floorplan.room_regions = floorplan.room_regions.map(flipPolygonRegionZ);
  }
  return floorplan;
}

function sceneDataForWorld(sceneData) {
  const worldScene = {
    ...sceneData,
    floorplan: floorplanForWorld(sceneData),
    surface_overrides: (sceneData?.surface_overrides || []).map((override) => ({
      ...override,
      room_bounds_cm: flipBoundsZ(override.room_bounds_cm),
      room_polygon_cm: (override.room_polygon_cm || []).map(flipPointZ),
    })),
  };
  if (worldScene.material_boundary?.room_bounds_cm) {
    worldScene.material_boundary = {
      ...worldScene.material_boundary,
      room_bounds_cm: flipBoundsZ(worldScene.material_boundary.room_bounds_cm),
      line_cm: (worldScene.material_boundary.line_cm || []).map(flipPointZ),
    };
  }
  return worldScene;
}

export function createSceneViewer(
  container,
  statusElement,
  { onSceneChange = null, onObjectSelect = null } = {},
) {
  if ("createImageBitmap" in globalThis) {
    globalThis.createImageBitmap = undefined;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8f4ef);

  const initialWidth = Math.max(container.clientWidth, 1);
  const initialHeight = Math.max(container.clientHeight, 1);
  const perspectiveCamera = new THREE.PerspectiveCamera(45, initialWidth / initialHeight, 10, 20_000);
  perspectiveCamera.position.set(550, 460, 680);
  const orthographicCamera = new THREE.OrthographicCamera(-500, 500, 500, -500, 1, 20_000);
  let camera = perspectiveCamera;

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(initialWidth, initialHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  const roomEnvironment = new RoomEnvironment();
  const environmentTarget = pmremGenerator.fromScene(roomEnvironment, 0.04);
  scene.environment = environmentTarget.texture;
  scene.environmentIntensity = 1;
  roomEnvironment.dispose();
  const environmentCache = new Map([["room-default", environmentTarget]]);
  let activeHdrProfile = "room-default";

  const usePostProcessing = container.id === "realistic-viewer"
    || container.dataset.renderQuality === "realistic";
  const renderPass = usePostProcessing ? new RenderPass(scene, camera) : null;
  const gtaoPass = usePostProcessing
    ? new GTAOPass(scene, camera, initialWidth, initialHeight)
    : null;
  const outputPass = usePostProcessing ? new OutputPass() : null;
  const composer = usePostProcessing ? new EffectComposer(renderer) : null;
  const performanceElement = usePostProcessing
    ? container.parentElement?.querySelector("#render-performance")
    : null;
  let lastMeasuredFps = 0;
  let performanceWindowStart = globalThis.performance.now();
  let performanceFrames = 0;
  let reducedPixelRatio = false;
  let gtaoRequested = true;
  if (composer) {
    gtaoPass.output = GTAOPass.OUTPUT.Default;
    gtaoPass.blendIntensity = 1.1;
    gtaoPass.updateGtaoMaterial({
      radius: 0.35,
      distanceExponent: 1.5,
      thickness: 1,
      distanceFallOff: 1,
      scale: 1,
      samples: 6,
      screenSpaceRadius: true,
    });
    gtaoPass.updatePdMaterial({ rings: 2, radiusExponent: 2, samples: 6 });
    composer.addPass(renderPass);
    composer.addPass(gtaoPass);
    composer.addPass(outputPass);
  }

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 140;
  controls.maxDistance = 1800;
  controls.zoomSpeed = 0.85;
  controls.target.set(0, 80, 0);
  let activeCameraPreset = "corner";
  const viewMode = createViewModeState("orbit");
  let cameraLocked = false;
  let interactionMode = "camera";
  const walkKeys = new Set();
  let walkDestination = null;
  let walkLookState = null;
  const WALK_MAX_PITCH_RAD = THREE.MathUtils.degToRad(18);

  function applyCameraControlMode(preset) {
    activeCameraPreset = preset;
    const isInside = preset === "inside";
    controls.enableRotate = true;
    controls.enablePan = !isInside;
    controls.enableZoom = !isInside;
    controls.minDistance = isInside ? 125 : 140;
    controls.maxDistance = isInside ? 340 : 1800;
    controls.minPolarAngle = isInside ? Math.PI * 0.38 : 0;
    controls.maxPolarAngle = isInside ? Math.PI * 0.62 : Math.PI;
  }

  function syncPostProcessingCamera() {
    if (!composer) return;
    renderPass.camera = camera;
    gtaoPass.camera = camera;
    const perspectiveFlag = camera.isPerspectiveCamera ? 1 : 0;
    if (gtaoPass.gtaoMaterial.defines.PERSPECTIVE_CAMERA !== perspectiveFlag) {
      gtaoPass.gtaoMaterial.defines.PERSPECTIVE_CAMERA = perspectiveFlag;
      gtaoPass.gtaoMaterial.needsUpdate = true;
    }
  }

  const ambientLight = new THREE.AmbientLight(0xffffff, 1.8);
  scene.add(ambientLight);

  const hemiLight = new THREE.HemisphereLight(0xffffff, 0xdac9b8, 1.35);
  hemiLight.position.set(0, 800, 0);
  scene.add(hemiLight);

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.9);
  keyLight.position.set(600, 800, 500);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xe5d0b2, 1.05);
  fillLight.position.set(-500, 500, -400);
  scene.add(fillLight);

  function lightColorForTemperature(temperatureK) {
    const temperature = Number(temperatureK) || 4200;
    if (temperature <= 3300) return new THREE.Color(0xffd7ad);
    if (temperature <= 3900) return new THREE.Color(0xffe5c8);
    return new THREE.Color(0xfff2e2);
  }

  function generatedHdrEnvironment(profile) {
    const environmentScene = new THREE.Scene();
    const shellMaterial = new THREE.MeshBasicMaterial({
      color: new THREE.Color(profile.sky).multiplyScalar(profile.skyEnergy),
      side: THREE.BackSide,
    });
    const shell = new THREE.Mesh(
      new THREE.SphereGeometry(1200, 48, 24),
      shellMaterial,
    );
    environmentScene.add(shell);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(11, 48),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(profile.ground).multiplyScalar(profile.groundEnergy),
        side: THREE.DoubleSide,
      }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -220;
    environmentScene.add(ground);

    const sun = new THREE.Mesh(
      new THREE.SphereGeometry(70, 24, 12),
      new THREE.MeshBasicMaterial({
        color: new THREE.Color(profile.sun).multiplyScalar(profile.sunEnergy),
      }),
    );
    sun.position.set(...profile.sunPosition);
    environmentScene.add(sun);
    const target = pmremGenerator.fromScene(environmentScene, 0.04);
    shell.geometry.dispose();
    shellMaterial.dispose();
    ground.geometry.dispose();
    ground.material.dispose();
    sun.geometry.dispose();
    sun.material.dispose();
    return target;
  }

  function applyRenderingProfile(sceneData) {
    const lighting = sceneData?.style?.lighting || {};
    const rendering = sceneData?.style?.rendering || {};
    const lightColor = lightColorForTemperature(lighting.colorTemperatureK);
    const environmentIntensity = Number(lighting.environmentIntensity) || 1;
    const hdrProfiles = {
      "studio-industrial": {
        background: 0xd8d7d3,
        key: [5.5, 7.5, 3.5],
        sky: 0x9ca6aa,
        ground: 0x4f4b45,
        sun: 0xffd2a0,
        skyEnergy: 0.7,
        groundEnergy: 0.35,
        sunEnergy: 7.5,
        sunPosition: [4.5, 5.8, 2.5],
      },
      "soft-overcast": {
        background: 0xe8eceb,
        key: [-4.5, 8, 5.5],
        sky: 0xdce8ec,
        ground: 0xb7b2a8,
        sun: 0xe9f2ff,
        skyEnergy: 1.15,
        groundEnergy: 0.55,
        sunEnergy: 2.2,
        sunPosition: [-4, 6.5, 4],
      },
      "apartment-daylight": {
        background: 0xf0eee9,
        key: [6, 8, 5],
        sky: 0xc8dcf2,
        ground: 0xb99f7d,
        sun: 0xffe2b6,
        skyEnergy: 0.95,
        groundEnergy: 0.48,
        sunEnergy: 5.4,
        sunPosition: [5.2, 6.2, 4.2],
      },
      "warm-interior": {
        background: 0xe9dfd2,
        key: [4.5, 6.5, 3.2],
        sky: 0xe8c9a6,
        ground: 0x8b684d,
        sun: 0xffc47d,
        skyEnergy: 0.72,
        groundEnergy: 0.42,
        sunEnergy: 6.2,
        sunPosition: [3.8, 4.8, 2.4],
      },
      "neutral-studio": {
        background: 0xe5e6e4,
        key: [-5.5, 8.5, 4.8],
        sky: 0xdce4e8,
        ground: 0xaaa49c,
        sun: 0xfff1dc,
        skyEnergy: 1.02,
        groundEnergy: 0.46,
        sunEnergy: 4.4,
        sunPosition: [-4.2, 6.8, 3.6],
      },
    };
    const hdrProfileId = hdrProfiles[lighting.hdr]
      ? lighting.hdr
      : "apartment-daylight";
    const hdrProfile = hdrProfiles[hdrProfileId];
    if (activeHdrProfile !== hdrProfileId) {
      if (!environmentCache.has(hdrProfileId)) {
        environmentCache.set(hdrProfileId, generatedHdrEnvironment(hdrProfile));
      }
      scene.environment = environmentCache.get(hdrProfileId).texture;
      activeHdrProfile = hdrProfileId;
    }
    scene.background = new THREE.Color(hdrProfile.background);
    keyLight.position.set(...hdrProfile.key);
    scene.environmentIntensity = environmentIntensity;
    ambientLight.intensity = 0.75 * environmentIntensity;
    hemiLight.intensity = 0.85 * environmentIntensity;
    hemiLight.color.set(hdrProfile.sky);
    hemiLight.groundColor.set(hdrProfile.ground);
    keyLight.color.copy(lightColor);
    keyLight.intensity = Math.max(1.2, Number(lighting.keyLightLux || 360) / 220);
    fillLight.color.copy(lightColor).lerp(new THREE.Color(0xffffff), 0.35);
    fillLight.intensity = Math.max(0.32, environmentIntensity * 0.62);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = Number(rendering.exposure) || 1.05;
    const shadowProfile = rendering.shadow || {};
    const shadowMapSize = Math.max(512, Number(shadowProfile.mapSize) || 1024);
    keyLight.shadow.mapSize.set(shadowMapSize, shadowMapSize);
    keyLight.shadow.radius = Math.max(1, Number(shadowProfile.radius) || 3);
    keyLight.shadow.bias = Number(shadowProfile.bias) || -0.0008;
    keyLight.shadow.normalBias = Number(shadowProfile.normalBias) || 0.018;
    if (gtaoPass) {
      gtaoRequested = rendering.gtao?.enabled !== false;
      gtaoPass.enabled = gtaoRequested && ["walk", "orbit"].includes(viewMode.mode);
      gtaoPass.blendIntensity = Number(rendering.gtao?.intensity) || 1.1;
      gtaoPass.updateGtaoMaterial({
        radius: Number(rendering.gtao?.radius) || 0.35,
        samples: 6,
        screenSpaceRadius: true,
      });
    }
  }

  const grid = new THREE.GridHelper(12, 48, 0xc6ad8e, 0xe8ddcf);
  grid.scale.setScalar(CM_PER_METER);
  grid.position.y = -1;
  grid.material.transparent = true;
  grid.material.opacity = 0.16;
  grid.visible = false;
  scene.add(grid);

  const axes = new THREE.AxesHelper(140);
  axes.position.set(-470, 2, 470);
  axes.visible = false;
  scene.add(axes);
  [
    ["+X 右", "#d94b3d", [-305, 8, 470]],
    ["-X 左", "#d94b3d", [-585, 8, 470]],
    ["+Y 上", "#47a65a", [-470, 160, 470]],
    ["-Y 地", "#47a65a", [-470, 8, 470]],
    ["+Z 深", "#3f73d8", [-470, 8, 635]],
    ["-Z 前", "#3f73d8", [-470, 8, 305]],
  ].filter(([label]) => !String(label).startsWith("-")).forEach(([label, color, position]) => {
    const sprite = createAxisLabel(label, color);
    sprite.position.set(...position);
    sprite.visible = false;
    scene.add(sprite);
  });

  const roomGroup = new THREE.Group();
  scene.add(roomGroup);

  const furnitureGroup = new THREE.Group();
  scene.add(furnitureGroup);

  const ceilingGroup = new THREE.Group();
  scene.add(ceilingGroup);

  const hangingLightGroup = new THREE.Group();
  scene.add(hangingLightGroup);

  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath("/static/vendor/draco/");

  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);
  const textureLoader = new THREE.TextureLoader();
  textureLoader.setCrossOrigin?.("anonymous");

  const wallMeshes = [];

  function setStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  function notifySceneChange(item) {
    if (typeof onSceneChange === "function") onSceneChange(item, lastSceneData);
  }

  function disposeObjectTree(child) {
    child.traverse?.((object) => {
      // 快取 GLB 的幾何/貼圖由頁面級 gltfPromiseCache 持有並跨場景共用，
      // 不得在此釋放；其餘（房殼、代理框、標記、接觸陰影）照常釋放。
      if (object.userData?.roompilotCachedAsset) return;
      if (object.geometry) {
        object.geometry.dispose();
      }
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => {
        ["map", "normalMap", "roughnessMap", "metalnessMap", "alphaMap", "aoMap", "emissiveMap"].forEach((key) => {
          // 共用快取貼圖(房殼面材)由 surfaceTextureCache 持有並跨場景重用,不得釋放,
          // 否則下一次 createRoom 會拿到已 dispose 的 GPU 貼圖 → 黑面。
          if (material[key] && !material[key].userData?.roompilotCachedTexture) {
            material[key].dispose();
          }
        });
        material.dispose();
      });
    });
  }

  function clearGroup(group) {
    while (group.children.length) {
      const child = group.children.pop();
      if (!child) break;
      group.remove(child);
      disposeObjectTree(child);
    }
  }

  function resetCamera() {
    setViewMode("orbit");
  }

  function setCameraPreset(preset = "corner") {
    if (camera !== perspectiveCamera) {
      camera = perspectiveCamera;
      controls.object = perspectiveCamera;
      viewMode.setMode(preset === "inside" ? "walk" : "orbit");
      configureWallsForView("orbit");
    }
    const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360, wallHeight: 270 };
    const presets = {
      overview: {
        position: [0, Math.max(room.widthCm, room.depthCm) * 1.12 + 210, 8],
        target: [0, 25, 0],
      },
      entrance: {
        position: [0, 172, room.depthCm / 2 + 115],
        target: [0, 105, -room.depthCm * 0.16],
      },
      corner: {
        position: [room.widthCm * 0.55 + 115, 272, room.depthCm * 0.55 + 135],
        target: [0, 85, 0],
      },
      inside: {
        position: [0, 145, Math.max(room.depthCm * 0.28, 95)],
        target: [0, 108, -Math.max(room.depthCm * 0.14, 48)],
      },
    };

    const selected = presets[preset] || presets.corner;
    applyCameraControlMode(presets[preset] ? preset : "corner");
    camera.fov = preset === "inside" ? 58 : 45;
    camera.updateProjectionMatrix();
    camera.position.set(...selected.position);
    controls.target.set(...selected.target);
    controls.update();
  }

  function moveModelToFootprintCenter(root) {
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const center = box.getCenter(new THREE.Vector3());
    const scale = root.scale;
    const localOffset = new THREE.Vector3(
      -center.x / (scale.x || 1),
      -box.min.y / (scale.y || 1),
      -center.z / (scale.z || 1),
    );
    root.children.forEach((child) => {
      child.position.add(localOffset);
    });
    root.updateMatrixWorld(true);
  }

  function focusObject(object) {
    applyCameraControlMode("corner");
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const distance = Math.max(size.x, size.y, size.z, 1) * 2.4;
    camera.position.set(center.x + distance, center.y + distance * 0.72, center.z + distance);
    controls.target.copy(center);
    controls.update();
  }

  function makeCanvasTexture({ width = 1024, height = 1024, repeatX = 1, repeatY = 1, draw }) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    draw(context, width, height);

    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(repeatX, repeatY);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return texture;
  }

  function createAxisLabel(label, color) {
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    const axisLetter = String(label).match(/[XYZ]/i)?.[0]?.toUpperCase() || "";
    context.beginPath();
    context.arc(48, 48, 28, 0, Math.PI * 2);
    context.fillStyle = color;
    context.fill();
    context.lineWidth = 7;
    context.strokeStyle = "rgba(255, 255, 255, 0.9)";
    context.stroke();
    context.fillStyle = "#ffffff";
    context.font = "800 34px 'Segoe UI', sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(axisLetter, 48, 49);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(24, 24, 1);
    sprite.renderOrder = 998;
    return sprite;
  }

  function findSurface(surfaceCatalog, surfaceId, usage) {
    return (surfaceCatalog?.surfaces || []).find(
      (surface) => surface.surface_id === surfaceId && surface.usage?.includes(usage)
    );
  }

  function findSurfaceTexture(surfaceCatalog, surfaceId) {
    return (surfaceCatalog?.surfaces || []).find(
      (surface) => surface.surface_id === surfaceId && surface.texture_url,
    ) || null;
  }

  function getSurfaceModuleSize(surface, usage) {
    if (usage !== "floor") return { x: 180, y: 180 };
    const physicalSize = String(surface.source_size || "")
      .match(/([\d.]+)\s*x\s*([\d.]+)\s*cm/i);
    if (physicalSize) {
      return {
        x: Math.max(45, Number(physicalSize[1])),
        y: Math.max(45, Number(physicalSize[2])),
      };
    }
    if (surface.category === "tile") return { x: 60, y: 60 };
    if (surface.category === "wood_tile") return { x: 90, y: 90 };
    return { x: 240, y: 240 };
  }

  function getContinuousSurfaceRepeat(surface, usage, spanX = 3, spanY = 3) {
    const fallback = surface.repeat?.[usage] || (usage === "floor" ? [4, 4] : [2.2, 1.6]);
    if (usage !== "floor") return fallback;
    const moduleSize = getSurfaceModuleSize(surface, usage);
    const width = Number(spanX) || 3;
    const depth = Number(spanY) || 3;
    return [
      Math.max(1, width / moduleSize.x),
      Math.max(1, depth / moduleSize.y),
    ];
  }

  // 房殼牆/地/門的面材每次 createRoom 都重建;若每次都 textureLoader.load 就會
  // 重新解碼並重傳 GPU,逐房切換材質、套材質時整場卡頓。以 url+用途+平鋪+色彩空間
  // 為鍵快取 THREE.Texture,跨 createRoom 共用同一顆 GPU 貼圖。型錄面材有限(數種
  // 牆/地 + 一張門木紋),故不設淘汰。ponytail: 型錄若暴增再加 LRU。
  const surfaceTextureCache = new Map();

  function createImageTexture(
    surface, usage, repeatOverride = null, colorSpace = THREE.SRGBColorSpace,
  ) {
    const repeat = repeatOverride || surface.repeat?.[usage] || (usage === "floor" ? [4, 4] : [2.2, 1.6]);
    const rx = Number(repeat[0]) || 1;
    const ry = Number(repeat[1]) || 1;
    // 色彩空間入鍵:colorMap(SRGB)與 bumpMap(NoColorSpace)同 url/平鋪但不可共用
    // 同一顆,否則其一改色彩空間會污染另一顆。
    const key = `${surface.texture_url}|${usage}|${rx}x${ry}|${colorSpace}`;
    const cached = surfaceTextureCache.get(key);
    if (cached) return cached;
    const texture = textureLoader.load(surface.texture_url);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(rx, ry);
    texture.colorSpace = colorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    // clearGroup→disposeObjectTree 會 dispose 材質貼圖;共用快取貼圖必須豁免,
    // 否則第一次清場就把下次還要用的 GPU 貼圖釋放掉 → 黑面。
    texture.userData.roompilotCachedTexture = true;
    surfaceTextureCache.set(key, texture);
    return texture;
  }

  function createSurfaceImageMaterial(surface, usage, options = {}) {
    const colorMap = createImageTexture(surface, usage, options.repeat);
    const bumpMap = createImageTexture(surface, usage, options.repeat, THREE.NoColorSpace);
    const profile = surfacePbrProfile(surface, usage);
    const material = new THREE.MeshPhysicalMaterial({
      color: surfaceTint(options.color ?? "#ffffff", true, usage),
      map: colorMap,
      bumpMap,
      bumpScale: options.bumpScale ?? profile.bumpScale,
      roughness: options.roughness ?? profile.roughness,
      metalness: options.metalness ?? profile.metalness,
      clearcoat: options.clearcoat ?? profile.clearcoat,
      clearcoatRoughness: options.clearcoatRoughness ?? profile.clearcoatRoughness,
      envMapIntensity: options.envMapIntensity ?? profile.envMapIntensity,
      side: options.side ?? THREE.FrontSide,
    });
    material.userData.roompilotImageSurface = true;
    material.userData.roompilotSurfaceUsage = usage;
    if (options.transparent) {
      material.transparent = true;
      material.opacity = options.opacity ?? 0.92;
      material.depthWrite = true;
    }
    return material;
  }

  function createArchitecturalMaterial(role, surfaceCatalog) {
    const profile = architecturalPbrProfile(role);
    const isDoor = role === "door_leaf";
    const material = new THREE.MeshPhysicalMaterial({
      color: isDoor ? 0xb98c62 : 0xe9ecec,
      ...profile,
    });

    // The existing wood surface gives the default closed door visible grain.
    // A future door catalog may replace it with a product-specific PBR set.
    if (isDoor) {
      const woodSurface = findSurfaceTexture(
        surfaceCatalog,
        "wood_cc0_wood_textures_woodfloor039",
      );
      if (woodSurface) {
        material.map = createImageTexture(woodSurface, "floor", [1, 2.2]);
        material.bumpMap = createImageTexture(woodSurface, "floor", [1, 2.2], THREE.NoColorSpace);
        material.bumpScale = 0.018;
        material.userData.roompilotImageSurface = true;
        material.userData.roompilotSurfaceUsage = "door";
      }
    }
    return material;
  }

  function applySurfaceTint(material, color) {
    if (!color || !material?.color) return;
    material.color.set(surfaceTint(
      color,
      material.userData.roompilotImageSurface === true,
      material.userData.roompilotSurfaceUsage || "generic",
    ));
  }

  function stabilizeWholeHouseWallAppearance(material) {
    if (!material?.color) return material;
    // A whole-house paint is a visual commitment, not a lighting experiment.
    // MeshPhysicalMaterial still shaded identical paint differently per wall
    // direction.  Use an unlit finish only for this explicit uniform mode so
    // every interior face presents the selected colour exactly the same way.
    const stableMaterial = new THREE.MeshBasicMaterial({
      color: material.color.clone(),
      // Keep the selected plaster or tile image.  MeshBasicMaterial removes
      // directional-light differences without discarding the material itself.
      map: material.map || null,
      side: material.side || THREE.DoubleSide,
      transparent: false,
      opacity: 1,
      toneMapped: false,
    });
    stableMaterial.userData.roompilotWholeHouseWall = true;
    stableMaterial.userData.roompilotImageSurface = Boolean(material.map);
    stableMaterial.userData.roompilotSurfaceUsage = "wall";
    return stableMaterial;
  }

  function createWoodTexture(base, grain, seam, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);

        const plankWidth = width / 6;
        for (let x = 0; x < width; x += plankWidth) {
          context.fillStyle = seam;
          context.fillRect(x, 0, 2, height);

          for (let line = 0; line < 14; line += 1) {
            context.strokeStyle = grain;
            context.globalAlpha = 0.08 + Math.random() * 0.06;
            context.lineWidth = 1 + Math.random() * 2;
            context.beginPath();
            const startY = Math.random() * height;
            context.moveTo(x, startY);
            context.bezierCurveTo(
              x + plankWidth * 0.25,
              startY + Math.random() * 16 - 8,
              x + plankWidth * 0.75,
              startY + Math.random() * 16 - 8,
              x + plankWidth,
              startY + Math.random() * 16 - 8
            );
            context.stroke();
          }
        }

        context.globalAlpha = 1;
      },
    });
  }

  function createHerringboneTexture(base, grain, seam, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);
        context.strokeStyle = seam;
        context.lineWidth = 3;

        const block = width / 8;
        for (let y = -block; y < height + block; y += block) {
          for (let x = -block; x < width + block; x += block) {
            context.save();
            context.translate(x + block / 2, y + block / 2);
            context.rotate(((x / block + y / block) % 2 === 0 ? 1 : -1) * Math.PI / 4);
            context.fillStyle = base;
            context.strokeStyle = seam;
            context.globalAlpha = 0.92;
            context.fillRect(-block * 0.52, -block * 0.18, block * 1.04, block * 0.36);
            context.strokeRect(-block * 0.52, -block * 0.18, block * 1.04, block * 0.36);
            context.strokeStyle = grain;
            context.globalAlpha = 0.18;
            for (let line = -2; line <= 2; line += 1) {
              context.beginPath();
              context.moveTo(-block * 0.42, line * 5);
              context.lineTo(block * 0.42, line * 5 + Math.sin(x + y + line) * 3);
              context.stroke();
            }
            context.restore();
          }
        }
        context.globalAlpha = 1;
      },
    });
  }

  function createStoneTexture(base, vein, seam, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);

        const tileSize = width / 4;
        context.strokeStyle = seam;
        context.lineWidth = 3;
        for (let x = 0; x <= width; x += tileSize) {
          context.beginPath();
          context.moveTo(x, 0);
          context.lineTo(x, height);
          context.stroke();
        }
        for (let y = 0; y <= height; y += tileSize) {
          context.beginPath();
          context.moveTo(0, y);
          context.lineTo(width, y);
          context.stroke();
        }

        for (let i = 0; i < 24; i += 1) {
          context.strokeStyle = vein;
          context.globalAlpha = 0.06 + Math.random() * 0.04;
          context.lineWidth = 1 + Math.random() * 1.5;
          context.beginPath();
          const startX = Math.random() * width;
          const startY = Math.random() * height;
          context.moveTo(startX, startY);
          context.bezierCurveTo(
            startX + 50,
            startY + Math.random() * 30 - 15,
            startX + 120,
            startY + Math.random() * 30 - 15,
            startX + 180,
            startY + Math.random() * 30 - 15
          );
          context.stroke();
        }
        context.globalAlpha = 1;
      },
    });
  }

  function createMarbleTexture(base, vein, accent, seam, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        const gradient = context.createLinearGradient(0, 0, width, height);
        gradient.addColorStop(0, base);
        gradient.addColorStop(0.52, "#eee8df");
        gradient.addColorStop(1, "#fbf7ef");
        context.fillStyle = gradient;
        context.fillRect(0, 0, width, height);

        const tileSize = width / 3;
        context.strokeStyle = seam;
        context.lineWidth = 3;
        for (let x = 0; x <= width; x += tileSize) {
          context.beginPath();
          context.moveTo(x, 0);
          context.lineTo(x, height);
          context.stroke();
        }
        for (let y = 0; y <= height; y += tileSize) {
          context.beginPath();
          context.moveTo(0, y);
          context.lineTo(width, y);
          context.stroke();
        }

        for (let i = 0; i < 36; i += 1) {
          context.strokeStyle = i % 5 === 0 ? accent : vein;
          context.globalAlpha = i % 5 === 0 ? 0.16 : 0.08;
          context.lineWidth = i % 5 === 0 ? 2.2 : 1.1;
          context.beginPath();
          const startX = Math.random() * width;
          const startY = Math.random() * height;
          context.moveTo(startX, startY);
          context.bezierCurveTo(
            startX + Math.random() * 110,
            startY + Math.random() * 80 - 40,
            startX + Math.random() * 220,
            startY + Math.random() * 100 - 50,
            startX + Math.random() * 340,
            startY + Math.random() * 120 - 60
          );
          context.stroke();
        }
        context.globalAlpha = 1;
      },
    });
  }

  function createMicrocementTexture(base, cloud, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);

        for (let i = 0; i < 48; i += 1) {
          context.fillStyle = cloud;
          context.globalAlpha = 0.035 + Math.random() * 0.04;
          const radius = 40 + Math.random() * 120;
          const x = Math.random() * width;
          const y = Math.random() * height;
          context.beginPath();
          context.arc(x, y, radius, 0, Math.PI * 2);
          context.fill();
        }

        for (let i = 0; i < 18; i += 1) {
          context.strokeStyle = cloud;
          context.globalAlpha = 0.05;
          context.lineWidth = 8 + Math.random() * 12;
          context.beginPath();
          const startX = Math.random() * width;
          const startY = Math.random() * height;
          context.moveTo(startX, startY);
          context.quadraticCurveTo(startX + 60, startY + 20, startX + 140, startY - 10);
          context.stroke();
        }
        context.globalAlpha = 1;
      },
    });
  }

  function createWallTexture(base, accent, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);

        for (let i = 0; i < 60; i += 1) {
          context.strokeStyle = accent;
          context.globalAlpha = 0.03 + Math.random() * 0.03;
          context.lineWidth = 10 + Math.random() * 18;
          const x = Math.random() * width;
          context.beginPath();
          context.moveTo(x, 0);
          context.lineTo(x + Math.random() * 18 - 9, height);
          context.stroke();
        }

        for (let i = 0; i < 18; i += 1) {
          context.fillStyle = accent;
          context.globalAlpha = 0.02 + Math.random() * 0.03;
          context.beginPath();
          context.arc(Math.random() * width, Math.random() * height, 24 + Math.random() * 72, 0, Math.PI * 2);
          context.fill();
        }
        context.globalAlpha = 1;
      },
    });
  }

  function createFloorMaterial(floorOption, surfaceCatalog, roomSize = {}) {
    const surface = findSurface(surfaceCatalog, floorOption, "floor");
    if (surface) {
      return createSurfaceImageMaterial(surface, "floor", {
        roughness: 0.86,
        metalness: 0.01,
        repeat: getContinuousSurfaceRepeat(surface, "floor", roomSize.widthCm, roomSize.depthCm),
      });
    }

    const presets = {
      auto: () =>
        new THREE.MeshStandardMaterial({
          color: 0xe6d1ae,
          map: createWoodTexture("#e3c99f", "#b48d63", "#cfb288", 4, 4),
          roughness: 0.9,
          metalness: 0.01,
        }),
      light_oak: () =>
        new THREE.MeshStandardMaterial({
          color: 0xe0c18d,
          map: createWoodTexture("#e7cca1", "#be9871", "#d7b58c", 4, 4),
          roughness: 0.88,
          metalness: 0.01,
        }),
      herringbone_oak: () =>
        new THREE.MeshStandardMaterial({
          color: 0xe4c395,
          map: createHerringboneTexture("#e9cda3", "#ad8054", "#d0ad82", 3.4, 3.4),
          roughness: 0.82,
          metalness: 0.01,
        }),
      walnut: () =>
        new THREE.MeshStandardMaterial({
          color: 0x6f4d34,
          map: createWoodTexture("#7b563a", "#4d3221", "#8f694a", 4, 4),
          roughness: 0.84,
          metalness: 0.02,
        }),
      stone_gray: () =>
        new THREE.MeshStandardMaterial({
          color: 0xd7d3cf,
          map: createStoneTexture("#d6d2cd", "#bdb7b2", "#f0ece7", 3, 3),
          roughness: 0.92,
          metalness: 0.01,
        }),
      marble: () =>
        new THREE.MeshStandardMaterial({
          color: 0xf2eee7,
          map: createMarbleTexture("#f8f5ef", "#9d968d", "#c6aa82", "#efe7dc", 2.2, 2.2),
          roughness: 0.38,
          metalness: 0.02,
        }),
      microcement: () =>
        new THREE.MeshStandardMaterial({
          color: 0xbcb3aa,
          map: createMicrocementTexture("#beb4aa", "#948a80", 3, 3),
          roughness: 0.96,
          metalness: 0.01,
        }),
    };

    return (presets[floorOption] ?? presets.auto)();
  }

  function createWallMaterial(wallOption, surfaceCatalog, { tintOnly = false } = {}) {
    const requestedSurface = findSurface(surfaceCatalog, wallOption, "wall");
    // Most imported wall records retain their original remote preview URL.
    // The viewer must still work offline, so render those with our bundled
    // plaster texture while preserving the selected wall colour and ID in data.
    const surface = requestedSurface?.texture_url?.startsWith("http")
      ? findSurface(surfaceCatalog, "wall_ambientcg_plaster006", "wall")
      : requestedSurface;
    if (surface) {
      const material = createSurfaceImageMaterial(surface, "wall", {
        roughness: 0.9,
        metalness: 0.01,
        repeat: surface.repeat?.wall || [2.4, 1.8],
        side: THREE.DoubleSide,
      });
      if (tintOnly) {
        // Keep the catalog texture as subtle relief, but never let its source color
        // override a whole-house wall color selected by the user.
        material.map = null;
        material.userData.roompilotImageSurface = false;
        material.userData.roompilotWallTintOnly = true;
      }
      material.transparent = false;
      material.opacity = 1;
      material.depthWrite = true;
      return material;
    }

    // Fallback wall choices stay procedural; floor catalog textures must never leak onto walls.
    const presets = {
      auto: () =>
        new THREE.MeshStandardMaterial({
          color: 0xf7f2eb,
          map: createWallTexture("#f5efe7", "#d8cebf", 2.2, 1.6),
          roughness: 0.98,
          metalness: 0.01,
          side: THREE.DoubleSide,
        }),
      warm_white: () =>
        new THREE.MeshStandardMaterial({
          color: 0xf8f3eb,
          map: createWallTexture("#f8f2ea", "#ddd3c4", 2.2, 1.6),
          roughness: 0.97,
          metalness: 0.01,
          side: THREE.DoubleSide,
        }),
      mineral_beige: () =>
        new THREE.MeshStandardMaterial({
          color: 0xd2bea6,
          map: createWallTexture("#d0baa0", "#b59a7d", 2.1, 1.5),
          roughness: 0.99,
          metalness: 0.01,
          side: THREE.DoubleSide,
        }),
      light_gray: () =>
        new THREE.MeshStandardMaterial({
          color: 0xe0e2e5,
          map: createWallTexture("#dfe2e5", "#c7cbd1", 2.2, 1.6),
          roughness: 0.98,
          metalness: 0.01,
          side: THREE.DoubleSide,
        }),
      limewash: () =>
        new THREE.MeshStandardMaterial({
          color: 0xded1bd,
          map: createWallTexture("#e6dac8", "#bfa98e", 2.4, 1.7),
          roughness: 1,
          metalness: 0,
          side: THREE.DoubleSide,
        }),
      sage: () =>
        new THREE.MeshStandardMaterial({
          color: 0xc5d0c0,
          map: createWallTexture("#d9e1d5", "#aebca8", 2.2, 1.6),
          roughness: 0.99,
          metalness: 0,
          side: THREE.DoubleSide,
        }),
      sand: () =>
        new THREE.MeshStandardMaterial({
          color: 0xd3bea2,
          map: createWallTexture("#e4d1b8", "#b99f7d", 2.3, 1.65),
          roughness: 1,
          metalness: 0,
          side: THREE.DoubleSide,
        }),
      greige: () =>
        new THREE.MeshStandardMaterial({
          color: 0xc8c1b7,
          map: createWallTexture("#ded8d0", "#aaa197", 2.2, 1.6),
          roughness: 0.99,
          metalness: 0,
          side: THREE.DoubleSide,
        }),
      clay: () =>
        new THREE.MeshStandardMaterial({
          color: 0xb88972,
          map: createWallTexture("#caa18d", "#926553", 2.25, 1.6),
          roughness: 0.98,
          metalness: 0,
          side: THREE.DoubleSide,
        }),
      charcoal: () =>
        new THREE.MeshStandardMaterial({
          color: 0x5a5550,
          map: createWallTexture("#59544f", "#77706a", 2.2, 1.6),
          roughness: 0.94,
          metalness: 0.02,
          side: THREE.DoubleSide,
        }),
    };

    const material = (presets[wallOption] ?? presets.auto)();
    material.transparent = false;
    material.opacity = 1;
    material.depthWrite = true;
    return material;
  }

  function wallSurfaceSegment(segment) {
    const startX = Number(segment?.start?.x);
    const startZ = Number(segment?.start?.z);
    const endX = Number(segment?.end?.x);
    const endZ = Number(segment?.end?.z);
    if (![startX, startZ, endX, endZ].every(Number.isFinite)) return null;
    return {
      start: { x: startX, z: startZ },
      end: { x: endX, z: endZ },
    };
  }

  function tagWallSurface(wallMesh, { segment = null, exteriorSideSign = 0 } = {}) {
    const surfaceSegment = wallSurfaceSegment(segment);
    if (surfaceSegment) {
      wallMesh.userData.roompilotWallSegment = surfaceSegment;
      wallMesh.userData.roompilotExteriorSideSign = Number(exteriorSideSign) || 0;
    }
    return wallMesh;
  }

  function registerWall(wallMesh, surfaceMetadata = {}) {
    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = 1;
    wallMesh.userData.fullPositionY = wallMesh.position.y;
    wallMesh.userData.fullScaleY = wallMesh.scale.y;
    tagWallSurface(wallMesh, surfaceMetadata);
    wallMeshes.push(wallMesh);
    return wallMesh;
  }

  function buildSegmentWalls(
    roomGroupRef,
    segments,
    wallMaterial,
    wallHeight,
    wallThickness,
    doorSegments = [],
    windowSegments = [],
    floorplan = null,
    surfaceCatalog = null,
    confirmedOpenings = [],
  ) {
    const renderedOpenings = new Set();
    const wallDoorSegments = doorSegments.filter((opening) => (
      opening?.topology_gap !== true && opening?.step4_skip_wall_cut !== true
    ));
    const topologyGapDoors = doorSegments.filter((opening) => opening?.topology_gap === true);
    const exteriorSegments = segments.filter((segment) => (
      isExteriorWallSegment(segment, floorplan, wallThickness)
    ));
    const protectedOpenings = [...confirmedOpenings, ...windowSegments]
      .map((opening) => opening?.wall_opening_segment || opening)
      .filter((opening) => opening?.start && opening?.end);

    function buildConfirmedWallJunctionFills() {
      const junctionToleranceCm = Math.max(36, Number(wallThickness) * 2);
      const maximumCollinearGapCm = Math.min(
        junctionToleranceCm,
        Number(wallThickness) + 4,
      );
      const endpoints = segments.flatMap((segment, segmentIndex) => (
        ["start", "end"].flatMap((key) => {
          const endpoint = wallSegmentPoint(segment, key);
          return endpoint
            ? [{
              key: `${segment.id || segmentIndex}:${key}`,
              segment,
              point: endpoint,
            }]
            : [];
        })
      ));
      const usedEndpoints = new Set();
      const bridgeTouchesProtectedOpening = (start, end) => {
        const midpoint = {
          x: (start.x + end.x) / 2,
          z: (start.z + end.z) / 2,
        };
        const toleranceCm = Math.max(Number(wallThickness) * 0.6, 7);
        return protectedOpenings.some((opening) => {
          const openingSegment = { start: opening.start, end: opening.end };
          return pointToWallSegmentDistance(midpoint, openingSegment) <= toleranceCm
            && (
              pointToWallSegmentDistance(start, openingSegment) <= toleranceCm
              || pointToWallSegmentDistance(end, openingSegment) <= toleranceCm
            );
        });
      };
      const sharesWallAxis = (left, right) => {
        const leftStart = wallSegmentPoint(left, "start");
        const leftEnd = wallSegmentPoint(left, "end");
        const rightStart = wallSegmentPoint(right, "start");
        const rightEnd = wallSegmentPoint(right, "end");
        if (!leftStart || !leftEnd || !rightStart || !rightEnd) return false;
        const leftLength = Math.hypot(leftEnd.x - leftStart.x, leftEnd.z - leftStart.z);
        const rightLength = Math.hypot(rightEnd.x - rightStart.x, rightEnd.z - rightStart.z);
        if (leftLength < 0.8 || rightLength < 0.8) return false;
        const alignment = Math.abs(
          ((leftEnd.x - leftStart.x) * (rightEnd.x - rightStart.x)
            + (leftEnd.z - leftStart.z) * (rightEnd.z - rightStart.z))
            / (leftLength * rightLength),
        );
        return alignment >= 0.995;
      };

      endpoints.forEach((endpoint, index) => {
        if (usedEndpoints.has(endpoint.key)) return;
        const neighbor = endpoints
          .slice(index + 1)
          .filter((candidate) => (
            candidate.segment !== endpoint.segment
            && !usedEndpoints.has(candidate.key)
          ))
          .map((candidate) => ({
            candidate,
            distance: Math.hypot(
              candidate.point.x - endpoint.point.x,
              candidate.point.z - endpoint.point.z,
            ),
          }))
          .filter(({ distance }) => distance > 0.8 && distance <= junctionToleranceCm)
          // Only bridge a small collinear OCR seam.  A nearby perpendicular
          // endpoint is a corner, not missing wall geometry.
          .filter(({ candidate, distance }) => (
            distance <= maximumCollinearGapCm
            && sharesWallAxis(endpoint.segment, candidate.segment)
          ))
          .sort((left, right) => left.distance - right.distance)[0];
        if (!neighbor) return;

        const start = endpoint.point;
        const end = neighbor.candidate.point;
        if (bridgeTouchesProtectedOpening(start, end)) return;
        const dx = end.x - start.x;
        const dz = end.z - start.z;
        const length = Math.hypot(dx, dz);
        if (length < 0.8) return;
        const bridgeSegment = { start, end };
        const bridgeMaterial = typeof wallMaterial === "function"
          ? (wallMaterial.faceMaterials?.(bridgeSegment, 0) || wallMaterial(bridgeSegment))
          : wallMaterial.clone();
        const bridge = new THREE.Mesh(
          new THREE.BoxGeometry(length, wallHeight, wallThickness),
          bridgeMaterial,
        );
        bridge.position.set(
          (start.x + end.x) / 2,
          wallHeight / 2,
          (start.z + end.z) / 2,
        );
        bridge.rotation.y = Math.atan2(-dz, dx);
        bridge.castShadow = true;
        bridge.receiveShadow = true;
        bridge.userData.roompilotArchitecturalDetail = "confirmed-wall-junction-fill";
        roomGroupRef.add(registerWall(bridge, { segment: bridgeSegment }));
        usedEndpoints.add(endpoint.key);
        usedEndpoints.add(neighbor.candidate.key);
      });
    }

    segments.forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;

      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const length = Math.hypot(dx, dz);
      if (length < 4) return;
      const unitX = dx / length;
      const unitZ = dz / length;
      const rotationY = Math.atan2(-dz, dx);
      const exteriorWall = isExteriorWallSegment(segment, floorplan, wallThickness);
      const exteriorSideSign = exteriorWall
        ? exteriorWallOutwardSideSign(segment, floorplan, unitX, unitZ)
        : 0;
      const wallJunctionInsets = exteriorWall
        ? { start: 0, end: 0 }
        : interiorWallJunctionInsets(segment, exteriorSegments, wallThickness);
      const sectionMin = Math.min(Math.max(wallJunctionInsets.start, 0), length / 2);
      const sectionMax = Math.max(
        sectionMin,
        length - Math.min(Math.max(wallJunctionInsets.end, 0), length / 2),
      );
      if (sectionMax - sectionMin < 4) return;

      const material = typeof wallMaterial === "function"
        ? wallMaterial(segment)
        : wallMaterial;
      const openingIntervals = [...wallDoorSegments.map((opening) => ({ opening, kind: "door" })),
        ...windowSegments.map((opening) => ({ opening, kind: "window" }))]
        .map(({ opening, kind }, index) => {
          const wallInterval = openingWallInterval(
            segment,
            opening,
            wallThickness,
            kind === "door" ? 68 : 50,
          );
          if (!wallInterval) return null;
          const windowMetrics = kind === "window"
            ? windowOpeningMetrics(opening, wallHeight)
            : null;
          const from = Math.max(wallInterval.from, sectionMin);
          const to = Math.min(wallInterval.to, sectionMax);
          if (to - from < 2.5) return null;
          return {
            from,
            to,
            kind,
            id: opening.id || null,
            width: wallInterval.width,
            opening,
            windowMetrics,
            key: opening.id
              || `${kind}-${index}-${wallInterval.centerX.toFixed(2)}-${wallInterval.centerZ.toFixed(2)}`,
          };
        })
        .filter(Boolean)
        .sort((left, right) => left.from - right.from);

      const addWallSection = (from, to, bottom, height, sectionMaterial = material) => {
        if (to - from < 2.5 || height < 2.5) return;
        const span = wallSectionSpan(from, to, length);
        const sectionFrom = span.from;
        const sectionTo = span.to;
        const center = (sectionFrom + sectionTo) / 2;
        const sectionGeometry = new THREE.BoxGeometry(sectionTo - sectionFrom, height, wallThickness);
        const sectionMaterials = typeof wallMaterial.faceMaterials === "function"
          ? wallMaterial.faceMaterials(segment, exteriorSideSign)
          : sectionMaterial.clone();
        const wallMesh = new THREE.Mesh(
          sectionGeometry,
          sectionMaterials,
        );
        wallMesh.position.set(
          Number(start.x) + unitX * center,
          bottom + height / 2,
          Number(start.z) + unitZ * center,
        );
        wallMesh.rotation.y = rotationY;
        roomGroupRef.add(registerWall(wallMesh, { segment, exteriorSideSign }));
      };

      const addBaseboard = (from, to) => {
        if (to - from < 4) return;
        const center = (from + to) / 2;
        const trimMaterials = typeof wallMaterial.faceMaterials === "function"
          ? wallMaterial.faceMaterials(segment, exteriorSideSign)
          : material.clone();
        const trim = new THREE.Mesh(
          new THREE.BoxGeometry(to - from, 7.5, wallThickness + 0.2),
          trimMaterials,
        );
        trim.position.set(
          Number(start.x) + unitX * center,
          3.8,
          Number(start.z) + unitZ * center,
        );
        trim.rotation.y = rotationY;
        trim.castShadow = true;
        trim.receiveShadow = true;
        trim.userData.roompilotArchitecturalDetail = "baseboard";
        roomGroupRef.add(tagWallSurface(trim, { segment, exteriorSideSign }));
      };

      let cursor = sectionMin;
      openingIntervals.forEach((interval) => {
        addWallSection(cursor, interval.from, 0, wallHeight);
        addBaseboard(cursor, interval.from);
        const openingHeight = interval.kind === "door"
          ? Math.min(Number(interval.opening.height_cm || 210), wallHeight - 8)
          : interval.windowMetrics.headHeightCm;
        if (interval.kind === "window") {
          const sillHeight = interval.windowMetrics.sillHeightCm;
          const frameAllowanceCm = 0.6;
          addWallSection(interval.from, interval.to, 0, Math.max(0, sillHeight - frameAllowanceCm));
          addWallSection(
            interval.from,
            interval.to,
            openingHeight + frameAllowanceCm,
            Math.max(0, wallHeight - openingHeight - frameAllowanceCm),
          );
        } else {
          addWallSection(interval.from, interval.to, openingHeight, wallHeight - openingHeight);
        }
        if (!renderedOpenings.has(interval.key)) {
          buildOpeningAssembly(
            roomGroupRef,
            interval,
            {
              ...openingAnchorOnWall(segment, interval),
              rotationY,
              wallThickness,
            },
            surfaceCatalog,
          );
          renderedOpenings.add(interval.key);
        }
        cursor = Math.max(cursor, interval.to);
      });
      addWallSection(cursor, sectionMax, 0, wallHeight);
      addBaseboard(cursor, sectionMax);

      const capLength = sectionMax - sectionMin;
      const capCenter = (sectionMin + sectionMax) / 2;
      const topCapMaterials = typeof wallMaterial.faceMaterials === "function"
        ? wallMaterial.faceMaterials(segment, exteriorSideSign)
        : material.clone();
      const topCap = new THREE.Mesh(
        new THREE.BoxGeometry(capLength, 2.5, wallThickness),
        topCapMaterials,
      );
      topCap.position.set(
        Number(start.x) + unitX * capCenter,
        wallHeight + 1.25,
        Number(start.z) + unitZ * capCenter,
      );
      topCap.rotation.y = rotationY;
      topCap.castShadow = true;
      topCap.receiveShadow = true;
      tagWallSurface(topCap, { segment, exteriorSideSign });
      roomGroupRef.add(topCap);
    });

    buildConfirmedWallJunctionFills();

    // A door may have a valid closed segment but no recognised wall span yet.
    // It must still be rendered once at that closed position; otherwise a
    // confirmed Step 4 door silently disappears in Step 6.
    const missingDoors = doorSegments.filter((opening) => {
      const openingId = String(opening?.id || "").trim();
      return opening?.topology_gap === true
        || opening?.step4_skip_wall_cut === true
        || !openingId
        || !renderedOpenings.has(openingId);
    }).filter((opening) => opening?.step4_skip_wall_cut !== true);
    const missingWindows = windowSegments.filter((opening) => !segments.some(
      (segment) => openingWallInterval(segment, opening, wallThickness, 50),
    ) && opening?.step4_skip_wall_cut !== true);
    if (missingDoors.length || missingWindows.length) {
      const standaloneWallMaterial = typeof wallMaterial === "function"
        ? (opening) => {
          const hostSegment = wallSegmentForOpening(segments, opening, wallThickness);
          return wallMaterial(hostSegment || segments[0] || {});
        }
        : wallMaterial;
      buildStandaloneOpeningAssemblies(
        roomGroupRef,
        missingDoors,
        missingWindows,
        standaloneWallMaterial,
        wallHeight,
        wallThickness,
        surfaceCatalog,
      );
    }
  }

  function buildConfirmedDoorLeaves(
    roomGroupRef,
    doorSegments,
    wallMaterial,
    wallHeight,
    wallThickness,
    surfaceCatalog = null,
  ) {
    const renderedDoorIds = new Set();
    doorSegments.forEach((door, index) => {
      // The Step 4 wall gap is authoritative for every wall component; the
      // closed leaf may be shown on it, but must never define a second opening.
      // A confirmed Step 4 door must still never vanish: when its wall opening
      // can't be resolved (no persisted opening and no detectable wall gap), the
      // closed_leaf_segment is the immutable Step 4 position, so render the leaf
      // + lintel there instead of dropping the door.
      // ponytail: fall back to closed_leaf_segment; do NOT route doors through
      // buildSegmentWalls to "fix" this — that path cuts walls and double-holes.
      const headerSegment = door?.wall_opening_segment || door?.closed_leaf_segment;
      const start = headerSegment?.start;
      const end = headerSegment?.end;
      if (!start || !end) return;
      const dx = Number(end?.x) - Number(start?.x);
      const dz = Number(end?.z) - Number(start?.z);
      const width = Math.hypot(dx, dz);
      if (width < 4) return;
      const id = String(door?.id || `door-${index + 1}`);
      if (renderedDoorIds.has(id)) return;
      const doorHeight = Math.min(
        Math.max(Number(door.height_cm || door.height) || 205, 180),
        wallHeight - 8,
      );
      const headerHeight = wallHeight - doorHeight;
      if (headerHeight >= 2.5) {
        const headerMaterial = typeof wallMaterial === "function"
          ? wallMaterial({ start, end })
          : wallMaterial;
        const headerMaterials = typeof wallMaterial?.faceMaterials === "function"
          ? wallMaterial.faceMaterials({ start, end }, 0)
          : headerMaterial.clone();
        // Extend the lintel fractionally into both jambs so it becomes one
        // continuous wall assembly instead of a visibly floating thin slab.
        const headerOverlapCm = 0.8;
        const header = new THREE.Mesh(
          new THREE.BoxGeometry(
            width + headerOverlapCm,
            headerHeight,
            wallThickness + headerOverlapCm,
          ),
          headerMaterials,
        );
        header.position.set(
          (Number(start.x) + Number(end.x)) / 2,
          doorHeight + headerHeight / 2,
          (Number(start.z) + Number(end.z)) / 2,
        );
        header.rotation.y = Math.atan2(-dz, dx);
        header.castShadow = true;
        header.receiveShadow = true;
        header.userData.roompilotArchitecturalDetail = "door-header-wall";
        header.userData.roompilotArchitecturalId = id;
        roomGroupRef.add(registerWall(header, { segment: { start, end } }));
      }
      buildOpeningAssembly(
        roomGroupRef,
        {
          kind: "door",
          id,
          // The Step 4 opening span owns the physical door width.  Catalog
          // metadata may describe a wider product, but it must never extend
          // a leaf beyond the confirmed wall opening.
          width,
          opening: door,
        },
        {
          x: (Number(start.x) + Number(end.x)) / 2,
          z: (Number(start.z) + Number(end.z)) / 2,
          rotationY: Math.atan2(-dz, dx),
          wallThickness,
        },
        surfaceCatalog,
      );
      renderedDoorIds.add(id);
    });
  }

  function buildOpeningAssembly(roomGroupRef, interval, anchor, surfaceCatalog = null) {
    const isWindow = interval.kind === "window";
    const frameMaterial = createArchitecturalMaterial(
      isWindow ? "window_frame" : "door_leaf",
      surfaceCatalog,
    );
    const height = isWindow ? interval.windowMetrics?.glazingHeightCm || 120 : 205;
    const centerY = isWindow
      ? (interval.windowMetrics?.sillHeightCm || 0) + height / 2
      : height / 2;
    const assembly = new THREE.Group();
    assembly.position.set(anchor.x, 0, anchor.z);
    assembly.rotation.y = anchor.rotationY;
    assembly.userData.roompilotArchitecturalDetail = interval.kind;
    assembly.userData.roompilotArchitecturalId = String(
      interval.id || interval.opening?.id || "",
    ).trim();

    if (isWindow) {
      const frameDepth = Math.max(Number(anchor.wallThickness || 12) + 0.4, 4.2);
      const frameThickness = 4.2;
      const faceOffset = 0;
      const bottomY = centerY - height / 2;
      const topY = centerY + height / 2;
      const glass = new THREE.Mesh(
        new THREE.PlaneGeometry(Math.max(interval.width - frameThickness * 2, 12), Math.max(height - frameThickness * 2, 12)),
        new THREE.MeshPhysicalMaterial({
          color: 0xd9edf2,
          ...architecturalPbrProfile("glass"),
          side: THREE.DoubleSide,
        }),
      );
      glass.position.y = centerY;
      glass.position.z = 0;
      glass.castShadow = false;
      assembly.add(glass);
      const mullionPositions = [0];
      [
        [interval.width, frameThickness, 0, bottomY],
        [interval.width, frameThickness, 0, topY],
        [frameThickness, height, -interval.width / 2, centerY],
        [frameThickness, height, interval.width / 2, centerY],
        ...mullionPositions.map((x) => [3.2, height - frameThickness, x, centerY]),
      ].forEach(([width, frameHeight, x, y]) => {
        const frame = new THREE.Mesh(
          new THREE.BoxGeometry(width, frameHeight, frameDepth),
          frameMaterial,
        );
        frame.position.set(x, y, faceOffset);
        frame.castShadow = true;
        frame.receiveShadow = true;
        assembly.add(frame);
      });
      const sill = new THREE.Mesh(
        new THREE.BoxGeometry(interval.width + 8, 2.2, frameDepth + 4),
        frameMaterial,
      );
      sill.position.set(0, bottomY - 1.1, 0);
      sill.castShadow = true;
      sill.receiveShadow = true;
      sill.userData.roompilotArchitecturalDetail = "flush-window-sill";
      assembly.add(sill);
    } else {
      // The wall opening is the single Step 4 source of truth.  A separately
      // inferred leaf line can be slightly offset and must not pull the door
      // out of its actual opening in the Step 6 scene.
      const doorLeafInsetCm = 0.6;
      const leafWidth = Math.max(interval.width - doorLeafInsetCm, 60);
      const leafDepth = Math.max(
        Math.min(Number(anchor.wallThickness || 12) - 1.2, 5),
        2,
      );
      const leaf = new THREE.Mesh(
        new THREE.BoxGeometry(leafWidth, height, leafDepth),
        frameMaterial,
      );
      leaf.position.set(0, centerY, 0);
      leaf.castShadow = true;
      leaf.receiveShadow = true;
      leaf.userData.roompilotArchitecturalDetail = "closed-door-leaf";
      assembly.add(leaf);
    }
    roomGroupRef.add(assembly);
  }

  function buildStandaloneOpeningAssemblies(
    roomGroupRef,
    doorSegments,
    windowSegments,
    wallMaterial,
    wallHeight,
    wallThickness,
    surfaceCatalog = null,
  ) {
    [
      ...doorSegments.map((opening) => ({ opening, kind: "door" })),
      ...windowSegments.map((opening) => ({ opening, kind: "window" })),
    ].forEach(({ opening, kind }) => {
      const openingWallMaterial = typeof wallMaterial === "function"
        ? wallMaterial(opening)
        : wallMaterial;
      const openingWallMaterials = typeof wallMaterial?.faceMaterials === "function"
        ? wallMaterial.faceMaterials(opening, 0)
        : openingWallMaterial.clone();
      const start = opening.start || {};
      const end = opening.end || {};
      const dx = Number(end.x || 0) - Number(start.x || 0);
      const dz = Number(end.z || 0) - Number(start.z || 0);
      const measuredWidth = Math.hypot(dx, dz);
      if (measuredWidth < 4) return;
      // A standalone opening has no host-wall interval to clamp against, so
      // use its detected segment exactly.  This keeps the assembly coplanar
      // with the recognised wall instead of letting catalog dimensions push
      // it into a neighbouring wall or across a corner.
      const openingWidth = measuredWidth;
      const windowMetrics = kind === "window"
        ? windowOpeningMetrics(opening, wallHeight)
        : null;
      buildOpeningAssembly(
        roomGroupRef,
        {
          kind,
          id: opening.id || null,
          width: openingWidth,
          opening,
          windowMetrics,
        },
        {
          x: (Number(start.x || 0) + Number(end.x || 0)) / 2,
          z: (Number(start.z || 0) + Number(end.z || 0)) / 2,
          rotationY: Math.atan2(-dz, dx),
          wallThickness,
        },
        surfaceCatalog,
      );
      const isWindow = kind === "window";
      const openingHeight = isWindow
        ? windowMetrics.headHeightCm
        : Math.min(Number(opening.height_cm || 210), wallHeight - 8);
      const sillHeight = isWindow
        ? windowMetrics.sillHeightCm
        : 0;
      const addOpeningWallSection = (bottom, height, detail) => {
        if (height < 2.5) return;
        const section = new THREE.Mesh(
          new THREE.BoxGeometry(
            openingWidth,
            height,
            wallThickness,
          ),
          openingWallMaterials,
        );
        section.position.set(
          (Number(start.x || 0) + Number(end.x || 0)) / 2,
          bottom + height / 2,
          (Number(start.z || 0) + Number(end.z || 0)) / 2,
        );
        section.rotation.y = Math.atan2(-dz, dx);
        section.userData.roompilotArchitecturalDetail = detail;
        roomGroupRef.add(registerWall(section, { segment: { start, end } }));
      };
      if (isWindow) {
        const frameAllowanceCm = 0.6;
        addOpeningWallSection(0, Math.max(0, sillHeight - frameAllowanceCm), "window-wall-sill");
        addOpeningWallSection(
          openingHeight + frameAllowanceCm,
          Math.max(0, wallHeight - openingHeight - frameAllowanceCm),
          "window-wall-header",
        );
      } else {
        addOpeningWallSection(
          openingHeight,
          wallHeight - openingHeight,
          "door-wall-header",
        );
      }
    });
  }

  function buildStructuralMembers(roomGroupRef, floorplan, wallHeight) {
    const material = new THREE.MeshStandardMaterial({
      color: 0xb9b3aa,
      roughness: 0.88,
      metalness: 0.02,
    });
    (floorplan.beam_segments || []).forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;
      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const length = Math.hypot(dx, dz);
      if (length < 4) return;
      const width = Math.max(Number(segment.width_cm || segment.thickness_cm || 30), 12);
      const height = Math.max(Number(segment.height_cm || 35), 12);
      const top = Math.min(Number(segment.top_cm || wallHeight), wallHeight);
      const beam = new THREE.Mesh(
        new THREE.BoxGeometry(length, height, width),
        material.clone(),
      );
      beam.position.set(
        (Number(start.x) + Number(end.x)) / 2,
        Math.max(height / 2, top - height / 2),
        (Number(start.z) + Number(end.z)) / 2,
      );
      beam.rotation.y = Math.atan2(-dz, dx);
      beam.castShadow = true;
      beam.receiveShadow = true;
      beam.userData.roompilotStructure = "beam";
      roomGroupRef.add(beam);
    });
    (floorplan.columns || []).forEach((column) => {
      const center = column.center;
      if (!center) return;
      const geometry = columnGeometryDescriptor(column, {
        minimumDimensionCm: 10,
        defaultHeightCm: wallHeight,
      });
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(geometry.widthCm, geometry.heightCm, geometry.depthCm),
        material.clone(),
      );
      mesh.position.set(geometry.centerX, geometry.centerHeightCm, geometry.centerZ);
      mesh.rotation.y = -THREE.MathUtils.degToRad(geometry.rotationDeg);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.roompilotStructure = "column";
      roomGroupRef.add(mesh);
    });
  }

  function buildFloorPlanOverlay(roomGroupRef, segments, color, opacity = 0.55, yOffset = 2.5) {
    if (!segments?.length) return;

    const points = [];
    segments.forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;
      points.push(new THREE.Vector3(start.x, yOffset, start.z));
      points.push(new THREE.Vector3(end.x, yOffset, end.z));
    });

    if (!points.length) return;

    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(geometry, material);
    lines.renderOrder = 20;
    roomGroupRef.add(lines);
  }

  function segmentMidpoint(segment) {
    return {
      x: (Number(segment.start?.x) + Number(segment.end?.x)) / 2,
      z: (Number(segment.start?.z) + Number(segment.end?.z)) / 2,
    };
  }

  function circulationAccessPoint(segment, reference, clearanceCm = 38) {
    const midpoint = segmentMidpoint(segment);
    const dx = Number(segment.end?.x) - Number(segment.start?.x);
    const dz = Number(segment.end?.z) - Number(segment.start?.z);
    const length = Math.hypot(dx, dz) || 1;
    const normal = { x: -dz / length, z: dx / length };
    const candidates = [1, -1].map((side) => ({
      x: midpoint.x + normal.x * clearanceCm * side,
      z: midpoint.z + normal.z * clearanceCm * side,
    })).filter(
      (point) => walkPositionInsideFloor(point) && !walkPositionBlocked(point, 17),
    );
    if (!candidates.length) return midpoint;
    return candidates.sort(
      (left, right) => Math.hypot(left.x - reference.x, left.z - reference.z)
        - Math.hypot(right.x - reference.x, right.z - reference.z),
    )[0];
  }

  function findCirculationPath(start, goal, floorplan, cellSize = 20) {
    const widthCm = Math.max(Number(floorplan.width_cm), 240);
    const depthCm = Math.max(Number(floorplan.depth_cm), 240);
    const minX = -widthCm / 2;
    const minZ = -depthCm / 2;
    const columns = Math.ceil(widthCm / cellSize) + 1;
    const rows = Math.ceil(depthCm / cellSize) + 1;
    const toCell = (point) => ({
      x: THREE.MathUtils.clamp(Math.round((point.x - minX) / cellSize), 0, columns - 1),
      z: THREE.MathUtils.clamp(Math.round((point.z - minZ) / cellSize), 0, rows - 1),
    });
    const toPoint = (cell) => ({
      x: minX + cell.x * cellSize,
      z: minZ + cell.z * cellSize,
    });
    const keyOf = (cell) => `${cell.x}:${cell.z}`;
    const isWalkable = (cell) => {
      const point = toPoint(cell);
      return walkPositionInsideFloor(point) && !walkPositionBlocked(point, 17);
    };
    const nearestWalkable = (point) => {
      const origin = toCell(point);
      if (isWalkable(origin)) return origin;
      for (let radius = 1; radius <= 5; radius += 1) {
        for (let x = -radius; x <= radius; x += 1) {
          for (let z = -radius; z <= radius; z += 1) {
            const candidate = { x: origin.x + x, z: origin.z + z };
            if (
              candidate.x >= 0 && candidate.x < columns
              && candidate.z >= 0 && candidate.z < rows
              && isWalkable(candidate)
            ) return candidate;
          }
        }
      }
      return null;
    };

    const startCell = nearestWalkable(start);
    const goalCell = nearestWalkable(goal);
    if (!startCell || !goalCell) return [];
    const goalKey = keyOf(goalCell);
    const open = [{ cell: startCell, score: 0 }];
    const cameFrom = new Map();
    const distance = new Map([[keyOf(startCell), 0]]);
    const closed = new Set();
    const directions = [
      [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
      [1, 1, Math.SQRT2], [1, -1, Math.SQRT2],
      [-1, 1, Math.SQRT2], [-1, -1, Math.SQRT2],
    ];

    while (open.length) {
      open.sort((left, right) => left.score - right.score);
      const current = open.shift().cell;
      const currentKey = keyOf(current);
      if (closed.has(currentKey)) continue;
      if (currentKey === goalKey) {
        const cells = [current];
        let cursor = currentKey;
        while (cameFrom.has(cursor)) {
          const previous = cameFrom.get(cursor);
          cells.push(previous);
          cursor = keyOf(previous);
        }
        return simplifyCirculationPath(cells.reverse().map(toPoint));
      }
      closed.add(currentKey);

      directions.forEach(([stepX, stepZ, stepCost]) => {
        const next = { x: current.x + stepX, z: current.z + stepZ };
        if (
          next.x < 0 || next.x >= columns || next.z < 0 || next.z >= rows
          || !isWalkable(next)
        ) return;
        const nextKey = keyOf(next);
        const nextDistance = (distance.get(currentKey) || 0) + stepCost;
        if (nextDistance >= (distance.get(nextKey) ?? Infinity)) return;
        distance.set(nextKey, nextDistance);
        cameFrom.set(nextKey, current);
        const heuristic = Math.hypot(next.x - goalCell.x, next.z - goalCell.z);
        open.push({ cell: next, score: nextDistance + heuristic });
      });
    }
    return [];
  }

  function circulationSegmentWalkable(start, end) {
    const distance = Math.hypot(end.x - start.x, end.z - start.z);
    const steps = Math.max(Math.ceil(distance / 10), 1);
    for (let index = 0; index <= steps; index += 1) {
      const progress = index / steps;
      const point = {
        x: THREE.MathUtils.lerp(start.x, end.x, progress),
        z: THREE.MathUtils.lerp(start.z, end.z, progress),
      };
      if (!walkPositionInsideFloor(point) || walkPositionBlocked(point, 17)) return false;
    }
    return true;
  }

  function simplifyCirculationPath(points) {
    if (points.length <= 2) return points;
    const simplified = [points[0]];
    let anchor = 0;
    while (anchor < points.length - 1) {
      let next = points.length - 1;
      while (next > anchor + 1 && !circulationSegmentWalkable(points[anchor], points[next])) {
        next -= 1;
      }
      simplified.push(points[next]);
      anchor = next;
    }
    return simplified;
  }

  function addCirculationStrip(roomGroupRef, points, color = 0x2f7d64) {
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.82,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    points.slice(1).forEach((point, index) => {
      const previous = points[index];
      const dx = point.x - previous.x;
      const dz = point.z - previous.z;
      const length = Math.hypot(dx, dz);
      if (length < 2) return;
      const strip = new THREE.Mesh(
        new THREE.BoxGeometry(length + 3, 1.2, 11),
        material,
      );
      strip.position.set((point.x + previous.x) / 2, 3.8, (point.z + previous.z) / 2);
      strip.rotation.y = Math.atan2(-dz, dx);
      strip.renderOrder = 24;
      strip.userData.roompilotCirculation = true;
      roomGroupRef.add(strip);
    });

    for (let index = 1; index < points.length; index += 2) {
      const previous = points[index - 1];
      const point = points[index];
      const direction = new THREE.Vector3(point.x - previous.x, 0, point.z - previous.z).normalize();
      const arrow = new THREE.Mesh(
        new THREE.ConeGeometry(11, 24, 3),
        material.clone(),
      );
      arrow.position.set(point.x, 5.2, point.z);
      arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
      arrow.renderOrder = 25;
      arrow.userData.roompilotCirculation = true;
      roomGroupRef.add(arrow);
    }
  }

  function createCirculationLabel(text) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    context.fillStyle = "rgba(255,255,255,0.94)";
    context.strokeStyle = "#2f7d64";
    context.lineWidth = 5;
    context.beginPath();
    context.roundRect(8, 8, 240, 80, 18);
    context.fill();
    context.stroke();
    context.fillStyle = "#214f42";
    context.font = "700 40px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, 128, 50);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas),
      transparent: true,
      depthTest: false,
    }));
    sprite.scale.set(110, 42, 1);
    sprite.renderOrder = 30;
    sprite.userData.roompilotCirculation = true;
    return sprite;
  }

  function buildCirculationRoute(roomGroupRef, floorplan) {
    const doors = (floorplan.door_segments || []).filter(
      (segment) => segment.start && segment.end,
    );
    if (doors.length < 2) return;
    const widthCm = Math.max(Number(floorplan.width_cm), 240);
    const depthCm = Math.max(Number(floorplan.depth_cm), 240);
    const edgeDistance = (point) => Math.min(
      Math.abs(point.x + widthCm / 2),
      Math.abs(point.x - widthCm / 2),
      Math.abs(point.z + depthCm / 2),
      Math.abs(point.z - depthCm / 2),
    );
    const entrance = [...doors].sort((left, right) => {
      const leftMidpoint = segmentMidpoint(left);
      const rightMidpoint = segmentMidpoint(right);
      const edgeDifference = edgeDistance(leftMidpoint) - edgeDistance(rightMidpoint);
      return Math.abs(edgeDifference) > 8
        ? edgeDifference
        : rightMidpoint.z - leftMidpoint.z;
    })[0];
    const entranceMidpoint = segmentMidpoint(entrance);
    const entranceAccess = circulationAccessPoint(entrance, { x: 0, z: 0 });
    const startMarker = new THREE.Mesh(
      new THREE.CircleGeometry(23, 32),
      new THREE.MeshBasicMaterial({
        color: 0x2f7d64,
        transparent: true,
        opacity: 0.92,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    startMarker.rotation.x = -Math.PI / 2;
    startMarker.position.set(entranceAccess.x, 4, entranceAccess.z);
    startMarker.renderOrder = 26;
    startMarker.userData.roompilotCirculation = true;
    roomGroupRef.add(startMarker);
    const label = createCirculationLabel("玄關");
    label.position.set(entranceAccess.x, 42, entranceAccess.z);
    label.userData = { ...label.userData, label: "玄關" };
    roomGroupRef.add(label);

    doors.filter((door) => door !== entrance).forEach((door) => {
      const goal = circulationAccessPoint(door, entranceAccess);
      const path = findCirculationPath(entranceAccess, goal, floorplan);
      if (path.length > 1) addCirculationStrip(roomGroupRef, path);
    });
    addCirculationStrip(roomGroupRef, [entranceMidpoint, entranceAccess]);
  }

  function createMaterialBoundarySurfaces(roomGroupRef, boundary, floorMaterial, sceneData) {
    const bounds = boundary?.room_bounds_cm;
    const line = boundary?.line_cm;
    if (!bounds || !Array.isArray(line) || line.length < 2) return;
    const minX = Number(bounds.minX);
    const maxX = Number(bounds.maxX);
    const minZ = Number(bounds.minZ);
    const maxZ = Number(bounds.maxZ);
    const vertical = Math.abs(Number(line[1].x) - Number(line[0].x))
      <= Math.abs(Number(line[1].y) - Number(line[0].y));
    const split = vertical
      ? Math.max(minX, Math.min(maxX, (Number(line[0].x) + Number(line[1].x)) / 2))
      : Math.max(minZ, Math.min(maxZ, (Number(line[0].y) + Number(line[1].y)) / 2));
    const palette = sceneData.style_card?.palette_hex || sceneData.style?.palette_hex || [];
    const materials = [floorMaterial.clone(), floorMaterial.clone()];
    applySurfaceTint(materials[0], palette[1] || "#c9a77d");
    applySurfaceTint(materials[1], palette[3] || "#8b684b");
    const parts = vertical
      ? [
          { width: split - minX, depth: maxZ - minZ, x: (minX + split) / 2, z: (minZ + maxZ) / 2 },
          { width: maxX - split, depth: maxZ - minZ, x: (split + maxX) / 2, z: (minZ + maxZ) / 2 },
        ]
      : [
          { width: maxX - minX, depth: split - minZ, x: (minX + maxX) / 2, z: (minZ + split) / 2 },
          { width: maxX - minX, depth: maxZ - split, x: (minX + maxX) / 2, z: (split + maxZ) / 2 },
        ];
    parts.forEach((part, index) => {
      if (part.width < 2 || part.depth < 2) return;
      const surface = new THREE.Mesh(
        new THREE.PlaneGeometry(part.width, part.depth),
        materials[index],
      );
      surface.rotation.x = -Math.PI / 2;
      surface.position.set(part.x, 0.6 + index * 0.1, part.z);
      surface.receiveShadow = true;
      surface.userData.roompilotMaterialZone = index + 1;
      roomGroupRef.add(surface);
    });
  }

  function pointInBounds(point, bounds, padding = 0) {
    return point.x >= Number(bounds.minX) - padding
      && point.x <= Number(bounds.maxX) + padding
      && point.z >= Number(bounds.minZ) - padding
      && point.z <= Number(bounds.maxZ) + padding;
  }

  function applyNormalizedPlanarUvs(geometry) {
    const position = geometry?.getAttribute?.("position");
    if (!position?.array?.length) return geometry;
    geometry.setAttribute(
      "uv",
      new THREE.Float32BufferAttribute(normalizedPlanarUvs(position.array), 2),
    );
    return geometry;
  }

  function createRoomSurfaceOverrides(roomGroupRef, sceneData) {
    (sceneData.surface_overrides || []).forEach((override, index) => {
      const bounds = override.room_bounds_cm;
      if (!bounds) return;
      const width = Number(bounds.maxX) - Number(bounds.minX);
      const depth = Number(bounds.maxZ) - Number(bounds.minZ);
      if (width < 2 || depth < 2) return;
      const material = createFloorMaterial(
        override.floor_option || "auto",
        sceneData.surface_catalog,
        { widthCm: width, depthCm: depth },
      );
      applySurfaceTint(material, override.floor_color_hex);
      const polygon = override.room_polygon_cm || [];
      let geometry;
      if (polygon.length >= 3) {
        const shape = new THREE.Shape();
        polygon.forEach((point, pointIndex) => {
          const x = Number(point.x);
          const y = -Number(point.z);
          if (pointIndex === 0) shape.moveTo(x, y);
          else shape.lineTo(x, y);
        });
        shape.closePath();
        geometry = new THREE.ShapeGeometry(shape);
        applyNormalizedPlanarUvs(geometry);
      } else {
        geometry = new THREE.PlaneGeometry(width, depth);
      }
      const surface = new THREE.Mesh(geometry, material);
      surface.rotation.x = -Math.PI / 2;
      surface.position.y = 0.4 + index * 0.1;
      if (polygon.length < 3) {
        surface.position.x = (Number(bounds.minX) + Number(bounds.maxX)) / 2;
        surface.position.z = (Number(bounds.minZ) + Number(bounds.maxZ)) / 2;
      }
      surface.receiveShadow = true;
      surface.userData.roompilotSurfaceOverride = override.room_id;
      roomGroupRef.add(surface);
    });
  }

  function createRoomCeilingOverrides(sceneData, wallHeight) {
    const dropByStyle = {
      flat: 12,
      cove: 18,
      floating: 20,
      linear: 14,
      "no-main-light": 12,
      "wood-grid": 16,
    };
    (sceneData.surface_overrides || []).forEach((override, index) => {
      const styleId = override.ceiling_style_id || "exposed";
      const polygon = override.room_polygon_cm || [];
      if (styleId === "exposed" || polygon.length < 3) return;
      const shape = new THREE.Shape();
      polygon.forEach((point, pointIndex) => {
        const x = Number(point.x);
        const y = -Number(point.z);
        if (pointIndex === 0) shape.moveTo(x, y);
        else shape.lineTo(x, y);
      });
      shape.closePath();
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(override.ceiling_color_hex || "#f4f1eb"),
        roughness: override.ceiling_material_id === "wood-veneer" ? 0.72 : 0.9,
        metalness: styleId === "linear" ? 0.12 : 0,
        side: THREE.DoubleSide,
      });
      const panel = new THREE.Mesh(new THREE.ShapeGeometry(shape), material);
      panel.rotation.x = Math.PI / 2;
      panel.position.y = wallHeight - (dropByStyle[styleId] || 12) - index * 0.05;
      panel.receiveShadow = true;
      panel.userData.roompilotCeilingOverride = override.room_id;
      panel.userData.ceilingStyle = styleId;
      panel.userData.ceilingMaterial = override.ceiling_material_id || "flat-paint";
      panel.userData.lightingId = override.lighting_id || "";
      ceilingGroup.add(panel);
    });
  }

  function wallMaterialResolver(sceneData, defaultMaterial) {
    // A room can be saved more than once while the questionnaire auto-saves.
    // Only the most recent record for that room may influence the final scene.
    const canonicalOverrides = new Map();
    (sceneData.surface_overrides || []).forEach((override) => {
      const roomId = String(override?.room_id || "").trim();
      if (roomId) canonicalOverrides.set(roomId, override);
    });
    const roomOverrides = [...canonicalOverrides.values()];
    const cache = new Map();
    const firstOverride = roomOverrides[0] || null;
    const usesOneWholeHouseWall = Boolean(firstOverride) && roomOverrides.every((override) => (
      override.wall_option === firstOverride.wall_option
        && override.wall_color_hex === firstOverride.wall_color_hex
    ));
    const pointToSegmentDistance = (point, start, end) => {
      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const lengthSquared = dx * dx + dz * dz;
      if (lengthSquared < 0.0001) {
        return Math.hypot(point.x - Number(start.x), point.z - Number(start.z));
      }
      const projection = THREE.MathUtils.clamp(
        ((point.x - Number(start.x)) * dx + (point.z - Number(start.z)) * dz)
          / lengthSquared,
        0,
        1,
      );
      return Math.hypot(
        point.x - (Number(start.x) + projection * dx),
        point.z - (Number(start.z) + projection * dz),
      );
    };
    const distanceToRoomBoundary = (point, override) => {
      const polygon = override.room_polygon_cm || [];
      if (polygon.length >= 3) {
        return polygon.reduce((nearest, current, index) => {
          const next = polygon[(index + 1) % polygon.length];
          const start = ringPointCoordinates(current);
          const end = ringPointCoordinates(next);
          return (!start || !end)
            ? nearest
            : Math.min(nearest, pointToSegmentDistance(point, start, end));
        }, Infinity);
      }
      const bounds = override.room_bounds_cm;
      if (!bounds) return Infinity;
      const nearestX = THREE.MathUtils.clamp(point.x, Number(bounds.minX), Number(bounds.maxX));
      const nearestZ = THREE.MathUtils.clamp(point.z, Number(bounds.minZ), Number(bounds.maxZ));
      return Math.hypot(point.x - nearestX, point.z - nearestZ);
    };
    function roomOverrideForInteriorPoint(point) {
      const exact = roomOverrides.filter((item) => {
        const polygon = item.room_polygon_cm || [];
        return polygon.length >= 3
          ? ringContainsPoint(point, polygon)
          : (item.room_bounds_cm && pointInBounds(point, item.room_bounds_cm, 18));
      });
      if (exact.length) return exact[0];

      // A wall face lies exactly on the room boundary.  Imperfect OCR polygons
      // can leave a few centimetres of drift, so retain the closest room rather
      // than falling back to an unrelated exterior/default finish.
      const nearest = roomOverrides
        .map((item) => ({ item, distance: distanceToRoomBoundary(point, item) }))
        .sort((left, right) => left.distance - right.distance)[0];
      return nearest?.distance <= 28 ? nearest.item : null;
    }
    const materialForOverride = (override) => {
      if (!override) return defaultMaterial;
      const cacheKey = override.room_id;
      if (!cache.has(cacheKey)) {
        let material = createWallMaterial(
          override.wall_option
            || "auto",
          sceneData.surface_catalog,
          { tintOnly: false },
        );
        applySurfaceTint(
          material,
          override.wall_color_hex,
        );
        if (usesOneWholeHouseWall) material = stabilizeWholeHouseWallAppearance(material);
        material.userData.roompilotWallSurfaceId = override.room_id;
        cache.set(cacheKey, material);
      }
      return cache.get(cacheKey);
    };
    const resolveWallMaterial = (segment) => {
      const midpoint = {
        x: (Number(segment.start?.x || 0) + Number(segment.end?.x || 0)) / 2,
        z: (Number(segment.start?.z || 0) + Number(segment.end?.z || 0)) / 2,
      };
      return materialForOverride(roomOverrideForInteriorPoint(midpoint));
    };
    resolveWallMaterial.faceMaterials = (segment, exteriorSideSign = 1) => {
      const start = segment.start || {};
      const end = segment.end || {};
      const dx = Number(end.x || 0) - Number(start.x || 0);
      const dz = Number(end.z || 0) - Number(start.z || 0);
      const length = Math.hypot(dx, dz);
      if (length < 4) return null;
      const midpoint = {
        x: (Number(start.x || 0) + Number(end.x || 0)) / 2,
        z: (Number(start.z || 0) + Number(end.z || 0)) / 2,
      };
      const normal = { x: -dz / length, z: dx / length };
      const materialForSide = (side) => {
        const sample = {
          x: midpoint.x + normal.x * side * 16,
          z: midpoint.z + normal.z * side * 16,
        };
        return materialForOverride(roomOverrideForInteriorPoint(sample));
      };
      let positiveSide = materialForSide(1);
      let negativeSide = materialForSide(-1);
      // The outside of a perimeter wall has no room polygon to sample.  It
      // therefore inherits the finish from the room on the opposite side,
      // instead of silently reverting to the generic wall material.
      if (exteriorSideSign) {
        const adjacentInteriorMaterial = materialForSide(-exteriorSideSign);
        if (exteriorSideSign > 0) positiveSide = adjacentInteriorMaterial;
        else negativeSide = adjacentInteriorMaterial;
      }
      const interior = resolveWallMaterial(segment);
      const materials = [
        interior.clone(), interior.clone(), interior.clone(),
        interior.clone(), positiveSide.clone(), negativeSide.clone(),
      ];
      return materials;
    };
    return resolveWallMaterial;
  }

  function wallSegmentPoint(segment, key) {
    const point = segment?.[key];
    const x = Number(point?.x);
    const z = Number(point?.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) return null;
    return { x, z };
  }

  function pointToWallSegmentDistance(point, segment) {
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!point || !start || !end) return Infinity;
    const dx = end.x - start.x;
    const dz = end.z - start.z;
    const lengthSquared = dx * dx + dz * dz;
    if (lengthSquared < 0.01) return Math.hypot(point.x - start.x, point.z - start.z);
    const projection = THREE.MathUtils.clamp(
      ((point.x - start.x) * dx + (point.z - start.z) * dz) / lengthSquared,
      0,
      1,
    );
    return Math.hypot(
      point.x - (start.x + projection * dx),
      point.z - (start.z + projection * dz),
    );
  }

  function wallSegmentBounds(floorplan = {}) {
    const points = (floorplan.wall_segments || [])
      .flatMap((segment) => [wallSegmentPoint(segment, "start"), wallSegmentPoint(segment, "end")])
      .filter(Boolean);
    if (!points.length) return null;
    return points.reduce((bounds, point) => ({
      minX: Math.min(bounds.minX, point.x),
      maxX: Math.max(bounds.maxX, point.x),
      minZ: Math.min(bounds.minZ, point.z),
      maxZ: Math.max(bounds.maxZ, point.z),
    }), {
      minX: Infinity,
      maxX: -Infinity,
      minZ: Infinity,
      maxZ: -Infinity,
    });
  }

  function ringPointCoordinates(point) {
    const x = Number(Array.isArray(point) ? point[0] : point?.x);
    const z = Number(Array.isArray(point) ? point[1] : point?.z ?? point?.y);
    if (!Number.isFinite(x) || !Number.isFinite(z)) return null;
    return { x, z };
  }

  function ringContainsPoint(position, ring) {
    if (!Array.isArray(ring) || ring.length < 3) return false;
    let inside = false;
    for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
      const currentPoint = ringPointCoordinates(ring[current]);
      const previousPoint = ringPointCoordinates(ring[previous]);
      if (!currentPoint || !previousPoint) continue;
      const crosses = (currentPoint.z > position.z) !== (previousPoint.z > position.z);
      const edgeX = ((previousPoint.x - currentPoint.x) * (position.z - currentPoint.z))
        / ((previousPoint.z - currentPoint.z) || Number.EPSILON) + currentPoint.x;
      if (crosses && position.x < edgeX) inside = !inside;
    }
    return inside;
  }

  function floorplanRoomRegions(floorplan = {}) {
    const regions = [
      ...(Array.isArray(floorplan.room_regions) ? floorplan.room_regions : []),
      ...(Array.isArray(floorplan.rooms) ? floorplan.rooms : []),
    ];
    return regions
      .map((region) => ({
        exterior: region.exterior || region.polygon_cm || region.polygon_m || [],
        holes: region.holes || [],
      }))
      .filter((region) => Array.isArray(region.exterior) && region.exterior.length >= 3);
  }

  function pointInsideAnyFloorplanRoom(point, floorplan = {}) {
    return floorplanRoomRegions(floorplan).some((region) => (
      ringContainsPoint(point, region.exterior)
        && !(region.holes || []).some((hole) => ringContainsPoint(point, hole))
    ));
  }

  function isExplicitExteriorWallSegment(segment = {}) {
    const role = String(
      segment.boundary_side
        || segment.wall_role
        || segment.role
        || segment.wall_type
        || segment.type
        || "",
    ).toLowerCase();
    return segment.exterior === true
      || segment.is_exterior === true
      || segment.boundary === true
      || ["exterior", "outer", "perimeter", "boundary"].some((token) => role.includes(token));
  }

  function isExteriorWallSegment(segment, floorplan = {}, toleranceCm = 10) {
    if (isExplicitExteriorWallSegment(segment)) return true;
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!start || !end) return false;
    const dx = end.x - start.x;
    const dz = end.z - start.z;
    const length = Math.hypot(dx, dz);
    const roomRegions = floorplanRoomRegions(floorplan);
    if (start && end && length > 0.01 && roomRegions.length) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const offset = Math.max(toleranceCm, 14);
      const normal = { x: -dz / length, z: dx / length };
      const leftInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x + normal.x * offset,
        z: midpoint.z + normal.z * offset,
      }, floorplan);
      const rightInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x - normal.x * offset,
        z: midpoint.z - normal.z * offset,
      }, floorplan);
      if (leftInside || rightInside) return leftInside !== rightInside;
    }
    const bounds = wallSegmentBounds(floorplan);
    if (!bounds) return false;
    const onLeft = Math.abs(start.x - bounds.minX) <= toleranceCm
      && Math.abs(end.x - bounds.minX) <= toleranceCm;
    const onRight = Math.abs(start.x - bounds.maxX) <= toleranceCm
      && Math.abs(end.x - bounds.maxX) <= toleranceCm;
    const onBack = Math.abs(start.z - bounds.minZ) <= toleranceCm
      && Math.abs(end.z - bounds.minZ) <= toleranceCm;
    const onFront = Math.abs(start.z - bounds.maxZ) <= toleranceCm
      && Math.abs(end.z - bounds.maxZ) <= toleranceCm;
    return onLeft || onRight || onBack || onFront
      || wallEndpointTouchesExteriorBounds(start, bounds, toleranceCm)
      || wallEndpointTouchesExteriorBounds(end, bounds, toleranceCm);
  }

  function wallEndpointTouchesExteriorBounds(point, bounds, toleranceCm = 10) {
    return Math.abs(point.x - bounds.minX) <= toleranceCm
      || Math.abs(point.x - bounds.maxX) <= toleranceCm
      || Math.abs(point.z - bounds.minZ) <= toleranceCm
      || Math.abs(point.z - bounds.maxZ) <= toleranceCm;
  }

  function exteriorWallOutwardSideSign(segment, floorplan = {}, unitX = 1, unitZ = 0) {
    const start = wallSegmentPoint(segment, "start");
    const end = wallSegmentPoint(segment, "end");
    if (!start || !end) return 1;
    const normal = { x: -unitZ, z: unitX };
    const length = Math.hypot(end.x - start.x, end.z - start.z);
    const roomRegions = floorplanRoomRegions(floorplan);
    if (length > 0.01 && roomRegions.length) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const offset = 14;
      const plusInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x + normal.x * offset,
        z: midpoint.z + normal.z * offset,
      }, floorplan);
      const minusInside = pointInsideAnyFloorplanRoom({
        x: midpoint.x - normal.x * offset,
        z: midpoint.z - normal.z * offset,
      }, floorplan);
      if (plusInside !== minusInside) {
        return plusInside ? -1 : 1;
      }
    }
    const side = String(segment.boundary_side || "").toLowerCase();
    const outwardBySide = {
      left: { x: -1, z: 0 },
      right: { x: 1, z: 0 },
      top: { x: 0, z: 1 },
      bottom: { x: 0, z: -1 },
    }[side];
    if (outwardBySide) {
      return (outwardBySide.x * normal.x + outwardBySide.z * normal.z) >= 0 ? 1 : -1;
    }
    const bounds = wallSegmentBounds(floorplan);
    if (bounds) {
      const midpoint = { x: (start.x + end.x) / 2, z: (start.z + end.z) / 2 };
      const distances = [
        { vector: { x: -1, z: 0 }, distance: Math.abs(midpoint.x - bounds.minX) },
        { vector: { x: 1, z: 0 }, distance: Math.abs(midpoint.x - bounds.maxX) },
        { vector: { x: 0, z: -1 }, distance: Math.abs(midpoint.z - bounds.minZ) },
        { vector: { x: 0, z: 1 }, distance: Math.abs(midpoint.z - bounds.maxZ) },
      ].sort((left, right) => left.distance - right.distance);
      const outward = distances[0]?.vector;
      if (outward) return (outward.x * normal.x + outward.z * normal.z) >= 0 ? 1 : -1;
    }
    return 1;
  }

  function interiorWallJunctionInsets(segment, exteriorSegments, wallThickness) {
    // Confirmed wall endpoints already describe the real junction.  Do not
    // retract them by half a wall thickness, or a false white slit appears
    // between otherwise continuous walls in the Step 6 model.
    const insetCm = 0;
    const toleranceCm = Math.max(Number(wallThickness) / 2 + 2, 8);
    const endpointTouchesExterior = (key) => {
      const point = wallSegmentPoint(segment, key);
      if (!point) return false;
      return exteriorSegments.some((exteriorSegment) => (
        exteriorSegment !== segment
          && pointToWallSegmentDistance(point, exteriorSegment) <= toleranceCm
      ));
    };
    return {
      start: endpointTouchesExterior("start") ? insetCm : 0,
      end: endpointTouchesExterior("end") ? insetCm : 0,
    };
  }

  function polygonShape(region = {}, includeHoles = true) {
    const exterior = region.exterior || [];
    if (exterior.length < 3) return null;
    const shape = new THREE.Shape();
    exterior.forEach((point, index) => {
      const x = Number(Array.isArray(point) ? point[0] : point.x);
      const z = Number(Array.isArray(point) ? point[1] : point.z);
      if (!Number.isFinite(x) || !Number.isFinite(z)) return;
      if (index === 0) shape.moveTo(x, -z);
      else shape.lineTo(x, -z);
    });
    shape.closePath();
    if (includeHoles) {
      (region.holes || []).forEach((ring) => {
        if (!Array.isArray(ring) || ring.length < 3) return;
        const hole = new THREE.Path();
        ring.forEach((point, index) => {
          const x = Number(Array.isArray(point) ? point[0] : point.x);
          const z = Number(Array.isArray(point) ? point[1] : point.z);
          if (!Number.isFinite(x) || !Number.isFinite(z)) return;
          if (index === 0) hole.moveTo(x, -z);
          else hole.lineTo(x, -z);
        });
        hole.closePath();
        shape.holes.push(hole);
      });
    }
    return shape;
  }

  // 文件 §5.5:多邊形牆擠出 Shape(x,-z) + ExtrudeGeometry(depth=牆高) +
  // rotateX(-90°)。polygonWalls 描述來自 SceneModel;100×100 環 → 世界 bbox
  // x[0,100]、y[0,牆高]、z[-100,0]…在本 repo 的世界對齊平面等價於 z[0,100]。
  function buildWallMass(roomGroupRef, floorplan, material, wallHeight) {
    const wallMassRegions = (floorplan?.wall_polys || []).filter(
      (region) => region?.exterior?.length >= 3,
    );
    if (!wallMassRegions.length) return false;

    wallMassRegions.forEach((region) => {
      const shape = polygonShape(region, true);
      if (!shape) return;
      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: wallHeight,
        bevelEnabled: false,
        curveSegments: 1,
      });
      geometry.computeVertexNormals();
      const wallMass = new THREE.Mesh(geometry, material.clone());
      wallMass.rotation.x = -Math.PI / 2;
      wallMass.userData.roompilotArchitecturalDetail = "continuous-wall-mass";
      wallMass.userData.roompilotWallHeightAxis = "z";
      wallMass.userData.fullScaleZ = wallMass.scale.z;
      roomGroupRef.add(registerWall(wallMass));
    });
    return true;
  }

  function buildWallMassTopCaps(roomGroupRef, floorplan, material, wallHeight) {
    const wallMassRegions = (floorplan?.wall_polys || []).filter(
      (region) => region?.exterior?.length >= 3,
    );
    wallMassRegions.forEach((region) => {
      const shape = polygonShape(region, true);
      if (!shape) return;
      const cap = new THREE.Mesh(
        new THREE.ShapeGeometry(shape),
        material.clone(),
      );
      cap.rotation.x = -Math.PI / 2;
      cap.position.y = wallHeight + 0.4;
      cap.userData.roompilotArchitecturalDetail = "continuous-wall-mass-top-cap";
      cap.castShadow = true;
      cap.receiveShadow = true;
      roomGroupRef.add(cap);
    });
  }

  function createFloorGeometry(floorplan, widthCm, depthCm) {
    const shapes = synchronizedFloorRegions(floorplan, widthCm, depthCm)
      .map((region) => polygonShape(region, true))
      .filter(Boolean);
    const geometry = new THREE.ShapeGeometry(shapes);
    geometry.computeVertexNormals();
    return geometry;
  }

  function createRoom(sceneData) {
    clearGroup(roomGroup);
    clearGroup(ceilingGroup);
    clearGroup(hangingLightGroup);
    wallMeshes.length = 0;
    const catalogThumbnailMode = sceneData.design_choices?.catalog_thumbnail_mode === true;

    const widthCm = Math.max(sceneData.floorplan.width_cm, 240);
    const depthCm = Math.max(sceneData.floorplan.depth_cm, 240);
    const wallHeight = Math.max(
      Number(sceneData.floorplan.room_height_cm || 270),
      210,
    );
    const floorOption = sceneData.design_choices?.floor_option || "auto";
    const wallOption = sceneData.design_choices?.wall_option || "auto";

    const floorMaterial = createFloorMaterial(
      floorOption,
      sceneData.surface_catalog,
      { widthCm, depthCm },
    );
    const floorPbr = sceneData.style?.pbr?.floor || {};
    const floorColor = sceneData.design_choices?.floor_color_hex
      || sceneData.style_card?.palette_hex?.[1];
    applySurfaceTint(floorMaterial, floorColor);
    if (floorPbr.roughness != null) floorMaterial.roughness = floorPbr.roughness;
    if (floorPbr.metalness != null) floorMaterial.metalness = floorPbr.metalness;
    const floor = new THREE.Mesh(
      createFloorGeometry(sceneData.floorplan, widthCm, depthCm),
      floorMaterial,
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    floor.userData.roompilotBaseFloor = true;
    if (!catalogThumbnailMode) roomGroup.add(floor);
    const presentationGround = new THREE.Mesh(
      new THREE.CircleGeometry(Math.max(widthCm, depthCm) * 1.15, 96),
      new THREE.MeshPhysicalMaterial({
        color: 0xe8e5df,
        roughness: 0.96,
        metalness: 0,
        envMapIntensity: 0.28,
      }),
    );
    presentationGround.rotation.x = -Math.PI / 2;
    presentationGround.position.y = -3.2;
    presentationGround.receiveShadow = true;
    presentationGround.userData.roompilotArchitecturalDetail = "shadow-ground";
    if (!catalogThumbnailMode) roomGroup.add(presentationGround);
    const shadowExtent = Math.max(widthCm, depthCm) * 0.72 + 100;
    keyLight.shadow.camera.left = -shadowExtent;
    keyLight.shadow.camera.right = shadowExtent;
    keyLight.shadow.camera.top = shadowExtent;
    keyLight.shadow.camera.bottom = -shadowExtent;
    keyLight.shadow.camera.near = 20;
    keyLight.shadow.camera.far = 3500;
    keyLight.shadow.camera.updateProjectionMatrix();
    if (!catalogThumbnailMode) {
      createRoomSurfaceOverrides(roomGroup, sceneData);
      createMaterialBoundarySurfaces(
        roomGroup,
        sceneData.material_boundary,
        floorMaterial,
        sceneData,
      );
    }

    const wallMaterial = createWallMaterial(wallOption, sceneData.surface_catalog);
    const wallPbr = sceneData.style?.pbr?.wall || {};
    const wallColor = sceneData.design_choices?.wall_color_hex
      || sceneData.style_card?.palette_hex?.[0];
    applySurfaceTint(wallMaterial, wallColor);
    if (wallPbr.roughness != null) wallMaterial.roughness = wallPbr.roughness;
    if (wallPbr.metalness != null) wallMaterial.metalness = wallPbr.metalness;
    const wallThickness = inferredWallThicknessCm(sceneData.floorplan, 12);
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const doorSegments = dedupeArchitecturalOpeningsFor3d(
      (sceneData.floorplan?.door_segments || []).map(
        (door) => doorOpeningForWallTopology(wallSegments, door, wallThickness),
      ),
      wallSegments,
      wallThickness,
    );
    const windowSegments = dedupeArchitecturalOpeningsFor3d(
      sceneData.floorplan?.window_segments || [],
      wallSegments,
      wallThickness,
    );
    const hasAccurateFloorplan = ["dxf", "user_confirmed"].includes(
      sceneData.floorplan?.source,
    );
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthCm, depthCm, wallHeight };
    roomGroup.userData.ceilingStyle = sceneData.design_choices?.ceiling_style || "exposed";

    const ceilingDropCm = Number(sceneData.design_choices?.ceiling_drop_cm) || 0;
    const ceilingHeight = wallHeight - ceilingDropCm;
    const hasRoomCeilings = (sceneData.surface_overrides || []).some(
      (override) => override.ceiling_style_id && override.ceiling_style_id !== "exposed",
    );
    if (!catalogThumbnailMode) {
      if (hasRoomCeilings) {
        createRoomCeilingOverrides(sceneData, wallHeight);
      } else {
        createCeilingGeometry(
          { widthCm, depthCm, wallHeight, ceilingHeight },
          roomGroup.userData.ceilingStyle,
          sceneData.style_card || sceneData.style || {},
          {
            color: sceneData.design_choices?.ceiling_color_hex,
            material: sceneData.design_choices?.ceiling_material,
          },
        );
      }
    }
    ceilingGroup.visible = false;

    // 12 cm 接近住宅隔間牆；原先 4 cm 會讓雙線牆與轉角看起來像中空。
    // Persisted Step 4 wall segments already contain true door gaps.  Always
    // use them for a confirmed multi-room plan so a blue open-door leaf can
    // never punch an invented opening through an otherwise continuous wall.
    const builtWallMass = !singleRoomMode && hasAccurateFloorplan && !wallSegments.length
      ? buildWallMass(
        roomGroup,
        sceneData.floorplan,
        wallMaterial,
        wallHeight,
      )
      : false;
    if (catalogThumbnailMode) {
      // Product thumbnails intentionally omit room geometry.
    } else if (builtWallMass) {
      buildWallMassTopCaps(
        roomGroup,
        sceneData.floorplan,
        wallMaterial,
        wallHeight,
      );
      buildStandaloneOpeningAssemblies(
        roomGroup,
        doorSegments,
        windowSegments,
        wallMaterial,
        wallHeight,
        wallThickness,
        sceneData.surface_catalog,
      );
    } else if (!builtWallMass && !singleRoomMode && wallSegments.length >= 2) {
      buildSegmentWalls(
        roomGroup,
        wallSegments,
        wallMaterialResolver(sceneData, wallMaterial),
        wallHeight,
        wallThickness,
        [],
        windowSegments,
        sceneData.floorplan,
        sceneData.surface_catalog,
        doorSegments,
      );
      buildConfirmedDoorLeaves(
        roomGroup,
        doorSegments,
        wallMaterialResolver(sceneData, wallMaterial),
        wallHeight,
        wallThickness,
        sceneData.surface_catalog,
      );
    } else {
      const backWall = new THREE.Mesh(new THREE.BoxGeometry(widthCm, wallHeight, wallThickness), wallMaterial.clone());
      backWall.position.set(0, wallHeight / 2, -depthCm / 2);
      roomGroup.add(registerWall(backWall, {
        segment: {
          start: { x: -widthCm / 2, z: -depthCm / 2 },
          end: { x: widthCm / 2, z: -depthCm / 2 },
        },
      }));

      const leftWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthCm), wallMaterial.clone());
      leftWall.position.set(-widthCm / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(leftWall, {
        segment: {
          start: { x: -widthCm / 2, z: depthCm / 2 },
          end: { x: -widthCm / 2, z: -depthCm / 2 },
        },
      }));

      const rightWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthCm), wallMaterial.clone());
      rightWall.position.set(widthCm / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(rightWall, {
        segment: {
          start: { x: widthCm / 2, z: -depthCm / 2 },
          end: { x: widthCm / 2, z: depthCm / 2 },
        },
      }));
    }

    // Keep a DOM-visible diagnostic for project-page verification. It measures
    // the assemblies actually added to this viewer, not merely input records.
    if (!catalogThumbnailMode) {
      const sourceDoorIds = (sceneData.floorplan?.door_segments || [])
        .map((door) => String(door?.id || "").trim())
        .filter(Boolean);
      const expectedDoorIds = doorSegments
        .map((door) => String(door?.id || "").trim())
        .filter(Boolean);
      const mergedDoorIds = sourceDoorIds.filter((id) => !expectedDoorIds.includes(id));
      const renderedDoors = roomGroup.children
        .filter((child) => child.userData?.roompilotArchitecturalDetail === "door")
        .map((child) => ({
          id: child.userData?.roompilotArchitecturalId || "",
          leafCount: child.children.filter(
            (mesh) => mesh.userData?.roompilotArchitecturalDetail === "closed-door-leaf",
          ).length,
          anchor: {
            x: Math.round(child.position.x * 100) / 100,
            z: Math.round(child.position.z * 100) / 100,
          },
        }))
        .filter((door) => door.id);
      const renderedDoorIds = renderedDoors.map((door) => door.id);
      const sourceDoorById = new Map(
        (sceneData.floorplan?.door_segments || []).map((door) => [String(door?.id || ""), door]),
      );
      const resolvedDoorById = new Map(
        doorSegments.map((door) => [String(door?.id || ""), door]),
      );
      const comparisons = expectedDoorIds.map((id) => {
        const source = sourceDoorById.get(id);
        const resolved = resolvedDoorById.get(id);
        const rendered = renderedDoors.find((door) => door.id === id);
        const confirmedOpening = resolved?.wall_opening_segment || resolved?.confirmed_wall_opening;
        const expectedAnchor = confirmedOpening?.start && confirmedOpening?.end
          ? {
            x: (Number(confirmedOpening.start.x) + Number(confirmedOpening.end.x)) / 2,
            z: (Number(confirmedOpening.start.z) + Number(confirmedOpening.end.z)) / 2,
          }
          : openingAnchorForWallTopology(resolved, wallSegments, wallThickness);
        const endpointDistance = source && resolved
          ? Math.min(
            Math.hypot(source.start.x - resolved.start.x, source.start.z - resolved.start.z)
              + Math.hypot(source.end.x - resolved.end.x, source.end.z - resolved.end.z),
            Math.hypot(source.start.x - resolved.end.x, source.start.z - resolved.end.z)
              + Math.hypot(source.end.x - resolved.start.x, source.end.z - resolved.start.z),
          )
          : Infinity;
        const anchorDistance = expectedAnchor && rendered
          ? Math.hypot(
            expectedAnchor.x - rendered.anchor.x,
            expectedAnchor.z - rendered.anchor.z,
          )
          : Infinity;
        return {
          id,
          source: source ? { start: source.start, end: source.end, hostWallId: source.host_wall_id || null } : null,
          resolved: resolved ? { start: resolved.start, end: resolved.end, hostWallId: resolved.host_wall_id || null } : null,
          expectedAnchor,
          anchorDistance: Number.isFinite(anchorDistance)
            ? Math.round(anchorDistance * 100) / 100
            : null,
          rendered: Boolean(rendered),
          // Recognition endpoints can be normalised in step 4. Compare the
          // rendered opening with the resolved wall anchor, not stale source coordinates.
          status: rendered && (!expectedAnchor || anchorDistance <= 1) ? "matched" : "mismatch",
        };
      });
      const doorDiagnostics = {
        expected: expectedDoorIds.length,
        recognized: sourceDoorIds.length,
        mergedDoorIds,
        resolved: doorSegments.length,
        rendered: renderedDoorIds.length,
        expectedIds: expectedDoorIds,
        renderedIds: renderedDoorIds,
        renderedDoors,
        comparisons,
      };
      container.dataset.roompilotDoorDiagnostics = JSON.stringify(doorDiagnostics);
      container.dispatchEvent(new CustomEvent("roompilot-door-diagnostics", {
        detail: doorDiagnostics,
      }));
    }

    if (!catalogThumbnailMode && hasAccurateFloorplan) {
      buildFloorPlanOverlay(roomGroup, doorSegments, 0xb9773f, 0.82, 3.8);
      buildFloorPlanOverlay(roomGroup, windowSegments, 0x6f9eb4, 0.9, 4.4);
      buildCirculationRoute(roomGroup, sceneData.floorplan);
    } else if (!catalogThumbnailMode && !builtWallMass) {
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(widthCm, wallHeight, depthCm)),
        new THREE.LineBasicMaterial({ color: 0xb89264, transparent: true, opacity: 0.35 })
      );
      outline.position.set(0, wallHeight / 2, 0);
      roomGroup.add(outline);
    }
    if (!catalogThumbnailMode) {
      buildStructuralMembers(roomGroup, sceneData.floorplan || {}, wallHeight);
    }

    const boundary = sceneData.material_boundary?.line_cm;
    if (!catalogThumbnailMode && Array.isArray(boundary) && boundary.length >= 2) {
      buildFloorPlanOverlay(roomGroup, [{
        start: { x: Number(boundary[0].x) || 0, z: Number(boundary[0].y) || 0 },
        end: { x: Number(boundary[1].x) || 0, z: Number(boundary[1].y) || 0 },
      }], 0x7b56b3, 0.96, 5.2);
    }

    if (!catalogThumbnailMode && sceneData.design_choices?.light_style) {
      createStyleLights(
        { widthCm, depthCm, wallHeight: ceilingHeight },
        sceneData.style_card || sceneData.style || {},
        sceneData.design_choices.light_style,
      );
    }

    if (!cameraLocked) {
      controls.target.set(0, 90, 0);
      setViewMode("orbit");
    }
  }

  function createCeilingGeometry(room, ceilingStyle, style = {}, finish = {}) {
    if (ceilingStyle === "exposed") return;
    const palette = style.palette_hex || ["#F3EBDD", "#D3B48A", "#8B684B"];
    const materialProfiles = {
      "flat-paint": { roughness: 0.86, metalness: 0 },
      "mineral-paint": { roughness: 0.96, metalness: 0 },
      "wood-veneer": { roughness: 0.58, metalness: 0 },
      "exposed-concrete": { roughness: 0.92, metalness: 0 },
    };
    const profile = materialProfiles[finish.material] || materialProfiles["flat-paint"];
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: finish.color || palette[0] || "#f3eee6",
      roughness: profile.roughness,
      metalness: profile.metalness,
      side: THREE.DoubleSide,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: palette[2] || "#8B684B",
      roughness: 0.55,
      metalness: ceilingStyle === "linear" ? 0.45 : 0.05,
    });
    const addPanel = (width, depth, y, material = baseMaterial, thickness = 4) => {
      const panel = new THREE.Mesh(
        new THREE.BoxGeometry(Math.max(width, 8), thickness, Math.max(depth, 8)),
        material,
      );
      panel.position.y = y;
      panel.receiveShadow = true;
      panel.castShadow = true;
      panel.userData.ceilingStyle = ceilingStyle;
      panel.userData.ceilingMaterial = finish.material || "flat-paint";
      ceilingGroup.add(panel);
      return panel;
    };

    if (ceilingStyle === "flat" || ceilingStyle === "no-main-light") {
      addPanel(room.widthCm, room.depthCm, room.ceilingHeight);
      return;
    }
    if (ceilingStyle === "cove") {
      const band = Math.min(42, room.widthCm / 6, room.depthCm / 6);
      addPanel(room.widthCm, band, room.ceilingHeight, baseMaterial, 10).position.z = -(room.depthCm - band) / 2;
      addPanel(room.widthCm, band, room.ceilingHeight, baseMaterial, 10).position.z = (room.depthCm - band) / 2;
      addPanel(band, Math.max(room.depthCm - band * 2, 10), room.ceilingHeight, baseMaterial, 10).position.x = -(room.widthCm - band) / 2;
      addPanel(band, Math.max(room.depthCm - band * 2, 10), room.ceilingHeight, baseMaterial, 10).position.x = (room.widthCm - band) / 2;
      addPanel(
        Math.max(room.widthCm - band * 2, 10),
        Math.max(room.depthCm - band * 2, 10),
        room.ceilingHeight + 10,
        baseMaterial,
      );
      return;
    }
    if (ceilingStyle === "floating" || ceilingStyle === "feature-pendant") {
      addPanel(
        ceilingStyle === "feature-pendant" ? Math.max(room.widthCm * 0.58, 120) : Math.max(room.widthCm - 70, 50),
        ceilingStyle === "feature-pendant" ? Math.max(room.depthCm * 0.42, 100) : Math.max(room.depthCm - 70, 50),
        room.ceilingHeight,
        baseMaterial,
        12,
      );
      return;
    }
    if (ceilingStyle === "linear") {
      addPanel(room.widthCm, room.depthCm, room.ceilingHeight);
      [-55, 55].forEach((x) => {
        const strip = addPanel(5.5, Math.max(room.depthCm - 50, 40), room.ceilingHeight - 3.5, accentMaterial, 1.8);
        strip.position.x = THREE.MathUtils.clamp(x, -room.widthCm / 3, room.widthCm / 3);
      });
      return;
    }
    if (ceilingStyle === "wood-grid") {
      const spacing = 24;
      const count = Math.max(3, Math.floor(room.widthCm / spacing));
      for (let index = 0; index <= count; index += 1) {
        const x = -room.widthCm / 2 + index * room.widthCm / count;
        const slat = addPanel(5.5, room.depthCm, room.ceilingHeight, accentMaterial, 8);
        slat.position.x = x;
      }
      return;
    }
    addPanel(room.widthCm, room.depthCm, room.ceilingHeight);
  }

  function createStyleLights(room, style = {}, lightStyle = "pendant") {
    const palette = style.palette_hex || ["#F3EBDD", "#D3B48A", "#8B684B"];
    const lightColor = new THREE.Color(palette[1] || "#D3B48A");
    const positions = room.widthCm >= 480 ? [-90, 0, 90] : [-62, 62];

    if (lightStyle === "track") {
      const rail = new THREE.Mesh(
        new THREE.BoxGeometry(Math.min(room.widthCm * 0.58, 340), 4.5, 5.5),
        new THREE.MeshStandardMaterial({ color: 0x292724, roughness: 0.34, metalness: 0.7 }),
      );
      rail.position.y = room.wallHeight - 8;
      hangingLightGroup.add(rail);
      positions.forEach((x, index) => {
        const spot = new THREE.Mesh(
          new THREE.CylinderGeometry(6.5, 9, 16, 18),
          new THREE.MeshStandardMaterial({ color: 0x34312e, roughness: 0.3, metalness: 0.65 }),
        );
        spot.position.set(x, room.wallHeight - 19, 0);
        spot.rotation.z = index % 2 ? -0.28 : 0.28;
        hangingLightGroup.add(spot);
        const light = new THREE.SpotLight(0xffdfb0, 2.2, 550, Math.PI / 5.5, 0.45, 1.7);
        light.position.copy(spot.position);
        light.target.position.set(x + (index % 2 ? 70 : -70), 0, 50);
        hangingLightGroup.add(light, light.target);
      });
      return;
    }
    if (lightStyle === "downlight") {
      const zPositions = room.depthCm > 420 ? [-80, 80] : [0];
      positions.forEach((x) => zPositions.forEach((z) => {
        const trim = new THREE.Mesh(
          new THREE.CylinderGeometry(9.5, 9.5, 3.5, 24),
          new THREE.MeshStandardMaterial({ color: 0xf8f5ee, roughness: 0.42, metalness: 0.12 }),
        );
        trim.position.set(x, room.wallHeight - 2.5, z);
        hangingLightGroup.add(trim);
        const light = new THREE.PointLight(0xffe4bd, 0.78, 350, 2);
        light.position.set(x, room.wallHeight - 12, z);
        hangingLightGroup.add(light);
      }));
      return;
    }
    if (lightStyle === "paper") {
      const paper = new THREE.Mesh(
        new THREE.SphereGeometry(34, 32, 20),
        new THREE.MeshStandardMaterial({
          color: 0xfff0cf,
          emissive: 0xffc36f,
          emissiveIntensity: 0.35,
          roughness: 0.94,
          transparent: true,
          opacity: 0.88,
        }),
      );
      paper.scale.y = 1.18;
      paper.position.set(0, room.wallHeight - 65, 0);
      hangingLightGroup.add(paper);
      const light = new THREE.PointLight(0xffd9a0, 1.8, 520, 2);
      light.position.copy(paper.position);
      hangingLightGroup.add(light);
      return;
    }
    positions.forEach((x, index) => {
      const pendant = new THREE.Group();
      pendant.position.set(x, room.wallHeight - 8, 0);

      const cord = new THREE.Mesh(
        new THREE.CylinderGeometry(1.2, 1.2, 72, 8),
        new THREE.MeshStandardMaterial({ color: 0x332b25, roughness: 0.7 })
      );
      cord.position.y = -36;
      pendant.add(cord);

      const shade = new THREE.Mesh(
        new THREE.ConeGeometry(19, 18, 32, 1, true),
        new THREE.MeshStandardMaterial({
          color: lightColor,
          roughness: 0.36,
          metalness: 0.2,
          side: THREE.DoubleSide,
        })
      );
      shade.position.y = -78;
      shade.rotation.y = index % 2 ? Math.PI : 0;
      pendant.add(shade);

      const bulb = new THREE.Mesh(
        new THREE.SphereGeometry(5.5, 16, 10),
        new THREE.MeshStandardMaterial({ color: 0xfff1ce, emissive: 0xffb45c, emissiveIntensity: 1.8 })
      );
      bulb.position.y = -82;
      pendant.add(bulb);

      const pointLight = new THREE.PointLight(0xffd6a0, 1.15, 480, 2);
      pointLight.position.y = -86;
      pointLight.castShadow = true;
      pendant.add(pointLight);
      hangingLightGroup.add(pendant);
    });
  }

  function physicalMaterialFrom(sourceMaterial) {
    if (sourceMaterial.isMeshPhysicalMaterial) return sourceMaterial.clone();
    const material = new THREE.MeshPhysicalMaterial({
      color: sourceMaterial.color?.clone() || new THREE.Color(0xffffff),
      map: sourceMaterial.map || null,
      normalMap: sourceMaterial.normalMap || null,
      normalScale: sourceMaterial.normalScale?.clone() || new THREE.Vector2(1, 1),
      bumpMap: sourceMaterial.bumpMap || null,
      bumpScale: sourceMaterial.bumpScale || 1,
      roughnessMap: sourceMaterial.roughnessMap || null,
      metalnessMap: sourceMaterial.metalnessMap || null,
      aoMap: sourceMaterial.aoMap || null,
      aoMapIntensity: sourceMaterial.aoMapIntensity || 1,
      emissive: sourceMaterial.emissive?.clone() || new THREE.Color(0x000000),
      emissiveMap: sourceMaterial.emissiveMap || null,
      emissiveIntensity: sourceMaterial.emissiveIntensity || 1,
      alphaMap: sourceMaterial.alphaMap || null,
      transparent: sourceMaterial.transparent,
      opacity: sourceMaterial.opacity,
      side: sourceMaterial.side,
      depthWrite: sourceMaterial.depthWrite,
      roughness: sourceMaterial.roughness ?? 0.62,
      metalness: sourceMaterial.metalness ?? 0,
    });
    material.name = sourceMaterial.name;
    return material;
  }

  function applyPhysicalFurnitureProfile(material, role) {
    const profile = furniturePbrProfile(role);
    Object.entries(profile).forEach(([key, value]) => {
      if (key in material && value != null) material[key] = value;
    });
    if (role === "fabric" && material.sheenColor) {
      material.sheenColor.copy(material.color || new THREE.Color(0xffffff));
    }
  }

  function applyStyleSkin(root, sceneData, sceneObject = {}) {
    if (
      sceneData.use_original_materials
      || (sceneObject.user_specified && !sceneObject.material_locked)
    ) return;
    const palette = sceneData.style_card?.palette_hex || sceneData.style?.palette_hex || [];
    if (!palette.length && !sceneData.material_role_overrides) return;

    const colors = (palette.length ? palette : ["#f3eee7", "#b58b63", "#59636a", "#d7c9b8"]).map((value) => new THREE.Color(value));
    root.traverse((object) => {
      if (!object.isMesh || !object.material) return;
      const sourceWasArray = Array.isArray(object.material);
      const materials = sourceWasArray ? object.material : [object.material];
      const styledMaterials = materials.map((sourceMaterial, index) => {
        const material = physicalMaterialFrom(sourceMaterial);
        const slotName = `${object.name || ""} ${material.name || ""}`.trim();
        const classifiedRole = classifyMaterialSlot(slotName);
        const role = classifiedRole === "unknown" ? fallbackMaterialRole(sceneObject.normalized_type) || "unknown" : classifiedRole;
        applyPhysicalFurnitureProfile(material, role);
        const packMaterial = sceneObject.material_override;
        const packRoughness = role === "wood"
          ? packMaterial?.pbr?.woodRoughness
          : role === "fabric"
            ? packMaterial?.pbr?.fabricRoughness
            : undefined;
        const override = sceneObject.material_overrides?.[material.name]
          || sceneObject.material_overrides?.[object.name]
          || sceneObject.material_overrides?.[`role:${role}`]
          || sceneData.material_role_overrides?.[role]
          || (packMaterial ? {
            colorHex: packMaterial.color,
            roughness: packMaterial.pbr?.roughness ?? packRoughness,
            metalness: packMaterial.pbr?.metalness,
          } : null);
        if (role === "unknown" && !override) return material;
        if (override?.preserveOriginal) return material;
        if (material.color) {
          const label = slotName.toLowerCase();
          const colorIndex = /metal|steel|brass|gold|chrome/.test(label) ? 2 : /wood|oak|walnut/.test(label) ? 1 : index % colors.length;
          if (override?.colorHex) material.color.set(override.colorHex);
          else material.color.lerp(colors[colorIndex] || colors[0], 0.34);
        }
        if ("roughness" in material) material.roughness = override?.roughness ?? Math.min(0.92, Math.max(0.28, material.roughness || 0.6));
        if ("metalness" in material && override?.metalness != null) material.metalness = override.metalness;
        if (override?.transparent) {
          material.transparent = true;
          material.opacity = override.opacity ?? 0.32;
        }
        material.needsUpdate = true;
        object.userData.roompilotSkinApplied = true;
        return material;
      });
      object.material = sourceWasArray ? styledMaterials : styledMaterials[0];
    });
  }

  function fitToTargetSize(root, targetSizeCm) {
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const target = {
      width: targetSizeCm.width || 120,
      depth: targetSizeCm.depth || 60,
      height: targetSizeCm.height || 80,
    };

    const scale = computeExactModelScale(size, target);
    root.scale.set(scale.x, scale.y, scale.z);
    root.updateMatrixWorld(true);
    moveModelToFootprintCenter(root);
  }

  function toggleCeiling() {
    ceilingGroup.visible = !ceilingGroup.visible;
    return ceilingGroup.visible;
  }

  function configureWallsForView(mode) {
    wallMeshes.forEach((wall) => {
      const heightAxis = wall.userData.roompilotWallHeightAxis || "y";
      if (mode === "topdown") {
        if (heightAxis === "z") wall.scale.z = 0.04;
        else wall.scale.y = 0.04;
        wall.position.y = 6;
      } else {
        if (heightAxis === "z") wall.scale.z = wall.userData.fullScaleZ || 1;
        else wall.scale.y = wall.userData.fullScaleY || 1;
        wall.position.y = wall.userData.fullPositionY ?? wall.position.y;
      }
    });
    ceilingGroup.visible = mode === "walk"
      && roomGroup.userData.ceilingStyle !== "exposed";
  }

  // 編號 sprite 是場景內物件，會被 capturePng 拍進去；預設關閉，只有
  // 白模 viewer 由前端 toggle 打開——生圖參考截圖與離屏預覽因此不帶編號。
  let showFurnitureNumberMarkers = false;
  let numberMarkerRoomId = "";

  function configurePlanLabels(mode) {
    const visible = viewPresentation(mode).showFurniturePlanLabels;
    furnitureGroup.traverse((object) => {
      if (object.userData.roompilotPlanLabel) object.visible = visible;
      if (object.userData.roompilotNumberMarker) {
        const roomId = String(object.parent?.userData?.sceneObject?.room_id
          || object.parent?.userData?.sceneObject?.roomId || "");
        object.visible = showFurnitureNumberMarkers
          && mode !== "walk"
          && (!numberMarkerRoomId || roomId === numberMarkerRoomId);
      }
    });
  }

  function configureCirculationForView(mode) {
    roomGroup.traverse((object) => {
      if (object.userData.roompilotCirculation) {
        object.visible = mode === "topdown";
      }
    });
  }

  function configureOpeningsForView(mode) {
    roomGroup.traverse((object) => {
      if (object.userData.roompilotArchitecturalDetail === "door") {
        object.visible = mode !== "walk";
      }
    });
  }

  function setViewMode(mode) {
    cameraLocked = false;
    interactionMode = mode === "walk" ? "walk" : "camera";
    const config = viewMode.setMode(mode);
    controls.object = config.camera === "orthographic" ? orthographicCamera : perspectiveCamera;
    camera = controls.object;
    controls.enabled = true;
    configureWallsForView(mode);
    configurePlanLabels(mode);
    configureCirculationForView(mode);
    configureOpeningsForView(mode);
    renderer.domElement.style.cursor = mode === "walk" ? "grab" : "";
    if (mode !== "walk") {
      walkDestination = null;
      walkMarker.visible = false;
    }
    if (mode === "walk") {
      selectWrapper(null);
      setCameraPreset("inside");
      activeCameraPreset = "walk";
      perspectiveCamera.up.set(0, 1, 0);
      controls.enabled = false;
      controls.enablePan = false;
      controls.enableZoom = false;
      const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360, wallHeight: 270 };
      const clamped = clampWalkPosition(perspectiveCamera.position, room);
      const spawn = findNearestWalkablePosition(
        clamped,
        room,
        (point) => (
          walkPositionInsideFloor(point)
          && !walkPositionBlocked(point)
          && !walkPositionBlockedByFurniture(point)
        ),
      ) || clamped;
      const spawnOffset = new THREE.Vector3(
        spawn.x - perspectiveCamera.position.x,
        spawn.y - perspectiveCamera.position.y,
        spawn.z - perspectiveCamera.position.z,
      );
      perspectiveCamera.position.set(spawn.x, spawn.y, spawn.z);
      controls.target.add(spawnOffset);
    } else if (mode === "topdown") {
      const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360 };
      const extent = Math.max(room.widthCm, room.depthCm) * 0.62 + 80;
      orthographicCamera.left = -extent;
      orthographicCamera.right = extent;
      orthographicCamera.top = extent;
      orthographicCamera.bottom = -extent;
      orthographicCamera.position.set(0, 1800, 0.1);
      orthographicCamera.up.set(0, 0, -1);
      orthographicCamera.lookAt(0, 0, 0);
      orthographicCamera.updateProjectionMatrix();
      controls.target.set(0, 0, 0);
      controls.enableRotate = false;
      controls.enablePan = true;
      controls.enableZoom = true;
      controls.update();
    } else if (mode === "dollhouse") {
      const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360 };
      const extent = Math.max(room.widthCm, room.depthCm) * 0.68 + 90;
      orthographicCamera.left = -extent;
      orthographicCamera.right = extent;
      orthographicCamera.top = extent;
      orthographicCamera.bottom = -extent;
      orthographicCamera.position.set(extent, extent * 0.92, extent);
      orthographicCamera.up.set(0, 1, 0);
      orthographicCamera.lookAt(0, 45, 0);
      orthographicCamera.updateProjectionMatrix();
      controls.target.set(0, 45, 0);
      controls.enabled = true;
      controls.enableRotate = true;
      controls.enablePan = true;
      controls.enableZoom = true;
      controls.screenSpacePanning = true;
      controls.update();
      activeCameraPreset = "dollhouse";
    } else {
      setCameraPreset("corner");
      activeCameraPreset = "corner";
    }
    syncPostProcessingCamera();
    if (gtaoPass) {
      // Orthographic GTAO creates dark projection wedges; contact shadows cover
      // the dollhouse while perspective modes retain full ambient occlusion.
      gtaoPass.enabled = gtaoRequested && ["walk", "orbit"].includes(mode);
    }
    onResize();
    return config;
  }

  function setWalkRoom(room = {}) {
    if (!lastSceneData) return false;
    const requested = sceneToWorldPosition(room.center_cm || {});
    const polygon = (room.polygon_cm || []).map(sceneToWorldPosition);
    const roomSize = roomGroup.userData.roomSize || {
      widthCm: 420,
      depthCm: 360,
      wallHeight: 270,
    };
    const eyeHeight = 145;
    const candidate = {
      x: requested.x,
      y: eyeHeight,
      z: requested.z,
    };
    const spawn = findNearestWalkablePosition(
      candidate,
      roomSize,
      (point) => (
        (!polygon.length || pointInRing(point, polygon))
        && walkPositionInsideFloor(point)
        && !walkPositionBlocked(point)
        && !walkPositionBlockedByFurniture(point)
      ),
    );
    if (!spawn) {
      setStatus(`無法進入「${room.label || "選取空間"}」：找不到可安全站立的位置。`);
      return false;
    }
    setViewMode("walk");
    perspectiveCamera.position.set(spawn.x, eyeHeight, spawn.z);
    const target = findWalkLookTarget(spawn, polygon);
    controls.target.set(target.x, 108, target.z);
    walkDestination = null;
    walkMarker.visible = false;
    setStatus(
      `走動模式：已進入「${room.label || "選取空間"}」，門片已隱藏；點地板移動，家具不會被選取。`,
    );
    return true;
  }

  function findWalkLookTarget(spawn, polygon = []) {
    const directions = [
      { x: 0, z: -1 }, { x: 1, z: 0 }, { x: 0, z: 1 }, { x: -1, z: 0 },
      { x: 0.707, z: -0.707 }, { x: 0.707, z: 0.707 },
      { x: -0.707, z: 0.707 }, { x: -0.707, z: -0.707 },
    ];
    const isInsideSelectedRoom = (point) => (
      !polygon.length || pointInRing(point, polygon)
    );
    const scored = directions.map((direction) => {
      let clearance = 0;
      for (let distance = 30; distance <= 210; distance += 30) {
        const point = {
          x: spawn.x + direction.x * distance,
          y: spawn.y,
          z: spawn.z + direction.z * distance,
        };
        if (!isInsideSelectedRoom(point)
          || !walkPositionInsideFloor(point)
          || walkPositionBlocked(point)
          || walkPositionBlockedByFurniture(point)) break;
        clearance = distance;
      }
      return { direction, clearance };
    });
    const best = scored.sort((left, right) => right.clearance - left.clearance)[0];
    const distance = Math.max(80, Math.min(best?.clearance || 100, 160));
    return {
      x: spawn.x + (best?.direction.x || 0) * distance,
      z: spawn.z + (best?.direction.z || -1) * distance,
    };
  }

  function toggleCameraLock(force) {
    cameraLocked = typeof force === "boolean" ? force : !cameraLocked;
    interactionMode = cameraLocked ? "edit" : (viewMode.mode === "walk" ? "walk" : "camera");
    controls.enabled = true;
    if (cameraLocked) {
      controls.enableRotate = false;
      controls.enablePan = false;
      controls.enableZoom = true;
    }
    if (!cameraLocked) {
      setViewMode(viewMode.mode);
    }
    return cameraLocked;
  }

  function setInteractionMode(mode) {
    if (mode === "walk") {
      setViewMode("walk");
      interactionMode = "walk";
      cameraLocked = false;
      setStatus("走動模式：使用 W／A／S／D 前後左右移動，拖曳空白處轉動視角。");
      return interactionMode;
    }
    if (mode === "edit") {
      interactionMode = "edit";
      cameraLocked = true;
      walkKeys.clear();
      walkDestination = null;
      walkMarker.visible = false;
      controls.enabled = true;
      controls.enableRotate = false;
      controls.enablePan = false;
      controls.enableZoom = true;
      renderer.domElement.style.cursor = selectedWrapper ? "grab" : "";
      setStatus("家具編輯模式：鏡頭已固定，可點選、拖曳或旋轉家具。");
      return interactionMode;
    }
    interactionMode = "camera";
    cameraLocked = false;
    setViewMode(viewMode.mode);
    return interactionMode;
  }

  function getDiagnostics() {
    return {
      ...JSON.parse(JSON.stringify(lastDiagnostics)),
      rendering: {
        gtaoEnabled: Boolean(gtaoPass?.enabled),
        toneMapping: "ACESFilmic",
        antialias: "MSAA",
        fps: lastMeasuredFps,
      },
    };
  }

  function updateWalkMovement() {
    if (viewMode.mode !== "walk" || interactionMode !== "walk") return;
    const forward = new THREE.Vector3();
    perspectiveCamera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3().crossVectors(forward, perspectiveCamera.up).normalize();
    const movement = new THREE.Vector3();
    if (walkKeys.has("w") || walkKeys.has("arrowup")) movement.add(forward);
    if (walkKeys.has("s") || walkKeys.has("arrowdown")) movement.sub(forward);
    if (walkKeys.has("a") || walkKeys.has("arrowleft")) movement.sub(right);
    if (walkKeys.has("d") || walkKeys.has("arrowright")) movement.add(right);
    if (movement.lengthSq()) {
      walkDestination = null;
      walkMarker.visible = false;
      movement.normalize().multiplyScalar(4.5);
    } else if (walkDestination) {
      movement.copy(walkDestination).sub(perspectiveCamera.position);
      movement.y = 0;
      if (movement.length() < 8) {
        walkDestination = null;
        walkMarker.visible = false;
        return;
      }
      movement.clampLength(0, 5.5);
    } else {
      return;
    }
    const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360, wallHeight: 270 };
    const proposed = perspectiveCamera.position.clone().add(movement);
    const clamped = clampWalkPosition(proposed, room);
    if (
      !walkPositionInsideFloor(clamped)
      || walkPositionBlocked(clamped)
      || walkPositionBlockedByFurniture(clamped)
    ) {
      walkDestination = null;
      walkMarker.visible = false;
      setStatus("前方是牆面；請從門洞通過，或點選同一空間內的地板位置。");
      return;
    }
    const actualMovement = new THREE.Vector3(clamped.x, clamped.y, clamped.z).sub(perspectiveCamera.position);
    perspectiveCamera.position.add(actualMovement);
    controls.target.add(actualMovement);
  }

  function capturePng() {
    // 截圖會當成生圖模型的 img2img 參考,家具號碼標籤不能入鏡,
    // 否則模型會把數字圓牌畫進成品。只藏當下可見的標籤,拍完復原。
    const hiddenMarkers = [];
    scene.traverse((object) => {
      if (object.userData?.roompilotNumberMarker && object.visible) hiddenMarkers.push(object);
    });
    hiddenMarkers.forEach((marker) => { marker.visible = false; });
    if (composer) composer.render();
    else renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL("image/png");
    hiddenMarkers.forEach((marker) => { marker.visible = true; });
    return dataUrl;
  }

  function getCameraState() {
    return {
      camera_type: camera.isPerspectiveCamera ? "perspective" : "orthographic",
      view_mode: viewMode.mode,
      preset: activeCameraPreset,
      position_cm: camera.position.toArray().map((value) => Number(value.toFixed(3))),
      target_cm: controls.target.toArray().map((value) => Number(value.toFixed(3))),
      up: camera.up.toArray().map((value) => Number(value.toFixed(6))),
      fov_deg: camera.isPerspectiveCamera ? Number(camera.fov.toFixed(3)) : null,
      zoom: Number(camera.zoom.toFixed(4)),
      aspect_ratio: `${Math.max(container.clientWidth, 1)}:${Math.max(container.clientHeight, 1)}`,
    };
  }

  function setCameraState(snapshot = {}) {
    const requestedMode = String(snapshot.view_mode || "orbit");
    setViewMode(requestedMode);
    const selectedCamera = snapshot.camera_type === "orthographic"
      ? orthographicCamera
      : perspectiveCamera;
    if (camera !== selectedCamera) {
      camera = selectedCamera;
      controls.object = selectedCamera;
      syncPostProcessingCamera();
    }
    if (Array.isArray(snapshot.position_cm) && snapshot.position_cm.length === 3) {
      camera.position.fromArray(snapshot.position_cm.map(Number));
    }
    if (Array.isArray(snapshot.target_cm) && snapshot.target_cm.length === 3) {
      controls.target.fromArray(snapshot.target_cm.map(Number));
    }
    if (Array.isArray(snapshot.up) && snapshot.up.length === 3) {
      camera.up.fromArray(snapshot.up.map(Number));
    }
    if (camera.isPerspectiveCamera && Number(snapshot.fov_deg) > 0) {
      camera.fov = THREE.MathUtils.clamp(Number(snapshot.fov_deg), 30, 80);
    }
    if (Number(snapshot.zoom) > 0) camera.zoom = Number(snapshot.zoom);
    camera.updateProjectionMatrix();
    controls.update();
    onResize();
    return getCameraState();
  }

  function lockRenderCamera(force = true) {
    cameraLocked = Boolean(force);
    controls.enabled = !cameraLocked;
    controls.enableRotate = !cameraLocked;
    controls.enablePan = !cameraLocked;
    controls.enableZoom = !cameraLocked;
    return cameraLocked;
  }

  async function exportGlb() {
    const exportRoot = new THREE.Group();
    exportRoot.add(roomGroup.clone(true));
    exportRoot.add(furnitureGroup.clone(true));
    const exportScale = lastSceneData?.floorplan?.coordinate_unit === "cm" ? 0.01 : 1;
    exportRoot.scale.setScalar(exportScale);
    exportRoot.updateMatrixWorld(true);
    const exporter = new GLTFExporter();
    return exporter.parseAsync(exportRoot, { binary: true, onlyVisible: true });
  }

  function createNumberMarker(label) {
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext("2d");

    context.beginPath();
    context.arc(64, 64, 44, 0, Math.PI * 2);
    context.fillStyle = "#fffaf2";
    context.fill();
    context.lineWidth = 8;
    context.strokeStyle = "#8a6648";
    context.stroke();

    context.fillStyle = "#3a2c22";
    context.font = "bold 54px 'Segoe UI', 'Noto Sans TC', sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(label), 64, 68);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(64, 64, 1);
    sprite.renderOrder = 1005;
    sprite.raycast = () => {};
    sprite.userData.roompilotNumberMarker = true;
    return sprite;
  }

  function createFurniturePlanLabel(label) {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 112;
    const context = canvas.getContext("2d");
    context.fillStyle = "rgba(255, 250, 242, 0.94)";
    context.strokeStyle = "#76563e";
    context.lineWidth = 6;
    context.beginPath();
    context.roundRect(8, 8, 496, 96, 22);
    context.fill();
    context.stroke();
    context.fillStyle = "#33271f";
    context.font = "bold 38px 'Segoe UI', 'Noto Sans TC', sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    const text = String(label || "家具");
    context.fillText(text.length > 14 ? `${text.slice(0, 13)}…` : text, 256, 58);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false }));
    sprite.scale.set(170, 38, 1);
    sprite.renderOrder = 1001;
    sprite.userData.roompilotPlanLabel = true;
    sprite.raycast = () => {};
    sprite.visible = false;
    return sprite;
  }

  function furnitureAnnotationsEnabled() {
    return lastWorldSceneData?.design_choices?.catalog_thumbnail_mode !== true;
  }

  let lastDiagnostics = {
    requestedFurnitureCount: 0,
    visibleFurnitureCount: 0,
    fallbackFurnitureCount: 0,
    failedFurniture: [],
  };

  let contactShadowTexture = null;

  function getContactShadowTexture() {
    if (contactShadowTexture) return contactShadowTexture;
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 256;
    const context = canvas.getContext("2d");
    const gradient = context.createRadialGradient(128, 128, 16, 128, 128, 126);
    gradient.addColorStop(0, "rgba(0, 0, 0, 0.64)");
    gradient.addColorStop(0.46, "rgba(0, 0, 0, 0.27)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 256);
    contactShadowTexture = new THREE.CanvasTexture(canvas);
    contactShadowTexture.colorSpace = THREE.NoColorSpace;
    return contactShadowTexture;
  }

  function addFurnitureContactShadow(wrapper, sizeCm = {}) {
    const width = Math.max(Number(sizeCm.width || 80), 25);
    const depth = Math.max(Number(sizeCm.depth || 60), 25);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(width * 1.08, depth * 1.08),
      new THREE.MeshBasicMaterial({
        map: getContactShadowTexture(),
        transparent: true,
        opacity: 0.34,
        depthWrite: false,
        toneMapped: false,
      }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.8;
    shadow.renderOrder = 2;
    shadow.userData.roompilotContactShadow = true;
    shadow.raycast = () => {};
    wrapper.add(shadow);
  }

  function createFallbackFurnitureProxy(item, index, reason) {
    const width = Math.max(Number(item.size_cm?.width || 120), 25);
    const depth = Math.max(Number(item.size_cm?.depth || 60), 25);
    const height = Math.max(Number(item.size_cm?.height || 80), 25);
    const wrapper = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({
      color: 0xd97706,
      transparent: true,
      opacity: 0.38,
      roughness: 0.78,
      metalness: 0,
    });
    const body = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
    body.position.y = height / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    wrapper.add(body);

    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(body.geometry),
      new THREE.LineBasicMaterial({ color: 0x9a3412, transparent: true, opacity: 0.95 }),
    );
    outline.position.copy(body.position);
    wrapper.add(outline);
    const worldPosition = sceneToWorldPosition(
      item.position_cm || { x: ((index % 4) - 1.5) * 130, z: Math.floor(index / 4) * 110 },
    );
    wrapper.position.x = worldPosition.x;
    wrapper.position.z = worldPosition.z;
    wrapper.rotation.y = THREE.MathUtils.degToRad(sceneToWorldRotationDeg(item.rotation_y_deg || 0));
    wrapper.userData.sceneIndex = index + 1;
    wrapper.userData.sceneObject = item;
    wrapper.userData.fallbackFurniture = true;
    wrapper.userData.fallbackReason = reason;
    wrapper.userData.modelLoadFailed = true;
    addFurnitureContactShadow(wrapper, item.size_cm || {});
    addFurniturePickProxy(wrapper, item);

    if (furnitureAnnotationsEnabled()) {
      const marker = createNumberMarker(index + 1);
      marker.userData.roompilotNumberMarker = true;
      marker.position.set(0, height + 48, 0);
      wrapper.add(marker);
      const planLabel = createFurniturePlanLabel(item.name_zh_raw || item.normalized_type);
      planLabel.position.set(0, height + 15, 0);
      wrapper.add(planLabel);
    }
    furnitureGroup.add(wrapper);
    return wrapper;
  }

  async function loadScene(sceneData) {
    onResize();
    // 場景常駐：內容（JSON）未變且上次載入沒有模型 fallback 時，直接沿用
    // 既有場景，不整包重建——步驟往返、還原重載、同方案重進都命中。
    // 有 fallback 時仍重載，讓暫時性模型錯誤有機會重試。
    const sceneKey = JSON.stringify(sceneData);
    if (
      sceneKey === lastSceneKey
      && lastSceneData
      && lastDiagnostics.fallbackFurnitureCount === 0
    ) {
      lastSceneData = sceneData;
      lastWorldSceneData = sceneDataForWorld(sceneData);
      return;
    }
    lastSceneKey = sceneKey;
    lastSceneData = sceneData;
    lastWorldSceneData = sceneDataForWorld(sceneData);
    dragState = null;
    selectedWrapper = null;
    selectedControls.hidden = true;
    disposeGuide();
    clearGroup(furnitureGroup);
    applyRenderingProfile(sceneData);
    // 房殼輸入（去除家具後的場景資料）未變時跳過重建，只重灌家具。
    const shellKey = JSON.stringify({ ...lastWorldSceneData, scene_objects: null });
    if (shellKey !== lastShellKey) {
      createRoom(lastWorldSceneData);
      lastShellKey = shellKey;
    }
    setStatus("正在生成 3D 場景...");

    const objects = sceneData.scene_objects || [];
    const failures = [];
    await Promise.all(
      objects.map((item, index) => buildFurnitureWrapper(item, index, sceneData, failures)),
    );
    refreshFurnitureDiagnostics();

    if (failures.length) {
      setStatus(`場景已生成，但部分家具未載入：${failures.join("、")}`);
    } else {
      setStatus("場景已生成：拖曳家具可移動（放手時檢查碰撞），點選後按 R 旋轉。");
    }

    // Keep the source-versus-rendered door result visible after the generic load status.
    if (container.dataset.roompilotDoorDiagnostics) {
      container.dispatchEvent(new CustomEvent("roompilot-door-diagnostics", {
        detail: JSON.parse(container.dataset.roompilotDoorDiagnostics),
      }));
    }
  }

  // A material edit only changes wall/floor/ceiling surfaces, which createRoom
  // bakes into the shell groups (roomGroup/ceilingGroup).  Furniture lives in a
  // separate furnitureGroup, so rebuild only the shell and leave the furniture —
  // and their cached GLB clones — in place.  Far cheaper than loadScene, which
  // clears and re-clones every model on each edit (the source of the step 6/7
  // per-material jank).  The camera is untouched.
  function updateRoomSurfaces(sceneData) {
    if (!sceneData) return;
    lastSceneData = sceneData;
    lastWorldSceneData = sceneDataForWorld(sceneData);
    const shellKey = JSON.stringify({ ...lastWorldSceneData, scene_objects: null });
    // 房殼(去家具後的場景)未變＝材質/覆蓋沒改:純房間切換或重套同一份材質時
    // 直接返回,省下整個 createRoom(牆/地/天花幾何 + 面材)。scene_objects 已折出,
    // 只要材質/覆蓋一改 shellKey 就變,不會漏更新。
    if (shellKey === lastShellKey) {
      lastSceneKey = JSON.stringify(sceneData);
      return;
    }
    createRoom(lastWorldSceneData);
    // Keep loadScene's skip keys coherent so a later navigation reload is a no-op.
    lastShellKey = shellKey;
    lastSceneKey = JSON.stringify(sceneData);
  }

  async function buildFurnitureWrapper(item, index, sceneData, failures = null) {
    if (item.placement_failed) {
      failures?.push(`${item.name_zh_raw || item.normalized_type}（空間放不下，未擺入）`);
      return null;
    }
    if (!item.model_url) {
      failures?.push(`${item.name_zh_raw || item.normalized_type} 無模型`);
      return createFallbackFurnitureProxy(item, index, "資料庫尚未提供 GLB");
    }

    try {
      const gltf = await loadGltfCached(loader, item.model_url);
      const modelRoot = cloneCachedGltfScene(gltf);
      applyStyleSkin(modelRoot, sceneData, item);
      modelRoot.traverse((object) => {
        if (object.isMesh) {
          object.castShadow = true;
          object.receiveShadow = true;
        }
      });
      const wrapper = new THREE.Group();
      wrapper.add(modelRoot);
      modelRoot.rotation.y = Math.PI;   // 型錄 GLB 正面朝 +z，補 180° 對齊場景約定(-z)
      fitToTargetSize(modelRoot, item.size_cm || {});
      modelRoot.traverse((object) => {
        if (object.isMesh || object.isSkinnedMesh) {
          object.raycast = () => {};
        }
      });
      wrapper.userData.sceneIndex = index + 1;
      wrapper.userData.sceneObject = item;

      const worldPosition = sceneToWorldPosition(item.position_cm || {});
      wrapper.position.x = worldPosition.x;
      wrapper.position.z = worldPosition.z;
      wrapper.rotation.y = THREE.MathUtils.degToRad(sceneToWorldRotationDeg(item.rotation_y_deg || 0));

      const size = sizeCentimeters(item);
      addFurnitureContactShadow(wrapper, item.size_cm || {});
      addFurniturePickProxy(wrapper, item);
      if (furnitureAnnotationsEnabled()) {
        const marker = createNumberMarker(index + 1);
        marker.userData.roompilotNumberMarker = true;
        marker.position.set(0, Math.max(size.height + 48, 72), 0);
        wrapper.add(marker);
        const planLabel = createFurniturePlanLabel(item.name_zh_raw || item.normalized_type);
        planLabel.position.set(0, Math.max(size.height + 15, 35), 0);
        wrapper.add(planLabel);
      }
      furnitureGroup.add(wrapper);
      return wrapper;
    } catch (error) {
      console.error(error);
      failures?.push(item.name_zh_raw || item.normalized_type || "未知家具");
      return createFallbackFurnitureProxy(
        item,
        index,
        "GLB 載入失敗，請更換家具或檢查資料庫模型權限",
      );
    }
  }

  function refreshFurnitureDiagnostics() {
    const objects = lastSceneData?.scene_objects || [];
    lastDiagnostics = {
      requestedFurnitureCount: objects.length,
      visibleFurnitureCount: 0,
      fallbackFurnitureCount: 0,
      failedFurniture: [],
    };
    objects.forEach((item) => {
      const wrapper = furnitureGroup.children.find(
        (candidate) => candidate.userData.sceneObject === item,
      );
      if (wrapper?.userData.modelLoadFailed === true) {
        lastDiagnostics.failedFurniture.push({
          id: item.furniture_id,
          reason: wrapper.userData.fallbackReason,
        });
        return;
      }
      if (wrapper) return;
      if (item.placement_failed) {
        lastDiagnostics.failedFurniture.push({
          id: item.furniture_id,
          reason: item.placement_reason || "家具位置無法通過碰撞與淨空檢查",
        });
        return;
      }
      const reason = item.model_url
          ? "GLB 載入失敗，請檢查資料庫模型權限或網址"
          : "資料庫尚未提供 GLB";
      lastDiagnostics.failedFurniture.push({
        id: item.furniture_id,
        reason,
      });
    });
    lastDiagnostics.visibleFurnitureCount = furnitureGroup.children.length;
    lastDiagnostics.fallbackFurnitureCount = furnitureGroup.children.filter(
      (wrapper) => wrapper.userData.fallbackFurniture === true,
    ).length;
  }

  // ── 增量操作：單件家具增/刪/換不動房殼與其他家具，模型走 GLB 快取 ──

  function wrapperForFurnitureId(furnitureId) {
    const key = String(furnitureId);
    return furnitureGroup.children.find(
      (candidate) => String(candidate.userData.sceneObject?.furniture_id || "") === key,
    ) || null;
  }

  function detachWrapper(wrapper) {
    if (selectedWrapper === wrapper) {
      selectedWrapper = null;
      selectedControls.hidden = true;
      dragState = null;
      disposeGuide();
    }
    furnitureGroup.remove(wrapper);
    disposeObjectTree(wrapper);
  }

  function renumberFurnitureWrappers() {
    const objects = lastSceneData?.scene_objects || [];
    furnitureGroup.children.forEach((wrapper) => {
      const index = objects.indexOf(wrapper.userData.sceneObject);
      if (index < 0) return;
      const sceneIndex = index + 1;
      if (wrapper.userData.sceneIndex === sceneIndex) return;
      wrapper.userData.sceneIndex = sceneIndex;
      const marker = wrapper.children.find(
        (child) => child.userData?.roompilotNumberMarker,
      );
      if (marker) {
        const position = marker.position.clone();
        wrapper.remove(marker);
        disposeObjectTree(marker);
        const replacement = createNumberMarker(sceneIndex);
        replacement.userData.roompilotNumberMarker = true;
        replacement.position.copy(position);
        wrapper.add(replacement);
      }
    });
  }

  async function addObject(item) {
    if (!lastSceneData || !item) return false;
    const objects = lastSceneData.scene_objects || [];
    const index = objects.indexOf(item);
    await buildFurnitureWrapper(item, index >= 0 ? index : objects.length, lastSceneData);
    lastSceneKey = JSON.stringify(lastSceneData);
    refreshFurnitureDiagnostics();
    return true;
  }

  function removeObject(furnitureId) {
    const wrapper = wrapperForFurnitureId(furnitureId);
    if (!wrapper) return false;
    detachWrapper(wrapper);
    renumberFurnitureWrappers();
    lastSceneKey = JSON.stringify(lastSceneData);
    refreshFurnitureDiagnostics();
    return true;
  }

  async function updateObject(item) {
    if (!lastSceneData || !item) return false;
    const wrapper = wrapperForFurnitureId(item.furniture_id);
    if (wrapper) detachWrapper(wrapper);
    await addObject(item);
    renumberFurnitureWrappers();
    return true;
  }

  function unloadScene() {
    // 卸載整包場景並釋放非快取資源（快取資產由 LRU 淘汰統一釋放）。
    // 給離屏/暫存用途：拍完預覽即卸載，context 不滯留整棟場景的 GPU 記憶體。
    dragState = null;
    selectedWrapper = null;
    selectedControls.hidden = true;
    disposeGuide();
    clearGroup(furnitureGroup);
    clearGroup(roomGroup);
    clearGroup(ceilingGroup);
    clearGroup(hangingLightGroup);
    wallMeshes.length = 0;
    lastSceneData = null;
    lastWorldSceneData = null;
    lastSceneKey = null;
    lastShellKey = null;
    refreshFurnitureDiagnostics();
  }

  // ── F6 自由拖曳：前端只負責拖，落點合法性由後端 furniture_engine 驗證 ──
  let lastSceneData = null;
  let lastWorldSceneData = null;
  let lastSceneKey = null;    // 整包場景 JSON：未變時 loadScene 直接沿用既有場景
  let lastShellKey = null;    // 房殼輸入 JSON：未變時跳過 createRoom
  let dragState = null;
  let selectedWrapper = null;
  let footprintGuide = null;
  let snapHint = null;
  let placementRequest = null;
  let beamPlacementRequest = null;

  const dragRaycaster = new THREE.Raycaster();
  const pointerNdc = new THREE.Vector2();
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const planeHit = new THREE.Vector3();
  const walkMarker = new THREE.Mesh(
    new THREE.RingGeometry(9, 14, 32),
    new THREE.MeshBasicMaterial({
      color: 0x2f7d64,
      transparent: true,
      opacity: 0.86,
      depthTest: false,
      side: THREE.DoubleSide,
    }),
  );
  walkMarker.rotation.x = -Math.PI / 2;
  walkMarker.position.y = 2.5;
  walkMarker.visible = false;
  scene.add(walkMarker);
  const selectedControls = document.createElement("div");
  selectedControls.className = "scene-object-controls";
  selectedControls.hidden = true;
  selectedControls.innerHTML = `
    <div class="scene-object-controls-title">單件家具微調</div>
    <div class="scene-object-controls-grid">
      <button type="button" data-object-move="forward">前</button>
      <button type="button" data-object-rotate="-15" title="Shift+R 反向 15 度">左轉 15°</button>
      <button type="button" data-object-rotate="15" title="R 旋轉 15 度">右轉 15°</button>
      <button type="button" data-object-move="left">左</button>
      <button type="button" data-object-move="back">後</button>
      <button type="button" data-object-move="right">右</button>
      <button type="button" class="scene-object-rotate-quarter-turn" data-object-rotate="90" title="旋轉 90 度">旋轉 90°</button>
    </div>
    <button type="button" class="scene-object-lock-button" data-object-lock>鎖定此家具</button>
  `;
  container.appendChild(selectedControls);
  selectedControls.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });

  function pointerToNdc(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointerNdc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointerNdc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  }

  function setWalkDestinationFromPointer(event) {
    if (viewMode.mode !== "walk") return false;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, perspectiveCamera);
    if (!dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) return false;
    const room = roomGroup.userData.roomSize || { widthCm: 420, depthCm: 360, wallHeight: 270 };
    const destination = clampWalkPosition(
      { x: planeHit.x, y: perspectiveCamera.position.y, z: planeHit.z },
      room,
    );
    if (!walkPositionInsideFloor(destination)) {
      walkDestination = null;
      walkMarker.visible = false;
      setStatus("請點選室內地板；室外與牆體範圍不能作為移動目的地。");
      return false;
    }
    walkDestination = new THREE.Vector3(
      destination.x,
      perspectiveCamera.position.y,
      destination.z,
    );
    walkMarker.position.set(destination.x, 2.5, destination.z);
    walkMarker.visible = true;
    setStatus("已設定室內移動位置；可拖曳畫面轉頭，或使用 WASD／方向鍵移動。");
    return true;
  }

  function pointInRing(position, ring) {
    if (!Array.isArray(ring) || ring.length < 3) return false;
    let inside = false;
    for (let current = 0, previous = ring.length - 1; current < ring.length; previous = current++) {
      const currentPoint = ring[current];
      const previousPoint = ring[previous];
      const currentX = Number(Array.isArray(currentPoint) ? currentPoint[0] : currentPoint?.x);
      const currentZ = Number(Array.isArray(currentPoint) ? currentPoint[1] : currentPoint?.z);
      const previousX = Number(Array.isArray(previousPoint) ? previousPoint[0] : previousPoint?.x);
      const previousZ = Number(Array.isArray(previousPoint) ? previousPoint[1] : previousPoint?.z);
      if (![currentX, currentZ, previousX, previousZ].every(Number.isFinite)) continue;
      const crosses = (currentZ > position.z) !== (previousZ > position.z);
      const edgeX = ((previousX - currentX) * (position.z - currentZ))
        / ((previousZ - currentZ) || Number.EPSILON) + currentX;
      if (crosses && position.x < edgeX) inside = !inside;
    }
    return inside;
  }

  function walkPositionInsideFloor(position) {
    const regions = lastWorldSceneData?.floorplan?.room_regions || [];
    if (!regions.length) return true;
    return regions.some((region) => {
      const exterior = region.exterior || region.polygon_cm || region.polygon_m || [];
      if (!pointInRing(position, exterior)) return false;
      return !(region.holes || []).some((hole) => pointInRing(position, hole));
    });
  }

  function walkPositionBlocked(position, clearanceCm = 20) {
    return (lastWorldSceneData?.floorplan?.wall_segments || []).some((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return false;
      const dx = Number(end.x) - Number(start.x);
      const dz = Number(end.z) - Number(start.z);
      const lengthSquared = dx * dx + dz * dz;
      if (lengthSquared < 0.0001) return false;
      const projection = THREE.MathUtils.clamp(
        ((position.x - Number(start.x)) * dx + (position.z - Number(start.z)) * dz)
          / lengthSquared,
        0,
        1,
      );
      const closestX = Number(start.x) + projection * dx;
      const closestZ = Number(start.z) + projection * dz;
      const insideDoorOpening = (lastWorldSceneData?.floorplan?.door_openings || []).some((opening) => {
        if (!openingBelongsToWall(segment, opening, 24)) return false;
        const openingStart = opening.start || opening.hinge || {};
        const openingEnd = opening.end || {};
        const centerX = Number.isFinite(Number(openingEnd.x))
          ? (Number(openingStart.x || 0) + Number(openingEnd.x || 0)) / 2
          : Number(openingStart.x || 0);
        const centerZ = Number.isFinite(Number(openingEnd.z))
          ? (Number(openingStart.z || 0) + Number(openingEnd.z || 0)) / 2
          : Number(openingStart.z || 0);
        const measuredWidth = Math.hypot(
          Number(openingEnd.x || centerX) - Number(openingStart.x || centerX),
          Number(openingEnd.z || centerZ) - Number(openingStart.z || centerZ),
        );
        const width = Math.max(
          Number(opening.width_cm || opening.width || opening.leafWidthCm || measuredWidth) || 80,
          68,
        );
        const openingProjection = (
          (centerX - Number(start.x)) * dx
          + (centerZ - Number(start.z)) * dz
        ) / lengthSquared;
        const alongDistance = Math.abs(projection - openingProjection) * Math.sqrt(lengthSquared);
        return alongDistance <= Math.max(12, width / 2 - clearanceCm * 0.35);
      });
      if (insideDoorOpening) return false;
      return Math.hypot(position.x - closestX, position.z - closestZ) < clearanceCm;
    });
  }

  function walkPositionBlockedByFurniture(position, clearanceCm = 17) {
    return furnitureGroup.children.some((wrapper) => {
      const item = wrapper.userData.sceneObject;
      if (!item) return false;
      const size = sizeCentimeters(item);
      const radians = THREE.MathUtils.degToRad(
        normalizedRotationDeg(item.rotation_y_deg || 0),
      );
      const halfWidth = (
        Math.abs(Math.cos(radians)) * size.width
        + Math.abs(Math.sin(radians)) * size.depth
      ) / 2;
      const halfDepth = (
        Math.abs(Math.sin(radians)) * size.width
        + Math.abs(Math.cos(radians)) * size.depth
      ) / 2;
      return (
        Math.abs(position.x - wrapper.position.x) < halfWidth + clearanceCm
        && Math.abs(position.z - wrapper.position.z) < halfDepth + clearanceCm
      );
    });
  }

  function beginWalkLook(event) {
    if (
      viewMode.mode !== "walk"
      || interactionMode !== "walk"
      || event.button !== 0
      || dragState
      || placementRequest
    ) return;
    pointerToNdc(event);
    walkDestination = null;
    walkMarker.visible = false;
    const direction = controls.target.clone().sub(perspectiveCamera.position).normalize();
    walkLookState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      anchorPosition: perspectiveCamera.position.clone(),
      yaw: Math.atan2(direction.x, -direction.z),
      pitch: Math.asin(THREE.MathUtils.clamp(direction.y, -1, 1)),
      dragged: false,
    };
    renderer.domElement.setPointerCapture?.(event.pointerId);
    renderer.domElement.style.cursor = "grabbing";
  }

  function updateWalkLook(event) {
    if (!walkLookState || event.pointerId !== walkLookState.pointerId) return;
    perspectiveCamera.position.copy(walkLookState.anchorPosition);
    const deltaX = event.clientX - walkLookState.startX;
    const deltaY = event.clientY - walkLookState.startY;
    if (Math.hypot(deltaX, deltaY) > 5) walkLookState.dragged = true;
    if (!walkLookState.dragged) return;
    const yaw = walkLookState.yaw - deltaX * 0.005;
    const pitch = THREE.MathUtils.clamp(
      walkLookState.pitch - deltaY * 0.004,
      -WALK_MAX_PITCH_RAD,
      WALK_MAX_PITCH_RAD,
    );
    const cosPitch = Math.cos(pitch);
    const direction = new THREE.Vector3(
      Math.sin(yaw) * cosPitch,
      Math.sin(pitch),
      -Math.cos(yaw) * cosPitch,
    );
    controls.target.copy(perspectiveCamera.position).addScaledVector(direction, 200);
  }

  function finishWalkLook(event) {
    if (!walkLookState || event.pointerId !== walkLookState.pointerId) return;
    const wasDragged = walkLookState.dragged;
    perspectiveCamera.position.copy(walkLookState.anchorPosition);
    walkLookState = null;
    renderer.domElement.releasePointerCapture?.(event.pointerId);
    renderer.domElement.style.cursor = "grab";
    if (!wasDragged) setWalkDestinationFromPointer(event);
  }

  function wrapperFromObject(object) {
    let node = object;
    while (node && node.parent !== furnitureGroup) node = node.parent;
    return node;
  }

  function sizeCentimeters(item) {
    const size = item?.size_cm || {};
    return {
      width: Number(size.width) || 120,
      depth: Number(size.depth) || 60,
      height: Number(size.height) || 80,
    };
  }

  function topdownPointerDeltaCm(event, startEvent) {
    if (!startEvent || viewMode.mode !== "topdown" || camera !== orthographicCamera) return null;
    const rect = renderer.domElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const worldWidth = (orthographicCamera.right - orthographicCamera.left) / orthographicCamera.zoom;
    const worldHeight = (orthographicCamera.top - orthographicCamera.bottom) / orthographicCamera.zoom;
    return {
      x: ((event.clientX - startEvent.clientX) / rect.width) * worldWidth,
      z: ((event.clientY - startEvent.clientY) / rect.height) * worldHeight,
    };
  }

  const pickLocal = new THREE.Vector3();
  const FLOOR_OVERLAY_TYPES = new Set(["large-medium-rug", "runner-small-rug"]);

  function isFloorOverlayItem(item) {
    const type = String(item?.normalized_type || "");
    if (FLOOR_OVERLAY_TYPES.has(type) || type.includes("rug")) return true;
    const height = Number(item?.size_cm?.height);
    return Number.isFinite(height) && height > 0 && height <= 5;
  }

  function pointInFurnitureFootprint(wrapper, x, z, padCm = 12) {
    const item = wrapper?.userData?.sceneObject;
    if (!item) return false;
    const size = sizeCentimeters(item);
    const radians = THREE.MathUtils.degToRad(sceneToWorldRotationDeg(item.rotation_y_deg || 0));
    const dx = x - wrapper.position.x;
    const dz = z - wrapper.position.z;
    const localX = dx * Math.cos(radians) + dz * Math.sin(radians);
    const localZ = -dx * Math.sin(radians) + dz * Math.cos(radians);
    return Math.abs(localX) <= size.width / 2 + padCm
      && Math.abs(localZ) <= size.depth / 2 + padCm;
  }

  function addFurniturePickProxy(wrapper, item) {
    const size = sizeCentimeters(item);
    const pickHeight = Math.max(size.height, isFloorOverlayItem(item) ? 16 : 10);
    const proxy = new THREE.Mesh(
      new THREE.BoxGeometry(
        Math.max(size.width, 20),
        pickHeight,
        Math.max(size.depth, 20),
      ),
      new THREE.MeshBasicMaterial({
        transparent: true,
        opacity: 0,
        depthWrite: false,
        depthTest: false,
        toneMapped: false,
      }),
    );
    proxy.position.y = pickHeight / 2;
    proxy.frustumCulled = false;
    proxy.userData.roompilotPickProxy = true;
    wrapper.add(proxy);
    return proxy;
  }

  function pickFurnitureWrapper() {
    const hits = dragRaycaster.intersectObjects(furnitureGroup.children, true);
    const proxyHits = [];
    for (const hit of hits) {
      if (!hit.object.userData?.roompilotPickProxy) continue;
      const wrapper = wrapperFromObject(hit.object);
      const item = wrapper?.userData?.sceneObject;
      if (!item) continue;
      proxyHits.push({
        wrapper,
        item,
        distance: hit.distance,
        overlay: isFloorOverlayItem(item),
      });
    }
    if (proxyHits.length) {
      proxyHits.sort((a, b) => a.distance - b.distance);
      const closest = proxyHits[0];
      const near = proxyHits.filter((candidate) => candidate.distance <= closest.distance + 40);
      if (near.length > 1) {
        near.sort((left, right) => {
          const leftHeight = sizeCentimeters(left.item).height;
          const rightHeight = sizeCentimeters(right.item).height;
          return leftHeight - rightHeight || left.distance - right.distance;
        });
        const shortest = near[0];
        const closestHeight = sizeCentimeters(closest.item).height;
        const shortestHeight = sizeCentimeters(shortest.item).height;
        if (
          shortest.overlay
          || shortestHeight <= 15
          || shortestHeight < closestHeight * 0.55
        ) {
          return shortest.wrapper;
        }
      }
      return closest.wrapper;
    }

    if (!dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) return null;
    let best = null;
    let bestHeight = Infinity;
    let bestDist = Infinity;
    for (const wrapper of furnitureGroup.children) {
      const item = wrapper.userData?.sceneObject;
      if (!item) continue;
      if (!pointInFurnitureFootprint(wrapper, planeHit.x, planeHit.z)) continue;
      const height = sizeCentimeters(item).height;
      const dist = Math.hypot(planeHit.x - wrapper.position.x, planeHit.z - wrapper.position.z);
      if (
        height < bestHeight - 0.5
        || (Math.abs(height - bestHeight) <= 0.5 && dist < bestDist)
      ) {
        best = wrapper;
        bestHeight = height;
        bestDist = dist;
      }
    }
    return best;
  }

  function disposeGuide() {
    if (!footprintGuide) return;
    scene.remove(footprintGuide);
    footprintGuide.traverse((object) => {
      object.geometry?.dispose?.();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => material.dispose?.());
    });
    footprintGuide = null;
    snapHint = null;
  }

  function createSnapHintSprite() {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    context.fillStyle = "rgba(35, 67, 45, 0.92)";
    if (context.roundRect) {
      context.beginPath();
      context.roundRect(12, 18, 232, 60, 22);
      context.fill();
      if (false)
      setStatus(`已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`);
      if (false)
      setStatus(`已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`);
    } else {
      context.fillRect(12, 18, 232, 60);
    }
    context.fillStyle = "#f4fff4";
    context.font = "bold 28px 'Segoe UI', 'Noto Sans TC', sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText("已吸附牆面", 128, 50);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(90, 34, 1);
    sprite.renderOrder = 1001;
    sprite.visible = false;
    return sprite;
  }

  function ensureFootprintGuide() {
    if (footprintGuide) return footprintGuide;

    footprintGuide = new THREE.Group();
    footprintGuide.visible = false;
    footprintGuide.renderOrder = 1000;

    const fill = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({
        color: 0x7ca7ff,
        transparent: true,
        opacity: 0.26,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
    );
    fill.rotation.x = -Math.PI / 2;
    fill.userData.guidePart = "fill";

    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(1, 1)),
      new THREE.LineBasicMaterial({
        color: 0x2f6df6,
        transparent: true,
        opacity: 0.95,
        depthTest: false,
      })
    );
    outline.rotation.x = -Math.PI / 2;
    outline.userData.guidePart = "outline";

    const crosshairGeometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-0.5, 0, 0),
      new THREE.Vector3(0.5, 0, 0),
      new THREE.Vector3(0, -0.5, 0),
      new THREE.Vector3(0, 0.5, 0),
    ]);
    const crosshair = new THREE.LineSegments(
      crosshairGeometry,
      new THREE.LineBasicMaterial({
        color: 0x2f6df6,
        transparent: true,
        opacity: 0.62,
        depthTest: false,
      })
    );
    crosshair.rotation.x = -Math.PI / 2;
    crosshair.position.y = 0.6;
    crosshair.userData.guidePart = "crosshair";

    snapHint = createSnapHintSprite();
    footprintGuide.add(fill, outline, crosshair, snapHint);
    scene.add(footprintGuide);
    return footprintGuide;
  }

  function setGuideSnapState(kind = null) {
    const guide = ensureFootprintGuide();
    const snapped = kind === "wall" || kind === "corner";
    const blocked = kind === "blocked";
    guide.children.forEach((child) => {
      if (child.userData.guidePart === "fill") {
        child.material.color.set(blocked ? 0xff8f7f : snapped ? 0x8ed49a : 0x7ca7ff);
        child.material.opacity = blocked ? 0.32 : snapped ? 0.28 : 0.2;
      }
      if (child.userData.guidePart === "outline") {
        child.material.color.set(blocked ? 0xe15b47 : snapped ? 0x299b4a : 0x2f6df6);
      }
      if (child.userData.guidePart === "crosshair") {
        child.material.color.set(blocked ? 0xe15b47 : snapped ? 0x299b4a : 0x2f6df6);
        child.material.opacity = blocked ? 0.82 : snapped ? 0.78 : 0.62;
      }
    });
    if (snapHint) snapHint.visible = snapped;
  }

  function updateFootprintGuide(wrapper, kind = null) {
    if (!wrapper?.userData?.sceneObject) {
      disposeGuide();
      return;
    }
    const guide = ensureFootprintGuide();
    const item = wrapper.userData.sceneObject;
    const size = sizeCentimeters(item);
    guide.visible = true;
    guide.position.set(wrapper.position.x, 3.2, wrapper.position.z);
    guide.rotation.y = wrapper.rotation.y;
    guide.children.forEach((child) => {
      if (child.userData.guidePart === "fill" || child.userData.guidePart === "outline" || child.userData.guidePart === "crosshair") {
        child.scale.set(size.width, size.depth, 1);
      }
    });
    if (snapHint) {
      snapHint.position.set(0, 6, -size.depth / 2 - 18);
    }
    setGuideSnapState(kind);
  }

  function selectWrapper(wrapper, kind = null, { notify = true } = {}) {
    selectedWrapper = wrapper || null;
    if (selectedWrapper) {
      updateFootprintGuide(selectedWrapper, kind);
      renderer.domElement.style.cursor = "grab";
      selectedControls.hidden = false;
      updateSelectedControlsState();
    } else {
      disposeGuide();
      renderer.domElement.style.cursor = "";
      selectedControls.hidden = true;
    }
    if (notify && typeof onObjectSelect === "function") {
      onObjectSelect(selectedWrapper?.userData?.sceneObject || null, lastSceneData);
    }
  }

  function updateSelectedControlsState() {
    const lockButton = selectedControls.querySelector("[data-object-lock]");
    if (!lockButton) return;
    const item = selectedWrapper?.userData?.sceneObject;
    const locked = item?.user_specified === true || item?.model_locked === true;
    lockButton.textContent = locked ? "取消鎖定此家具" : "鎖定此家具";
    lockButton.classList.toggle("is-active", locked);
    lockButton.setAttribute(
      "aria-pressed",
      locked ? "true" : "false",
    );
  }

  function toggleSelectedObjectLock() {
    if (!selectedWrapper) return false;
    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;
    const locked = item.user_specified === true || item.model_locked === true;
    item.user_specified = !locked;
    item.user_required = !locked;
    item.model_locked = !locked;
    if (!locked) item.position_locked = true;
    updateSelectedControlsState();
    notifySceneChange(item);
    const label = item.name_zh || item.name_zh_raw || item.normalized_type || "家具";
    setStatus(!locked
      ? `已鎖定「${label}」為指定需求。`
      : `已取消「${label}」的指定需求鎖定。`);
    return true;
  }

  function selectObjectByIndex(index, { focus = true, showGuide = true } = {}) {
    const sceneIndex = Number(index) + 1;
    const wrapper = furnitureGroup.children.find(
      (candidate) => candidate.userData.sceneIndex === sceneIndex,
    );
    if (!wrapper) return false;
    if (showGuide) selectWrapper(wrapper, null, { notify: false });
    else selectWrapper(null, null, { notify: false });
    if (focus) focusObject(wrapper);
    return true;
  }

  async function validatePlacement(item, positionCm, rotationDeg) {
    if (!lastSceneData) return { ok: false, reason: "場景未載入" };
    try {
      const response = await fetch("/api/scene/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan: lastSceneData.floorplan || null,
          item: { ...item, position_cm: positionCm, rotation_y_deg: rotationDeg },
          others: (lastSceneData.scene_objects || []).filter((other) => other !== item),
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("擺放驗證失敗", error);
      return { ok: false, reason: "驗證服務未回應" };
    }
  }

  renderer.domElement.addEventListener("contextmenu", (event) => {
    // 右鍵按在家具上時是拖曳,不要跳出瀏覽器選單
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    if (pickFurnitureWrapper()) {
      event.preventDefault();
    }
  });

  renderer.domElement.addEventListener("pointerdown", (event) => {
    if ((event.button !== 0 && event.button !== 2) || !lastSceneData || dragState) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    if (beamPlacementRequest && event.button === 0) {
      if (dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
        const point = { x: planeHit.x, z: planeHit.z };
        beamPlacementRequest.points.push(point);
        if (beamPlacementRequest.points.length === 1) {
          setStatus("已設定樑起點，請在室內點選終點；樑會固定於天花板下方。");
        } else {
          const start = beamPlacementRequest.points[0];
          const rawEnd = beamPlacementRequest.points[1];
          const dx = rawEnd.x - start.x;
          const dz = rawEnd.z - start.z;
          const end = Math.abs(dx) >= Math.abs(dz)
            ? { x: rawEnd.x, z: start.z }
            : { x: start.x, z: rawEnd.z };
          const callback = beamPlacementRequest.callback;
          beamPlacementRequest = null;
          renderer.domElement.style.cursor = "";
          callback({
            start: worldToScenePosition(start),
            end: worldToScenePosition(end),
          });
        }
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (placementRequest && event.button === 0) {
      const callback = placementRequest;
      placementRequest = null;
      renderer.domElement.style.cursor = "";
      if (dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
        callback(worldToScenePosition(planeHit));
      } else {
        setStatus("沒有點到可擺放的地板，請重新選擇「新增到 3D」。");
      }
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (interactionMode === "walk") {
      selectWrapper(null);
      return;
    }
    const wrapper = pickFurnitureWrapper();
    if (!wrapper) {
      selectWrapper(null);
      return;
    }
    if (!wrapper || !wrapper.userData.sceneObject) return;

    selectWrapper(wrapper);
    if (interactionMode !== "edit") {
      setStatus("已選取家具；請切換至「編輯家具」模式再拖曳。");
      return;
    }
    dragRaycaster.ray.intersectPlane(floorPlane, planeHit);
    dragState = {
      wrapper,
      item: wrapper.userData.sceneObject,
      startPosition: wrapper.position.clone(),
      startEvent: { clientX: event.clientX, clientY: event.clientY },
      startRotationDeg: sceneToWorldRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
      pendingRotationDeg: sceneToWorldRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
      grabOffset: planeHit.clone().sub(wrapper.position),
      lastValid: {
        x: wrapper.position.x,
        z: wrapper.position.z,
        rotationDeg: sceneToWorldRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
        kind: "grid",
      },
      materials: [],
    };
    wrapper.traverse((node) => {
      if (!node.isMesh && !node.isSprite) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach((material) => {
        dragState.materials.push({ material, opacity: material.opacity, transparent: material.transparent });
        material.transparent = true;
        material.opacity = 0.6;
      });
    });
    controls.enabled = false;  // OrbitControls 的 move handler 會檢查 enabled,拖家具時不轉鏡頭
    renderer.domElement.style.cursor = "grabbing";
  });

  // 房間邊界是室內完成面；靠牆家具不額外留縫，其他移動使用 5 cm 格點。
  const SNAP_RANGE = 30;
  const WALL_GAP = 0;
  const DRAG_GRID = 5;

  function normalizedRotationDeg(rotationDeg = 0) {
    return ((Math.round(rotationDeg / 90) * 90) % 360 + 360) % 360;
  }

  function halfExtentsForRotation(item, rotationDeg = 0) {
    const size = sizeCentimeters(item);
    const radians = (Math.abs(normalizedRotationDeg(rotationDeg) % 180) * Math.PI) / 180;
    return {
      x: (size.width * Math.abs(Math.cos(radians)) + size.depth * Math.abs(Math.sin(radians))) / 2,
      z: (size.width * Math.abs(Math.sin(radians)) + size.depth * Math.abs(Math.cos(radians))) / 2,
    };
  }

  function roomBounds() {
    const floorplan = lastWorldSceneData?.floorplan || {};
    const widthCm = Math.max(Number(floorplan.width_cm) || 420, 240);
    const depthCm = Math.max(Number(floorplan.depth_cm) || 360, 240);
    return {
      minX: -widthCm / 2,
      maxX: widthCm / 2,
      minZ: -depthCm / 2,
      maxZ: depthCm / 2,
      widthCm,
      depthCm,
    };
  }

  function clampTransformToRoom(item, x, z, rotationDeg) {
    const bounds = roomBounds();
    const half = halfExtentsForRotation(item, rotationDeg);
    const safeGap = WALL_GAP;
    const minX = bounds.minX + half.x + safeGap;
    const maxX = bounds.maxX - half.x - safeGap;
    const minZ = bounds.minZ + half.z + safeGap;
    const maxZ = bounds.maxZ - half.z - safeGap;

    return {
      x: minX > maxX ? 0 : THREE.MathUtils.clamp(x, minX, maxX),
      z: minZ > maxZ ? 0 : THREE.MathUtils.clamp(z, minZ, maxZ),
    };
  }

  function footprintCorners(item, x, z, rotationDeg) {
    const size = sizeCentimeters(item);
    const hw = size.width / 2;
    const hd = size.depth / 2;
    const radians = THREE.MathUtils.degToRad(normalizedRotationDeg(rotationDeg));
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);

    return [
      { x: -hw, z: -hd },
      { x: hw, z: -hd },
      { x: hw, z: hd },
      { x: -hw, z: hd },
    ].map((point) => ({
      x: x + point.x * cos + point.z * sin,
      z: z - point.x * sin + point.z * cos,
    }));
  }

  function ccw(a, b, c) {
    return (c.z - a.z) * (b.x - a.x) > (b.z - a.z) * (c.x - a.x);
  }

  function segmentsIntersect(a, b, c, d) {
    return ccw(a, c, d) !== ccw(b, c, d) && ccw(a, b, c) !== ccw(a, b, d);
  }

  function pointSegmentDistance(point, a, b) {
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const lengthSq = dx * dx + dz * dz;
    if (lengthSq < 0.01) return Math.hypot(point.x - a.x, point.z - a.z);
    const t = Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.z - a.z) * dz) / lengthSq));
    return Math.hypot(point.x - (a.x + dx * t), point.z - (a.z + dz * t));
  }

  function segmentToSegmentDistance(a, b, c, d) {
    if (segmentsIntersect(a, b, c, d)) return 0;
    return Math.min(
      pointSegmentDistance(a, c, d),
      pointSegmentDistance(b, c, d),
      pointSegmentDistance(c, a, b),
      pointSegmentDistance(d, a, b)
    );
  }

  function isOuterBoundarySegment(seg) {
    const bounds = roomBounds();
    const ax = Number(seg.start?.x);
    const az = Number(seg.start?.z);
    const bx = Number(seg.end?.x);
    const bz = Number(seg.end?.z);
    const eps = 8;
    const onLeft = Math.abs(ax - bounds.minX) < eps && Math.abs(bx - bounds.minX) < eps;
    const onRight = Math.abs(ax - bounds.maxX) < eps && Math.abs(bx - bounds.maxX) < eps;
    const onBack = Math.abs(az - bounds.minZ) < eps && Math.abs(bz - bounds.minZ) < eps;
    const onFront = Math.abs(az - bounds.maxZ) < eps && Math.abs(bz - bounds.maxZ) < eps;
    return onLeft || onRight || onBack || onFront;
  }

  function transformHitsWall(item, x, z, rotationDeg) {
    const corners = footprintCorners(item, x, z, rotationDeg);
    const edges = corners.map((point, index) => [point, corners[(index + 1) % corners.length]]);
    for (const seg of wallSegmentsForSnap()) {
      if (isOuterBoundarySegment(seg)) continue;
      const a = { x: Number(seg.start?.x), z: Number(seg.start?.z) };
      const b = { x: Number(seg.end?.x), z: Number(seg.end?.z) };
      if (![a.x, a.z, b.x, b.z].every(Number.isFinite)) continue;
      if (edges.some(([c, d]) => segmentToSegmentDistance(a, b, c, d) < 5)) return true;
    }
    return false;
  }

  function constrainTransform(item, x, z, rotationDeg, fallback = null) {
    const clamped = clampTransformToRoom(item, x, z, rotationDeg);
    const allowed = !transformHitsWall(item, clamped.x, clamped.z, rotationDeg);
    if (!allowed && fallback) {
      return { ...fallback, kind: "blocked", blocked: true };
    }
    return {
      x: clamped.x,
      z: clamped.z,
      rotationDeg: normalizedRotationDeg(rotationDeg),
      kind: allowed ? "grid" : "blocked",
      blocked: !allowed,
    };
  }

  function wallSegmentsForSnap() {
    const floorplan = lastWorldSceneData?.floorplan || {};
    const segments = floorplan.wall_segments || [];
    if (segments.length) return segments;
    // 手動矩形模式沒有牆段資料,用房間四邊當虛擬牆
    const widthCm = Math.max(Number(floorplan.width_cm) || 420, 240);
    const depthCm = Math.max(Number(floorplan.depth_cm) || 360, 240);
    const hw = widthCm / 2;
    const hd = depthCm / 2;
    return [
      { start: { x: -hw, z: -hd }, end: { x: hw, z: -hd } },
      { start: { x: hw, z: -hd }, end: { x: hw, z: hd } },
      { start: { x: hw, z: hd }, end: { x: -hw, z: hd } },
      { start: { x: -hw, z: hd }, end: { x: -hw, z: -hd } },
    ];
  }

  function snapDragPosition(item, x, z) {
    const size = sizeCentimeters(item);
    const radians = (Math.abs((item.rotation_y_deg || 0) % 180) * Math.PI) / 180;
    const w = size.width;
    const d = size.depth;
    const halfW = (w * Math.abs(Math.cos(radians)) + d * Math.abs(Math.sin(radians))) / 2;
    const halfD = (w * Math.abs(Math.sin(radians)) + d * Math.abs(Math.cos(radians))) / 2;

    let bestX = null;
    let bestZ = null;
    for (const seg of wallSegmentsForSnap()) {
      const isVertical = Math.abs(seg.start.x - seg.end.x) < 2;   // 沿 z 的牆
      const isHorizontal = Math.abs(seg.start.z - seg.end.z) < 2; // 沿 x 的牆
      if (isVertical) {
        const zLo = Math.min(seg.start.z, seg.end.z);
        const zHi = Math.max(seg.start.z, seg.end.z);
        if (z < zLo - halfD || z > zHi + halfD) continue;  // 沒對到這段牆的側向範圍
        for (const candidate of [seg.start.x + halfW + WALL_GAP, seg.start.x - halfW - WALL_GAP]) {
          const dist = Math.abs(x - candidate);
          if (dist < SNAP_RANGE && (!bestX || dist < bestX.dist)) bestX = { value: candidate, dist };
        }
      } else if (isHorizontal) {
        const xLo = Math.min(seg.start.x, seg.end.x);
        const xHi = Math.max(seg.start.x, seg.end.x);
        if (x < xLo - halfW || x > xHi + halfW) continue;
        for (const candidate of [seg.start.z + halfD + WALL_GAP, seg.start.z - halfD - WALL_GAP]) {
          const dist = Math.abs(z - candidate);
          if (dist < SNAP_RANGE && (!bestZ || dist < bestZ.dist)) bestZ = { value: candidate, dist };
        }
      }
    }

    const snapKind = bestX || bestZ ? "wall" : "grid";
    return {
      x: bestX ? bestX.value : Math.round(x / DRAG_GRID) * DRAG_GRID,
      z: bestZ ? bestZ.value : Math.round(z / DRAG_GRID) * DRAG_GRID,
      kind: snapKind,
    };
  }

  function snapDragPositionV2(item, x, z) {
    let bestX = null;
    let bestZ = null;
    for (const seg of wallSegmentsForSnap()) {
      const isVertical = Math.abs(seg.start.x - seg.end.x) < 2;
      const isHorizontal = Math.abs(seg.start.z - seg.end.z) < 2;
      if (isVertical) {
        const wallRotationDeg = 90;
        const half = halfExtentsForRotation(item, wallRotationDeg);
        const zLo = Math.min(seg.start.z, seg.end.z);
        const zHi = Math.max(seg.start.z, seg.end.z);
        if (z < zLo - half.z || z > zHi + half.z) continue;
        for (const candidate of [seg.start.x + half.x + WALL_GAP, seg.start.x - half.x - WALL_GAP]) {
          const dist = Math.abs(x - candidate);
          if (dist < SNAP_RANGE && (!bestX || dist < bestX.dist)) {
            bestX = { value: candidate, dist, rotationDeg: wallRotationDeg };
          }
        }
      } else if (isHorizontal) {
        const wallRotationDeg = 0;
        const half = halfExtentsForRotation(item, wallRotationDeg);
        const xLo = Math.min(seg.start.x, seg.end.x);
        const xHi = Math.max(seg.start.x, seg.end.x);
        if (x < xLo - half.x || x > xHi + half.x) continue;
        for (const candidate of [seg.start.z + half.z + WALL_GAP, seg.start.z - half.z - WALL_GAP]) {
          const dist = Math.abs(z - candidate);
          if (dist < SNAP_RANGE && (!bestZ || dist < bestZ.dist)) {
            bestZ = { value: candidate, dist, rotationDeg: wallRotationDeg };
          }
        }
      }
    }

    const snapKind = bestX && bestZ ? "corner" : bestX || bestZ ? "wall" : "grid";
    const rotationSource = bestX && bestZ
      ? (bestX.dist <= bestZ.dist ? bestX : bestZ)
      : (bestX || bestZ);
    return {
      x: bestX ? bestX.value : Math.round(x / DRAG_GRID) * DRAG_GRID,
      z: bestZ ? bestZ.value : Math.round(z / DRAG_GRID) * DRAG_GRID,
      kind: snapKind,
      rotationDeg: rotationSource ? rotationSource.rotationDeg : sceneToWorldRotationDeg(item.rotation_y_deg || 0),
    };
  }

  function snapDragPositionV3(item, x, z) {
    const snapped = snapFurnitureToRoomSurface({
      floorplan: lastWorldSceneData?.floorplan || {},
      roomId: item.placement_room_id || item.room_id || item.roomId || "",
      sizeCm: sizeCentimeters(item),
      position: { x, z },
      rotationDeg: sceneToWorldRotationDeg(item.rotation_y_deg || 0),
      snapRangeCm: SNAP_RANGE,
      gridCm: DRAG_GRID,
    }) || snapDragPositionV2(item, x, z);
    const constrained = constrainTransform(
      item,
      snapped.x,
      snapped.z,
      snapped.rotationDeg ?? sceneToWorldRotationDeg(item.rotation_y_deg || 0)
    );
    return constrained;
  }

  window.addEventListener("pointermove", (event) => {
    if (!dragState) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    const topdownDelta = topdownPointerDeltaCm(event, dragState.startEvent);
    const target = topdownDelta
      ? {
          x: dragState.startPosition.x + topdownDelta.x,
          z: dragState.startPosition.z + topdownDelta.z,
        }
      : null;
    if (target || dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
      const snapped = snapDragPositionV3(
        dragState.item,
        target ? target.x : planeHit.x - dragState.grabOffset.x,
        target ? target.z : planeHit.z - dragState.grabOffset.z
      );
      const nextTransform = snapped.blocked ? dragState.lastValid : snapped;
      dragState.wrapper.position.x = nextTransform.x;
      dragState.wrapper.position.z = nextTransform.z;
      dragState.pendingRotationDeg = nextTransform.rotationDeg;
      dragState.wrapper.rotation.y = THREE.MathUtils.degToRad(nextTransform.rotationDeg);
      if (!snapped.blocked) dragState.lastValid = { ...nextTransform };
      updateFootprintGuide(dragState.wrapper, snapped.blocked ? "blocked" : nextTransform.kind);
      if (false)
      setStatus(`無法移動「${label}」：${verdict.reason || "位置不符合限制"}，已復原。`);
    }
  });

  window.addEventListener("pointerup", async () => {
    if (!dragState) return;
    const { wrapper, item, startPosition, startRotationDeg, pendingRotationDeg, materials } = dragState;
    dragState = null;
    materials.forEach(({ material, opacity, transparent }) => {
      material.opacity = opacity;
      material.transparent = transparent;
    });
    controls.enabled = true;
    if (cameraLocked) {
      controls.enableRotate = false;
      controls.enablePan = false;
      controls.enableZoom = true;
    }
    renderer.domElement.style.cursor = selectedWrapper ? "grab" : "";

    const movedCm = Math.hypot(wrapper.position.x - startPosition.x, wrapper.position.z - startPosition.z);
    const rotated = normalizedRotationDeg(pendingRotationDeg) !== normalizedRotationDeg(startRotationDeg);
    if (movedCm < 1 && !rotated) return;  // 只是點選,沒有拖

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const newPositionCm = worldToScenePosition(wrapper.position);
    const newRotationDeg = worldToSceneRotationDeg(pendingRotationDeg);
    setStatus(`正在檢查「${label}」的新位置...`);
    const verdict = await validatePlacement(item, newPositionCm, newRotationDeg);
    if (verdict.ok) {
      item.position_cm = newPositionCm;
      item.rotation_y_deg = newRotationDeg;
      const worldPosition = sceneToWorldPosition(item.position_cm || {});
      wrapper.position.x = worldPosition.x;
      wrapper.position.z = worldPosition.z;
      wrapper.rotation.y = THREE.MathUtils.degToRad(sceneToWorldRotationDeg(item.rotation_y_deg || 0));
      updateFootprintGuide(wrapper);
      setStatus(`已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`);
      item.position_locked = true;  // 之後的重排/替換不會沖掉手動位置
      notifySceneChange(item);
      setStatus(`已移動「${label}」。`);
    } else {
      wrapper.position.copy(startPosition);
      wrapper.rotation.y = THREE.MathUtils.degToRad(startRotationDeg);
      updateFootprintGuide(wrapper);
      setStatus(`⚠ 「${label}」無法放在那裡：${verdict.reason || "位置不合法"}，已彈回原位。`);
    }
    setStatus(verdict.ok
      ? `已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`
      : `無法移動「${label}」：${verdict.reason || "位置不符合限制"}，已復原。`);
  });

  async function rotateSelected(deltaDeg = 90) {
    if (!selectedWrapper || dragState) return false;
    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const nextRotation = ((item.rotation_y_deg || 0) + deltaDeg + 360) % 360;
    const verdict = await validatePlacement(item, item.position_cm || { x: 0, z: 0 }, nextRotation);
    if (verdict.ok) {
      item.rotation_y_deg = nextRotation;
      item.position_locked = true;
      selectedWrapper.rotation.y = THREE.MathUtils.degToRad(sceneToWorldRotationDeg(nextRotation));
      updateFootprintGuide(selectedWrapper);
      notifySceneChange(item);
      setStatus(`${label} 已旋轉到 ${nextRotation} 度。`);
      return true;
    }

    setStatus(`${label} 目前不能旋轉：${verdict.reason || "會碰撞或超出可用空間"}。`);
    return false;
  }

  function wrapperPositionCm(wrapper) {
    return worldToScenePosition(wrapper.position);
  }

  async function rotateSelectedManual(deltaDeg = 90) {
    if (!selectedWrapper) {
      setStatus("請先點選要旋轉的家具。");
      return false;
    }
    if (dragState) return false;

    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const nextRotation = normalizedRotationDeg((item.rotation_y_deg || 0) + deltaDeg);
    const nextWorldRotation = sceneToWorldRotationDeg(nextRotation);
    const currentPositionCm = wrapperPositionCm(selectedWrapper);
    const candidate = constrainTransform(item, selectedWrapper.position.x, selectedWrapper.position.z, nextWorldRotation);
    if (candidate.blocked) {
      setStatus(`「${label}」旋轉後會超出房間或碰到牆，已取消。`);
      return false;
    }
    const precheck = await validatePlacement(item, currentPositionCm, nextRotation);
    if (!precheck.ok) {
      setStatus(`「${label}」不能旋轉：${precheck.reason || "會超出房間、穿牆或碰撞"}。`);
      return false;
    }

    item.rotation_y_deg = nextRotation;
    item.position_cm = currentPositionCm;
    item.position_locked = true;
    selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextWorldRotation);
    updateFootprintGuide(selectedWrapper);
    notifySceneChange(item);
    setStatus(`已旋轉「${label}」到 ${nextRotation}°。`);

    const verdict = await validatePlacement(item, currentPositionCm, nextRotation);
    if (!verdict.ok) {
      setStatus(`已旋轉「${label}」，但請注意：${verdict.reason || "目前位置可能不符合擺放限制"}。`);
    }
    return true;
  }

  async function moveSelectedBy(direction) {
    if (!selectedWrapper || dragState) {
      setStatus("請先點選一件家具。");
      return false;
    }

    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const step = 10;
    const delta = {
      forward: { x: 0, z: -step },
      back: { x: 0, z: step },
      left: { x: -step, z: 0 },
      right: { x: step, z: 0 },
    }[direction];
    if (!delta) return false;

    const rotationDeg = normalizedRotationDeg(item.rotation_y_deg || 0);
    const worldRotationDeg = sceneToWorldRotationDeg(rotationDeg);
    const candidate = constrainTransform(
      item,
      selectedWrapper.position.x + delta.x,
      selectedWrapper.position.z + delta.z,
      worldRotationDeg,
      { x: selectedWrapper.position.x, z: selectedWrapper.position.z, rotationDeg: worldRotationDeg, kind: "blocked" }
    );

    if (candidate.blocked) {
      setStatus(`「${label}」不能往那個方向移動，會超出房間或碰到牆。`);
      updateFootprintGuide(selectedWrapper, "blocked");
      return false;
    }

    const nextPositionCm = {
      x: Math.round(candidate.x * 100) / 100,
      z: Math.round(candidate.z * 100) / 100,
    };
    const verdict = await validatePlacement(item, nextPositionCm, rotationDeg);
    if (!verdict.ok) {
      setStatus(`「${label}」不能移到那裡：${verdict.reason || "會超出房間、穿牆或碰撞"}。`);
      updateFootprintGuide(selectedWrapper, "blocked");
      return false;
    }

    selectedWrapper.position.set(candidate.x, selectedWrapper.position.y, candidate.z);
    item.position_cm = nextPositionCm;
    item.position_locked = true;
    updateFootprintGuide(selectedWrapper, candidate.kind);
    notifySceneChange(item);
    setStatus(`已微調「${label}」。`);
    return true;
  }

  function selectedObjectLabel(item) {
    return item?.name_zh_raw || item?.normalized_type || "家具";
  }

  function scenePositionCm(x, z) {
    return worldToScenePosition({ x, z });
  }

  async function rotateSelectedFromControls(deltaDeg = 15) {
    if (!selectedWrapper || dragState) {
      setStatus("請先點選一件家具。");
      return false;
    }

    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;
    const label = selectedObjectLabel(item);
    const currentWorldRotation = sceneToWorldRotationDeg(item.rotation_y_deg || 0);
    const nextWorldRotation = normalizedRotationDeg(currentWorldRotation + deltaDeg);
    const nextRotation = worldToSceneRotationDeg(nextWorldRotation);
    const candidate = constrainTransform(item, selectedWrapper.position.x, selectedWrapper.position.z, nextWorldRotation);
    if (candidate.blocked) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 旋轉後會碰牆或超出房間，已取消。`);
      return false;
    }

    const nextPositionCm = scenePositionCm(candidate.x, candidate.z);
    setStatus(`${label} 旋轉檢查中...`);
    const verdict = await validatePlacement(item, nextPositionCm, nextRotation);
    if (!verdict.ok) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 目前不能旋轉：${verdict.reason || "位置不合法"}。`);
      return false;
    }

    selectedWrapper.position.set(candidate.x, selectedWrapper.position.y, candidate.z);
    selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextWorldRotation);
    item.position_cm = nextPositionCm;
    item.rotation_y_deg = nextRotation;
    item.position_locked = true;
    updateFootprintGuide(selectedWrapper, candidate.kind);
    notifySceneChange(item);
    setStatus(`${label} 已旋轉到 ${nextRotation} 度。`);
    return true;
  }

  async function moveSelectedFromControls(direction) {
    if (!selectedWrapper || dragState) {
      setStatus("請先點選一件家具。");
      return false;
    }

    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;
    const label = selectedObjectLabel(item);
    const rotationDeg = normalizedRotationDeg(item.rotation_y_deg || 0);
    const worldRotationDeg = sceneToWorldRotationDeg(rotationDeg);
    const radians = THREE.MathUtils.degToRad(worldRotationDeg);
    const step = 25;
    const forward = { x: -Math.sin(radians), z: -Math.cos(radians) };
    const right = { x: Math.cos(radians), z: -Math.sin(radians) };
    const delta = {
      forward: { x: forward.x * step, z: forward.z * step },
      back: { x: -forward.x * step, z: -forward.z * step },
      left: { x: -right.x * step, z: -right.z * step },
      right: { x: right.x * step, z: right.z * step },
    }[direction];
    if (!delta) return false;

    const candidate = constrainTransform(
      item,
      selectedWrapper.position.x + delta.x,
      selectedWrapper.position.z + delta.z,
      worldRotationDeg,
      { x: selectedWrapper.position.x, z: selectedWrapper.position.z, rotationDeg: worldRotationDeg, kind: "blocked" }
    );
    if (candidate.blocked) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 不能往這個方向移動，會碰牆或超出房間。`);
      return false;
    }

    const nextPositionCm = scenePositionCm(candidate.x, candidate.z);
    setStatus(`${label} 移動檢查中...`);
    const verdict = await validatePlacement(item, nextPositionCm, rotationDeg);
    if (!verdict.ok) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 目前不能移動：${verdict.reason || "位置不合法"}。`);
      return false;
    }

    selectedWrapper.position.set(candidate.x, selectedWrapper.position.y, candidate.z);
    item.position_cm = nextPositionCm;
    item.position_locked = true;
    updateFootprintGuide(selectedWrapper, candidate.kind);
    notifySceneChange(item);
    setStatus(`${label} 已移動 ${Math.round(step)} 公分。`);
    return true;
  }

  selectedControls.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    const lockButton = event.target.closest("[data-object-lock]");
    if (lockButton) {
      toggleSelectedObjectLock();
      return;
    }
    const moveButton = event.target.closest("[data-object-move]");
    if (moveButton) {
      await moveSelectedFromControls(moveButton.dataset.objectMove);
      return;
    }
    const rotateButton = event.target.closest("[data-object-rotate]");
    if (rotateButton) {
      await rotateSelectedFromControls(Number(rotateButton.dataset.objectRotate) || 15);
    }
  });

  window.addEventListener("keydown", async (event) => {
    if (event.key !== "r" && event.key !== "R") return;
    const tag = event.target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    event.preventDefault();
    await rotateSelectedFromControls(event.shiftKey ? -15 : 15);
    return;
    if (!selectedWrapper || dragState) return;
    const item = selectedWrapper.userData.sceneObject;
    if (!item) return;

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const nextRotation = ((item.rotation_y_deg || 0) + 90) % 360;
    const verdict = await validatePlacement(item, item.position_cm || { x: 0, z: 0 }, nextRotation);
    if (verdict.ok) {
      item.rotation_y_deg = nextRotation;
      item.position_locked = true;
      selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextRotation);
      setStatus(`已旋轉「${label}」至 ${nextRotation}°。`);
    } else {
      setStatus(`⚠ 旋轉「${label}」會造成：${verdict.reason || "位置不合法"}，未套用。`);
    }
  });

  function updateWallVisibility() {
    wallMeshes.forEach((wall) => {
      wall.visible = true;
      const materials = Array.isArray(wall.material) ? wall.material : [wall.material];
      materials.filter(Boolean).forEach((material) => {
        material.transparent = false;
        material.opacity = wall.userData.baseOpacity || 1;
        material.depthWrite = true;
      });
    });
  }

  function onResize() {
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) return;
    perspectiveCamera.aspect = width / height;
    perspectiveCamera.updateProjectionMatrix();
    if (camera === orthographicCamera) {
      const vertical = orthographicCamera.top - orthographicCamera.bottom;
      orthographicCamera.left = -(vertical * width / height) / 2;
      orthographicCamera.right = (vertical * width / height) / 2;
      orthographicCamera.updateProjectionMatrix();
    }
    renderer.setSize(width, height);
    composer?.setSize(width, height);
  }

  function beginPlacement(callback) {
    if (typeof callback !== "function" || !lastSceneData) return false;
    placementRequest = callback;
    selectWrapper(null);
    renderer.domElement.style.cursor = "crosshair";
    setStatus("新增模式：請在 3D 地板上點選家具位置。");
    return true;
  }

  function cancelPlacement() {
    placementRequest = null;
    renderer.domElement.style.cursor = "";
  }

  function beginBeamPlacement(callback) {
    if (typeof callback !== "function" || !lastSceneData) return false;
    placementRequest = null;
    beamPlacementRequest = { callback, points: [] };
    selectWrapper(null);
    renderer.domElement.style.cursor = "crosshair";
    setStatus("請在室內點選樑的起點，再點選終點；系統會自動水平或垂直對齊。");
    return true;
  }

  function cancelBeamPlacement() {
    beamPlacementRequest = null;
    renderer.domElement.style.cursor = "";
  }

  renderer.domElement.addEventListener("pointerdown", beginWalkLook);
  window.addEventListener("pointermove", updateWalkLook);
  window.addEventListener("pointerup", finishWalkLook);
  renderer.domElement.addEventListener("wheel", (event) => {
    if (viewMode.mode !== "walk" || interactionMode !== "walk") return;
    event.preventDefault();
    perspectiveCamera.fov = THREE.MathUtils.clamp(
      perspectiveCamera.fov + Math.sign(event.deltaY) * 3,
      42,
      75,
    );
    perspectiveCamera.updateProjectionMatrix();
  }, { passive: false });

  window.addEventListener("resize", onResize);
  const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(onResize);
  resizeObserver?.observe(container);
  onResize();

  window.addEventListener("keydown", (event) => {
    if (viewMode.mode !== "walk") return;
    const tag = document.activeElement?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    event.preventDefault();
    walkKeys.add(event.key.toLowerCase());
  });
  window.addEventListener("keyup", (event) => walkKeys.delete(event.key.toLowerCase()));

  renderer.setAnimationLoop((time) => {
    // 隱藏面板與離屏縮圖臺（offsetParent === null）不必每幀渲染——
    // 七個 renderer 全速跑會把 GPU 撐到 context 遺失；capturePng 走
    // 顯式渲染不受影響，面板重新可見時自動恢復。
    if (container.offsetParent === null) return;
    updateWalkMovement();
    controls.update();
    updateWallVisibility();
    if (composer) composer.render();
    else renderer.render(scene, camera);
    if (performanceElement) {
      performanceFrames += 1;
      const elapsed = time - performanceWindowStart;
      if (elapsed >= 1000) {
        lastMeasuredFps = Math.round((performanceFrames * 1000) / elapsed);
        performanceElement.textContent = `${lastMeasuredFps} FPS · HDR／GTAO／ACES`;
        const occlusionLabel = gtaoPass?.enabled ? "GTAO" : "接觸陰影";
        performanceElement.textContent = `${lastMeasuredFps} FPS · HDR／${occlusionLabel}／ACES`;
        if (lastMeasuredFps < 30 && !reducedPixelRatio) {
          reducedPixelRatio = true;
          renderer.setPixelRatio(1);
          onResize();
          performanceElement.textContent = `${lastMeasuredFps} FPS · 已自動降低解析度維持互動`;
        }
        performanceFrames = 0;
        performanceWindowStart = time;
      }
    }
  });

  return {
    loadScene,
    // The bella-new step 5-8 material state machine calls updateRoomSurfaces to
    // re-apply per-room wall/floor/ceiling materials after the user edits them.
    // roomId is an unused targeting hint; rebuilding the shell from the current
    // sceneData yields the same visible result (only edited surfaces change).
    updateRoomSurfaces,
    addObject,
    removeObject,
    updateObject,
    unloadScene,
    resetCamera,
    setCameraPreset,
    setViewMode,
    setWalkRoom,
    setFurnitureNumberMarkersVisible(visible, roomId = "") {
      showFurnitureNumberMarkers = Boolean(visible);
      numberMarkerRoomId = String(roomId || "");
      configurePlanLabels(viewMode.mode);
    },
    setInteractionMode,
    toggleCameraLock,
    capturePng,
    getCameraState,
    setCameraState,
    lockRenderCamera,
    exportGlb,
    focusObject,
    selectObjectByIndex,
    getCanvasHost: () => renderer.domElement,
    getSelectedFurnitureId: () => selectedWrapper?.userData?.sceneObject?.furniture_id || null,
    projectFurnitureCenters() {
      const rect = renderer.domElement.getBoundingClientRect();
      camera.updateMatrixWorld(true);
      return furnitureGroup.children.map((wrapper) => {
        const item = wrapper.userData.sceneObject || {};
        const size = sizeCentimeters(item);
        const point = new THREE.Vector3(
          wrapper.position.x,
          Math.max(15, size.height * 0.45),
          wrapper.position.z,
        );
        point.project(camera);
        return {
          furniture_id: item.furniture_id,
          name: item.name_zh_raw,
          screen: {
            x: (point.x * 0.5 + 0.5) * rect.width + rect.left,
            y: (-point.y * 0.5 + 0.5) * rect.height + rect.top,
          },
          behind: point.z > 1,
        };
      });
    },
    rotateSelected: rotateSelectedFromControls,
    beginPlacement,
    cancelPlacement,
    beginBeamPlacement,
    cancelBeamPlacement,
    toggleCeiling,
    getDiagnostics,
  };
}
