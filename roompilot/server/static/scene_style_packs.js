function styleCard(id, name, palette, sourceImage, signatureFurniture, signatureDecor, options = {}) {
  return Object.freeze({
    id,
    name,
    palette,
    sourceImage,
    signatureFurniture,
    signatureDecor,
    ...options,
  });
}

const STYLE_DEFINITIONS = Object.freeze([
  {
    id: "scandinavian",
    label: "北歐風",
    cards: [
      styleCard("scandinavian_1", "自然木質", ["#F3EBDD", "#D3B48A", "#8B684B", "#9DB5B0"], "/static/style_cards/01_北歐/01_北歐_自然木質.png", ["模組布沙發", "淺橡木電視櫃", "淺木茶几"], ["藤編吊燈", "窗邊植栽", "亞麻地毯"], { wallOption: "warm_white", floorOption: "light_oak" }),
      styleCard("scandinavian_2", "清新明亮", ["#F7F5ED", "#DCE7DF", "#A5C0B0", "#5E746B"], "/static/style_cards/01_北歐/02_北歐_清新明亮.png", ["低扶手沙發", "圓形茶几", "開放層架"], ["白紗簾", "輕量吊燈", "小型植栽"], { wallOption: "warm_white", floorOption: "light_oak" }),
      styleCard("scandinavian_3", "低彩度質感", ["#E8E6DF", "#B9B5A9", "#6E706D", "#B9855A"], "/static/style_cards/01_北歐/03_北歐_低彩度質感.png", ["柔角直線沙發", "低矮影音櫃", "簡潔邊桌"], ["低彩度地毯", "植物掛畫", "暖色間接光"], { wallOption: "limewash", floorOption: "stone_gray" }),
    ],
  },
  {
    id: "japanese",
    label: "日式風",
    cards: [
      styleCard("japanese_1", "侘寂自然", ["#E5DED0", "#C7AE88", "#7C6A55", "#667060"], "/static/style_cards/02_日式/01_日式_侘寂自然.png", ["低床架", "低木桌", "素木層架"], ["和紙吊燈", "陶器花器", "枯枝植栽"], { wallOption: "limewash", floorOption: "light_oak" }),
      styleCard("japanese_2", "茶室禪意", ["#F1E8D8", "#D6C6A5", "#9A795B", "#5D5146"], "/static/style_cards/02_日式/02_日式_茶室禪意.png", ["矮茶桌", "低座椅", "木格柵櫃"], ["和紙燈籠", "暖色間接光", "極簡陶器"], { lightingProfile: "warm_evening", wallOption: "limewash", floorOption: "walnut" }),
      styleCard("japanese_3", "現代和風", ["#DDD8CD", "#B7AA96", "#716A60", "#383A37"], "/static/style_cards/02_日式/03_日式_現代和風.png", ["低背沙發", "平台床", "格柵收納櫃"], ["線性和紙燈", "隱藏燈帶", "留白掛畫"], { wallOption: "warm_white", floorOption: "light_oak" }),
    ],
  },
  {
    id: "modern_minimal",
    label: "現代簡約",
    cards: [
      styleCard("modern_minimal_1", "黑白俐落", ["#F4F3F0", "#B7B7B5", "#555555", "#252525"], "/static/style_cards/03_現代簡約/01_現代簡約_黑白俐落.png", ["俐落直線沙發", "玻璃石材茶几", "黑白影音櫃"], ["軌道燈", "單幅抽象畫", "素色地毯"], { wallOption: "warm_white", floorOption: "stone_gray" }),
      styleCard("modern_minimal_2", "暖灰質感", ["#E4DED5", "#A69C91", "#5A534D", "#B58A68"], "/static/style_cards/03_現代簡約/02_現代簡約_暖灰質感.png", ["模組沙發", "窄框收納櫃", "圓角長桌"], ["暖金屬飾件", "間接燈", "灰褐地毯"], { wallOption: "light_gray", floorOption: "stone_gray" }),
      styleCard("modern_minimal_3", "自然留白", ["#F5F2EB", "#D3C7B5", "#77736B", "#997958"], "/static/style_cards/03_現代簡約/03_現代簡約_自然留白.png", ["整合式低櫃", "簡潔床架", "精簡餐桌"], ["隱藏燈帶", "單件主飾品", "留白牆面"], { wallOption: "warm_white", floorOption: "light_oak" }),
    ],
  },
  {
    id: "cream",
    label: "奶油風",
    cards: [
      styleCard("cream_1", "奶油米白", ["#F8F0E5", "#E5D2B8", "#C3A17F", "#8F6C54"], "/static/style_cards/04_奶油風/01_奶油風_奶油米白.png", ["弧形沙發", "圓形茶几", "包覆餐椅"], ["暖色吊燈", "白紗簾", "柔軟地毯"], { lightingProfile: "warm_evening", wallOption: "limewash", floorOption: "light_oak" }),
      styleCard("cream_2", "法式柔霧", ["#FAEEE5", "#E9CFC0", "#C99B84", "#8B6E61"], "/static/style_cards/04_奶油風/02_奶油風_法式柔霧.png", ["曲線沙發", "優雅餐桌椅", "拱形鏡"], ["小型吊燈", "間接燈槽", "低調線板"], { lightingProfile: "warm_evening", wallOption: "warm_white", floorOption: "marble" }),
      styleCard("cream_3", "奶茶木質", ["#F3E8D8", "#D5B998", "#AA8062", "#6F5140"], "/static/style_cards/04_奶油風/03_奶油風_奶茶木質.png", ["暖木收納櫃", "柔角沙發", "圓角桌"], ["亞麻窗簾", "暖色燈帶", "奶茶色織品"], { lightingProfile: "warm_evening", wallOption: "limewash", floorOption: "light_oak" }),
    ],
  },
  {
    id: "industrial",
    label: "工業風",
    cards: [
      styleCard("industrial_1", "黑鐵水泥", ["#C8C5BE", "#8D8B87", "#4A4B49", "#B87345"], "/static/style_cards/05_工業風/01_工業風_黑鐵水泥.png", ["皮革沙發", "黑鐵層架", "深木茶几"], ["軌道燈", "網格櫃", "外露層架"], { lightingProfile: "industrial_contrast", wallOption: "light_gray", floorOption: "microcement" }),
      styleCard("industrial_2", "復古工坊", ["#D8C8B8", "#A86449", "#6D483A", "#2D302F"], "/static/style_cards/05_工業風/02_工業風_復古工坊.png", ["皮革單椅", "工作桌餐桌", "開放層架"], ["鎢絲吊燈", "黑色軌道燈", "復古時鐘"], { lightingProfile: "industrial_contrast", wallOption: "charcoal", floorOption: "stone_gray" }),
      styleCard("industrial_3", "極簡冷調", ["#B7B5B0", "#706F6B", "#333638", "#9A704C"], "/static/style_cards/05_工業風/03_工業風_極簡冷調.png", ["直線深色沙發", "極簡黑櫃", "黑鐵木桌"], ["冷色軌道燈", "稀疏金屬飾品", "灰色地毯"], { lightingProfile: "industrial_contrast", wallOption: "light_gray", floorOption: "microcement" }),
    ],
  },
  {
    id: "american",
    label: "美式風",
    cards: [
      styleCard("american_1", "鄉村溫馨", ["#F4EFE4", "#D8C8AC", "#8C735A", "#536273"], "/static/style_cards/06_美式/01_美式_鄉村溫馨.png", ["大尺寸沙發", "扶手椅", "木質茶几"], ["桌燈", "花紋地毯", "框畫"], { lightingProfile: "warm_evening", wallOption: "warm_white", floorOption: "walnut" }),
      styleCard("american_2", "經典優雅", ["#F5F4EE", "#C8D8DB", "#7798A5", "#3E5867"], "/static/style_cards/06_美式/02_美式_經典優雅.png", ["對稱沙發單椅", "古典餐桌", "線板展示櫃"], ["枝形吊燈", "成對桌燈", "典雅框畫"], { lightingProfile: "warm_evening", wallOption: "warm_white", floorOption: "light_oak" }),
      styleCard("american_3", "現代輕奢", ["#EAE5D9", "#B99D78", "#6D4B35", "#536653"], "/static/style_cards/06_美式/03_美式_現代輕奢.png", ["俐落大沙發", "大理石玻璃茶几", "金屬邊桌"], ["黃銅燈具", "精緻飾品", "層次窗簾"], { lightingProfile: "gallery_neutral", wallOption: "limewash", floorOption: "walnut" }),
    ],
  },
]);

