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
import { createViewModeState } from "./scene_view_modes.js?v=20260712b";
import { clampWalkPosition, computeExactModelScale, fallbackMaterialRole, viewPresentation } from "./scene_visual_contracts.js?v=20260718d";

export function createSceneViewer(container, statusElement) {
  if ("createImageBitmap" in globalThis) {
    globalThis.createImageBitmap = undefined;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8f4ef);

  const initialWidth = Math.max(container.clientWidth, 1);
  const initialHeight = Math.max(container.clientHeight, 1);
  const perspectiveCamera = new THREE.PerspectiveCamera(45, initialWidth / initialHeight, 0.1, 200);
  perspectiveCamera.position.set(5.5, 4.6, 6.8);
  const orthographicCamera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.01, 200);
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

  const usePostProcessing = container.id === "realistic-viewer";
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
  if (composer) {
    gtaoPass.output = GTAOPass.OUTPUT.Default;
    gtaoPass.blendIntensity = 1.1;
    gtaoPass.updateGtaoMaterial({
      radius: 0.35,
      distanceExponent: 1.5,
      thickness: 1,
      distanceFallOff: 1,
      scale: 1,
      samples: 8,
      screenSpaceRadius: true,
    });
    gtaoPass.updatePdMaterial({ rings: 2, radiusExponent: 2, samples: 8 });
    composer.addPass(renderPass);
    composer.addPass(gtaoPass);
    composer.addPass(outputPass);
  }

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 1.4;
  controls.maxDistance = 18;
  controls.zoomSpeed = 0.85;
  controls.target.set(0, 0.8, 0);
  let activeCameraPreset = "dollhouse";
  const viewMode = createViewModeState("dollhouse");
  let cameraLocked = false;
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
    controls.minDistance = isInside ? 1.25 : 1.4;
    controls.maxDistance = isInside ? 3.4 : 18;
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
  hemiLight.position.set(0, 8, 0);
  scene.add(hemiLight);

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.9);
  keyLight.position.set(6, 8, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xe5d0b2, 1.05);
  fillLight.position.set(-5, 5, -4);
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
      new THREE.SphereGeometry(12, 48, 24),
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
    ground.position.y = -2.2;
    environmentScene.add(ground);

    const sun = new THREE.Mesh(
      new THREE.SphereGeometry(0.7, 24, 12),
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
    keyLight.color.copy(lightColor);
    keyLight.intensity = Math.max(1.2, Number(lighting.keyLightLux || 360) / 220);
    fillLight.color.copy(lightColor).lerp(new THREE.Color(0xffffff), 0.35);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = Number(rendering.exposure) || 1.05;
    const shadowProfile = rendering.shadow || {};
    const shadowMapSize = Math.max(512, Number(shadowProfile.mapSize) || 1024);
    keyLight.shadow.mapSize.set(shadowMapSize, shadowMapSize);
    keyLight.shadow.radius = Math.max(1, Number(shadowProfile.radius) || 3);
    keyLight.shadow.bias = Number(shadowProfile.bias) || -0.0008;
    keyLight.shadow.normalBias = Number(shadowProfile.normalBias) || 0.018;
    if (gtaoPass) {
      gtaoPass.enabled = rendering.gtao?.enabled !== false;
      gtaoPass.blendIntensity = Number(rendering.gtao?.intensity) || 1.1;
      gtaoPass.updateGtaoMaterial({
        radius: Number(rendering.gtao?.radius) || 0.35,
        samples: 8,
        screenSpaceRadius: true,
      });
    }
  }

  const grid = new THREE.GridHelper(12, 48, 0xc6ad8e, 0xe8ddcf);
  grid.position.y = -0.01;
  grid.material.transparent = true;
  grid.material.opacity = 0.16;
  grid.visible = false;
  scene.add(grid);

  const axes = new THREE.AxesHelper(1.4);
  axes.position.set(-4.7, 0.02, 4.7);
  axes.visible = false;
  scene.add(axes);
  [
    ["+X 右", "#d94b3d", [-3.05, 0.08, 4.7]],
    ["-X 左", "#d94b3d", [-5.85, 0.08, 4.7]],
    ["+Y 上", "#47a65a", [-4.7, 1.6, 4.7]],
    ["-Y 地", "#47a65a", [-4.7, 0.08, 4.7]],
    ["+Z 深", "#3f73d8", [-4.7, 0.08, 6.35]],
    ["-Z 前", "#3f73d8", [-4.7, 0.08, 3.05]],
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

  function clearGroup(group) {
    while (group.children.length) {
      const child = group.children.pop();
      if (!child) break;
      group.remove(child);
      child.traverse?.((object) => {
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
  }

  function resetCamera() {
    setViewMode("dollhouse");
  }

  function setCameraPreset(preset = "corner") {
    if (camera !== perspectiveCamera) {
      camera = perspectiveCamera;
      controls.object = perspectiveCamera;
      viewMode.setMode(preset === "inside" ? "walk" : "orbit");
      configureWallsForView("orbit");
    }
    const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6, wallHeight: 2.7 };
    const presets = {
      overview: {
        position: [0, Math.max(room.widthM, room.depthM) * 1.12 + 2.1, 0.08],
        target: [0, 0.25, 0],
      },
      entrance: {
        position: [0, 1.72, room.depthM / 2 + 1.15],
        target: [0, 1.05, -room.depthM * 0.16],
      },
      corner: {
        position: [room.widthM * 0.55 + 1.15, 2.72, room.depthM * 0.55 + 1.35],
        target: [0, 0.85, 0],
      },
      inside: {
        position: [0, 1.45, Math.max(room.depthM * 0.28, 0.95)],
        target: [0, 1.08, -Math.max(room.depthM * 0.14, 0.48)],
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
    sprite.scale.set(0.24, 0.24, 1);
    sprite.renderOrder = 998;
    return sprite;
  }

  function findSurface(surfaceCatalog, surfaceId, usage) {
    return (surfaceCatalog?.surfaces || []).find(
      (surface) => surface.surface_id === surfaceId && surface.usage?.includes(usage)
    );
  }

  function getSurfaceModuleSize(surface, usage) {
    if (usage !== "floor") return { x: 1.8, y: 1.8 };
    if (surface.category === "tile") return { x: 0.6, y: 0.6 };
    if (surface.category === "wood_tile") return { x: 0.9, y: 0.9 };
    return { x: 1.2, y: 1.2 };
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

  function createImageTexture(surface, usage, repeatOverride = null) {
    const texture = textureLoader.load(surface.texture_url);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    const repeat = repeatOverride || surface.repeat?.[usage] || (usage === "floor" ? [4, 4] : [2.2, 1.6]);
    texture.repeat.set(Number(repeat[0]) || 1, Number(repeat[1]) || 1);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return texture;
  }

  function createSurfaceImageMaterial(surface, usage, options = {}) {
    const colorMap = createImageTexture(surface, usage, options.repeat);
    const bumpMap = usage === "floor"
      ? createImageTexture(surface, usage, options.repeat)
      : null;
    if (bumpMap) bumpMap.colorSpace = THREE.NoColorSpace;
    const material = new THREE.MeshStandardMaterial({
      color: options.color ?? 0xffffff,
      map: colorMap,
      ...(bumpMap ? {
        bumpMap,
        bumpScale: 0.035,
      } : {}),
      roughness: options.roughness ?? 0.9,
      metalness: options.metalness ?? 0.01,
      side: options.side ?? THREE.FrontSide,
    });
    material.userData.roompilotImageSurface = true;
    if (options.transparent) {
      material.transparent = true;
      material.opacity = options.opacity ?? 0.92;
      material.depthWrite = true;
    }
    return material;
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
        repeat: getContinuousSurfaceRepeat(surface, "floor", roomSize.widthM, roomSize.depthM),
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

  function createWallMaterial(wallOption, surfaceCatalog) {
    const surface = findSurface(surfaceCatalog, wallOption, "wall");
    if (surface) {
      const material = createSurfaceImageMaterial(surface, "wall", {
        roughness: 0.9,
        metalness: 0.01,
        repeat: surface.repeat?.wall || [2.4, 1.8],
        side: THREE.DoubleSide,
      });
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

  function registerWall(wallMesh) {
    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = 1;
    wallMesh.userData.fullPositionY = wallMesh.position.y;
    wallMesh.userData.fullScaleY = wallMesh.scale.y;
    wallMeshes.push(wallMesh);
    return wallMesh;
  }

  function buildSegmentWalls(roomGroupRef, segments, wallMaterial, wallHeight, wallThickness) {
    segments.forEach((segment) => {
      const start = segment.start;
      const end = segment.end;
      if (!start || !end) return;

      const dx = end.x - start.x;
      const dz = end.z - start.z;
      const length = Math.hypot(dx, dz);
      if (length < 0.04) return;

      const material = typeof wallMaterial === "function"
        ? wallMaterial(segment)
        : wallMaterial;
      const wallMesh = new THREE.Mesh(
        new THREE.BoxGeometry(length + wallThickness, wallHeight, wallThickness),
        material.clone(),
      );
      wallMesh.position.set((start.x + end.x) / 2, wallHeight / 2, (start.z + end.z) / 2);
      wallMesh.rotation.y = Math.atan2(-dz, dx);
      roomGroupRef.add(registerWall(wallMesh));

      /*
      // 平面圖牆段在轉角處不一定精準相交；頂部封板同時遮住牆頂接縫。
      */
      const topCap = new THREE.Mesh(
        new THREE.BoxGeometry(length + wallThickness, 0.025, wallThickness),
        material.clone(),
      );
      topCap.position.set(
        (start.x + end.x) / 2,
        wallHeight + 0.0125,
        (start.z + end.z) / 2,
      );
      topCap.rotation.y = wallMesh.rotation.y;
      topCap.castShadow = true;
      topCap.receiveShadow = true;
      roomGroupRef.add(topCap);
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
      if (length < 0.04) return;
      const width = Math.max(Number(segment.width_m || segment.thickness_m || 0.3), 0.12);
      const height = Math.max(Number(segment.height_m || 0.35), 0.12);
      const top = Math.min(Number(segment.top_m || wallHeight), wallHeight);
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
      const size = Math.max(Number(column.size_m || 0.35), 0.12);
      const height = Math.max(Number(column.height_m || wallHeight), 0.12);
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(size, height, size),
        material.clone(),
      );
      mesh.position.set(Number(center.x), height / 2, Number(center.z));
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.roompilotStructure = "column";
      roomGroupRef.add(mesh);
    });
  }

  function buildFloorPlanOverlay(roomGroupRef, segments, color, opacity = 0.55, yOffset = 0.025) {
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

  function circulationAccessPoint(segment, reference, clearanceM = 0.38) {
    const midpoint = segmentMidpoint(segment);
    const dx = Number(segment.end?.x) - Number(segment.start?.x);
    const dz = Number(segment.end?.z) - Number(segment.start?.z);
    const length = Math.hypot(dx, dz) || 1;
    const normal = { x: -dz / length, z: dx / length };
    const candidates = [1, -1].map((side) => ({
      x: midpoint.x + normal.x * clearanceM * side,
      z: midpoint.z + normal.z * clearanceM * side,
    })).filter(
      (point) => walkPositionInsideFloor(point) && !walkPositionBlocked(point, 0.17),
    );
    if (!candidates.length) return midpoint;
    return candidates.sort(
      (left, right) => Math.hypot(left.x - reference.x, left.z - reference.z)
        - Math.hypot(right.x - reference.x, right.z - reference.z),
    )[0];
  }

  function findCirculationPath(start, goal, floorplan, cellSize = 0.2) {
    const widthM = Math.max(Number(floorplan.width_cm) / 100, 2.4);
    const depthM = Math.max(Number(floorplan.depth_cm) / 100, 2.4);
    const minX = -widthM / 2;
    const minZ = -depthM / 2;
    const columns = Math.ceil(widthM / cellSize) + 1;
    const rows = Math.ceil(depthM / cellSize) + 1;
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
      return walkPositionInsideFloor(point) && !walkPositionBlocked(point, 0.17);
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
    const steps = Math.max(Math.ceil(distance / 0.1), 1);
    for (let index = 0; index <= steps; index += 1) {
      const progress = index / steps;
      const point = {
        x: THREE.MathUtils.lerp(start.x, end.x, progress),
        z: THREE.MathUtils.lerp(start.z, end.z, progress),
      };
      if (!walkPositionInsideFloor(point) || walkPositionBlocked(point, 0.17)) return false;
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
      if (length < 0.02) return;
      const strip = new THREE.Mesh(
        new THREE.BoxGeometry(length + 0.03, 0.012, 0.11),
        material,
      );
      strip.position.set((point.x + previous.x) / 2, 0.038, (point.z + previous.z) / 2);
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
        new THREE.ConeGeometry(0.11, 0.24, 3),
        material.clone(),
      );
      arrow.position.set(point.x, 0.052, point.z);
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
    sprite.scale.set(1.1, 0.42, 1);
    sprite.renderOrder = 30;
    sprite.userData.roompilotCirculation = true;
    return sprite;
  }

  function buildCirculationRoute(roomGroupRef, floorplan) {
    const doors = (floorplan.door_segments || []).filter(
      (segment) => segment.start && segment.end,
    );
    if (doors.length < 2) return;
    const widthM = Math.max(Number(floorplan.width_cm) / 100, 2.4);
    const depthM = Math.max(Number(floorplan.depth_cm) / 100, 2.4);
    const edgeDistance = (point) => Math.min(
      Math.abs(point.x + widthM / 2),
      Math.abs(point.x - widthM / 2),
      Math.abs(point.z + depthM / 2),
      Math.abs(point.z - depthM / 2),
    );
    const entrance = [...doors].sort((left, right) => {
      const leftMidpoint = segmentMidpoint(left);
      const rightMidpoint = segmentMidpoint(right);
      const edgeDifference = edgeDistance(leftMidpoint) - edgeDistance(rightMidpoint);
      return Math.abs(edgeDifference) > 0.08
        ? edgeDifference
        : rightMidpoint.z - leftMidpoint.z;
    })[0];
    const entranceMidpoint = segmentMidpoint(entrance);
    const entranceAccess = circulationAccessPoint(entrance, { x: 0, z: 0 });
    const startMarker = new THREE.Mesh(
      new THREE.CircleGeometry(0.23, 32),
      new THREE.MeshBasicMaterial({
        color: 0x2f7d64,
        transparent: true,
        opacity: 0.92,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    startMarker.rotation.x = -Math.PI / 2;
    startMarker.position.set(entranceAccess.x, 0.04, entranceAccess.z);
    startMarker.renderOrder = 26;
    startMarker.userData.roompilotCirculation = true;
    roomGroupRef.add(startMarker);
    const label = createCirculationLabel("玄關");
    label.position.set(entranceAccess.x, 0.42, entranceAccess.z);
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
    const bounds = boundary?.room_bounds_m;
    const line = boundary?.line_m;
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
    if (materials[0].color) materials[0].color.set(palette[1] || 0xc9a77d);
    if (materials[1].color) materials[1].color.set(palette[3] || 0x8b684b);
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
      if (part.width < 0.02 || part.depth < 0.02) return;
      const surface = new THREE.Mesh(
        new THREE.PlaneGeometry(part.width, part.depth),
        materials[index],
      );
      surface.rotation.x = -Math.PI / 2;
      surface.position.set(part.x, 0.006 + index * 0.001, part.z);
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

  function createRoomSurfaceOverrides(roomGroupRef, sceneData) {
    (sceneData.surface_overrides || []).forEach((override, index) => {
      const bounds = override.room_bounds_m;
      if (!bounds) return;
      const width = Number(bounds.maxX) - Number(bounds.minX);
      const depth = Number(bounds.maxZ) - Number(bounds.minZ);
      if (width < 0.02 || depth < 0.02) return;
      const material = createFloorMaterial(
        override.floor_option || "auto",
        sceneData.surface_catalog,
        { widthM: width, depthM: depth },
      );
      if (override.floor_color_hex && material.color) {
        material.color.set(override.floor_color_hex);
      }
      const polygon = override.room_polygon_m || [];
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
      } else {
        geometry = new THREE.PlaneGeometry(width, depth);
      }
      const surface = new THREE.Mesh(geometry, material);
      surface.rotation.x = -Math.PI / 2;
      surface.position.y = 0.004 + index * 0.001;
      if (polygon.length < 3) {
        surface.position.x = (Number(bounds.minX) + Number(bounds.maxX)) / 2;
        surface.position.z = (Number(bounds.minZ) + Number(bounds.maxZ)) / 2;
      }
      surface.receiveShadow = true;
      surface.userData.roompilotSurfaceOverride = override.room_id;
      roomGroupRef.add(surface);
    });
  }

  function wallMaterialResolver(sceneData, defaultMaterial) {
    const overrides = sceneData.surface_overrides || [];
    const cache = new Map();
    return (segment) => {
      const midpoint = {
        x: (Number(segment.start?.x || 0) + Number(segment.end?.x || 0)) / 2,
        z: (Number(segment.start?.z || 0) + Number(segment.end?.z || 0)) / 2,
      };
      const override = overrides.findLast(
        (item) => item.room_bounds_m
          && pointInBounds(midpoint, item.room_bounds_m, 0.18),
      );
      if (!override) return defaultMaterial;
      if (!cache.has(override.room_id)) {
        const material = createWallMaterial(
          override.wall_option || "auto",
          sceneData.surface_catalog,
        );
        if (override.wall_color_hex && material.color) {
          material.color.set(override.wall_color_hex);
        }
        cache.set(override.room_id, material);
      }
      return cache.get(override.room_id);
    };
  }

  function createRoom(sceneData) {
    clearGroup(roomGroup);
    clearGroup(ceilingGroup);
    clearGroup(hangingLightGroup);
    wallMeshes.length = 0;

    const widthM = Math.max(sceneData.floorplan.width_cm / 100, 2.4);
    const depthM = Math.max(sceneData.floorplan.depth_cm / 100, 2.4);
    const wallHeight = Math.max(
      Number(sceneData.floorplan.room_height_cm || 270) / 100,
      2.1,
    );
    const floorOption = sceneData.design_choices?.floor_option || "auto";
    const wallOption = sceneData.design_choices?.wall_option || "auto";

    const floorMaterial = createFloorMaterial(
      floorOption,
      sceneData.surface_catalog,
      { widthM, depthM },
    );
    const floorPbr = sceneData.style?.pbr?.floor || {};
    const floorColor = sceneData.design_choices?.floor_color_hex
      || sceneData.style_card?.palette_hex?.[1];
    if (floorColor && floorMaterial.color) floorMaterial.color.set(floorColor);
    if (floorPbr.roughness != null) floorMaterial.roughness = floorPbr.roughness;
    if (floorPbr.metalness != null) floorMaterial.metalness = floorPbr.metalness;
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(widthM, depthM),
      floorMaterial,
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    roomGroup.add(floor);
    createRoomSurfaceOverrides(roomGroup, sceneData);
    createMaterialBoundarySurfaces(
      roomGroup,
      sceneData.material_boundary,
      floorMaterial,
      sceneData,
    );

    const wallMaterial = createWallMaterial(wallOption, sceneData.surface_catalog);
    const wallPbr = sceneData.style?.pbr?.wall || {};
    const wallColor = sceneData.design_choices?.wall_color_hex
      || sceneData.style_card?.palette_hex?.[0];
    if (wallColor && wallMaterial.color) wallMaterial.color.set(wallColor);
    if (wallPbr.roughness != null) wallMaterial.roughness = wallPbr.roughness;
    if (wallPbr.metalness != null) wallMaterial.metalness = wallPbr.metalness;
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const doorSegments = sceneData.floorplan?.door_segments || [];
    const windowSegments = sceneData.floorplan?.window_segments || [];
    const hasAccurateFloorplan = ["dxf", "user_confirmed"].includes(
      sceneData.floorplan?.source,
    );
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthM, depthM, wallHeight };
    roomGroup.userData.ceilingStyle = sceneData.design_choices?.ceiling_style || "exposed";

    const ceilingDropCm = Number(sceneData.design_choices?.ceiling_drop_cm) || 0;
    const ceilingHeight = wallHeight - ceilingDropCm / 100;
    createCeilingGeometry(
      { widthM, depthM, wallHeight, ceilingHeight },
      roomGroup.userData.ceilingStyle,
      sceneData.style_card || sceneData.style || {},
    );
    ceilingGroup.visible = false;

    // 12 cm 接近住宅隔間牆；原先 4 cm 會讓雙線牆與轉角看起來像中空。
    const wallThickness = 0.12;
    if (!singleRoomMode && wallSegments.length >= 2) {
      buildSegmentWalls(
        roomGroup,
        wallSegments,
        wallMaterialResolver(sceneData, wallMaterial),
        wallHeight,
        wallThickness,
      );
    } else {
      const backWall = new THREE.Mesh(new THREE.BoxGeometry(widthM, wallHeight, wallThickness), wallMaterial.clone());
      backWall.position.set(0, wallHeight / 2, -depthM / 2);
      roomGroup.add(registerWall(backWall));

      const leftWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthM), wallMaterial.clone());
      leftWall.position.set(-widthM / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(leftWall));

      const rightWall = new THREE.Mesh(new THREE.BoxGeometry(wallThickness, wallHeight, depthM), wallMaterial.clone());
      rightWall.position.set(widthM / 2, wallHeight / 2, 0);
      roomGroup.add(registerWall(rightWall));
    }

    if (hasAccurateFloorplan) {
      buildFloorPlanOverlay(roomGroup, doorSegments, 0xb9773f, 0.82, 0.038);
      buildFloorPlanOverlay(roomGroup, windowSegments, 0x6f9eb4, 0.9, 0.044);
      buildCirculationRoute(roomGroup, sceneData.floorplan);
    } else {
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(widthM, wallHeight, depthM)),
        new THREE.LineBasicMaterial({ color: 0xb89264, transparent: true, opacity: 0.35 })
      );
      outline.position.set(0, wallHeight / 2, 0);
      roomGroup.add(outline);
    }
    buildStructuralMembers(roomGroup, sceneData.floorplan || {}, wallHeight);

    const boundary = sceneData.material_boundary?.line_m;
    if (Array.isArray(boundary) && boundary.length >= 2) {
      buildFloorPlanOverlay(roomGroup, [{
        start: { x: Number(boundary[0].x) || 0, z: Number(boundary[0].y) || 0 },
        end: { x: Number(boundary[1].x) || 0, z: Number(boundary[1].y) || 0 },
      }], 0x7b56b3, 0.96, 0.052);
    }

    if (sceneData.design_choices?.light_style) {
      createStyleLights(
        { widthM, depthM, wallHeight: ceilingHeight },
        sceneData.style_card || sceneData.style || {},
        sceneData.design_choices.light_style,
      );
    }

    if (!cameraLocked) {
      controls.target.set(0, 0.9, 0);
      setViewMode("dollhouse");
    }
  }

  function createCeilingGeometry(room, ceilingStyle, style = {}) {
    if (ceilingStyle === "exposed") return;
    const palette = style.palette_hex || ["#F3EBDD", "#D3B48A", "#8B684B"];
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: palette[0] || "#f3eee6",
      roughness: 0.86,
      side: THREE.DoubleSide,
    });
    const accentMaterial = new THREE.MeshStandardMaterial({
      color: palette[2] || "#8B684B",
      roughness: 0.55,
      metalness: ceilingStyle === "linear" ? 0.45 : 0.05,
    });
    const addPanel = (width, depth, y, material = baseMaterial, thickness = 0.04) => {
      const panel = new THREE.Mesh(
        new THREE.BoxGeometry(Math.max(width, 0.08), thickness, Math.max(depth, 0.08)),
        material,
      );
      panel.position.y = y;
      panel.receiveShadow = true;
      panel.castShadow = true;
      panel.userData.ceilingStyle = ceilingStyle;
      ceilingGroup.add(panel);
      return panel;
    };

    if (ceilingStyle === "flat" || ceilingStyle === "no-main-light") {
      addPanel(room.widthM, room.depthM, room.ceilingHeight);
      return;
    }
    if (ceilingStyle === "cove") {
      const band = Math.min(0.42, room.widthM / 6, room.depthM / 6);
      addPanel(room.widthM, band, room.ceilingHeight, baseMaterial, 0.1).position.z = -(room.depthM - band) / 2;
      addPanel(room.widthM, band, room.ceilingHeight, baseMaterial, 0.1).position.z = (room.depthM - band) / 2;
      addPanel(band, Math.max(room.depthM - band * 2, 0.1), room.ceilingHeight, baseMaterial, 0.1).position.x = -(room.widthM - band) / 2;
      addPanel(band, Math.max(room.depthM - band * 2, 0.1), room.ceilingHeight, baseMaterial, 0.1).position.x = (room.widthM - band) / 2;
      addPanel(
        Math.max(room.widthM - band * 2, 0.1),
        Math.max(room.depthM - band * 2, 0.1),
        room.ceilingHeight + 0.1,
        baseMaterial,
      );
      return;
    }
    if (ceilingStyle === "floating") {
      addPanel(
        Math.max(room.widthM - 0.7, 0.5),
        Math.max(room.depthM - 0.7, 0.5),
        room.ceilingHeight,
        baseMaterial,
        0.12,
      );
      return;
    }
    if (ceilingStyle === "linear") {
      addPanel(room.widthM, room.depthM, room.ceilingHeight);
      [-0.55, 0.55].forEach((x) => {
        const strip = addPanel(0.055, Math.max(room.depthM - 0.5, 0.4), room.ceilingHeight - 0.035, accentMaterial, 0.018);
        strip.position.x = THREE.MathUtils.clamp(x, -room.widthM / 3, room.widthM / 3);
      });
      return;
    }
    if (ceilingStyle === "wood-grid") {
      const spacing = 0.24;
      const count = Math.max(3, Math.floor(room.widthM / spacing));
      for (let index = 0; index <= count; index += 1) {
        const x = -room.widthM / 2 + index * room.widthM / count;
        const slat = addPanel(0.055, room.depthM, room.ceilingHeight, accentMaterial, 0.08);
        slat.position.x = x;
      }
      return;
    }
    addPanel(room.widthM, room.depthM, room.ceilingHeight);
  }

  function createStyleLights(room, style = {}, lightStyle = "pendant") {
    const palette = style.palette_hex || ["#F3EBDD", "#D3B48A", "#8B684B"];
    const lightColor = new THREE.Color(palette[1] || "#D3B48A");
    const positions = room.widthM >= 4.8 ? [-0.9, 0, 0.9] : [-0.62, 0.62];

    if (lightStyle === "track") {
      const rail = new THREE.Mesh(
        new THREE.BoxGeometry(Math.min(room.widthM * 0.58, 3.4), 0.045, 0.055),
        new THREE.MeshStandardMaterial({ color: 0x292724, roughness: 0.34, metalness: 0.7 }),
      );
      rail.position.y = room.wallHeight - 0.08;
      hangingLightGroup.add(rail);
      positions.forEach((x, index) => {
        const spot = new THREE.Mesh(
          new THREE.CylinderGeometry(0.065, 0.09, 0.16, 18),
          new THREE.MeshStandardMaterial({ color: 0x34312e, roughness: 0.3, metalness: 0.65 }),
        );
        spot.position.set(x, room.wallHeight - 0.19, 0);
        spot.rotation.z = index % 2 ? -0.28 : 0.28;
        hangingLightGroup.add(spot);
        const light = new THREE.SpotLight(0xffdfb0, 2.2, 5.5, Math.PI / 5.5, 0.45, 1.7);
        light.position.copy(spot.position);
        light.target.position.set(x + (index % 2 ? 0.7 : -0.7), 0, 0.5);
        hangingLightGroup.add(light, light.target);
      });
      return;
    }
    if (lightStyle === "downlight") {
      const zPositions = room.depthM > 4.2 ? [-0.8, 0.8] : [0];
      positions.forEach((x) => zPositions.forEach((z) => {
        const trim = new THREE.Mesh(
          new THREE.CylinderGeometry(0.095, 0.095, 0.035, 24),
          new THREE.MeshStandardMaterial({ color: 0xf8f5ee, roughness: 0.42, metalness: 0.12 }),
        );
        trim.position.set(x, room.wallHeight - 0.025, z);
        hangingLightGroup.add(trim);
        const light = new THREE.PointLight(0xffe4bd, 0.78, 3.5, 2);
        light.position.set(x, room.wallHeight - 0.12, z);
        hangingLightGroup.add(light);
      }));
      return;
    }
    if (lightStyle === "paper") {
      const paper = new THREE.Mesh(
        new THREE.SphereGeometry(0.34, 32, 20),
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
      paper.position.set(0, room.wallHeight - 0.65, 0);
      hangingLightGroup.add(paper);
      const light = new THREE.PointLight(0xffd9a0, 1.8, 5.2, 2);
      light.position.copy(paper.position);
      hangingLightGroup.add(light);
      return;
    }
    positions.forEach((x, index) => {
      const pendant = new THREE.Group();
      pendant.position.set(x, room.wallHeight - 0.08, 0);

      const cord = new THREE.Mesh(
        new THREE.CylinderGeometry(0.012, 0.012, 0.72, 8),
        new THREE.MeshStandardMaterial({ color: 0x332b25, roughness: 0.7 })
      );
      cord.position.y = -0.36;
      pendant.add(cord);

      const shade = new THREE.Mesh(
        new THREE.ConeGeometry(0.19, 0.18, 32, 1, true),
        new THREE.MeshStandardMaterial({
          color: lightColor,
          roughness: 0.36,
          metalness: 0.2,
          side: THREE.DoubleSide,
        })
      );
      shade.position.y = -0.78;
      shade.rotation.y = index % 2 ? Math.PI : 0;
      pendant.add(shade);

      const bulb = new THREE.Mesh(
        new THREE.SphereGeometry(0.055, 16, 10),
        new THREE.MeshStandardMaterial({ color: 0xfff1ce, emissive: 0xffb45c, emissiveIntensity: 1.8 })
      );
      bulb.position.y = -0.82;
      pendant.add(bulb);

      const pointLight = new THREE.PointLight(0xffd6a0, 1.15, 4.8, 2);
      pointLight.position.y = -0.86;
      pointLight.castShadow = true;
      pendant.add(pointLight);
      hangingLightGroup.add(pendant);
    });
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
        const material = sourceMaterial.clone();
        const slotName = `${object.name || ""} ${material.name || ""}`.trim();
        const classifiedRole = classifyMaterialSlot(slotName);
        const role = classifiedRole === "unknown" ? fallbackMaterialRole(sceneObject.normalized_type) || "unknown" : classifiedRole;
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
      width: (targetSizeCm.width || 120) / 100,
      depth: (targetSizeCm.depth || 60) / 100,
      height: (targetSizeCm.height || 80) / 100,
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
      if (mode === "topdown") {
        wall.scale.y = 0.04;
        wall.position.y = 0.06;
      } else {
        wall.scale.y = wall.userData.fullScaleY || 1;
        wall.position.y = wall.userData.fullPositionY ?? wall.position.y;
      }
    });
    ceilingGroup.visible = mode === "walk"
      && roomGroup.userData.ceilingStyle !== "exposed";
  }

  function configurePlanLabels(mode) {
    const visible = viewPresentation(mode).showFurniturePlanLabels;
    furnitureGroup.traverse((object) => {
      if (object.userData.roompilotPlanLabel) object.visible = visible;
    });
  }

  function setViewMode(mode) {
    cameraLocked = false;
    const config = viewMode.setMode(mode);
    controls.object = config.camera === "orthographic" ? orthographicCamera : perspectiveCamera;
    camera = controls.object;
    controls.enabled = true;
    configureWallsForView(mode);
    configurePlanLabels(mode);
    renderer.domElement.style.cursor = mode === "walk" ? "grab" : "";
    if (mode !== "walk") {
      walkDestination = null;
      walkMarker.visible = false;
    }
    if (mode === "walk") {
      setCameraPreset("inside");
      activeCameraPreset = "walk";
      perspectiveCamera.up.set(0, 1, 0);
      controls.enabled = false;
      controls.enablePan = false;
      controls.enableZoom = false;
      const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6, wallHeight: 2.7 };
      const clamped = clampWalkPosition(perspectiveCamera.position, room);
      perspectiveCamera.position.set(clamped.x, clamped.y, clamped.z);
    } else if (mode === "topdown") {
      const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6 };
      const extent = Math.max(room.widthM, room.depthM) * 0.62 + 0.8;
      orthographicCamera.left = -extent;
      orthographicCamera.right = extent;
      orthographicCamera.top = extent;
      orthographicCamera.bottom = -extent;
      orthographicCamera.position.set(0, 18, 0.001);
      orthographicCamera.up.set(0, 0, -1);
      orthographicCamera.lookAt(0, 0, 0);
      orthographicCamera.updateProjectionMatrix();
      controls.target.set(0, 0, 0);
      controls.enableRotate = false;
      controls.enablePan = true;
      controls.enableZoom = true;
      controls.update();
    } else if (mode === "dollhouse") {
      const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6 };
      const extent = Math.max(room.widthM, room.depthM) * 0.68 + 0.9;
      orthographicCamera.left = -extent;
      orthographicCamera.right = extent;
      orthographicCamera.top = extent;
      orthographicCamera.bottom = -extent;
      orthographicCamera.position.set(extent, extent * 0.92, extent);
      orthographicCamera.up.set(0, 1, 0);
      orthographicCamera.lookAt(0, 0.45, 0);
      orthographicCamera.updateProjectionMatrix();
      controls.target.set(0, 0.45, 0);
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
    onResize();
    return config;
  }

  function toggleCameraLock(force) {
    cameraLocked = typeof force === "boolean" ? force : !cameraLocked;
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
    if (viewMode.mode !== "walk") return;
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
      movement.normalize().multiplyScalar(0.045);
    } else if (walkDestination) {
      movement.copy(walkDestination).sub(perspectiveCamera.position);
      movement.y = 0;
      if (movement.length() < 0.08) {
        walkDestination = null;
        walkMarker.visible = false;
        return;
      }
      movement.clampLength(0, 0.055);
    } else {
      return;
    }
    const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6, wallHeight: 2.7 };
    const proposed = perspectiveCamera.position.clone().add(movement);
    const clamped = clampWalkPosition(proposed, room);
    if (!walkPositionInsideFloor(clamped) || walkPositionBlocked(clamped)) {
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
    if (composer) composer.render();
    else renderer.render(scene, camera);
    return renderer.domElement.toDataURL("image/png");
  }

  async function exportGlb() {
    const exportRoot = new THREE.Group();
    exportRoot.add(roomGroup.clone(true));
    exportRoot.add(furnitureGroup.clone(true));
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
    sprite.scale.set(0.52, 0.52, 1);
    sprite.renderOrder = 999;
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
    sprite.scale.set(1.7, 0.38, 1);
    sprite.renderOrder = 1001;
    sprite.userData.roompilotPlanLabel = true;
    sprite.visible = false;
    return sprite;
  }

  let lastDiagnostics = {
    requestedFurnitureCount: 0,
    visibleFurnitureCount: 0,
    fallbackFurnitureCount: 0,
    failedFurniture: [],
  };

  function createFallbackFurnitureProxy(item, index, reason) {
    const width = Math.max(Number(item.size_cm?.width || 120) / 100, 0.25);
    const depth = Math.max(Number(item.size_cm?.depth || 60) / 100, 0.25);
    const height = Math.max(Number(item.size_cm?.height || 80) / 100, 0.25);
    const wrapper = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({
      color: item.material_override?.color
        || lastSceneData?.style_card?.palette_hex?.[2]
        || 0xf4f1ec,
      roughness: item.material_override?.pbr?.fabricRoughness || 0.84,
      metalness: 0,
    });
    const body = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
    body.position.y = height / 2;
    body.castShadow = true;
    body.receiveShadow = true;
    wrapper.add(body);

    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(body.geometry),
      new THREE.LineBasicMaterial({ color: 0x8b6b52, transparent: true, opacity: 0.72 }),
    );
    outline.position.copy(body.position);
    wrapper.add(outline);
    wrapper.position.x = Number(item.position_cm?.x || ((index % 4) - 1.5) * 130) / 100;
    wrapper.position.z = Number(item.position_cm?.z || Math.floor(index / 4) * 110) / 100;
    wrapper.rotation.y = THREE.MathUtils.degToRad(item.rotation_y_deg || 0);
    wrapper.userData.sceneIndex = index + 1;
    wrapper.userData.sceneObject = item;
    wrapper.userData.fallbackFurniture = true;
    wrapper.userData.fallbackReason = reason;

    const marker = createNumberMarker(index + 1);
    marker.position.set(0, height + 0.48, 0);
    wrapper.add(marker);
    const planLabel = createFurniturePlanLabel(item.name_zh_raw || item.normalized_type);
    planLabel.position.set(0, height + 0.15, 0);
    wrapper.add(planLabel);
    furnitureGroup.add(wrapper);
    return wrapper;
  }

  async function loadScene(sceneData) {
    onResize();
    lastSceneData = sceneData;
    dragState = null;
    selectedWrapper = null;
    selectedControls.hidden = true;
    disposeGuide();
    clearGroup(furnitureGroup);
    applyRenderingProfile(sceneData);
    createRoom(sceneData);
    setStatus("正在生成 3D 場景...");

    const objects = sceneData.scene_objects || [];
    const failures = [];
    lastDiagnostics = {
      requestedFurnitureCount: objects.length,
      visibleFurnitureCount: 0,
      fallbackFurnitureCount: 0,
      failedFurniture: [],
    };

    await Promise.all(
      objects.map(async (item, index) => {
        if (item.placement_failed) {
          failures.push(`${item.name_zh_raw || item.normalized_type}（空間放不下，未擺入）`);
          return;
        }
        if (!item.model_url) {
          failures.push(`${item.name_zh_raw || item.normalized_type} 無模型`);
          return;
        }

        try {
          const gltf = await loader.loadAsync(item.model_url);
          applyStyleSkin(gltf.scene, sceneData, item);
          gltf.scene.traverse((object) => {
            if (object.isMesh) {
              object.castShadow = true;
              object.receiveShadow = true;
            }
          });
          const wrapper = new THREE.Group();
          wrapper.add(gltf.scene);
          fitToTargetSize(wrapper, item.size_cm || {});
          wrapper.userData.sceneIndex = index + 1;
          wrapper.userData.sceneObject = item;

          wrapper.position.x = (item.position_cm?.x || 0) / 100;
          wrapper.position.z = (item.position_cm?.z || 0) / 100;
          wrapper.rotation.y = THREE.MathUtils.degToRad(item.rotation_y_deg || 0);

          const itemBox = new THREE.Box3().setFromObject(wrapper);
          const itemSize = itemBox.getSize(new THREE.Vector3());
          const marker = createNumberMarker(index + 1);
          marker.position.set(0, Math.max(itemSize.y + 0.48, 0.72), 0);
          wrapper.add(marker);
          const planLabel = createFurniturePlanLabel(item.name_zh_raw || item.normalized_type);
          planLabel.position.set(0, Math.max(itemSize.y + 0.15, 0.35), 0);
          wrapper.add(planLabel);
          furnitureGroup.add(wrapper);
        } catch (error) {
          console.error(error);
          failures.push(item.name_zh_raw || item.normalized_type || "未知家具");
        }
      })
    );

    objects.forEach((item, index) => {
      const visible = furnitureGroup.children.some(
        (wrapper) => wrapper.userData.sceneObject === item,
      );
      if (visible) return;
      if (item.placement_failed) {
        lastDiagnostics.failedFurniture.push({
          id: item.furniture_id,
          reason: item.placement_reason || "家具位置無法通過碰撞與淨空檢查",
        });
        return;
      }
      const reason = item.model_url
          ? "GLB 載入失敗，已顯示同尺寸白色替代物"
          : "資料庫找不到 GLB，已顯示同尺寸白色替代物";
      createFallbackFurnitureProxy(item, index, reason);
      lastDiagnostics.failedFurniture.push({
        id: item.furniture_id,
        reason,
      });
    });
    lastDiagnostics.visibleFurnitureCount = furnitureGroup.children.length;
    lastDiagnostics.fallbackFurnitureCount = furnitureGroup.children.filter(
      (wrapper) => wrapper.userData.fallbackFurniture === true,
    ).length;

    if (failures.length) {
      setStatus(`場景已生成，但部分家具未載入：${failures.join("、")}`);
    } else {
      setStatus("場景已生成：拖曳家具可移動（放手時檢查碰撞），點選後按 R 旋轉。");
    }
  }

  // ── F6 自由拖曳：前端只負責拖，落點合法性由後端 furniture_engine 驗證 ──
  let lastSceneData = null;
  let dragState = null;
  let selectedWrapper = null;
  let footprintGuide = null;
  let snapHint = null;
  let placementRequest = null;

  const dragRaycaster = new THREE.Raycaster();
  const pointerNdc = new THREE.Vector2();
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const planeHit = new THREE.Vector3();
  const walkMarker = new THREE.Mesh(
    new THREE.RingGeometry(0.09, 0.14, 32),
    new THREE.MeshBasicMaterial({
      color: 0x2f7d64,
      transparent: true,
      opacity: 0.86,
      depthTest: false,
      side: THREE.DoubleSide,
    }),
  );
  walkMarker.rotation.x = -Math.PI / 2;
  walkMarker.position.y = 0.025;
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
    </div>
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
    const room = roomGroup.userData.roomSize || { widthM: 4.2, depthM: 3.6, wallHeight: 2.7 };
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
    walkMarker.position.set(destination.x, 0.025, destination.z);
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
    const regions = lastSceneData?.floorplan?.room_regions || [];
    if (!regions.length) return true;
    return regions.some((region) => {
      const exterior = region.exterior || region.polygon_m || [];
      if (!pointInRing(position, exterior)) return false;
      return !(region.holes || []).some((hole) => pointInRing(position, hole));
    });
  }

  function walkPositionBlocked(position, clearanceM = 0.2) {
    return (lastSceneData?.floorplan?.wall_segments || []).some((segment) => {
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
      return Math.hypot(position.x - closestX, position.z - closestZ) < clearanceM;
    });
  }

  function beginWalkLook(event) {
    if (viewMode.mode !== "walk" || event.button !== 0 || dragState || placementRequest) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, perspectiveCamera);
    if (dragRaycaster.intersectObjects(furnitureGroup.children, true).length) return;
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
    controls.target.copy(perspectiveCamera.position).addScaledVector(direction, 2);
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

  function sizeMeters(item) {
    const size = item?.size_cm || {};
    return {
      width: (Number(size.width) || 120) / 100,
      depth: (Number(size.depth) || 60) / 100,
      height: (Number(size.height) || 80) / 100,
    };
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
    sprite.scale.set(0.9, 0.34, 1);
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
    crosshair.position.y = 0.006;
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
    const size = sizeMeters(item);
    guide.visible = true;
    guide.position.set(wrapper.position.x, 0.032, wrapper.position.z);
    guide.rotation.y = wrapper.rotation.y;
    guide.children.forEach((child) => {
      if (child.userData.guidePart === "fill" || child.userData.guidePart === "outline" || child.userData.guidePart === "crosshair") {
        child.scale.set(size.width, size.depth, 1);
      }
    });
    if (snapHint) {
      snapHint.position.set(0, 0.06, -size.depth / 2 - 0.18);
    }
    setGuideSnapState(kind);
  }

  function selectWrapper(wrapper, kind = null) {
    selectedWrapper = wrapper || null;
    if (selectedWrapper) {
      updateFootprintGuide(selectedWrapper, kind);
      renderer.domElement.style.cursor = "grab";
      selectedControls.hidden = false;
    } else {
      disposeGuide();
      renderer.domElement.style.cursor = "";
      selectedControls.hidden = true;
    }
  }

  function selectObjectByIndex(index, { focus = true } = {}) {
    const sceneIndex = Number(index) + 1;
    const wrapper = furnitureGroup.children.find(
      (candidate) => candidate.userData.sceneIndex === sceneIndex,
    );
    if (!wrapper) return false;
    selectWrapper(wrapper);
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
    if (dragRaycaster.intersectObjects(furnitureGroup.children, true).length) {
      event.preventDefault();
    }
  });

  renderer.domElement.addEventListener("pointerdown", (event) => {
    if ((event.button !== 0 && event.button !== 2) || !lastSceneData || dragState) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    if (placementRequest && event.button === 0) {
      const callback = placementRequest;
      placementRequest = null;
      renderer.domElement.style.cursor = "";
      if (dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
        callback({
          x: Math.round(planeHit.x * 10000) / 100,
          z: Math.round(planeHit.z * 10000) / 100,
        });
      } else {
        setStatus("沒有點到可擺放的地板，請重新選擇「新增到 3D」。");
      }
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const hits = dragRaycaster.intersectObjects(furnitureGroup.children, true);
    if (!hits.length) {
      selectWrapper(null);
      return;
    }
    const wrapper = wrapperFromObject(hits[0].object);
    if (!wrapper || !wrapper.userData.sceneObject) return;

    selectWrapper(wrapper);
    if (!cameraLocked) {
      setStatus("已選取家具；請先按「鎖定視角並編輯家具」再拖曳。");
      return;
    }
    dragRaycaster.ray.intersectPlane(floorPlane, planeHit);
    dragState = {
      wrapper,
      item: wrapper.userData.sceneObject,
      startPosition: wrapper.position.clone(),
      startRotationDeg: normalizedRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
      pendingRotationDeg: normalizedRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
      grabOffset: planeHit.clone().sub(wrapper.position),
      lastValid: {
        x: wrapper.position.x,
        z: wrapper.position.z,
        rotationDeg: normalizedRotationDeg(wrapper.userData.sceneObject.rotation_y_deg || 0),
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

  // ── 拖曳吸附:靠近牆段時貼齊(留 10cm,大於後端 8cm 邊距故吸附後必過驗證),平時 5cm 格點 ──
  const SNAP_RANGE = 0.3;
  const WALL_GAP = 0;
  const DRAG_GRID = 0.05;

  function normalizedRotationDeg(rotationDeg = 0) {
    return ((Math.round(rotationDeg / 90) * 90) % 360 + 360) % 360;
  }

  function halfExtentsForRotation(item, rotationDeg = 0) {
    const size = sizeMeters(item);
    const radians = (Math.abs(normalizedRotationDeg(rotationDeg) % 180) * Math.PI) / 180;
    return {
      x: (size.width * Math.abs(Math.cos(radians)) + size.depth * Math.abs(Math.sin(radians))) / 2,
      z: (size.width * Math.abs(Math.sin(radians)) + size.depth * Math.abs(Math.cos(radians))) / 2,
    };
  }

  function roomBounds() {
    const floorplan = lastSceneData?.floorplan || {};
    const widthM = Math.max((Number(floorplan.width_cm) || 420) / 100, 2.4);
    const depthM = Math.max((Number(floorplan.depth_cm) || 360) / 100, 2.4);
    return {
      minX: -widthM / 2,
      maxX: widthM / 2,
      minZ: -depthM / 2,
      maxZ: depthM / 2,
      widthM,
      depthM,
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
    const size = sizeMeters(item);
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
    if (lengthSq < 0.0001) return Math.hypot(point.x - a.x, point.z - a.z);
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
    const eps = 0.08;
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
      if (edges.some(([c, d]) => segmentToSegmentDistance(a, b, c, d) < 0.05)) return true;
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
    const floorplan = lastSceneData?.floorplan || {};
    const segments = floorplan.wall_segments || [];
    if (segments.length) return segments;
    // 手動矩形模式沒有牆段資料,用房間四邊當虛擬牆
    const widthM = Math.max((Number(floorplan.width_cm) || 420) / 100, 2.4);
    const depthM = Math.max((Number(floorplan.depth_cm) || 360) / 100, 2.4);
    const hw = widthM / 2;
    const hd = depthM / 2;
    return [
      { start: { x: -hw, z: -hd }, end: { x: hw, z: -hd } },
      { start: { x: hw, z: -hd }, end: { x: hw, z: hd } },
      { start: { x: hw, z: hd }, end: { x: -hw, z: hd } },
      { start: { x: -hw, z: hd }, end: { x: -hw, z: -hd } },
    ];
  }

  function snapDragPosition(item, x, z) {
    const size = sizeMeters(item);
    const radians = (Math.abs((item.rotation_y_deg || 0) % 180) * Math.PI) / 180;
    const w = size.width;
    const d = size.depth;
    const halfW = (w * Math.abs(Math.cos(radians)) + d * Math.abs(Math.sin(radians))) / 2;
    const halfD = (w * Math.abs(Math.sin(radians)) + d * Math.abs(Math.cos(radians))) / 2;

    let bestX = null;
    let bestZ = null;
    for (const seg of wallSegmentsForSnap()) {
      const isVertical = Math.abs(seg.start.x - seg.end.x) < 0.02;   // 沿 z 的牆
      const isHorizontal = Math.abs(seg.start.z - seg.end.z) < 0.02; // 沿 x 的牆
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
      const isVertical = Math.abs(seg.start.x - seg.end.x) < 0.02;
      const isHorizontal = Math.abs(seg.start.z - seg.end.z) < 0.02;
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
      rotationDeg: rotationSource ? rotationSource.rotationDeg : normalizedRotationDeg(item.rotation_y_deg || 0),
    };
  }

  function snapDragPositionV3(item, x, z) {
    let best = null;
    for (const seg of wallSegmentsForSnap()) {
      const ax = Number(seg.start?.x);
      const az = Number(seg.start?.z);
      const bx = Number(seg.end?.x);
      const bz = Number(seg.end?.z);
      if (![ax, az, bx, bz].every(Number.isFinite)) continue;

      const dx = bx - ax;
      const dz = bz - az;
      const lengthSq = dx * dx + dz * dz;
      if (lengthSq < 0.0001) continue;

      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / lengthSq));
      const px = ax + dx * t;
      const pz = az + dz * t;
      const fromWallX = x - px;
      const fromWallZ = z - pz;
      const distance = Math.hypot(fromWallX, fromWallZ);
      if (distance > SNAP_RANGE + 0.28) continue;

      const length = Math.sqrt(lengthSq);
      const normalX = -dz / length;
      const normalZ = dx / length;
      const side = (fromWallX * normalX + fromWallZ * normalZ) >= 0 ? 1 : -1;
      const rotationDeg = normalizedRotationDeg(THREE.MathUtils.radToDeg(Math.atan2(-dz, dx)));
      const half = halfExtentsForRotation(item, rotationDeg);
      const halfNormal = Math.abs(half.x * normalX) + Math.abs(half.z * normalZ);
      const snappedX = px + normalX * side * (halfNormal + WALL_GAP);
      const snappedZ = pz + normalZ * side * (halfNormal + WALL_GAP);
      const score = Math.hypot(x - snappedX, z - snappedZ);

      if (!best || score < best.score) {
        best = { x: snappedX, z: snappedZ, rotationDeg, score };
      }
    }

    if (best) {
      const constrained = constrainTransform(item, best.x, best.z, best.rotationDeg);
      return {
        ...constrained,
        kind: constrained.blocked ? "blocked" : "wall",
        rotationDeg: best.rotationDeg,
      };
    }

    return constrainTransform(
      item,
      Math.round(x / DRAG_GRID) * DRAG_GRID,
      Math.round(z / DRAG_GRID) * DRAG_GRID,
      normalizedRotationDeg(item.rotation_y_deg || 0)
    );
  }

  window.addEventListener("pointermove", (event) => {
    if (!dragState) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    if (dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
      const snapped = snapDragPositionV3(
        dragState.item,
        planeHit.x - dragState.grabOffset.x,
        planeHit.z - dragState.grabOffset.z
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

    const movedM = Math.hypot(wrapper.position.x - startPosition.x, wrapper.position.z - startPosition.z);
    const rotated = normalizedRotationDeg(pendingRotationDeg) !== normalizedRotationDeg(startRotationDeg);
    if (movedM < 0.01 && !rotated) return;  // 只是點選,沒有拖

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const newPositionCm = {
      x: Math.round(wrapper.position.x * 100 * 100) / 100,
      z: Math.round(wrapper.position.z * 100 * 100) / 100,
    };
    setStatus(`正在檢查「${label}」的新位置...`);
    const verdict = await validatePlacement(item, newPositionCm, normalizedRotationDeg(pendingRotationDeg));
    if (verdict.ok) {
      item.position_cm = newPositionCm;
      item.rotation_y_deg = normalizedRotationDeg(pendingRotationDeg);
      updateFootprintGuide(wrapper);
      setStatus(`已移動「${label}」，靠近牆面時會自動貼齊並旋轉。`);
      item.position_locked = true;  // 之後的重排/替換不會沖掉手動位置
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
      selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextRotation);
      updateFootprintGuide(selectedWrapper);
      setStatus(`${label} 已旋轉到 ${nextRotation} 度。`);
      return true;
    }

    setStatus(`${label} 目前不能旋轉：${verdict.reason || "會碰撞或超出可用空間"}。`);
    return false;
  }

  function wrapperPositionCm(wrapper) {
    return {
      x: Math.round(wrapper.position.x * 100 * 100) / 100,
      z: Math.round(wrapper.position.z * 100 * 100) / 100,
    };
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
    const currentPositionCm = wrapperPositionCm(selectedWrapper);
    const candidate = constrainTransform(item, selectedWrapper.position.x, selectedWrapper.position.z, nextRotation);
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
    selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextRotation);
    updateFootprintGuide(selectedWrapper);
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
    const step = 0.1;
    const delta = {
      forward: { x: 0, z: -step },
      back: { x: 0, z: step },
      left: { x: -step, z: 0 },
      right: { x: step, z: 0 },
    }[direction];
    if (!delta) return false;

    const rotationDeg = normalizedRotationDeg(item.rotation_y_deg || 0);
    const candidate = constrainTransform(
      item,
      selectedWrapper.position.x + delta.x,
      selectedWrapper.position.z + delta.z,
      rotationDeg,
      { x: selectedWrapper.position.x, z: selectedWrapper.position.z, rotationDeg, kind: "blocked" }
    );

    if (candidate.blocked) {
      setStatus(`「${label}」不能往那個方向移動，會超出房間或碰到牆。`);
      updateFootprintGuide(selectedWrapper, "blocked");
      return false;
    }

    const nextPositionCm = {
      x: Math.round(candidate.x * 100 * 100) / 100,
      z: Math.round(candidate.z * 100 * 100) / 100,
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
    setStatus(`已微調「${label}」。`);
    return true;
  }

  function selectedObjectLabel(item) {
    return item?.name_zh_raw || item?.normalized_type || "家具";
  }

  function metersToPositionCm(x, z) {
    return {
      x: Math.round(x * 100 * 100) / 100,
      z: Math.round(z * 100 * 100) / 100,
    };
  }

  async function rotateSelectedFromControls(deltaDeg = 15) {
    if (!selectedWrapper || dragState) {
      setStatus("請先點選一件家具。");
      return false;
    }

    const item = selectedWrapper.userData.sceneObject;
    if (!item) return false;
    const label = selectedObjectLabel(item);
    const nextRotation = normalizedRotationDeg((item.rotation_y_deg || 0) + deltaDeg);
    const candidate = constrainTransform(item, selectedWrapper.position.x, selectedWrapper.position.z, nextRotation);
    if (candidate.blocked) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 旋轉後會碰牆或超出房間，已取消。`);
      return false;
    }

    const nextPositionCm = metersToPositionCm(candidate.x, candidate.z);
    setStatus(`${label} 旋轉檢查中...`);
    const verdict = await validatePlacement(item, nextPositionCm, nextRotation);
    if (!verdict.ok) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 目前不能旋轉：${verdict.reason || "位置不合法"}。`);
      return false;
    }

    selectedWrapper.position.set(candidate.x, selectedWrapper.position.y, candidate.z);
    selectedWrapper.rotation.y = THREE.MathUtils.degToRad(nextRotation);
    item.position_cm = nextPositionCm;
    item.rotation_y_deg = nextRotation;
    item.position_locked = true;
    updateFootprintGuide(selectedWrapper, candidate.kind);
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
    const radians = THREE.MathUtils.degToRad(rotationDeg);
    const step = 0.25;
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
      rotationDeg,
      { x: selectedWrapper.position.x, z: selectedWrapper.position.z, rotationDeg, kind: "blocked" }
    );
    if (candidate.blocked) {
      updateFootprintGuide(selectedWrapper, "blocked");
      setStatus(`${label} 不能往這個方向移動，會碰牆或超出房間。`);
      return false;
    }

    const nextPositionCm = metersToPositionCm(candidate.x, candidate.z);
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
    setStatus(`${label} 已移動 ${Math.round(step * 100)} 公分。`);
    return true;
  }

  selectedControls.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
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
    const presentation = viewPresentation(viewMode.mode);
    if (!presentation.hideOccludingWalls) {
      wallMeshes.forEach((wall) => {
        wall.visible = true;
        const materials = Array.isArray(wall.material) ? wall.material : [wall.material];
        materials.filter(Boolean).forEach((material) => {
          material.transparent = false;
          material.opacity = 1;
          material.depthWrite = true;
        });
      });
      return;
    }
    const targetVector = new THREE.Vector3().subVectors(controls.target, camera.position);
    const targetDistance = targetVector.length();
    if (targetDistance < 0.001) return;

    const viewDirection = targetVector.normalize();
    wallMeshes.forEach((wall) => {
      const wallCenter = new THREE.Vector3();
      wall.getWorldPosition(wallCenter);
      const wallVector = wallCenter.sub(camera.position);
      const wallDistance = wallVector.length();
      if (wallDistance < 0.001) return;

      const alignment = wallVector.normalize().dot(viewDirection);
      const wallBlocksRoom = alignment > 0.88 && wallDistance < targetDistance + 0.35;
      const wallTooClose = wallDistance < 1.65;
      const shouldHide = wallBlocksRoom || wallTooClose;
      wall.visible = !shouldHide;
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

  renderer.domElement.addEventListener("pointerdown", beginWalkLook);
  window.addEventListener("pointermove", updateWalkLook);
  window.addEventListener("pointerup", finishWalkLook);
  renderer.domElement.addEventListener("wheel", (event) => {
    if (viewMode.mode !== "walk") return;
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
    resetCamera,
    setCameraPreset,
    setViewMode,
    toggleCameraLock,
    capturePng,
    exportGlb,
    focusObject,
    selectObjectByIndex,
    rotateSelected: rotateSelectedFromControls,
    beginPlacement,
    cancelPlacement,
    toggleCeiling,
    getDiagnostics,
  };
}
