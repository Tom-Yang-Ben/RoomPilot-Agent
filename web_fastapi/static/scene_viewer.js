import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function createSceneViewer(container, statusElement, options = {}) {
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
  controls.target.set(0, 0.8, 0);

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

  const roomGroup = new THREE.Group();
  scene.add(roomGroup);

  const furnitureGroup = new THREE.Group();
  scene.add(furnitureGroup);

  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath("/static/vendor/draco/");

  const loader = new GLTFLoader();
  loader.setDRACOLoader(dracoLoader);

  const surfaceCatalog = options.surfaceCatalog || { walls: [], floors: [] };
  const wallSurfaceMap = new Map((surfaceCatalog.walls || []).map((item) => [item.surface_id, item]));
  const floorSurfaceMap = new Map((surfaceCatalog.floors || []).map((item) => [item.surface_id, item]));
  const textureLoader = new THREE.TextureLoader();
  const textureTemplateCache = new Map();

  const wallMeshes = [];
  const wallRaycaster = new THREE.Raycaster();
  let currentSceneLoadToken = 0;

  function setStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  function disposeMaterialResources(material) {
    if (!material) return;
    ["map", "normalMap", "roughnessMap", "metalnessMap", "alphaMap", "aoMap", "emissiveMap"].forEach((key) => {
      if (material[key]) {
        material[key].dispose();
      }
    });
    material.dispose();
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
        materials.filter(Boolean).forEach(disposeMaterialResources);
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
        position: [0, Math.max(room.widthM, room.depthM) * 1.6 + 3.2, 0.08],
        target: [0, 0.25, 0],
      },
      entrance: {
        position: [0, 1.95, room.depthM / 2 + 1.9],
        target: [0, 1.05, -room.depthM * 0.16],
      },
      corner: {
        position: [room.widthM * 0.9 + 1.8, 3.8, room.depthM * 0.88 + 2.1],
        target: [0, 0.85, 0],
      },
      inside: {
        position: [-room.widthM * 0.28, 1.55, room.depthM * 0.14],
        target: [room.widthM * 0.18, 1.05, -room.depthM * 0.32],
      },
    };

    const selected = presets[preset] || presets.corner;
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

  function createWoodTexture(base, grain, seam, repeatX, repeatY) {
    return makeCanvasTexture({
      repeatX,
      repeatY,
      draw(context, width, height) {
        context.fillStyle = base;
        context.fillRect(0, 0, width, height);

        const plankWidth = width / 7;
        for (let x = 0; x < width; x += plankWidth) {
          context.fillStyle = x / plankWidth % 2 === 0 ? base : `${base}ee`;
          context.fillRect(x, 0, plankWidth, height);

          context.fillStyle = seam;
          context.fillRect(x, 0, 4, height);

          let boardY = 0;
          let stitch = 0;
          while (boardY < height) {
            const boardLength = 120 + ((stitch + x / plankWidth) % 3) * 48;
            context.fillStyle = "rgba(92, 63, 38, 0.18)";
            context.fillRect(x + 1, boardY, plankWidth - 2, 2.4);
            context.fillStyle = "rgba(255, 255, 255, 0.08)";
            context.fillRect(x + 1, boardY + 2.4, plankWidth - 2, 1);
            boardY += boardLength;
            stitch += 1;
          }

          for (let line = 0; line < 18; line += 1) {
            context.strokeStyle = grain;
            context.globalAlpha = 0.1 + Math.random() * 0.08;
            context.lineWidth = 1 + Math.random() * 2.4;
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

          context.fillStyle = grain;
          context.globalAlpha = 0.12;
          context.beginPath();
          context.ellipse(
            x + plankWidth * (0.3 + Math.random() * 0.4),
            height * (0.2 + Math.random() * 0.6),
            8 + Math.random() * 10,
            2 + Math.random() * 4,
            Math.random() * Math.PI,
            0,
            Math.PI * 2
          );
          context.fill();
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
        for (let row = 0; row < 4; row += 1) {
          for (let col = 0; col < 4; col += 1) {
            const tileX = col * tileSize;
            const tileY = row * tileSize;
            context.fillStyle = row % 2 === col % 2 ? `${base}` : "#cec8c1";
            context.globalAlpha = 0.24;
            context.fillRect(tileX, tileY, tileSize, tileSize);
            context.fillStyle = "rgba(255,255,255,0.14)";
            context.fillRect(tileX + 6, tileY + 6, tileSize - 12, tileSize * 0.18);
            context.fillStyle = "rgba(88,82,77,0.08)";
            context.fillRect(tileX + 6, tileY + tileSize * 0.72, tileSize - 12, tileSize * 0.16);
          }
        }
        context.strokeStyle = seam;
        context.lineWidth = 5;
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

        for (let i = 0; i < 30; i += 1) {
          context.strokeStyle = vein;
          context.globalAlpha = 0.07 + Math.random() * 0.05;
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
        gradient.addColorStop(1, "#f7efe3");
        context.fillStyle = gradient;
        context.fillRect(0, 0, width, height);

        const tileSize = width / 3;
        context.strokeStyle = seam;
        context.lineWidth = 4;
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

        for (let i = 0; i < 42; i += 1) {
          context.strokeStyle = i % 5 === 0 ? accent : vein;
          context.globalAlpha = i % 5 === 0 ? 0.32 : 0.14;
          context.lineWidth = i % 5 === 0 ? 3.2 : 1.4;
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

        for (let i = 0; i < 18; i += 1) {
          context.fillStyle = i % 2 === 0 ? accent : "#d9c5ac";
          context.globalAlpha = 0.08;
          context.beginPath();
          context.arc(Math.random() * width, Math.random() * height, 24 + Math.random() * 42, 0, Math.PI * 2);
          context.fill();
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
          context.globalAlpha = 0.04 + Math.random() * 0.04;
          context.lineWidth = 10 + Math.random() * 18;
          const x = Math.random() * width;
          context.beginPath();
          context.moveTo(x, 0);
          context.lineTo(x + Math.random() * 18 - 9, height);
          context.stroke();
        }

        for (let i = 0; i < 28; i += 1) {
          context.fillStyle = accent;
          context.globalAlpha = 0.03 + Math.random() * 0.04;
          context.beginPath();
          context.arc(Math.random() * width, Math.random() * height, 24 + Math.random() * 72, 0, Math.PI * 2);
          context.fill();
        }
        context.globalAlpha = 1;
      },
    });
  }

  function getSurfaceRecord(kind, surfaceId) {
    const map = kind === "wall" ? wallSurfaceMap : floorSurfaceMap;
    return map.get(surfaceId) || map.get("auto") || null;
  }

  async function loadTextureTemplate(textureUrl) {
    if (!textureUrl) return null;

    if (!textureTemplateCache.has(textureUrl)) {
      textureTemplateCache.set(
        textureUrl,
        textureLoader.loadAsync(textureUrl).then((texture) => {
          texture.colorSpace = THREE.SRGBColorSpace;
          return texture;
        })
      );
    }

    return textureTemplateCache.get(textureUrl);
  }

  async function createRepeatedTexture(textureUrl, repeatX = 4, repeatY = 4) {
    const template = await loadTextureTemplate(textureUrl);
    if (!template) return null;

    const texture = template.clone();
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(repeatX, repeatY);
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    texture.needsUpdate = true;
    return texture;
  }

  async function createFloorMaterial(floorOption) {
    const surface = getSurfaceRecord("floor", floorOption) || getSurfaceRecord("floor", "auto");
    const repeatX = surface?.repeat_x ?? 4;
    const repeatY = surface?.repeat_y ?? 4;
    const hasTexture = Boolean(surface?.texture_url);
    const materialConfig = {
      color: new THREE.Color(hasTexture ? "#ffffff" : surface?.base_hex || surface?.preview_hex || "#e6d1ae"),
      roughness: surface?.roughness ?? 0.9,
      metalness: surface?.metalness ?? 0.01,
    };

    if (hasTexture) {
      const map = await createRepeatedTexture(surface.texture_url, repeatX, repeatY);
      if (map) {
        return new THREE.MeshStandardMaterial({
          ...materialConfig,
          map,
        });
      }
    }

    const presets = {
      auto: () => createWoodTexture("#e3c99f", "#b48d63", "#cfb288", repeatX, repeatY),
      light_oak: () => createWoodTexture("#e7cca1", "#be9871", "#d7b58c", repeatX, repeatY),
      medium_oak: () => createWoodTexture("#c9aa84", "#9c7756", "#e0c29b", repeatX, repeatY),
      herringbone_oak: () => createHerringboneTexture("#e9cda3", "#ad8054", "#d0ad82", repeatX, repeatY),
      walnut: () => createWoodTexture("#7b563a", "#4d3221", "#8f694a", repeatX, repeatY),
      white_oak_tile: () => createWoodTexture("#ddc79f", "#b69368", "#e7d1ac", repeatX, repeatY),
      smoked_walnut_tile: () => createWoodTexture("#8d6545", "#5b3a27", "#a37c58", repeatX, repeatY),
      stone_gray: () => createStoneTexture("#d6d2cd", "#bdb7b2", "#f0ece7", repeatX, repeatY),
      stone_beige: () => createStoneTexture("#d5c3ab", "#b49a7f", "#efe1cf", repeatX, repeatY),
      marble: () => createMarbleTexture("#f8f5ef", "#9d968d", "#c6aa82", "#efe7dc", repeatX, repeatY),
      marble_gray: () => createMarbleTexture("#ddd7d1", "#9b958f", "#bfb5ad", "#f1eeea", repeatX, repeatY),
      microcement: () => createMicrocementTexture("#beb4aa", "#948a80", repeatX, repeatY),
    };

    return new THREE.MeshStandardMaterial({
      ...materialConfig,
      map: (presets[floorOption] ?? presets.auto)(),
    });
  }

  function createWallMaterial(wallOption) {
    const surface = getSurfaceRecord("wall", wallOption) || getSurfaceRecord("wall", "auto");
    const base = surface?.base_hex || surface?.preview_hex || "#f5efe7";
    const accent = surface?.accent_hex || "#d8cebf";
    const material = new THREE.MeshStandardMaterial({
      color: new THREE.Color(base),
      map: createWallTexture(base, accent, 2.2, 1.6),
      roughness: surface?.surface_id === "charcoal" || surface?.surface_id === "graphite_gray" ? 0.94 : 0.98,
      metalness: 0.01,
      side: THREE.DoubleSide,
    });
    material.transparent = true;
    material.opacity = 0.92;
    material.depthWrite = true;
    return material;
  }

  function registerWall(wallMesh, options = {}) {
    const baseOpacity = options.baseOpacity ?? 0.92;
    const fadeOpacity = options.fadeOpacity ?? 0.16;

    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = baseOpacity;
    wallMesh.userData.fadeOpacity = fadeOpacity;
    wallMesh.userData.isDxfWall = Boolean(options.isDxfWall);

    const materials = Array.isArray(wallMesh.material) ? wallMesh.material : [wallMesh.material];
    materials.filter(Boolean).forEach((material) => {
      material.transparent = true;
      material.opacity = baseOpacity;
      material.depthWrite = baseOpacity > 0.34;
    });

    wallMeshes.push(wallMesh);
    return wallMesh;
  }

  function buildSegmentWalls(roomGroupRef, segments, wallMaterial, wallHeight, wallThickness, options = {}) {
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
      roomGroupRef.add(registerWall(wallMesh, options));
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

  async function createRoom(sceneData, loadToken) {
    clearGroup(roomGroup);
    wallMeshes.length = 0;

    const widthM = Math.max(sceneData.floorplan.width_cm / 100, 2.4);
    const depthM = Math.max(sceneData.floorplan.depth_cm / 100, 2.4);
    const wallHeight = 2.7;
    const floorOption = sceneData.design_choices?.floor_option || "auto";
    const wallOption = sceneData.design_choices?.wall_option || "auto";

    const floorMaterial = await createFloorMaterial(floorOption);
    if (loadToken !== currentSceneLoadToken) {
      disposeMaterialResources(floorMaterial);
      return false;
    }

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(widthM, depthM), floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    roomGroup.add(floor);

    const wallMaterial = createWallMaterial(wallOption);
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const planSegments = sceneData.floorplan?.plan_segments || [];
    const doorSegments = sceneData.floorplan?.door_segments || [];
    const windowSegments = sceneData.floorplan?.window_segments || [];
    const isDxfFloorplan = sceneData.floorplan?.source === "dxf";
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthM, depthM, wallHeight };

    const wallThickness = isDxfFloorplan ? 0.12 : 0.04;
    const dxfWallSegments = wallSegments.length >= 2 ? wallSegments : planSegments;
    const shouldUseDxfWalls = isDxfFloorplan && dxfWallSegments.length >= 2;
    if (shouldUseDxfWalls) {
      buildSegmentWalls(roomGroup, dxfWallSegments, wallMaterial, wallHeight, wallThickness, {
        isDxfWall: true,
        baseOpacity: 0.98,
        fadeOpacity: 0.32,
      });
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
    return true;
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
    const loadToken = ++currentSceneLoadToken;
    clearGroup(furnitureGroup);
    setStatus("載入 3D 場景中...");

    const roomCreated = await createRoom(sceneData, loadToken);
    if (!roomCreated || loadToken !== currentSceneLoadToken) {
      return;
    }
    setStatus("正在生成 3D 場景...");

    const objects = sceneData.scene_objects || [];
    const failures = [];

    await Promise.all(
      objects.map(async (item, index) => {
        if (loadToken !== currentSceneLoadToken) return;

        if (!item.model_url) {
          failures.push(`${item.name_zh_raw || item.normalized_type} 無模型`);
          return;
        }

        try {
          const gltf = await loader.loadAsync(item.model_url);
          if (loadToken !== currentSceneLoadToken) return;
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
          if (loadToken !== currentSceneLoadToken) return;
          console.error(error);
          failures.push(item.name_zh_raw || item.normalized_type || "未知家具");
        }
      })
    );

    if (loadToken !== currentSceneLoadToken) {
      return;
    }

    if (failures.length) {
      setStatus(`場景已生成，但部分家具未載入：${failures.join("、")}`);
    } else {
      setStatus("場景已生成，可拖曳查看家具配置。");
    }
    if (failures.length) {
      statusElement && (statusElement.textContent = `場景已更新，但以下家具載入失敗：${failures.join("、")}`);
    } else {
      statusElement && (statusElement.textContent = "場景已更新，可直接拖曳、縮放與旋轉視角。");
    }
  }

  function updateWallVisibility() {
    const targetVector = new THREE.Vector3().subVectors(controls.target, camera.position);
    const targetDistance = targetVector.length();
    if (targetDistance < 0.001) return;

    const viewDirection = targetVector.normalize();
    wallRaycaster.set(camera.position, viewDirection);
    wallRaycaster.far = targetDistance;
    const blockingWalls = new Set(
      wallRaycaster.intersectObjects(wallMeshes, false).map((hit) => hit.object)
    );

    wallMeshes.forEach((wall) => {
      const wallCenter = new THREE.Vector3();
      wall.getWorldPosition(wallCenter);
      const wallVector = wallCenter.sub(camera.position);
      const wallDistance = wallVector.length();
      if (wallDistance < 0.001) return;

      const alignment = wallVector.normalize().dot(viewDirection);
      const wallBlocksRoom = blockingWalls.has(wall);
      const closeInFront = alignment > 0.35 && wallDistance < (wall.userData.isDxfWall ? 0.75 : 1.25);
      const targetOpacity = wallBlocksRoom || closeInFront
        ? wall.userData.fadeOpacity || 0.16
        : wall.userData.baseOpacity || 0.92;
      const materials = Array.isArray(wall.material) ? wall.material : [wall.material];

      materials.filter(Boolean).forEach((material) => {
        material.transparent = true;
        material.opacity += (targetOpacity - material.opacity) * 0.18;
        material.depthWrite = material.opacity > (wall.userData.isDxfWall ? 0.28 : 0.38);
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

  return { loadScene, resetCamera, setCameraPreset, focusObject };
}
