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
import { classifyMaterialSlot } from "./scene_material_schemes.js?v=sha256-e4e6b4391198";
import {
  architecturalPbrProfile,
  furniturePbrProfile,
  surfacePbrProfile,
  surfaceTint,
} from "./scene_pbr_contracts.js?v=sha256-d695a0f07d33";
import {
  doorOpeningForWallTopology,
  openingBelongsToWall,
  openingWallInterval,
  wallSectionSpan,
  wallSegmentForOpening,
} from "./scene_architecture.js?v=sha256-7899eae4c7ba";
import { createViewModeState } from "./scene_view_modes.js?v=sha256-13bc85e6a748";
import { columnGeometryDescriptor } from "./scene_structure_geometry.js?v=sha256-041eec531ccf";
import { windowOpeningMetrics } from "./scene_window_types.js?v=sha256-ebe4923f97c0";
import {
  clampWalkPosition,
  computeExactModelScale,
  fallbackMaterialRole,
  findNearestWalkablePosition,
  inferredWallThicknessCm,
  snapFurnitureToRoomSurface,
  synchronizedFloorRegions,
  viewPresentation,
} from "./scene_visual_contracts.js?v=sha256-df17eff718c3";
import { normalizedPlanarUvs } from "./scene_texture_uv.js?v=sha256-1d68ae8102bc";

const CM_PER_METER = 100;

import { createViewerArchitecture } from "./scene_viewer_architecture.js?v=sha256-0e24b3923208";
import { createSurfaceMaterialFactory } from "./scene_viewer_materials.js?v=sha256-a26ada740ef8";
import { createAxisLabel } from "./scene_viewer_labels.js?v=sha256-6155285a51be";
import { cloneCachedGltfScene, loadGltfCached } from "./scene_gltf_cache.js?v=sha256-07eb284d64fb";
import {
  dedupeArchitecturalOpeningsFor3d,
  openingAnchorForWallTopology,
  openingAnchorOnWall,
  sceneDataForWorld,
  sceneToWorldPosition,
  sceneToWorldRotationDeg,
  worldToScenePosition,
  worldToSceneRotationDeg,
} from "./scene_viewer_coordinates.js?v=sha256-cc21ad50a82f";
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

  const {
    applySurfaceTint,
    createArchitecturalMaterial,
    createFloorMaterial,
    createWallMaterial,
    stabilizeWholeHouseWallAppearance,
  } = createSurfaceMaterialFactory({ textureLoader });
  const { createRoom } = createViewerArchitecture({
    applySurfaceTint,
    architecturalPbrProfile,
    ceilingGroup,
    clearGroup,
    columnGeometryDescriptor,
    controls,
    createArchitecturalMaterial,
    createCeilingGeometry,
    createFloorMaterial,
    createWallMaterial,
    dedupeArchitecturalOpeningsFor3d,
    doorOpeningForWallTopology,
    grid,
    inferredWallThicknessCm,
    isCameraLocked: () => cameraLocked,
    keyLight,
    normalizedPlanarUvs,
    openingAnchorForWallTopology,
    openingAnchorOnWall,
    openingWallInterval,
    roomGroup,
    scene,
    setViewMode,
    stabilizeWholeHouseWallAppearance,
    synchronizedFloorRegions,
    walkPositionBlocked,
    walkPositionInsideFloor,
    wallMeshes,
    wallSectionSpan,
    wallSegmentForOpening,
    windowOpeningMetrics,
  });

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

  function createFallbackFurnitureProxy(item, index, reason, { validFixture = false } = {}) {
    const width = Math.max(Number(item.size_cm?.width || 120), 25);
    const depth = Math.max(Number(item.size_cm?.depth || 60), 25);
    const height = Math.max(Number(item.size_cm?.height || 80), 25);
    const wrapper = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({
      color: validFixture ? 0x7c8f78 : 0xd97706,
      transparent: true,
      opacity: validFixture ? 0.62 : 0.38,
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
      new THREE.LineBasicMaterial({
        color: validFixture ? 0x36513a : 0x9a3412,
        transparent: true,
        opacity: 0.95,
      }),
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
    wrapper.userData.fallbackFurniture = !validFixture;
    wrapper.userData.proceduralFixture = validFixture;
    wrapper.userData.fallbackReason = reason;
    wrapper.userData.modelLoadFailed = !validFixture;
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
    if (item.render_mode === "procedural_fixture") {
      return createFallbackFurnitureProxy(
        item,
        index,
        "portable profile procedural fixture",
        { validFixture: true },
      );
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
      item.position_locked = true;  // 之後的重排/替換不會沖掉手動位置
      notifySceneChange(item);
    } else {
      wrapper.position.copy(startPosition);
      wrapper.rotation.y = THREE.MathUtils.degToRad(startRotationDeg);
      updateFootprintGuide(wrapper);
    }
    setStatus(verdict.ok
      ? `已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`
      : `無法移動「${label}」：${verdict.reason || "位置不符合限制"}，已復原。`);
  });

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
    // The Step 5-8 material state machine calls updateRoomSurfaces to
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