const DEFAULT_RENDERING = Object.freeze({
  gtao: { enabled: true, radius: 0.42, intensity: 1.15 },
  toneMapping: "ACESFilmic",
  antialias: "SMAA",
  shadow: { type: "PCFSoft", contactOpacity: 0.5, mapSize: 2048 },
});

const STYLE_LANGUAGE = Object.freeze({
  scandinavian: {
    materialLanguage: ["light_oak", "linen", "rattan", "matte_ceramic"],
    displayHighlights: ["淺橡木", "亞麻", "藤編"],
    furnitureRules: {
      sofa: ["modular_fabric_sofa", "low_arm_linen_sofa"],
      coffeeTable: ["light_oak_rect_table", "round_light_oak_table"],
      storage: ["low_light_oak_tv_bench", "open_light_wood_shelf"],
      dining: ["slim_light_wood_dining_set"],
      lighting: ["rattan_pendant", "warm_floor_lamp"],
    },
    decorRules: ["linen_rug", "sheer_curtain", "plant_near_window", "botanical_wall_art"],
    placementRules: {
      livingRoom: { sofaFacesMainWall: true, rugZone: true, plantsNearWindow: true },
      bedroom: { lowVisualWeight: true, keepWindowClear: true },
    },
  },
  japanese: {
    materialLanguage: ["pale_wood", "raw_linen", "paper", "matte_ceramic"],
    displayHighlights: ["淡木", "原麻", "和紙"],
    furnitureRules: {
      sofa: ["low_clean_sofa", "floor_cushion"],
      coffeeTable: ["low_wood_table", "tea_table"],
      storage: ["wood_slat_cabinet", "simple_low_shelf"],
      bed: ["low_platform_bed"],
      lighting: ["paper_pendant", "concealed_warm_light"],
    },
    decorRules: ["ceramic_vase", "minimal_branch", "woven_mat", "paper_screen"],
    placementRules: {
      livingRoom: { preserveEmptyWall: true, lowProfiles: true },
      bedroom: { bedOnLongestQuietWall: true, oneLowNightstand: true },
    },
  },
  modern_minimal: {
    materialLanguage: ["smooth_mineral", "stone", "matte_black_metal", "glass"],
    displayHighlights: ["礦物塗料", "石材", "霧黑金屬"],
    furnitureRules: {
      sofa: ["clean_rectangular_sofa", "modular_low_sofa"],
      coffeeTable: ["stone_coffee_table", "glass_coffee_table"],
      storage: ["integrated_low_storage", "wall_aligned_cabinet"],
      dining: ["slim_linear_dining_set"],
      lighting: ["linear_light", "track_light"],
    },
    decorRules: ["single_statement_art", "plain_rug", "minimal_vase"],
    placementRules: {
      livingRoom: { alignToAxes: true, reduceFurnitureCount: true },
      storage: { wallAligned: true, avoidScatteredPieces: true },
    },
  },
  cream: {
    materialLanguage: ["warm_oak", "boucle", "linen", "muted_brass"],
    displayHighlights: ["暖橡木", "圈圈絨", "霧面黃銅"],
    furnitureRules: {
      sofa: ["curved_boucle_sofa", "soft_edge_sofa"],
      coffeeTable: ["round_coffee_table", "rounded_stone_table"],
      storage: ["warm_wood_rounded_cabinet"],
      dining: ["rounded_dining_chair", "round_dining_table"],
      lighting: ["soft_pendant", "cove_light"],
    },
    decorRules: ["soft_rug", "sheer_curtain", "arched_mirror", "cream_cushion"],
    placementRules: {
      livingRoom: { preferCurves: true, rugZone: true },
      wholeHouse: { avoidSharpContrast: true, warmSoftLighting: true },
    },
  },
  industrial: {
    materialLanguage: ["concrete", "black_iron", "dark_walnut", "brown_leather"],
    displayHighlights: ["清水模", "黑鐵", "深胡桃木"],
    furnitureRules: {
      sofa: ["brown_leather_sofa", "straight_dark_sofa"],
      coffeeTable: ["dark_wood_iron_table"],
      storage: ["black_iron_open_shelf", "mesh_media_cabinet"],
      dining: ["workbench_dining_table"],
      lighting: ["black_track_light", "filament_pendant"],
    },
    decorRules: ["mesh_storage", "vintage_clock", "sparse_metal_art"],
    placementRules: {
      livingRoom: { darkSofaAnchorsRoom: true, shelfOnLongWall: true },
      lighting: { trackAlongLongAxis: true, keepCirculationClear: true },
    },
  },
  american: {
    materialLanguage: ["walnut", "cotton_linen", "brass", "clear_glass"],
    displayHighlights: ["胡桃木", "棉麻", "黃銅"],
    furnitureRules: {
      sofa: ["large_comfort_sofa", "classic_armchair"],
      coffeeTable: ["wood_coffee_table", "marble_glass_table"],
      storage: ["panel_sideboard", "classic_display_cabinet"],
      dining: ["classic_dining_table", "upholstered_dining_chair"],
      lighting: ["classic_pendant", "table_lamp"],
    },
    decorRules: ["patterned_rug", "layered_curtain", "framed_art", "side_table_lamp"],
    placementRules: {
      livingRoom: { preferSymmetry: true, addSideTablesIfClear: true },
      wholeHouse: { layeredSoftFurnishings: true, preserveCirculation: true },
    },
  },
});

