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

  function createFloorMaterial(floorOption) {
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

  function createWallMaterial(wallOption) {
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
    material.transparent = true;
    material.opacity = 0.92;
    material.depthWrite = true;
    return material;
  }

  function registerWall(wallMesh) {
    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = 0.92;
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
      createFloorMaterial(floorOption)
    );
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
    clearGroup(furnitureGroup);
    createRoom(sceneData);
    setStatus("正在生成 3D 場景...");

    const objects = sceneData.scene_objects || [];
    const failures = [];

    await Promise.all(
      objects.map(async (item, index) => {
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
      setStatus("場景已生成，可拖曳查看家具配置。");
    }
  }

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

  return { loadScene, resetCamera, setCameraPreset, focusObject };
}
