export async function fetchSiteData() {
  const response = await fetch("/api/site-data");
  return response.json();
}

export function formatList(items = []) {
  return items.filter(Boolean).join(" / ");
}

export function formatSize(size) {
  if (!size) return "未提供";

  const values = [size.width ?? size.w, size.depth ?? size.d, size.height ?? size.h]
    .map((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
    })
    .filter((value) => value !== null);

  if (!values.length) return "未提供";
  return `${values.join(" × ")} cm`;
}

export const TYPE_LABELS = {
  armchair: "扶手椅",
  "bar-table": "吧台桌",
  bed: "床",
  "bed-frame": "床架",
  "bedside-table": "床頭櫃",
  bookcase: "書櫃",
  "cabinets-cupboard": "櫃體",
  "chests-of-drawer": "抽屜櫃",
  "childrens-furniture": "兒童家具",
  "childrens-rugs-curtain": "兒童地毯與窗簾",
  "childrens-stools-benche": "兒童凳椅",
  "childrens-table": "兒童桌",
  "clothes-rack": "衣架",
  "coffee-table": "茶几",
  decoration: "裝飾擺件",
  desk: "書桌",
  "dining-chair": "餐椅",
  "dining-table": "餐桌",
  "display-cabinet": "展示櫃",
  "door-mat": "門墊",
  "floor-lamp": "落地燈",
  "flower-pots-planter": "花盆植栽",
  "gaming-chair": "電競椅",
  "handmade-rug": "手工地毯",
  "kids-chairs-stool": "兒童椅凳",
  lamp: "燈具",
  "lamp-shades-base": "燈罩與燈座",
  "large-medium-rug": "中大型地毯",
  "large-mirror": "大型鏡",
  mattress: "床墊",
  mirror: "鏡子",
  "mirror-cabinet": "鏡櫃",
  "modular-sofa": "模組沙發",
  "office-chair": "辦公椅",
  "outdoor-coffee-side-table": "戶外咖啡邊桌",
  "outdoor-dining": "戶外餐桌組",
  "outdoor-furniture": "戶外家具",
  "outdoor-rug": "戶外地毯",
  "outdoor-seating": "戶外座椅",
  "pax-wardrobe": "衣櫃",
  "room-divider": "屏風隔間",
  "round-rug": "圓形地毯",
  rug: "地毯",
  "runner-small-rug": "長形地毯",
  "sheepskins-cowhide": "羊皮與皮毛毯",
  "shelving-unit": "層架",
  "side-table": "邊桌",
  sideboard: "邊櫃",
  sofa: "沙發",
  "sofa-bed": "沙發床",
  "standing-mirror": "立鏡",
  "stool-bench": "凳子／長凳",
  "storage-boxes-basket": "收納盒籃",
  "storage-furniture": "收納家具",
  "storage-solution-system": "收納系統",
  "sun-loungers-hammock": "躺椅與吊床",
  table: "桌子",
  "table-lamp": "檯燈",
  trolley: "推車",
  "tv-bench": "電視櫃",
  "tv-media-furniture": "電視與影音家具",
  "wall-mirror": "壁鏡",
  "wall-shelf": "壁架",
  wardrobe: "衣櫥",
  "work-lamp": "工作燈",
};

export function formatTypeLabel(typeName) {
  return TYPE_LABELS[typeName] || typeName || "未分類";
}

export function styleNameMap(styles) {
  return new Map(styles.map((style) => [style.style_id, style.style_name_zh]));
}

export function scrollPageTop(target = null, offset = 24) {
  const anchor =
    target instanceof Element
      ? target
      : document.querySelector("main") || document.querySelector(".page-shell") || document.body;
  const top = Math.max(0, window.scrollY + anchor.getBoundingClientRect().top - offset);

  window.scrollTo({ top, behavior: "smooth" });
  if (document.scrollingElement) {
    document.scrollingElement.scrollTop = top;
  }
  if (document.documentElement) {
    document.documentElement.scrollTop = top;
  }
  if (document.body) {
    document.body.scrollTop = top;
  }
}

export function initBackgroundFx() {
  const canvas = document.getElementById("fx-canvas");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.4 };
  let particles = [];
  let blueprintLines = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    particles = Array.from({ length: Math.min(56, Math.floor(window.innerWidth / 28)) }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.8 + 0.6,
      speedX: (Math.random() - 0.5) * 0.16,
      speedY: (Math.random() - 0.5) * 0.16,
      glow: Math.random() * 0.35 + 0.12,
    }));

    blueprintLines = Array.from({ length: 12 }, (_, index) => ({
      x: (index / 12) * canvas.width,
      y: ((index % 4) / 4) * canvas.height * 0.72 + 80,
      w: 120 + (index % 3) * 90,
      h: 70 + (index % 4) * 42,
    }));
  }

  function drawGlowParticles() {
    particles.forEach((particle) => {
      particle.x += particle.speedX + (pointer.x - canvas.width / 2) * 0.000015;
      particle.y += particle.speedY + (pointer.y - canvas.height / 2) * 0.000015;

      if (particle.x < 0) particle.x = canvas.width;
      if (particle.x > canvas.width) particle.x = 0;
      if (particle.y < 0) particle.y = canvas.height;
      if (particle.y > canvas.height) particle.y = 0;

      const gradient = context.createRadialGradient(
        particle.x,
        particle.y,
        0,
        particle.x,
        particle.y,
        particle.radius * 10
      );
      gradient.addColorStop(0, `rgba(255,255,255,${particle.glow})`);
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(particle.x, particle.y, particle.radius * 10, 0, Math.PI * 2);
      context.fill();
    });
  }

  function drawBlueprintLines() {
    if (document.body.dataset.page !== "home") return;

    context.save();
    context.strokeStyle = "rgba(206, 183, 156, 0.14)";
    context.lineWidth = 1;
    blueprintLines.forEach((line) => {
      context.strokeRect(line.x, line.y, line.w, line.h);
      context.beginPath();
      context.moveTo(line.x + line.w * 0.28, line.y);
      context.lineTo(line.x + line.w * 0.28, line.y + line.h);
      context.moveTo(line.x, line.y + line.h * 0.52);
      context.lineTo(line.x + line.w, line.y + line.h * 0.52);
      context.stroke();
    });
    context.restore();
  }

  function animate() {
    context.clearRect(0, 0, canvas.width, canvas.height);
    drawBlueprintLines();
    drawGlowParticles();
    requestAnimationFrame(animate);
  }

  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  });

  resize();
  animate();
}