const LIGHTING_PROFILES = Object.freeze({
  soft_daylight: {
    hdr: "apartment-daylight",
    colorTemperatureK: 4200,
    environmentIntensity: 1.05,
    keyLightLux: 360,
    contactShadow: 0.5,
    gtaoIntensity: 1.1,
  },
  warm_evening: {
    hdr: "warm-interior",
    colorTemperatureK: 3200,
    environmentIntensity: 0.9,
    keyLightLux: 280,
    contactShadow: 0.58,
    gtaoIntensity: 1.15,
  },
  gallery_neutral: {
    hdr: "neutral-studio",
    colorTemperatureK: 4600,
    environmentIntensity: 1,
    keyLightLux: 390,
    contactShadow: 0.56,
    gtaoIntensity: 1.2,
  },
  industrial_contrast: {
    hdr: "studio-industrial",
    colorTemperatureK: 3800,
    environmentIntensity: 0.82,
    keyLightLux: 330,
    contactShadow: 0.68,
    gtaoIntensity: 1.28,
  },
});

function lightingProfile(styleId, cardIndex) {
  if (styleId === "industrial") return "industrial_contrast";
  if (styleId === "modern_minimal") return "gallery_neutral";
  if (styleId === "cream" || styleId === "american" || (styleId === "japanese" && cardIndex === 1)) {
    return "warm_evening";
  }
  return "soft_daylight";
}

