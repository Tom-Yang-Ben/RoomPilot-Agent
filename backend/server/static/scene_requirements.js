import {
  QUESTIONNAIRE_READY_IMAGE_KEYS,
} from "./questionnaire_image_assets.generated.js?v=sha256-8104b6acd3ec";

export const QUESTIONNAIRE_SCHEMA_VERSION = "3.0";
export const QUESTIONNAIRE_NOTICE = "目前只選擇格局；色卡與風格尚未定義。";

const quick = (value, label, description = "") => ({ value, label, description });
const visual = (value, label, imageKey, extra = {}) => ({
  value,
  label,
  imageKey,
  imageStatus: "pending_discussion",
  ...extra,
});
export const AXIS_PREFERENCE_OPTIONS = Object.freeze([
  Object.freeze({ value: "lean_a", label: "偏重 A" }),
  Object.freeze({ value: "balanced", label: "兩者平衡" }),
  Object.freeze({ value: "lean_b", label: "偏重 B" }),
]);
const axis = ({
  id,
  label,
  prompt,
  options,
  required = true,
  customExample = "",
  mode = "continuum",
}) => {
  const [endpointA, endpointB, ...legacyMiddleOptions] = options;
  if (!endpointA || !endpointB) throw new Error(`axis_endpoints_required:${id}`);
  return {
    id,
    label,
    prompt,
    mode,
    options: [
      { ...endpointA, pole: "a" },
      { ...endpointB, pole: "b" },
    ],
    preferenceOptions: mode === "exclusive" ? [] : AXIS_PREFERENCE_OPTIONS,
    legacyPreferenceMap: Object.fromEntries([
      [endpointA.value, "a"],
      [endpointB.value, "b"],
      ...legacyMiddleOptions.map((option) => [option.value, "balanced"]),
    ]),
    required,
    customExample,
  };
};

export const WHOLE_HOUSE_QUESTIONS = Object.freeze([
  {
    id: "residents",
    label: "實際居住成員",
    type: "multi",
    required: true,
    options: [
      quick("adult", "成人"),
      quick("child", "兒童"),
      quick("elderly", "長者"),
      quick("pet", "寵物"),
      quick("frequent_guest", "常態留宿親友"),
    ],
    example: "例如：2 位成人、1 位學齡兒童、1 隻貓。",
  },
  {
    id: "residentCount",
    label: "實際常住人數",
    type: "single",
    required: true,
    options: [
      quick("one", "1 人"),
      quick("two", "2 人"),
      quick("three", "3 人"),
      quick("four", "4 人"),
      quick("five_plus", "5 人以上"),
    ],
    example: "例如：目前 3 人常住，親友留宿另外在聚會題記錄。",
  },
  {
    id: "ageNeeds",
    label: "需要特別照顧的年齡或行動需求",
    type: "multi",
    required: true,
    exclusiveValues: ["none"],
    options: [
      quick("none", "目前沒有"),
      quick("preschool", "幼兒安全"),
      quick("school_age", "學習成長"),
      quick("aging", "高齡友善"),
      quick("mobility", "行動輔助"),
    ],
    example: "例如：長者夜間會走到浴室，希望減少高低差。",
  },
  {
    id: "scheduleInterference",
    label: "家人的生活作息會互相干擾嗎？",
    type: "multi",
    required: true,
    exclusiveValues: ["same_schedule"],
    options: [
      quick("same_schedule", "作息接近"),
      quick("noise_conflict", "容易被聲音干擾"),
      quick("light_conflict", "容易被燈光干擾"),
      quick("bathroom_conflict", "衛浴時段衝突"),
      quick("kitchen_conflict", "料理氣味或時間衝突"),
    ],
    example: "例如：一人晚睡工作，另一人早睡，需要隔音或分區照明。",
  },
  {
    id: "homeWorkStudyCount",
    label: "在家工作或讀書的頻率與人數",
    type: "single",
    required: true,
    options: [
      quick("none", "幾乎沒有"),
      quick("occasional", "偶爾使用"),
      quick("one_regular", "1 人固定使用"),
      quick("multiple_regular", "多人固定使用"),
    ],
    example: "例如：平日 2 人同時工作，其中 1 人常開視訊。",
  },
  {
    id: "homeWorkStudyNeeds",
    label: "工作或讀書時需要哪些條件？",
    type: "multi",
    required: true,
    exclusiveValues: ["none"],
    options: [
      quick("none", "沒有特別需求"),
      quick("video_calls", "視訊會議"),
      quick("quiet_focus", "安靜專注"),
      quick("simultaneous", "多人同時使用"),
      quick("background_storage", "文件與背景收納"),
    ],
    example: "例如：兩人同時使用，其中一人需要安靜視訊。",
  },
  {
    id: "futureChanges",
    label: "未來幾年可能發生哪些家庭變化？",
    type: "multi",
    required: true,
    exclusiveValues: ["stable"],
    options: [
      quick("stable", "成員大致不變"),
      quick("new_child", "可能新增幼兒"),
      quick("children_grow", "孩子進入下一成長階段"),
      quick("elderly_move_in", "長者可能同住"),
      quick("work_change", "在家工作需求改變"),
      quick("rent_or_resale", "可能出租或轉售"),
    ],
    example: "例如：三年內可能有新生兒，書房需能轉成嬰兒房。",
  },
  {
    id: "hostingFrequency",
    label: "親友來訪的頻率",
    type: "single",
    required: true,
    options: [
      quick("rare", "很少"),
      quick("monthly", "每月約 1–2 次"),
      quick("small_regular", "常有 2–4 人來訪"),
      quick("large_regular", "常有多人聚會"),
    ],
    example: "例如：每月約一次 6 人聚餐，偶爾有 1 人留宿。",
  },
  {
    id: "hostingNeeds",
    label: "來訪時通常有哪些使用需求？",
    type: "multi",
    required: true,
    exclusiveValues: ["none"],
    options: [
      quick("none", "沒有特別需求"),
      quick("meal", "一起用餐"),
      quick("large_gathering", "多人聚會"),
      quick("overnight", "親友留宿"),
      quick("children_visit", "兒童來訪"),
    ],
    example: "例如：聚餐為主，偶爾需要一人留宿。",
  },
  {
    id: "budgetPriority",
    label: "預算、品質與時間的優先方向",
    type: "single",
    required: true,
    options: [
      quick("budget_first", "預算優先"),
      quick("balanced", "預算與品質平衡"),
      quick("quality_first", "品質優先"),
      quick("timeline_first", "入住時間優先"),
    ],
    example: "例如：品質優先，但希望把主要工程控制在預算級距內。",
  },
  {
    id: "budgetRange",
    label: "目前預估的工程預算級距",
    type: "single",
    required: true,
    options: [
      quick("undecided", "尚未決定"),
      quick("under_100", "100 萬以下"),
      quick("100_200", "100–200 萬"),
      quick("200_350", "200–350 萬"),
      quick("350_plus", "350 萬以上"),
    ],
    example: "例如：目前先以 100–200 萬作為方案篩選級距。",
  },
  {
    id: "targetTimeline",
    label: "希望何時完成或入住？",
    type: "single",
    required: true,
    options: [
      quick("undecided", "尚未決定"),
      quick("within_3_months", "3 個月內"),
      quick("three_to_six_months", "3–6 個月"),
      quick("six_to_twelve_months", "6–12 個月"),
      quick("over_one_year", "一年以上"),
    ],
    example: "例如：希望 8 月底入住；若工期不足，可先完成必要空間。",
  },
  {
    id: "immutableNeeds",
    label: "既有物件或不可改動條件",
    type: "multi",
    required: true,
    exclusiveValues: ["none"],
    options: [
      quick("none", "目前沒有"),
      quick("existing_furniture", "保留既有家具"),
      quick("appliance", "保留家電"),
      quick("altar_or_piano", "神明桌或鋼琴"),
      quick("fixed_pipes", "既有管線位置"),
      quick("building_rules", "大樓施工限制"),
    ],
    example: "例如：冰箱與鋼琴保留；管理規約禁止移動外牆開口。",
  },
]);

