import * as THREE from "three";

export function createAxisLabel(label, color) {
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
    sprite.scale.set(24, 24, 1);
    sprite.renderOrder = 998;
    return sprite;
  }
