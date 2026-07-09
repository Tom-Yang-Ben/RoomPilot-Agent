import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import {
  buildFloorPlanOverlay,
  buildSegmentWalls,
  buildWindowBoxes,
  clearGroup,
  createFloorMaterial,
  createWallMaterial,
  fitToTargetSize,
} from "./scene_builders.js?v=20260709a";

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

  function focusObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const distance = Math.max(size.x, size.y, size.z, 1) * 2.4;
    camera.position.set(center.x + distance, center.y + distance * 0.72, center.z + distance);
    controls.target.copy(center);
    controls.update();
  }

  function registerWall(wallMesh) {
    wallMesh.castShadow = true;
    wallMesh.receiveShadow = true;
    wallMesh.userData.baseOpacity = 0.92;
    wallMeshes.push(wallMesh);
    return wallMesh;
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
      createFloorMaterial(renderer, floorOption)
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    roomGroup.add(floor);

    // 編輯視角的牆維持半透明,配合鏡頭遮擋自動淡出;環景頁另外用全實心牆
    const wallMaterial = createWallMaterial(renderer, wallOption);
    wallMaterial.transparent = true;
    wallMaterial.opacity = 0.92;
    wallMaterial.depthWrite = true;
    const wallSegments = sceneData.floorplan?.wall_segments || [];
    const planSegments = sceneData.floorplan?.plan_segments || [];
    const doorSegments = sceneData.floorplan?.door_segments || [];
    const windowSegments = sceneData.floorplan?.window_segments || [];
    const isDxfFloorplan = sceneData.floorplan?.source === "dxf";
    const singleRoomMode = sceneData.design_choices?.single_room_mode !== false;
    roomGroup.userData.roomSize = { widthM, depthM, wallHeight };

    const wallThickness = 0.04;
    if (!singleRoomMode && wallSegments.length >= 2) {
      buildSegmentWalls(roomGroup, wallSegments, wallMaterial, wallHeight, wallThickness, registerWall);
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
      buildWindowBoxes(roomGroup, windowSegments, wallHeight);
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

  const dragRaycaster = new THREE.Raycaster();
  const pointerNdc = new THREE.Vector2();
  const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const planeHit = new THREE.Vector3();

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
      selectedWrapper = null;
      return;
    }
    const wrapper = wrapperFromObject(hits[0].object);
    if (!wrapper || !wrapper.userData.sceneObject) return;

    selectedWrapper = wrapper;
    dragRaycaster.ray.intersectPlane(floorPlane, planeHit);
    dragState = {
      wrapper,
      item: wrapper.userData.sceneObject,
      startPosition: wrapper.position.clone(),
      grabOffset: planeHit.clone().sub(wrapper.position),
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
  const WALL_GAP = 0.1;
  const DRAG_GRID = 0.05;

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
    const size = item.size_cm || {};
    const radians = (Math.abs((item.rotation_y_deg || 0) % 180) * Math.PI) / 180;
    const w = (Number(size.width) || 120) / 100;
    const d = (Number(size.depth) || 60) / 100;
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

    return {
      x: bestX ? bestX.value : Math.round(x / DRAG_GRID) * DRAG_GRID,
      z: bestZ ? bestZ.value : Math.round(z / DRAG_GRID) * DRAG_GRID,
    };
  }

  window.addEventListener("pointermove", (event) => {
    if (!dragState) return;
    pointerToNdc(event);
    dragRaycaster.setFromCamera(pointerNdc, camera);
    if (dragRaycaster.ray.intersectPlane(floorPlane, planeHit)) {
      const snapped = snapDragPosition(
        dragState.item,
        planeHit.x - dragState.grabOffset.x,
        planeHit.z - dragState.grabOffset.z
      );
      dragState.wrapper.position.x = snapped.x;
      dragState.wrapper.position.z = snapped.z;
    }
  });

  window.addEventListener("pointerup", async () => {
    if (!dragState) return;
    const { wrapper, item, startPosition, materials } = dragState;
    dragState = null;
    materials.forEach(({ material, opacity, transparent }) => {
      material.opacity = opacity;
      material.transparent = transparent;
    });
    controls.enabled = true;
    renderer.domElement.style.cursor = "";

    const movedM = Math.hypot(wrapper.position.x - startPosition.x, wrapper.position.z - startPosition.z);
    if (movedM < 0.01) return;  // 只是點選,沒有拖

    const label = item.name_zh_raw || item.normalized_type || "家具";
    const newPositionCm = {
      x: Math.round(wrapper.position.x * 100 * 100) / 100,
      z: Math.round(wrapper.position.z * 100 * 100) / 100,
    };
    setStatus(`正在檢查「${label}」的新位置...`);
    const verdict = await validatePlacement(item, newPositionCm, item.rotation_y_deg || 0);
    if (verdict.ok) {
      item.position_cm = newPositionCm;
      item.position_locked = true;  // 之後的重排/替換不會沖掉手動位置
      setStatus(`已移動「${label}」。`);
    } else {
      wrapper.position.copy(startPosition);
      setStatus(`⚠ 「${label}」無法放在那裡：${verdict.reason || "位置不合法"}，已彈回原位。`);
    }
  });

  window.addEventListener("keydown", async (event) => {
    if (event.key !== "r" && event.key !== "R") return;
    const tag = event.target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
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

  return { loadScene, resetCamera, setCameraPreset, focusObject };
}