const SHARED_AXES = Object.freeze([
  axis({
    id: "ceiling",
    label: "天花板",
    prompt: "這個房間的天花希望偏向哪種處理？",
    customExample: "例如：主要維持平頂，只在窗邊做局部窗簾盒。",
    options: [
      visual("flat", "維持平整、保留淨高", "ceiling/flat"),
      visual("functional_drop", "局部降板、整合管線", "ceiling/functional-drop"),
      visual("zoned_mix", "依機能分區混合", "ceiling/zoned-mix"),
    ],
  }),
  axis({
    id: "air_conditioning",
    label: "冷氣",
    prompt: "冷氣配置希望偏向哪種方式？",
    customExample: "例如：室內機靠外牆，排水就近，不跨樑。",
    options: [
      visual("wall_mounted", "壁掛式、路徑直接", "air-conditioning/wall-mounted"),
      visual("concealed", "隱藏式、整合天花", "air-conditioning/concealed", {
        riskTags: ["electricity"],
      }),
    ],
  }),
  axis({
    id: "lighting",
    label: "燈光",
    prompt: "主要照明形式希望偏重哪一種？",
    customExample: "例如：明裝燈為主，閱讀桌上方另加局部崁燈。",
    options: [
      visual("recessed_focus", "偏重崁入式", "lighting/recessed-focus"),
      visual("surface_focus", "偏重明裝式", "lighting/surface-focus"),
      visual("layered_by_role", "依用途分層搭配", "lighting/layered-by-role"),
    ],
  }),
]);

const MATERIAL_PREFERENCE_BASE = Object.freeze({
  wall: Object.freeze([
    quick("paint", "塗料"),
    quick("mineral", "礦物／灰泥"),
    quick("microcement", "微水泥"),
    quick("stone", "石材感"),
    quick("wood", "木質牆面"),
    quick("tile", "磁磚"),
    quick("fabric", "布紋／軟包"),
    quick("metal", "金屬質感"),
  ]),
  floor: Object.freeze([
    quick("wood", "木地板"),
    quick("tile", "磁磚"),
    quick("stone", "石材"),
    quick("cement", "水泥質感"),
    quick("terrazzo", "磨石子"),
    quick("vinyl", "塑膠地板"),
  ]),
  furniture: Object.freeze([
    quick("wood", "木質"),
    quick("fabric", "布料"),
    quick("leather", "皮革"),
    quick("metal", "金屬"),
    quick("glass", "玻璃"),
    quick("stone", "石材"),
  ]),
  color: Object.freeze([
    quick("warm_neutral", "暖中性色"),
    quick("cool_neutral", "冷中性色"),
    quick("earth", "大地色"),
    quick("green", "自然綠"),
    quick("dark", "深色沉穩"),
    quick("high_contrast", "高對比"),
  ]),
  finish: Object.freeze([
    quick("matte", "霧面／平光"),
    quick("eggshell", "柔和蛋殼光"),
    quick("semi_gloss", "半光"),
    quick("gloss", "亮面"),
    quick("textured", "明顯紋理"),
  ]),
});

