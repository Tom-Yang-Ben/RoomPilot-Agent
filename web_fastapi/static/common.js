export async function fetchSiteData() {
  const response = await fetch("/api/site-data");
  return response.json();
}

export function formatList(items = []) {
  return items.filter(Boolean).join("、");
}

export function formatSize(size) {
  if (!size) return "未提供";
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

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    particles = Array.from({ length: Math.min(84, Math.floor(window.innerWidth / 22)) }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.8 + 0.4,
      speedX: (Math.random() - 0.5) * 0.18,
      speedY: (Math.random() - 0.5) * 0.18,
      glow: Math.random() * 0.5 + 0.3,
    }));
  }

  function animate() {
    context.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach((particle) => {
      particle.x += particle.speedX + (pointer.x - canvas.width / 2) * 0.00002;
      particle.y += particle.speedY + (pointer.y - canvas.height / 2) * 0.00002;

      if (particle.x < 0) particle.x = canvas.width;
      if (particle.x > canvas.width) particle.x = 0;
      if (particle.y < 0) particle.y = canvas.height;
      if (particle.y > canvas.height) particle.y = 0;

      const gradient = context.createRadialGradient(particle.x, particle.y, 0, particle.x, particle.y, particle.radius * 10);
      gradient.addColorStop(0, `rgba(255,255,255,${particle.glow})`);
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(particle.x, particle.y, particle.radius * 10, 0, Math.PI * 2);
      context.fill();
    });

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
