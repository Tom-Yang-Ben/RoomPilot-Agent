import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function createSceneViewer(container, statusElement) {
  if ("createImageBitmap" in globalThis) {
    globalThis.createImageBitmap = undefined;
  }

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8f4ef);

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 200);
  camera.position.set(5.5, 4.6, 6.8);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 1.4;
  controls.maxDistance = 18;
  controls.zoomSpeed = 0.85;
  controls.target.set(0, 0.8, 0);
  let activeCameraPreset = "corner";

  function applyCameraControlMode(preset) {
    activeCameraPreset = preset;
    const isInside = preset === "inside";
    controls.enablePan = !isInside;
    controls.enableZoom = !isInside;
    controls.minDistance = isInside ? 1.25 : 1.4;
    controls.maxDistance = isInside ? 3.4 : 18;
    controls.minPolarAngle = isInside ? Math.PI * 0.38 : 0;
    controls.maxPolarAngle = isInside ? Math.PI * 0.62 : Math.PI;
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

  const grid = new THREE.GridHelper(12, 48, 0xc6ad8e, 0xe8ddcf);
  grid.position.y = -0.01;
  grid.material.transparent = true;
  grid.material.opacity = 0.16;
  scene.add(grid);

  const axes = new THREE.AxesHelper(1.4);
  axes.position.set(-4.7, 0.02, 4.7);
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
    scene.add(sprite);
  });

  const roomGroup = new THREE.Group();
  scene.add(roomGroup);

  const furnitureGroup = new THREE.Group();
  scene.add(furnitureGroup);

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
    setCameraPreset("corner");
  }

  function setCameraPreset(preset = "corner") {
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
    const scale = root.scale.x || 1;
    const localOffset = new THREE.Vector3(-center.x / scale, -box.min.y / scale, -center.z / scale);
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
    const material = new THREE.MeshStandardMaterial({
      color: options.color ?? 0xffffff,
      map: createImageTexture(surface, usage, options.repeat),
      roughness: options.roughness ?? 0.9,
      metalness: options.metalness ?? 0.01,
      side: options.side ?? THREE.FrontSide,
    });
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

      const wallMesh = new THREE.Mesh(new THREE.BoxGeometry(length, wallHeight, wallThickness), wallMaterial.clone());
      wallMesh.position.set((start.x + end.x) / 2, wallHeight / 2, (start.z + end.z) / 2);
      wallMesh.rotation.y = Math.atan2(-dz, dx);
      roomGroupRef.add(registerWall(wallMesh));
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

  function createRoom(sceneData) {
    clearGroup(roomGroup);
    wallMeshes.length = 0;

    const widthM = Math.max(sceneData.floorplan.width_cm / 100, 2.4);
    const depthM = Math.max(sceneData.floorplan.depth_cm / 100, 2.4);
    const wallHeight = 2.7;
    const floorOption = sceneData.design_choices?.floor_option || "auto";
    const wallOption = sceneData.design_choices?.wall_option || "auto";

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(widthM, depthM),
      createFloorMaterial(floorOption, sceneData.surface_catalog, { widthM, depthM })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    roomGroup.add(floor);

    const wallMaterial = createWallMaterial(wallOption, sceneData.surface_catalog);
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const planSegments = sceneData.floorplan?.plan_segments || [];
    const doorSegments = sceneData.floorplan?.door_segments || [];
    const windowSegments = sceneData.floorplan?.window_segments || [];
    const isDxfFloorplan = sceneData.floorplan?.source === "dxf";
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthM, depthM, wallHeight };

    const wallThickness = 0.04;
    if (!singleRoomMode && wallSegments.length >= 2) {
      buildSegmentWalls(roomGroup, wallSegments, wallMaterial, wallHeight, wallThickness);
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

    if (isDxfFloorplan) {
      buildFloorPlanOverlay(roomGroup, planSegments.length ? planSegments : wallSegments, 0x6b513b, 0.32, 0.022);
      buildFloorPlanOverlay(roomGroup, doorSegments, 0xb9773f, 0.82, 0.038);
      buildFloorPlanOverlay(roomGroup, windowSegments, 0x6f9eb4, 0.9, 0.044);
    } else {
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(widthM, wallHeight, depthM)),
        new THREE.LineBasicMaterial({ color: 0xb89264, transparent: true, opacity: 0.35 })
      );
      outline.position.set(0, wallHeight / 2, 0);
      roomGroup.add(outline);
    }

    controls.target.set(0, 0.9, 0);
    setCameraPreset("corner");
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

    const ratios = [];
    if (size.x > 0.001) ratios.push(target.width / size.x);
    if (size.z > 0.001) ratios.push(target.depth / size.z);
    if (size.y > 0.001) ratios.push(target.height / size.y);

    const scale = Math.min(...ratios.filter((value) => Number.isFinite(value) && value > 0), 1);
    root.scale.setScalar(scale);
    root.updateMatrixWorld(true);
    moveModelToFootprintCenter(root);
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

  async function loadScene(sceneData) {
    lastSceneData = sceneData;
    dragState = null;
    selectedWrapper = null;
    selectedControls.hidden = true;
    disposeGuide();
    clearGroup(furnitureGroup);
    createRoom(sceneData);
    setStatus("正在生成 3D 場景...");

    const objects = sceneData.scene_objects || [];
    const failures = [];

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
          furnitureGroup.add(wrapper);
        } catch (error) {
          console.error(error);
          failures.push(item.name_zh_raw || item.normalized_type || "未知家具");
        }
      })
    );

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

  const dragRaycaster = new THREE.Raycaster();
  const pointerNdc = new THREE.Vector2();
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const planeHit = new THREE.Vector3();
  const selectedControls = document.createElement("div");
  selectedControls.className = "scene-object-controls";
  selectedControls.hidden = true;
  selectedControls.innerHTML = `
    <div class="scene-object-controls-title">單件家具微調</div>
    <div class="scene-object-controls-grid">
      <button type="button" data-object-move="forward">前</button>
      <button type="button" data-object-rotate="-90">左轉</button>
      <button type="button" data-object-rotate="90">右轉</button>
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
    const hits = dragRaycaster.intersectObjects(furnitureGroup.children, true);
    if (!hits.length) {
      selectWrapper(null);
      return;
    }
    const wrapper = wrapperFromObject(hits[0].object);
    if (!wrapper || !wrapper.userData.sceneObject) return;

    selectWrapper(wrapper);
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

  async function rotateSelectedFromControls(deltaDeg = 90) {
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
      await rotateSelectedFromControls(Number(rotateButton.dataset.objectRotate) || 90);
    }
  });

  window.addEventListener("keydown", async (event) => {
    if (event.key !== "r" && event.key !== "R") return;
    const tag = event.target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    event.preventDefault();
    await rotateSelectedFromControls(event.shiftKey ? -90 : 90);
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
      const targetOpacity = wallBlocksRoom || wallTooClose ? 0.16 : wall.userData.baseOpacity || 0.92;
      const materials = Array.isArray(wall.material) ? wall.material : [wall.material];

      materials.filter(Boolean).forEach((material) => {
        material.transparent = true;
        material.opacity += (targetOpacity - material.opacity) * 0.14;
        material.depthWrite = material.opacity > 0.38;
      });
    });
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
    controls.update();
    updateWallVisibility();
    renderer.render(scene, camera);
  });

  return { loadScene, resetCamera, setCameraPreset, focusObject, rotateSelected: rotateSelectedFromControls };
}