const ROOM_SPECIFIC_AXES = {
  living_room: [
    axis({
      id: "openness_storage",
      label: "開放感與收納",
      prompt: "客廳希望偏向寬敞通透，還是完整收納？",
      customExample: "例如：主要保持通透，只在電視牆做到頂收納。",
      options: [
        visual("open_flow", "寬大走道、視線通透", "living-room/open-flow"),
        visual("storage_wall", "整面收納、機能集中", "living-room/storage-wall"),
        visual("balanced", "保留走道並集中單側收納", "living-room/balanced"),
      ],
    }),
    axis({
      id: "social_focus",
      label: "交流重心",
      prompt: "空間核心偏向影音，還是面對面交流？",
      customExample: "例如：保留投影，但座位仍以聊天圍合為主。",
      options: [
        visual("media", "影音主導", "living-room/media"),
        visual("conversation", "交流主導", "living-room/conversation"),
      ],
    }),
    axis({
      id: "seating_flexibility",
      label: "座位形式",
      prompt: "座位偏向固定舒適，還是彈性重組？",
      customExample: "例如：主沙發固定，另用兩張可移動單椅。",
      options: [
        visual("fixed_sofa", "大型固定沙發", "living-room/fixed-sofa"),
        visual("flexible_seating", "分散可移動座位", "living-room/flexible-seating"),
      ],
    }),
  ],
  bedroom: [
    axis({
    id: "sleep_storage",
    label: "睡眠與收納",
      prompt: "臥室希望保有舒適寬鬆的休息空間，還是最大化收納？",
      customExample: "例如：床周保持留白，入口側做整面衣櫃。",
      options: [
        visual("calm_sleep", "舒適休息、空間寬鬆", "bedroom/calm-sleep"),
        visual("max_storage", "完整衣櫃、收納優先", "bedroom/max-storage"),
        visual("zoned_storage", "單側集中收納", "bedroom/zoned-storage"),
      ],
    }),
    axis({
      id: "work_presence",
      label: "工作機能",
      prompt: "房內偏向純休息，還是整合固定工作區？",
      customExample: "例如：只需一張可收折臨時書桌。",
      options: [
        visual("rest_only", "純休息", "bedroom/rest-only"),
        visual("work_zone", "固定工作區", "bedroom/work-zone"),
      ],
    }),
    axis({
      id: "bed_access",
      label: "床側動線",
      prompt: "床要保留雙側通道，還是靠牆換取空間？",
      customExample: "例如：兒童房床靠牆，床尾保留遊戲區。",
      options: [
        visual("two_side_access", "雙側可上下床", "bedroom/two-side-access"),
        visual("wall_side", "靠牆放大活動區", "bedroom/wall-side"),
      ],
    }),
  ],
  dining_room: [
    axis({
      id: "table_mode",
      label: "餐桌使用",
      prompt: "餐桌偏向日常精簡，還是多人聚餐？",
      customExample: "例如：平日 4 人，週末需展開到 8 人。",
      options: [
        visual("compact_daily", "精簡日常", "dining-room/compact-daily"),
        visual("large_gathering", "多人聚餐", "dining-room/large-gathering"),
      ],
    }),
    axis({
      id: "fixed_flexible",
      label: "配置彈性",
      prompt: "餐桌位置固定，還是需要移動重組？",
      customExample: "例如：桌子可靠牆，聚餐時再拉出。",
      options: [
        visual("fixed", "固定餐區", "dining-room/fixed"),
        visual("flexible", "可移動重組", "dining-room/flexible"),
      ],
    }),
    axis({
      id: "dining_storage",
      label: "餐區收納",
      prompt: "偏向開放展示，還是封閉餐邊收納？",
      customExample: "例如：上層展示杯具，下層封閉收納電器。",
      options: [
        visual("display", "展示型", "dining-room/display"),
        visual("closed_storage", "封閉收納型", "dining-room/closed-storage"),
      ],
    }),
  ],
  kitchen: [
    axis({
      id: "kitchen_enclosure",
      label: "開放或封閉",
      prompt: "廚房要保持開放，還是阻隔油煙？",
      customExample: "例如：用玻璃拉門或半高窗兼顧互動與油煙。",
      mode: "exclusive",
      options: [
        visual("open", "開放式廚房", "kitchen/open", { riskTags: ["wall", "gas", "smoke_exhaust"] }),
        visual("closed", "封閉式廚房", "kitchen/closed"),
      ],
    }),
    axis({
      id: "cooking_intensity",
      label: "料理強度",
      prompt: "以簡易料理為主，還是高頻熱炒？",
      customExample: "例如：平日簡餐，週末會油炸與多人共煮。",
      options: [
        visual("light", "簡易料理", "kitchen/light"),
        visual("heavy", "高頻熱炒", "kitchen/heavy", { riskTags: ["gas", "smoke_exhaust"] }),
      ],
    }),
    axis({
      id: "worktop_storage",
      label: "檯面與收納",
      prompt: "偏向大檯面操作，還是高密度電器收納？",
      customExample: "例如：保留 120 公分備餐面，家電集中高櫃。",
      options: [
        visual("worktop", "大檯面", "kitchen/worktop"),
        visual("appliance_storage", "電器收納", "kitchen/appliance-storage"),
        visual("zoned", "檯面與高櫃分區", "kitchen/zoned"),
      ],
    }),
  ],
  bathroom: [
    axis({
      id: "wet_dry",
      label: "乾濕安排",
      prompt: "偏向完整乾濕分離，還是放大使用空間？",
      customExample: "例如：只做半片玻璃，保留輪椅迴轉空間。",
      options: [
        visual("separated", "完整乾濕分離", "bathroom/separated"),
        visual("open_wet", "開放淋浴區", "bathroom/open-wet"),
      ],
    }),
    axis({
      id: "bath_mode",
      label: "沐浴方式",
      prompt: "以淋浴效率為主，還是需要泡澡？",
      customExample: "例如：保留小型坐浴缸，但仍要獨立淋浴。",
      options: [
        visual("shower", "淋浴優先", "bathroom/shower"),
        visual("tub", "泡澡需求", "bathroom/tub", { riskTags: ["plumbing", "drainage"] }),
      ],
    }),
    axis({
      id: "bath_storage",
      label: "衛浴收納",
      prompt: "偏向檯面留白，還是完整鏡櫃浴櫃？",
      customExample: "例如：鏡櫃收日用品，檯面只留洗手用品。",
      options: [
        visual("minimal", "檯面留白", "bathroom/minimal"),
        visual("full_storage", "完整收納", "bathroom/full-storage"),
      ],
    }),
  ],
  balcony: [
    axis({
      id: "balcony_role",
      label: "陽台用途",
      prompt: "偏向家務機能，還是休閒使用？",
      customExample: "例如：一側洗曬，另一側保留植栽座位。",
      options: [
        visual("utility", "洗曬家務", "balcony/utility", { riskTags: ["plumbing", "drainage"] }),
        visual("leisure", "休閒植栽", "balcony/leisure"),
      ],
    }),
    axis({
      id: "balcony_storage",
      label: "陽台收納",
      prompt: "保持通透，還是增加戶外收納？",
      customExample: "例如：只在洗衣機上方做防潮吊櫃。",
      options: [
        visual("open", "保持通透", "balcony/open"),
        visual("storage", "增加收納", "balcony/storage"),
      ],
    }),
    axis({
      id: "weather_protection",
      label: "氣候防護",
      prompt: "偏向自然通風，還是加強遮雨防曬？",
      customExample: "例如：保留通風，但西曬側加可調百葉。",
      options: [
        visual("ventilated", "自然通風", "balcony/ventilated"),
        visual("protected", "遮雨防曬", "balcony/protected"),
      ],
    }),
  ],
  storage: [
    axis({
      id: "storage_visibility",
      label: "收納可見度",
      prompt: "物品希望容易看到，還是完全隱藏？",
      customExample: "例如：常用品開放，備品放封閉櫃。",
      options: [
        visual("open", "開放易取", "storage/open"),
        visual("closed", "封閉整齊", "storage/closed"),
      ],
    }),
    axis({
      id: "storage_density",
      label: "收納密度",
      prompt: "保留走道餘裕，還是最大化容量？",
      customExample: "例如：單側深櫃，另一側維持 90 公分走道。",
      options: [
        visual("clearance", "走道優先", "storage/clearance"),
        visual("capacity", "容量優先", "storage/capacity"),
      ],
    }),
    axis({
      id: "storage_access",
      label: "取物方式",
      prompt: "偏向日常快速取用，還是長期備品管理？",
      customExample: "例如：下層每日取用，上層存季節用品。",
      options: [
        visual("daily", "日常快取", "storage/daily"),
        visual("archive", "長期備品", "storage/archive"),
      ],
    }),
  ],
  circulation: [
    axis({
      id: "circulation_width",
      label: "通道感受",
      prompt: "偏向寬敞通道，還是利用牆面增加機能？",
      customExample: "例如：主要通道保持寬敞，轉角做薄櫃。",
      options: [
        visual("wide", "寬敞通行", "circulation/wide"),
        visual("functional", "牆面機能", "circulation/functional"),
      ],
    }),
    axis({
      id: "entry_privacy",
      label: "入口視線",
      prompt: "進門希望一眼通透，還是有遮擋轉折？",
      customExample: "例如：用半高櫃遮擋客廳，但保持採光。",
      options: [
        visual("open", "視線通透", "circulation/open"),
        visual("screened", "遮擋隱私", "circulation/screened"),
      ],
    }),
    axis({
      id: "entry_storage",
      label: "入口收納",
      prompt: "偏向輕量落塵，還是完整玄關櫃？",
      customExample: "例如：鞋櫃做到頂，旁邊留穿鞋椅與掃地機位。",
      options: [
        visual("light", "輕量落塵", "circulation/light"),
        visual("full", "完整玄關收納", "circulation/full"),
      ],
    }),
  ],
};

