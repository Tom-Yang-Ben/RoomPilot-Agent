import * as THREE from "three";
import {
  architecturalPbrProfile,
  surfacePbrProfile,
  surfaceTint,
} from "./scene_pbr_contracts.js?v=sha256-d695a0f07d33";

export function createSurfaceMaterialFactory({ textureLoader }) {
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

  function findSurface(surfaceCatalog, surfaceId, usage) {
    return (surfaceCatalog?.surfaces || []).find(
      (surface) => surface.surface_id === surfaceId && surface.usage?.includes(usage)
    );
  }

  function findSurfaceTexture(surfaceCatalog, surfaceId) {
    return (surfaceCatalog?.surfaces || []).find(
      (surface) => surface.surface_id === surfaceId && surface.texture_url,
    ) || null;
  }

  function getSurfaceModuleSize(surface, usage) {
    if (usage !== "floor") return { x: 180, y: 180 };
    const physicalSize = String(surface.source_size || "")
      .match(/([\d.]+)\s*x\s*([\d.]+)\s*cm/i);
    if (physicalSize) {
      return {
        x: Math.max(45, Number(physicalSize[1])),
        y: Math.max(45, Number(physicalSize[2])),
      };
    }
    if (surface.category === "tile") return { x: 60, y: 60 };
    if (surface.category === "wood_tile") return { x: 90, y: 90 };
    return { x: 240, y: 240 };
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

  // 房殼牆/地/門的面材每次 createRoom 都重建;若每次都 textureLoader.load 就會
  // 重新解碼並重傳 GPU,逐房切換材質、套材質時整場卡頓。以 url+用途+平鋪+色彩空間
  // 為鍵快取 THREE.Texture,跨 createRoom 共用同一顆 GPU 貼圖。型錄面材有限(數種
  // 牆/地 + 一張門木紋),故不設淘汰。ponytail: 型錄若暴增再加 LRU。
  const surfaceTextureCache = new Map();

  function createImageTexture(
    surface, usage, repeatOverride = null, colorSpace = THREE.SRGBColorSpace,
  ) {
    const repeat = repeatOverride || surface.repeat?.[usage] || (usage === "floor" ? [4, 4] : [2.2, 1.6]);
    const rx = Number(repeat[0]) || 1;
    const ry = Number(repeat[1]) || 1;
    // 色彩空間入鍵:colorMap(SRGB)與 bumpMap(NoColorSpace)同 url/平鋪但不可共用
    // 同一顆,否則其一改色彩空間會污染另一顆。
    const key = `${surface.texture_url}|${usage}|${rx}x${ry}|${colorSpace}`;
    const cached = surfaceTextureCache.get(key);
    if (cached) return cached;
    const texture = textureLoader.load(surface.texture_url);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(rx, ry);
    texture.colorSpace = colorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    // clearGroup→disposeObjectTree 會 dispose 材質貼圖;共用快取貼圖必須豁免,
    // 否則第一次清場就把下次還要用的 GPU 貼圖釋放掉 → 黑面。
    texture.userData.roompilotCachedTexture = true;
    surfaceTextureCache.set(key, texture);
    return texture;
  }

  function createSurfaceImageMaterial(surface, usage, options = {}) {
    const colorMap = createImageTexture(surface, usage, options.repeat);
    const bumpMap = createImageTexture(surface, usage, options.repeat, THREE.NoColorSpace);
    const profile = surfacePbrProfile(surface, usage);
    const material = new THREE.MeshPhysicalMaterial({
      color: surfaceTint(options.color ?? "#ffffff", true, usage),
      map: colorMap,
      bumpMap,
      bumpScale: options.bumpScale ?? profile.bumpScale,
      roughness: options.roughness ?? profile.roughness,
      metalness: options.metalness ?? profile.metalness,
      clearcoat: options.clearcoat ?? profile.clearcoat,
      clearcoatRoughness: options.clearcoatRoughness ?? profile.clearcoatRoughness,
      envMapIntensity: options.envMapIntensity ?? profile.envMapIntensity,
      side: options.side ?? THREE.FrontSide,
    });
    material.userData.roompilotImageSurface = true;
    material.userData.roompilotSurfaceUsage = usage;
    if (options.transparent) {
      material.transparent = true;
      material.opacity = options.opacity ?? 0.92;
      material.depthWrite = true;
    }
    return material;
  }

  function createArchitecturalMaterial(role, surfaceCatalog) {
    const profile = architecturalPbrProfile(role);
    const isDoor = role === "door_leaf";
    const material = new THREE.MeshPhysicalMaterial({
      color: isDoor ? 0xb98c62 : 0xe9ecec,
      ...profile,
    });

    // The existing wood surface gives the default closed door visible grain.
    // A future door catalog may replace it with a product-specific PBR set.
    if (isDoor) {
      const woodSurface = findSurfaceTexture(
        surfaceCatalog,
        "wood_cc0_wood_textures_woodfloor039",
      );
      if (woodSurface) {
        material.map = createImageTexture(woodSurface, "floor", [1, 2.2]);
        material.bumpMap = createImageTexture(woodSurface, "floor", [1, 2.2], THREE.NoColorSpace);
        material.bumpScale = 0.018;
        material.userData.roompilotImageSurface = true;
        material.userData.roompilotSurfaceUsage = "door";
      }
    }
    return material;
  }

  function applySurfaceTint(material, color) {
    if (!color || !material?.color) return;
    material.color.set(surfaceTint(
      color,
      material.userData.roompilotImageSurface === true,
      material.userData.roompilotSurfaceUsage || "generic",
    ));
  }

  function stabilizeWholeHouseWallAppearance(material) {
    if (!material?.color) return material;
    // A whole-house paint is a visual commitment, not a lighting experiment.
    // MeshPhysicalMaterial still shaded identical paint differently per wall
    // direction.  Use an unlit finish only for this explicit uniform mode so
    // every interior face presents the selected colour exactly the same way.
    const stableMaterial = new THREE.MeshBasicMaterial({
      color: material.color.clone(),
      // Keep the selected plaster or tile image.  MeshBasicMaterial removes
      // directional-light differences without discarding the material itself.
      map: material.map || null,
      side: material.side || THREE.DoubleSide,
      transparent: false,
      opacity: 1,
      toneMapped: false,
    });
    stableMaterial.userData.roompilotWholeHouseWall = true;
    stableMaterial.userData.roompilotImageSurface = Boolean(material.map);
    stableMaterial.userData.roompilotSurfaceUsage = "wall";
    return stableMaterial;
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
        repeat: getContinuousSurfaceRepeat(surface, "floor", roomSize.widthCm, roomSize.depthCm),
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

  function createWallMaterial(wallOption, surfaceCatalog, { tintOnly = false } = {}) {
    const requestedSurface = findSurface(surfaceCatalog, wallOption, "wall");
    // Most imported wall records retain their original remote preview URL.
    // The viewer must still work offline, so render those with our bundled
    // plaster texture while preserving the selected wall colour and ID in data.
    const surface = requestedSurface?.texture_url?.startsWith("http")
      ? findSurface(surfaceCatalog, "wall_ambientcg_plaster006", "wall")
      : requestedSurface;
    if (surface) {
      const material = createSurfaceImageMaterial(surface, "wall", {
        roughness: 0.9,
        metalness: 0.01,
        repeat: surface.repeat?.wall || [2.4, 1.8],
        side: THREE.DoubleSide,
      });
      if (tintOnly) {
        // Keep the catalog texture as subtle relief, but never let its source color
        // override a whole-house wall color selected by the user.
        material.map = null;
        material.userData.roompilotImageSurface = false;
        material.userData.roompilotWallTintOnly = true;
      }
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

  return {
    applySurfaceTint,
    createArchitecturalMaterial,
    createFloorMaterial,
    createWallMaterial,
    stabilizeWholeHouseWallAppearance,
  };
}