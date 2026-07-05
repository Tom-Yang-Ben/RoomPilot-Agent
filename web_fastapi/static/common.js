export async function fetchSiteData() {
  const response = await fetch("/api/site-data");
  return response.json();
}

export function formatList(items = []) {
  return items.filter(Boolean).join("、");
}

export function formatSize(size) {
  if (!size) return "未提供尺寸";
  const width = size.width ?? size.w ?? "-";
  const depth = size.depth ?? size.d ?? "-";
  const height = size.height ?? size.h ?? "-";
  return `${width} × ${depth} × ${height} cm`;
}

export function styleNameMap(styles) {
  return new Map(styles.map((style) => [style.style_id, style.style_name_zh]));
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