const USES_AND_FURNITURE = {
  living_room: {
    uses: ["日常休息", "親友聚會", "影音娛樂", "親子活動", "居家工作"],
    furniture: ["沙發", "L 型沙發", "茶几", "電視櫃", "單椅", "收納櫃", "工作桌"],
  },
  bedroom: {
    uses: ["睡眠休息", "閱讀", "更衣", "化妝保養", "簡易工作"],
    furniture: ["床", "床頭櫃", "衣櫃", "梳妝台", "書桌", "工作椅"],
  },
  dining_room: {
    uses: ["日常用餐", "多人聚餐", "工作閱讀", "親子手作"],
    furniture: ["圓桌", "長桌", "餐椅", "餐邊櫃", "收納櫃"],
  },
  kitchen: {
    uses: ["簡易料理", "每日下廚", "烘焙", "多人共煮"],
    furniture: ["冰箱", "電器櫃", "中島", "餐櫃", "收納櫃"],
  },
  bathroom: {
    uses: ["淋浴", "泡澡", "乾濕分離", "衣物收納"],
    furniture: ["浴櫃", "鏡櫃", "浴缸", "收納架"],
  },
  balcony: {
    uses: ["洗曬衣物", "植栽", "休閒座位", "儲物"],
    furniture: ["洗衣機", "收納櫃", "戶外椅", "植栽架"],
  },
  storage: {
    uses: ["日用品收納", "季節備品", "家務工具", "大型物件"],
    furniture: ["收納櫃", "層架", "工作桌"],
  },
  circulation: {
    uses: ["通行", "玄關落塵", "穿鞋", "展示", "臨時置物"],
    furniture: ["鞋櫃", "穿鞋椅", "收納櫃", "展示架"],
  },
};

function imageKeyToken(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/_/g, "-")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function buildQuestionnaireImageKey(roomType, kind, groupId, value) {
  return [
    canonicalQuestionnaireRoomType(roomType),
    kind,
    groupId,
    value,
  ].map(imageKeyToken).join("/");
}

const READY_QUESTIONNAIRE_AXIS_IMAGE_KEYS =
  new Set(QUESTIONNAIRE_READY_IMAGE_KEYS);

const QUESTIONNAIRE_IMAGE_URLS = new Map([
  ["bathroom/axis/wet-dry/open-wet", "/static/questionnaire_images/qv-bathroom-wetroom-open.png"],
  ["bathroom/axis/wet-dry/separated", "/static/questionnaire_images/qv-bathroom-wetdry-separated.png"],
  ["kitchen/axis/kitchen-enclosure/closed", "/static/questionnaire_images/qv-kitchen-boundary-enclosed.png"],
  ["kitchen/axis/kitchen-enclosure/open", "/static/questionnaire_images/qv-kitchen-boundary-open.png"],
  ["living-room/axis/lighting/recessed-focus", "/static/questionnaire_images/qv-ceiling-lighting-recessed.png"],
  ["living-room/axis/lighting/surface-focus", "/static/questionnaire_images/qv-ceiling-lighting-surface.png"],
  ["living-room/axis/openness-storage/open-flow", "/static/questionnaire_images/qv-living-circulation-wide.png"],
  ["living-room/axis/openness-storage/storage-wall", "/static/questionnaire_images/qv-living-circulation-storage.png"],
]);

function questionnaireImageStatus(imageKeys = []) {
  const keys = [...new Set(imageKeys.filter(Boolean))];
  if (!keys.length) return "pending_discussion";
  const readyCount = keys.filter(
    (imageKey) => (
      READY_QUESTIONNAIRE_AXIS_IMAGE_KEYS.has(imageKey)
      && QUESTIONNAIRE_IMAGE_URLS.has(imageKey)
    ),
  ).length;
  if (readyCount === keys.length) return "ready";
  return readyCount > 0 ? "partially_ready" : "pending_discussion";
}

function scopedAxes(roomType, definitions) {
  return definitions.map((axisDefinition) => ({
    ...axisDefinition,
    options: axisDefinition.options.map((option) => {
      const imageKey = buildQuestionnaireImageKey(
        roomType,
        "axis",
        axisDefinition.id,
        option.value,
      );
      const imageUrl = QUESTIONNAIRE_IMAGE_URLS.get(imageKey);
      const imageReady =
        READY_QUESTIONNAIRE_AXIS_IMAGE_KEYS.has(imageKey) && Boolean(imageUrl);
      return {
        ...option,
        imageKey,
        imageStatus: imageReady ? "ready" : "pending_discussion",
        ...(imageReady
          ? { imageUrl }
          : {}),
      };
    }),
  }));
}

function technicalAxesForRoomType(roomType) {
  return scopedAxes(roomType, SHARED_AXES.filter((axisDefinition) => {
    if (axisDefinition.id !== "air_conditioning") return true;
    return ["living_room", "bedroom", "dining_room"].includes(roomType);
  }));
}

function makeTemplate(roomType) {
  const legacy = USES_AND_FURNITURE[roomType] || USES_AND_FURNITURE.storage;
  const specific = ROOM_SPECIFIC_AXES[roomType] || ROOM_SPECIFIC_AXES.storage;
  return Object.freeze({
    uses: legacy.uses,
    furniture: legacy.furniture,
    axes: Object.freeze(scopedAxes(roomType, specific)),
  });
}

export const ROOM_QUESTION_TEMPLATES = Object.freeze({
  living_room: makeTemplate("living_room"),
  bedroom: makeTemplate("bedroom"),
  dining_room: makeTemplate("dining_room"),
  kitchen: makeTemplate("kitchen"),
  bathroom: makeTemplate("bathroom"),
  balcony: makeTemplate("balcony"),
  storage: makeTemplate("storage"),
  circulation: makeTemplate("circulation"),
});

export function requirementsGate({
  basic,
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
} = {}) {
  const blockers = [];
  if (basic?.confirmed !== true) blockers.push("basic_questionnaire_incomplete");
  const keepExisting = new Set(keepExistingRoomIds);
  const unresolvedRoomIds = rooms
    .map((room) => room.id)
    .filter((roomId) => {
      const answer = answers[roomId];
      const room = rooms.find((candidate) => candidate.id === roomId);
      const planned = roomAnswerIsComplete(room, answer);
      return !planned && !keepExisting.has(roomId);
    });
  if (unresolvedRoomIds.length) blockers.push("room_requirements_incomplete");
  return {
    ready: blockers.length === 0,
    blockers,
    unresolvedRoomIds,
  };
}

export function canonicalQuestionnaireRoomType(roomType) {
  const aliases = {
    dormitory: "bedroom",
    master_bedroom: "bedroom",
    deposit: "storage",
    living: "living_room",
    dining: "dining_room",
    toilet: "bathroom",
    washroom: "bathroom",
    corridor: "circulation",
    hallway: "circulation",
  };
  return aliases[String(roomType || "").toLowerCase()]
    || String(roomType || "").toLowerCase();
}

export function roomQuestionTemplate(roomType) {
  const canonicalType = canonicalQuestionnaireRoomType(roomType);
  return ROOM_QUESTION_TEMPLATES[canonicalType] || ROOM_QUESTION_TEMPLATES.storage;
}

export function roomTechnicalAxes(roomType) {
  const canonicalType = canonicalQuestionnaireRoomType(roomType);
  const namespace = ROOM_QUESTION_TEMPLATES[canonicalType] ? canonicalType : "storage";
  return technicalAxesForRoomType(namespace);
}