function buildPack(style, card, cardIndex) {
  const { id, name, palette, sourceImage, signatureFurniture, signatureDecor } = card;
  const industrial = style.id === "industrial";
  const american = style.id === "american";
  const warm = style.id === "cream" || style.id === "japanese";
  const language = STYLE_LANGUAGE[style.id];
  const profile = card.lightingProfile || lightingProfile(style.id, cardIndex);
  const lighting = LIGHTING_PROFILES[profile];
  const rendering = JSON.parse(JSON.stringify(DEFAULT_RENDERING));
  rendering.gtao.intensity = lighting.gtaoIntensity;
  rendering.shadow.contactOpacity = lighting.contactShadow;
  rendering.exposure = profile === "industrial_contrast" ? 0.96 : profile === "warm_evening" ? 1.02 : 1.08;
  return {
    id,
    styleId: style.id,
    styleLabel: style.label,
    name,
    sourceImage,
    palette,
    wall: {
      color: palette[0],
      surfaceOption: card.wallOption || (industrial
        ? (cardIndex === 0 ? "light_gray" : "charcoal")
        : warm ? "limewash" : "warm_white"),
      pbr: {
        material: industrial ? "micro-cement" : "mineral-paint",
        roughness: industrial ? 0.74 : 0.88,
        metalness: 0,
        normalScale: industrial ? 0.32 : 0.12,
      },
    },
    floor: {
      color: palette[2],
      surfaceOption: card.floorOption || (industrial
        ? "microcement"
        : american ? "walnut"
          : style.id === "modern_minimal" && cardIndex === 0 ? "stone_gray"
            : "light_oak"),
      pbr: {
        material: industrial ? "sealed-concrete" : american ? "walnut-plank" : "wood-plank",
        roughness: industrial ? 0.62 : 0.48,
        metalness: 0,
        reflection: industrial ? 0.18 : 0.24,
      },
    },
    furniture: {
      color: palette[1],
      accent: palette[3],
      materialLanguage: language.materialLanguage,
      displayHighlights: language.displayHighlights,
      pbr: {
        woodRoughness: warm ? 0.58 : 0.46,
        fabricRoughness: 0.86,
        metalness: industrial ? 0.72 : 0.2,
        glassTransmission: 0.88,
      },
      replacementPolicy: "same-style-unlocked-only",
    },
    furnitureRules: {
      ...language.furnitureRules,
      signature: signatureFurniture,
    },
    decorRules: signatureDecor,
    placementRules: language.placementRules,
    lighting: { profile, ...lighting },
    rendering,
  };
}

