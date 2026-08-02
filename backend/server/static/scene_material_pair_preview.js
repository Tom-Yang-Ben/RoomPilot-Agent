import * as THREE from "three";

const previewsByHost = new WeakMap();

function disposePreview(preview) {
  preview.renderer.dispose();
  preview.scene.traverse((item) => {
    if (item.material?.map) item.material.map.dispose();
    if (item.material?.dispose) item.material.dispose();
    if (item.geometry?.dispose) item.geometry.dispose();
  });
}

function materialFor(textureUrl, color, rerender) {
  const material = new THREE.MeshStandardMaterial({ color, roughness: 0.82, side: THREE.DoubleSide });
  if (!textureUrl) return material;
  new THREE.TextureLoader().load(textureUrl, (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(2.4, 1.8);
    material.map = texture;
    material.needsUpdate = true;
    rerender();
  });
  return material;
}

function createPreview(canvas, pair) {
  const width = Math.max(canvas.clientWidth, 180);
  const height = Math.max(canvas.clientHeight, 132);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf1ede6);
  const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 40);
  camera.position.set(5.6, 4.4, 6.5);
  camera.lookAt(0, 1.6, 0);
  const render = () => renderer.render(scene, camera);

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(6.2, 5.4), materialFor(pair.floor.textureUrl, pair.floor.color, render));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const backWall = new THREE.Mesh(new THREE.PlaneGeometry(6.2, 3.8), materialFor(pair.wall.textureUrl, pair.wall.color, render));
  backWall.position.set(0, 1.9, -2.7);
  scene.add(backWall);
  const sideWall = new THREE.Mesh(new THREE.PlaneGeometry(5.4, 3.8), materialFor(pair.wall.textureUrl, pair.wall.color, render));
  sideWall.position.set(-3.1, 1.9, 0);
  sideWall.rotation.y = Math.PI / 2;
  scene.add(sideWall);

  const baseboard = new THREE.Mesh(
    new THREE.BoxGeometry(6.2, 0.08, 0.1),
    new THREE.MeshStandardMaterial({ color: 0x6e6255, roughness: 0.6 }),
  );
  baseboard.position.set(0, 0.04, -2.66);
  scene.add(baseboard);
  scene.add(new THREE.HemisphereLight(0xfff8ed, 0x776a5a, 1.65));
  const key = new THREE.DirectionalLight(0xffefd5, 2.5);
  key.position.set(2.5, 5.5, 3.5);
  scene.add(key);
  const fill = new THREE.PointLight(0xffffff, 11, 12);
  fill.position.set(-1.8, 3.1, 1.5);
  scene.add(fill);
  render();
  return { renderer, scene };
}

export function renderMaterialPairPreviews(host, pairs) {
  (previewsByHost.get(host) || []).forEach(disposePreview);
  const previews = [...host.querySelectorAll("canvas[data-material-pair-preview]")]
    .map((canvas, index) => createPreview(canvas, pairs[index]))
    .filter(Boolean);
  previewsByHost.set(host, previews);
}