function inferLegacyRoomType(roomId, answer = {}) {
  const axisIds = new Set(Object.keys(answer?.axes || answer?.preference_axes || {}));
  const axisType = Object.entries(ROOM_SPECIFIC_AXES).find(([, axes]) =>
    axes.some((axisDefinition) => axisIds.has(axisDefinition.id))
  )?.[0];
  if (axisType) return axisType;
  const raw = String(roomId || "")
    .replace(/-\d+$/, "")
    .replace(/_\d+$/, "");
  return canonicalQuestionnaireRoomType(raw);
}

function legacyRoomOrdinal(roomId) {
  const match = String(roomId || "").match(/[-_](\d+)$/);
  return match ? Math.max(0, Number(match[1]) - 1) : 0;
}

export function questionnaireRoomIdentity(room = {}) {
  const points = Array.isArray(room.polygon_m) ? room.polygon_m : [];
  const validPoints = points
    .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const centroidM = validPoints.length
    ? {
        x: validPoints.reduce((sum, point) => sum + point.x, 0) / validPoints.length,
        y: validPoints.reduce((sum, point) => sum + point.y, 0) / validPoints.length,
      }
    : null;
  const areaM2 = validPoints.length >= 3
    ? Math.abs(validPoints.reduce((sum, point, index) => {
        const next = validPoints[(index + 1) % validPoints.length];
        return sum + point.x * next.y - next.x * point.y;
      }, 0) / 2)
    : null;
  return {
    type: canonicalQuestionnaireRoomType(room.type),
    label: String(room.label || "").trim(),
    centroid_m: centroidM,
    area_m2: areaM2,
  };
}

function roomIdentityDistance(room, storedIdentity) {
  const current = questionnaireRoomIdentity(room);
  const storedCenter = storedIdentity?.centroid_m;
  if (
    !current.centroid_m
    || !Number.isFinite(Number(storedCenter?.x))
    || !Number.isFinite(Number(storedCenter?.y))
  ) return Number.POSITIVE_INFINITY;
  const distance = Math.hypot(
    current.centroid_m.x - Number(storedCenter.x),
    current.centroid_m.y - Number(storedCenter.y),
  );
  const storedArea = Number(storedIdentity?.area_m2);
  const areaPenalty = Number.isFinite(storedArea) && Number.isFinite(current.area_m2)
    ? Math.abs(current.area_m2 - storedArea) / Math.max(1, storedArea)
    : 0;
  return distance + areaPenalty;
}

function bestLegacyRoomCandidate(candidates, roomId, answer = {}) {
  if (!candidates.length) return null;
  const storedIdentity = answer?.roomIdentity;
  if (storedIdentity?.centroid_m) {
    return [...candidates].sort(
      (left, right) =>
        roomIdentityDistance(left, storedIdentity)
        - roomIdentityDistance(right, storedIdentity)
    )[0];
  }
  const storedLabel = String(storedIdentity?.label || "").trim();
  if (storedLabel) {
    const labelMatch = candidates.find(
      (room) => String(room.label || "").trim() === storedLabel
    );
    if (labelMatch) return labelMatch;
  }
  return candidates[legacyRoomOrdinal(roomId)] || candidates[0];
}

export function reconcileRoomQuestionnaireState({
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
} = {}) {
  const currentIds = new Set(rooms.map((room) => room.id));
  const roomsByType = new Map();
  rooms.forEach((room) => {
    const type = canonicalQuestionnaireRoomType(room.type);
    const entries = roomsByType.get(type) || [];
    entries.push(room);
    roomsByType.set(type, entries);
  });
  const reconciledAnswers = {};
  const consumedLegacyIds = new Set();
  const discardedRoomIds = new Set();
  const reconciledKeepIds = [];

  Object.entries(answers || {}).forEach(([roomId, answer]) => {
    if (currentIds.has(roomId)) reconciledAnswers[roomId] = answer;
  });
  Object.entries(answers || {}).forEach(([roomId, answer]) => {
    if (currentIds.has(roomId)) return;
    const candidates = (roomsByType.get(inferLegacyRoomType(roomId, answer)) || [])
      .filter((room) => !reconciledAnswers[room.id]);
    const target = bestLegacyRoomCandidate(candidates, roomId, answer);
    if (!target) {
      discardedRoomIds.add(roomId);
      return;
    }
    reconciledAnswers[target.id] = answer;
    if (
      answer?.keepExisting === true
      && keepExistingRoomIds.includes(roomId)
      && !reconciledKeepIds.includes(target.id)
    ) {
      reconciledKeepIds.push(target.id);
    }
    consumedLegacyIds.add(roomId);
  });

  (keepExistingRoomIds || []).forEach((roomId) => {
    if (currentIds.has(roomId)) {
      if (!reconciledKeepIds.includes(roomId)) {
        reconciledKeepIds.push(roomId);
      }
      return;
    }
    if (consumedLegacyIds.has(roomId)) return;
    const candidates = roomsByType.get(inferLegacyRoomType(roomId)) || [];
    const preferred = candidates[legacyRoomOrdinal(roomId)];
    const target = preferred
      && !reconciledAnswers[preferred.id]
      && !reconciledKeepIds.includes(preferred.id)
      ? preferred
      : candidates.find(
        (room) => !reconciledAnswers[room.id] && !reconciledKeepIds.includes(room.id)
      );
    if (target) {
      reconciledKeepIds.push(target.id);
      consumedLegacyIds.add(roomId);
    } else {
      discardedRoomIds.add(roomId);
    }
  });

  return {
    answers: reconciledAnswers,
    keepExistingRoomIds: reconciledKeepIds,
    discardedRoomIds: [...discardedRoomIds],
  };
}

export function materialPreferenceOptions(roomType) {
  const canonicalType = canonicalQuestionnaireRoomType(roomType);
  const namespace = ROOM_QUESTION_TEMPLATES[canonicalType] ? canonicalType : "storage";
  return Object.fromEntries(
    Object.entries(MATERIAL_PREFERENCE_BASE).map(([category, options]) => [
      category,
      options.map((option) => ({
        ...option,
        imageKey: buildQuestionnaireImageKey(
          namespace,
          "material",
          category,
          option.value,
        ),
        imageStatus: "pending_discussion",
      })),
    ])
  );
}

export function questionnaireImageManifest() {
  const entries = [];
  Object.entries(ROOM_QUESTION_TEMPLATES).forEach(([roomType, template]) => {
    [...template.axes, ...roomTechnicalAxes(roomType)].forEach((axisDefinition) => {
      axisDefinition.options.forEach((option) => {
        entries.push({
          image_key: option.imageKey,
          room_type: roomType,
          kind: "axis_option",
          group_id: axisDefinition.id,
          value: option.value,
          label: option.label,
          status: option.imageStatus,
          ...(option.imageUrl ? { image_url: option.imageUrl } : {}),
        });
      });
    });
    Object.entries(materialPreferenceOptions(roomType)).forEach(([category, options]) => {
      options.forEach((option) => {
        entries.push({
          image_key: option.imageKey,
          room_type: roomType,
          kind: "material_option",
          group_id: category,
          value: option.value,
          label: option.label,
          status: option.imageStatus,
        });
      });
    });
  });
  return entries;
}