export const STYLE_PACKS = Object.freeze(
  STYLE_DEFINITIONS.flatMap((style) =>
    style.cards.map((card, cardIndex) => buildPack(style, card, cardIndex)),
  ),
);

export const STYLE_MATERIAL_OPTIONS = Object.freeze({
  scandinavian: {
    wall: [
      { id: "warm_white", label: "暖白礦物漆", color: "#F7F3EA", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "乾淨、明亮，適合小宅放大感" },
      { id: "limewash", label: "柔霧石灰洗", color: "#EDE5D8", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "低對比紋理，搭配淺木家具" },
    ],
    floor: [
      { id: "light_oak", label: "淺橡木地板", color: "#D9B985", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks039.jpg", note: "北歐風主材質" },
      { id: "stone_gray", label: "霧灰石紋", color: "#B9B8B2", materialPreview: "/static/surface_assets/tile/ccity-CAL288001.png", note: "客餐廳更俐落" },
    ],
  },
  japanese: {
    wall: [
      { id: "limewash", label: "米白土佐壁", color: "#EFE6D6", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "和紙與木質感的底色" },
      { id: "warm_white", label: "暖白抹面", color: "#F3EFE6", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "保留空間留白" },
    ],
    floor: [
      { id: "light_oak", label: "淺木地板", color: "#C9AD7E", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks039.jpg", note: "自然、安定" },
      { id: "walnut", label: "溫潤胡桃木", color: "#8B6B4E", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-WoodFloor039.jpg", note: "偏沉穩的日式宅" },
    ],
  },
  modern_minimal: {
    wall: [
      { id: "warm_white", label: "極簡白牆", color: "#F5F4F0", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "乾淨背景，突出家具線條" },
      { id: "light_gray", label: "霧灰塗料", color: "#C9C9C6", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Tiles008.jpg", note: "現代感更強" },
    ],
    floor: [
      { id: "stone_gray", label: "灰石地坪", color: "#AFAEAA", materialPreview: "/static/surface_assets/tile/ccity-CAL288001.png", note: "適合無縫感" },
      { id: "light_oak", label: "淡木地板", color: "#D6BE94", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks039.jpg", note: "降低冷感" },
    ],
  },
  cream: {
    wall: [
      { id: "limewash", label: "奶油石灰洗", color: "#F6E9D7", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "柔和包覆感" },
      { id: "warm_white", label: "暖奶白牆", color: "#FAF0E4", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "明亮不刺眼" },
    ],
    floor: [
      { id: "light_oak", label: "奶茶淺木", color: "#E0C69C", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks039.jpg", note: "搭配奶油家具" },
      { id: "marble", label: "米白石紋", color: "#E5D8C4", materialPreview: "/static/surface_assets/tile/ccity-CAL330121.png", note: "偏精緻的奶油宅" },
    ],
  },
  industrial: {
    wall: [
      { id: "light_gray", label: "清水模灰牆", color: "#B9B7B1", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Tiles009.jpg", note: "工業風主牆面" },
      { id: "charcoal", label: "炭黑重點牆", color: "#3C3D3B", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Tiles009.jpg", note: "用於局部立面" },
    ],
    floor: [
      { id: "microcement", label: "微水泥地坪", color: "#9B9992", materialPreview: "/static/surface_assets/tile/ccity-CAL288001.png", note: "霧面、耐看" },
      { id: "stone_gray", label: "灰石磚", color: "#8D8B87", materialPreview: "/static/surface_assets/tile/ccity-CAL288001.png", note: "較易維護" },
    ],
  },
  american: {
    wall: [
      { id: "warm_white", label: "美式暖白牆", color: "#F4EFE4", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "搭配線板與深木" },
      { id: "limewash", label: "柔霧米牆", color: "#EDE3D3", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", note: "降低厚重感" },
    ],
    floor: [
      { id: "walnut", label: "胡桃木地板", color: "#8C735A", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-WoodFloor039.jpg", note: "美式經典主材" },
      { id: "light_oak", label: "淺橡木拼板", color: "#D8C8AC", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks039.jpg", note: "較清爽的美式" },
    ],
  },
});

export function stylePackById(id) {
  return STYLE_PACKS.find((pack) => pack.id === id) || null;
}

export function applyStylePack(sceneState, stylePack) {
  if (!stylePack) throw new Error("style_pack_required");
  const next = JSON.parse(JSON.stringify(sceneState || {}));
  next.stylePackId = stylePack.id;
  next.wall = {
    ...(next.wall || {}),
    color: stylePack.wall.color,
    material: stylePack.wall.surfaceOption,
    pbr: stylePack.wall.pbr,
    scope: "house",
    styleLocked: false,
  };
  next.floor = {
    ...(next.floor || {}),
    color: stylePack.floor.color,
    material: stylePack.floor.surfaceOption,
    pbr: stylePack.floor.pbr,
    scope: "house",
    styleLocked: false,
  };
  next.furniture = (next.furniture || []).map((item) => {
    if (item.styleLocked) return item;
    return {
      ...item,
      material: {
        ...(item.material || {}),
        color: stylePack.furniture.color,
        accent: stylePack.furniture.accent,
        pbr: stylePack.furniture.pbr,
      },
    };
  });
  next.lighting = stylePack.lighting;
  next.rendering = stylePack.rendering;
  next.sourceImage = stylePack.sourceImage;
  next.furnitureRules = stylePack.furnitureRules;
  next.decorRules = stylePack.decorRules;
  next.placementRules = stylePack.placementRules;
  return next;
}

export const CEILING_STYLES = Object.freeze([
  { id: "exposed", label: "裸頂", styles: ["industrial"], dropCm: 0 },
  { id: "flat", label: "平釘天花", styles: ["scandinavian", "modern_minimal", "cream"], dropCm: 12 },
  { id: "cove", label: "間接燈槽", styles: ["modern_minimal", "cream", "american"], dropCm: 18 },
  { id: "floating", label: "懸浮天花", styles: ["modern_minimal", "cream"], dropCm: 20 },
  { id: "linear", label: "線性燈天花", styles: ["modern_minimal", "industrial"], dropCm: 15 },
  { id: "no-main-light", label: "無主燈", styles: ["scandinavian", "modern_minimal"], dropCm: 10 },
  { id: "wood-grid", label: "木格柵", styles: ["japanese", "american"], dropCm: 16 },
]);

export const LIGHT_STYLES = Object.freeze([
  { id: "track", label: "軌道燈", styles: ["industrial", "modern_minimal"], lumens: 900, beamAngle: 36, installationDepthCm: 0 },
  { id: "pendant", label: "吊燈", styles: ["scandinavian", "cream", "american"], lumens: 1200, beamAngle: 60, installationDepthCm: 5 },
  { id: "downlight", label: "崁燈", styles: ["modern_minimal", "cream"], lumens: 720, beamAngle: 50, installationDepthCm: 12 },
  { id: "paper", label: "和紙燈", styles: ["japanese"], lumens: 800, beamAngle: 90, installationDepthCm: 5 },
]);

export function detectCeilingConflicts({
  ceilingStyle,
  roomHeightCm,
  beams = [],
  cabinets = [],
  lights = [],
} = {}) {
  const style = CEILING_STYLES.find((item) => item.id === ceilingStyle) || CEILING_STYLES[1];
  const finishedHeight = Number(roomHeightCm || 270) - style.dropCm;
  const conflicts = [];
  [...beams, ...cabinets, ...lights].forEach((item) => {
    const topCm = Number(item.topCm ?? item.heightCm ?? 0);
    if (item.kind === "light") {
      const requiredPlenumCm = Number(item.requiredPlenumCm || 0);
      if (requiredPlenumCm <= style.dropCm) return;
      const overlapCm = Math.round((requiredPlenumCm - style.dropCm) * 10) / 10;
      conflicts.push({
        objectId: item.id,
        objectLabel: item.label,
        location: item.roomLabel || "目前房間",
        overlapCm,
        reason: `${item.label}需要 ${requiredPlenumCm} cm 安裝深度，目前天花夾層只有 ${style.dropCm} cm。`,
        impact: `安裝空間不足 ${overlapCm} cm，燈體或驅動器會與樓板衝突。`,
        recommendations: [
          `增加天花下降量至少 ${Math.ceil(overlapCm + 2)} cm`,
          `改用安裝深度較小的燈具`,
          "改採吸頂或軌道燈方案",
        ],
      });
      return;
    }
    const bottomCm = Number(item.bottomCm ?? topCm);
    if (item.kind === "beam" && bottomCm < finishedHeight && topCm > finishedHeight) {
      const overlapCm = Math.round((finishedHeight - bottomCm) * 10) / 10;
      const estimateNote = item.estimated ? "（圖面估計，須以現場丈量覆核）" : "";
      conflicts.push({
        objectId: item.id,
        objectLabel: item.label,
        location: item.roomLabel || "目前房間",
        overlapCm,
        reason: `${item.label}梁底 ${bottomCm} cm、梁頂 ${topCm} cm${estimateNote}，完成天花 ${finishedHeight} cm 會穿過梁體。`,
        impact: `天花平面與梁重疊 ${overlapCm} cm，無法直接連續施工。`,
        recommendations: [
          "改做包梁或分區高低天花",
          `將天花降到梁底 ${bottomCm} cm 以下`,
          "現場量測梁底後重算燈具與櫃體高度",
        ],
      });
      return;
    }
    if (topCm <= finishedHeight) return;
    const overlapCm = Math.round((topCm - finishedHeight) * 10) / 10;
    conflicts.push({
      objectId: item.id,
      objectLabel: item.label,
      location: item.roomLabel || "目前房間",
      overlapCm,
      reason: `${item.label}頂部 ${topCm} cm，高於完成天花 ${finishedHeight} cm。`,
      impact: `會穿入天花 ${overlapCm} cm，無法按目前幾何施工。`,
      recommendations: [
        `局部抬高天花至少 ${Math.ceil(overlapCm + 3)} cm`,
        `降低或更換 ${item.label}`,
        "改用較薄的天花方案",
      ],
    });
  });
  return { finishedHeightCm: finishedHeight, conflicts };
}