export function normalizeQuickValues(question, values = []) {
  const normalized = [...new Set((values || []).filter(Boolean))];
  const exclusive = new Set(question?.exclusiveValues || []);
  if (normalized.length <= 1 || !normalized.some((value) => exclusive.has(value))) {
    return normalized;
  }
  return normalized.filter((value) => !exclusive.has(value));
}

export function resolveAxisChoice(axisDefinition, value) {
  if (!axisDefinition) throw new Error("axis_not_found");
  const normalizedValue = normalizeAxisChoice(axisDefinition, value);
  if (
    value === "both"
    || (axisDefinition.mode === "exclusive" && !["a", "b"].includes(normalizedValue))
  ) {
    throw new Error("mutually_exclusive_axis");
  }
  if (!["a", "lean_a", "balanced", "lean_b", "b"].includes(normalizedValue)) {
    throw new Error("invalid_axis_choice");
  }
  const endpointA = axisDefinition.options.find((item) => item.pole === "a");
  const endpointB = axisDefinition.options.find((item) => item.pole === "b");
  const selectedLabel = {
    a: endpointA.label,
    lean_a: `偏重 A：${endpointA.label}`,
    balanced: "兩者平衡",
    lean_b: `偏重 B：${endpointB.label}`,
    b: endpointB.label,
  }[normalizedValue];
  const selectedEndpoints = {
    a: [endpointA],
    lean_a: [endpointA, endpointB],
    balanced: [endpointA, endpointB],
    lean_b: [endpointA, endpointB],
    b: [endpointB],
  }[normalizedValue];
  return {
    value: normalizedValue,
    selected_label: selectedLabel,
    mode: axisDefinition.mode,
    endpoint_a: {
      value: endpointA.value,
      label: endpointA.label,
      image_key: endpointA.imageKey,
    },
    endpoint_b: {
      value: endpointB.value,
      label: endpointB.label,
      image_key: endpointB.imageKey,
    },
    image_keys: selectedEndpoints.map((item) => item.imageKey),
    riskTags: [...new Set(selectedEndpoints.flatMap((item) => item.riskTags || []))],
  };
}

export function normalizeAxisChoice(axisDefinition, value) {
  const raw = typeof value === "object" && value
    ? value.preference || value.value || ""
    : String(value || "");
  if (["a", "lean_a", "balanced", "lean_b", "b"].includes(raw)) return raw;
  return axisDefinition?.legacyPreferenceMap?.[raw] || raw;
}

export function buildRoomPreferenceSummary(room, answer = {}) {
  const template = roomQuestionTemplate(room?.type);
  const decisions = [...template.axes, ...roomTechnicalAxes(room?.type)]
    .flatMap((axisDefinition) => {
    const storedValue = answer.axes?.[axisDefinition.id];
    if (!storedValue) return [];
    try {
      const resolved = resolveAxisChoice(axisDefinition, storedValue);
      const explanation = {
        a: `明確採用 A「${resolved.endpoint_a.label}」`,
        lean_a: `以 A「${resolved.endpoint_a.label}」為主，保留少量 B 的機能`,
        balanced: `在 A「${resolved.endpoint_a.label}」與 B「${resolved.endpoint_b.label}」之間平衡`,
        lean_b: `以 B「${resolved.endpoint_b.label}」為主，保留少量 A 的特點`,
        b: `明確採用 B「${resolved.endpoint_b.label}」`,
      }[resolved.value];
      return [{
        axis_id: axisDefinition.id,
        axis_label: axisDefinition.label,
        preference: resolved.value,
        selected_label: resolved.selected_label,
        basis: explanation,
        explanation,
        other_approach: answer.customNotes?.[axisDefinition.id] || "",
      }];
    } catch {
      return [];
    }
    });
  const warnings = collectQuestionnaireWarnings({
    rooms: room ? [room] : [],
    answers: room ? { [room.id]: answer } : {},
  });
  const uses = answer.uses || [];
  const furniture = answer.furniture || [];
  const decisionText = decisions.map((item) => `${item.axis_label}：${item.explanation}`);
  return {
    room_id: room?.id || "",
    room_label: room?.label || "此空間",
    headline: decisions.length
      ? `${room?.label || "此空間"}已整理 ${decisions.length} 項偏好，可交給家具與材質檢索。`
      : `尚未完成${room?.label || "此空間"}的偏好選擇。`,
    basis: [
      uses.length ? `使用需求：${uses.join("、")}` : "",
      ...decisionText,
    ].filter(Boolean),
    decisions,
    furniture,
    other_approaches: decisions
      .filter((item) => item.other_approach)
      .map((item) => `${item.axis_label}：${item.other_approach}`),
    warnings,
  };
}

export function validateCeilingPreference({
  axisDefinition,
  value,
  choice,
  roomHeightCm = 270,
  rawHeightCm,
  minimumFinishedHeightCm = 240,
} = {}) {
  const resolvedRoomHeightCm = Number(rawHeightCm ?? roomHeightCm);
  const resolvedValue = choice ?? value;
  const ceilingAxis = axisDefinition
    || SHARED_AXES.find((axisItem) => axisItem.id === "ceiling");
  if (ceilingAxis?.id !== "ceiling") {
    return {
      ready: true,
      estimatedDropCm: 0,
      finishedHeightCm: resolvedRoomHeightCm,
      estimatedFinishedHeightCm: resolvedRoomHeightCm,
    };
  }
  const preference = normalizeAxisChoice(ceilingAxis, resolvedValue);
  const estimatedDropCm = {
    a: 0,
    lean_a: 8,
    balanced: 15,
    lean_b: 22,
    b: 25,
  }[preference];
  if (!Number.isFinite(estimatedDropCm)) {
    return {
      ready: false,
      code: "ceiling_preference_required",
      reason: "ceiling_preference_required",
    };
  }
  const finishedHeightCm = resolvedRoomHeightCm - estimatedDropCm;
  const code = finishedHeightCm >= Number(minimumFinishedHeightCm)
    ? ""
    : "minimum_finished_height";
  return {
    ready: finishedHeightCm >= Number(minimumFinishedHeightCm),
    estimatedDropCm,
    finishedHeightCm,
    estimatedFinishedHeightCm: finishedHeightCm,
    minimumFinishedHeightCm: Number(minimumFinishedHeightCm),
    code,
    reason: code ? "minimum_finished_height_not_met" : "",
  };
}

export function validateQuestionnaireCeilings({
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
  roomHeightCm = 270,
  minimumFinishedHeightCm = 240,
} = {}) {
  const keepExisting = new Set(keepExistingRoomIds);
  const invalidRooms = rooms.flatMap((room) => {
    if (keepExisting.has(room.id)) return [];
    const answer = answers[room.id];
    if (!answer?.confirmed) return [];
    const axisDefinition = roomTechnicalAxes(room.type).find(
      (item) => item.id === "ceiling"
    );
    const result = validateCeilingPreference({
      axisDefinition,
      value: answer.axes?.ceiling,
      roomHeightCm,
      minimumFinishedHeightCm,
    });
    return result.ready ? [] : [{
      roomId: room.id,
      roomLabel: room.label,
      ...result,
    }];
  });
  return {
    ready: invalidRooms.length === 0,
    invalidRooms,
    firstInvalid: invalidRooms[0] || null,
  };
}

function basicQuestionIsAnswered(question, value) {
  if (!question.required) return true;
  if (Array.isArray(value)) return value.length > 0;
  return Boolean(String(value ?? "").trim());
}

export function roomAnswerIsComplete(room, answer) {
  if (!answer?.confirmed) return false;
  if (answer.schemaVersion !== QUESTIONNAIRE_SCHEMA_VERSION) return false;
  if (!Array.isArray(answer.uses) || answer.uses.length === 0) return false;
  const template = roomQuestionTemplate(room.type);
  return [...template.axes, ...roomTechnicalAxes(room.type)]
    .filter((item) => item.required)
    .every((item) => {
      const selected = answer.axes?.[item.id];
      if (!selected) return false;
      try {
        resolveAxisChoice(item, selected);
        return true;
      } catch {
        return false;
      }
    });
}

export function questionnaireCompletion({
  basicAnswers = {},
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
} = {}) {
  const incomplete = WHOLE_HOUSE_QUESTIONS
    .filter((question) => !basicQuestionIsAnswered(question, basicAnswers[question.id]))
    .map((question) => ({
      kind: "basic",
      questionId: question.id,
      label: question.label,
    }));
  const keepExisting = new Set(keepExistingRoomIds);
  rooms.forEach((room) => {
    if (!keepExisting.has(room.id) && !roomAnswerIsComplete(room, answers[room.id])) {
      incomplete.push({
        kind: "room",
        roomId: room.id,
        label: room.label,
      });
    }
  });
  const completedRooms = rooms.filter((room) =>
    keepExisting.has(room.id) || roomAnswerIsComplete(room, answers[room.id])
  ).length;
  return {
    ready: incomplete.length === 0,
    completedRooms,
    totalRooms: rooms.length,
    incomplete,
    nextIncomplete: incomplete[0] || null,
  };
}

const RISK_MESSAGES = {
  wall: "此選擇涉及拆牆或改牆，需確認牆體性質、管委會規範與現場條件。",
  gas: "此選擇涉及瓦斯設備或管線，需由合格專業人員確認位置與安全距離。",
  electricity: "此選擇涉及用電調整，需確認迴路、負載與施工可行性。",
  plumbing: "此選擇涉及給水位置，需確認既有管線與防水層。",
  drainage: "此選擇涉及排水位置或坡度，需確認落水頭與樓板條件。",
  smoke_exhaust: "此選擇涉及排煙，需確認可用排放路徑及大樓規範。",
  function_relocation: "此功能可能離開原有合理位置，需核對既有機電與結構條件。",
};

export function collectQuestionnaireWarnings({ rooms = [], answers = {} } = {}) {
  const warnings = [];
  const seen = new Set();
  rooms.forEach((room) => {
    const answer = answers[room.id];
    if (!answer?.axes) return;
    const axes = [
      ...roomQuestionTemplate(room.type).axes,
      ...roomTechnicalAxes(room.type),
    ];
    axes.forEach((axisDefinition) => {
      let selected = null;
      try {
        selected = resolveAxisChoice(axisDefinition, answer.axes[axisDefinition.id]);
      } catch {
        selected = null;
      }
      (selected?.riskTags || []).forEach((risk) => {
        const key = `${room.id}:${risk}`;
        if (seen.has(key)) return;
        seen.add(key);
        warnings.push({
          id: key,
          roomId: room.id,
          roomLabel: room.label,
          risk,
          reason: RISK_MESSAGES[risk] || "此選擇需要設計師進一步確認。",
        });
      });
    });
    const freeText = [
      ...Object.values(answer.customNotes || {}),
      ...Object.values(answer.stageNotes || {}),
      answer.priority,
      answer.personalNeeds,
      ...(answer.materialPreferences?.cuts || []),
    ].join(" ");
    const keywordRisks = [
      ["wall", /拆牆|改牆|移牆|打牆|開放式/],
      ["gas", /瓦斯|燃氣/],
      ["electricity", /插座|電路|用電|220\s*v|電箱|電力|新增燈/iu],
      ["plumbing", /給水|水管|洗手台|水槽/],
      ["drainage", /排水|落水|馬桶|浴缸/],
      ["smoke_exhaust", /排煙|油煙|抽油煙/],
      ["function_relocation", /移位|換位置|搬到|改到|改成廚房|改成浴室|改成廁所/],
    ];
    keywordRisks.forEach(([risk, pattern]) => {
      if (!pattern.test(freeText)) return;
      const key = `${room.id}:${risk}`;
      if (seen.has(key)) return;
      seen.add(key);
      warnings.push({
        id: key,
        roomId: room.id,
        roomLabel: room.label,
        risk,
        reason: RISK_MESSAGES[risk],
      });
    });
  });
  return warnings.map((warning, index) => ({
    ...warning,
    index: index + 1,
    total: warnings.length,
    position: `${index + 1}/${warnings.length}`,
  }));
}

export function cloneRoomAnswer(sourceAnswer, { sourceRoomId = null } = {}) {
  if (!sourceAnswer) return null;
  return {
    ...JSON.parse(JSON.stringify(sourceAnswer)),
    confirmed: false,
    copiedFromRoomId: sourceRoomId,
  };
}

function materialPreferences(answer) {
  const preferences = answer?.materialPreferences || {};
  const hasPreference = Object.values(preferences).some((value) =>
    Array.isArray(value) ? value.length > 0 : Boolean(value)
  );
  return {
    status: hasPreference ? "defined" : "not_defined",
    wall: preferences.wall || [],
    floor: preferences.floor || [],
    furniture: preferences.furniture || [],
    color: preferences.color || [],
    finish: preferences.finish || [],
    cuts: preferences.cuts || [],
  };
}

export function buildClientBrief({
  basicAnswers = {},
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
  designerNotes = "",
} = {}) {
  const keepExisting = new Set(keepExistingRoomIds);
  const roomBriefs = {};
  rooms.forEach((room) => {
    const answer = answers[room.id] || {};
    if (keepExisting.has(room.id)) {
      roomBriefs[room.id] = {
        room_id: room.id,
        room_label: room.label,
        room_type: room.type,
        planning_status: "keep_existing",
        material_preferences: materialPreferences(null),
      };
      return;
    }
    const selectedRisks = collectQuestionnaireWarnings({
      rooms: [room],
      answers: { [room.id]: answer },
    }).map((warning) => warning.risk);
    const template = roomQuestionTemplate(room.type);
    const documentedAxes = [
      ...template.axes,
      ...roomTechnicalAxes(room.type),
    ];
    const preferenceAxisDetails = Object.fromEntries(
      documentedAxes.map((axisDefinition) => {
        const storedValue = answer.axes?.[axisDefinition.id] || "";
        try {
          const resolved = resolveAxisChoice(axisDefinition, storedValue);
          return [axisDefinition.id, {
            preference: resolved.value,
            selected_label: resolved.selected_label,
            mode: resolved.mode,
            endpoint_a: resolved.endpoint_a,
            endpoint_b: resolved.endpoint_b,
            other_approach: answer.customNotes?.[axisDefinition.id] || "",
          }];
        } catch {
          return [axisDefinition.id, {
            preference: "",
            selected_label: "",
            mode: axisDefinition.mode,
            endpoint_a: null,
            endpoint_b: null,
            other_approach: answer.customNotes?.[axisDefinition.id] || "",
          }];
        }
      })
    );
    roomBriefs[room.id] = {
      room_id: room.id,
      room_label: room.label,
      room_type: room.type,
      planning_status: roomAnswerIsComplete(room, answer)
        ? "confirmed"
        : "incomplete",
      uses: answer.uses || [],
      furniture_requirements: answer.furniture || [],
      preference_axes: answer.axes || {},
      preference_axis_details: preferenceAxisDetails,
      integrated_summary: buildRoomPreferenceSummary(room, answer),
      custom_notes: answer.customNotes || {},
      stage_notes: answer.stageNotes || { uses: "", furniture: "" },
      priority: answer.priority || "",
      personal_needs: answer.personalNeeds || "無",
      material_preferences: materialPreferences(answer),
      structure_strategy: selectedRisks.includes("wall")
        ? "compare_changed_and_unchanged"
        : "keep_current_structure",
      safety_risks: selectedRisks,
    };
  });
  return {
    schema_version: QUESTIONNAIRE_SCHEMA_VERSION,
    occupants: {
      residents: basicAnswers.residents || [],
      resident_count: basicAnswers.residentCount || "",
      age_needs: basicAnswers.ageNeeds || [],
    },
    lifestyle: {
      schedule_interference: basicAnswers.scheduleInterference || [],
      home_work_study: {
        frequency_and_people: basicAnswers.homeWorkStudyCount || "",
        needs: basicAnswers.homeWorkStudyNeeds || [],
      },
      hosting: {
        frequency: basicAnswers.hostingFrequency || "",
        needs: basicAnswers.hostingNeeds || [],
      },
    },
    future_changes: basicAnswers.futureChanges || [],
    budget_and_timeline: {
      priority: basicAnswers.budgetPriority || "",
      range: basicAnswers.budgetRange || "",
      target: basicAnswers.targetTimeline || "",
    },
    immutable_needs: basicAnswers.immutableNeeds || [],
    basic_notes: basicAnswers.notes || {},
    rooms: roomBriefs,
    warnings: collectQuestionnaireWarnings({ rooms, answers }),
    designer_notes: designerNotes,
    privacy: {
      project_only: true,
      no_training: true,
    },
  };
}

function selectedBasicValues(question, basicAnswers) {
  const value = basicAnswers?.[question.id];
  if (question.type === "multi") return Array.isArray(value) ? value : [];
  return value ? [value] : [];
}

export function buildQuestionnaireDocument({
  projectId = "",
  basicAnswers = {},
  rooms = [],
  answers = {},
  keepExistingRoomIds = [],
  designerNotes = "",
} = {}) {
  const keepExisting = new Set(keepExistingRoomIds);
  const requiredImageKeys = new Set();
  const selectedImageKeys = new Set();
  const roomDocuments = rooms.map((room) => {
    const answer = answers[room.id] || {};
    const template = roomQuestionTemplate(room.type);
    const questionnaireAxes = [
      ...template.axes,
      ...roomTechnicalAxes(room.type),
    ];
    const availableMaterials = materialPreferenceOptions(room.type);
    Object.entries(availableMaterials).forEach(([category, options]) => {
      const selectedValues = answer.materialPreferences?.[category] || [];
      options.forEach((option) => {
        if (selectedValues.includes(option.value)) selectedImageKeys.add(option.imageKey);
      });
    });
    const axes = questionnaireAxes.map((axisDefinition) => {
      const storedValue = answer.axes?.[axisDefinition.id] || "";
      let selected = null;
      try {
        selected = resolveAxisChoice(axisDefinition, storedValue);
      } catch {
        selected = null;
      }
      const availableOptions = axisDefinition.options.map((option) => {
        if (option.imageKey) requiredImageKeys.add(option.imageKey);
        return {
          pole: option.pole,
          value: option.value,
          label: option.label,
          image_key: option.imageKey || "",
          image_status: option.imageStatus || "pending_discussion",
          risk_tags: option.riskTags || [],
        };
      });
      (selected?.image_keys || []).forEach((imageKey) => selectedImageKeys.add(imageKey));
      return {
        axis_id: axisDefinition.id,
        label: axisDefinition.label,
        prompt: axisDefinition.prompt,
        mode: axisDefinition.mode,
        selected_value: selected?.value || "",
        selected_label: selected?.selected_label || "",
        image_keys: selected?.image_keys || [],
        image_status: questionnaireImageStatus(selected?.image_keys || []),
        custom_note: answer.customNotes?.[axisDefinition.id] || "",
        risk_tags: selected?.riskTags || [],
        preference_options: axisDefinition.preferenceOptions,
        available_options: availableOptions,
      };
    });
    return {
      room_id: room.id,
      room_label: room.label,
      room_type: room.type,
      planning_status: keepExisting.has(room.id)
        ? "keep_existing"
        : roomAnswerIsComplete(room, answer)
          ? "confirmed"
          : "incomplete",
      axes,
      uses: answer.uses || [],
      furniture: answer.furniture || [],
      stage_notes: answer.stageNotes || { uses: "", furniture: "" },
      priority: answer.priority || "",
      personal_needs: answer.personalNeeds || "無",
      material_preferences: materialPreferences(answer),
      copied_from_room_id: answer.copiedFromRoomId || null,
      available_material_options: Object.fromEntries(
        Object.entries(availableMaterials).map(([category, options]) => [
          category,
          options.map((option) => {
            requiredImageKeys.add(option.imageKey);
            return {
              value: option.value,
              label: option.label,
              image_key: option.imageKey,
              image_status: option.imageStatus,
            };
          }),
        ])
      ),
    };
  });
  return {
    document_type: "roompilot.requirements_questionnaire",
    schema_version: QUESTIONNAIRE_SCHEMA_VERSION,
    project_id: projectId,
    notice: QUESTIONNAIRE_NOTICE,
    image_assets: {
      status: questionnaireImageStatus([...requiredImageKeys]),
      required_image_keys: [...requiredImageKeys],
      selected_image_keys: [...selectedImageKeys],
    },
    basic_questions: WHOLE_HOUSE_QUESTIONS.map((question) => {
      const selectedValues = selectedBasicValues(question, basicAnswers);
      return {
        question_id: question.id,
        label: question.label,
        answer_type: question.type,
        required: question.required,
        selected_values: selectedValues,
        selected_labels: selectedValues.map(
          (value) => question.options.find((option) => option.value === value)?.label || value
        ),
        note: basicAnswers.notes?.[question.id] || "",
      };
    }),
    rooms: roomDocuments,
    client_brief: buildClientBrief({
      basicAnswers,
      rooms,
      answers,
      keepExistingRoomIds,
      designerNotes,
    }),
  };
}
