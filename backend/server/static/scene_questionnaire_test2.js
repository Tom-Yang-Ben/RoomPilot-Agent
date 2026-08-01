const ROOM_TO_VISUAL_SPACES = Object.freeze({
  entry: ["entryway"],
  living_room: ["living_room"],
  dining_room: ["dining_room"],
  kitchen: ["kitchen"],
  bathroom: ["bathroom"],
  workspace: ["study"],
  balcony: ["balcony"],
  storage: ["storage"],
});

export const VISUAL_SPACE_LABELS = Object.freeze({
  entryway: "玄關",
  living_room: "客廳",
  dining_room: "餐廳",
  kitchen: "廚房",
  primary_bedroom: "主臥",
  secondary_bedroom: "次臥",
  bathroom: "浴室",
  study: "書房／工作區",
  balcony: "陽台",
  storage: "儲藏空間",
  circulation: "走道／動線",
  all_rooms: "全屋共通",
});

function roomAreaM2(room = {}) {
  const polygon = room.polygon_cm || [];
  if (polygon.length < 3) {
    return Number(room.area_m2 || room.areaM2 || 0);
  }
  let twiceArea = 0;
  for (let index = 0; index < polygon.length; index += 1) {
    const current = polygon[index];
    const next = polygon[(index + 1) % polygon.length];
    twiceArea += (Number(current.x) * Number(next.y)) - (Number(next.x) * Number(current.y));
  }
  return Math.abs(twiceArea) / 2 / 10_000;
}

// 主臥依面積決定，不是依辨識順序。原本取「第一間臥室」，QA 的案子因此把 7.29 m²
// 標成主臥，8.04 m² 的真主臥反而變次臥。
function primaryBedroomId(rooms = []) {
  const bedrooms = rooms.filter(
    (room) => room.type === "bedroom"
      && !["primary_bedroom", "secondary_bedroom"].includes(room.visual_space_type),
  );
  if (!bedrooms.length) return null;
  const largest = bedrooms.reduce(
    (winner, room) => (roomAreaM2(room) > roomAreaM2(winner) ? room : winner),
    bedrooms[0],
  );
  return largest.id;
}

export function questionsForRooms(questions = [], rooms = []) {
  const primaryId = primaryBedroomId(rooms);
  const roomSpaces = new Set();
  rooms.forEach((room) => {
    if (["primary_bedroom", "secondary_bedroom"].includes(room.visual_space_type)) {
      roomSpaces.add(room.visual_space_type);
      return;
    }
    if (room.type === "bedroom") {
      roomSpaces.add(room.id === primaryId ? "primary_bedroom" : "secondary_bedroom");
      return;
    }
    (ROOM_TO_VISUAL_SPACES[room.type] || []).forEach((space) => roomSpaces.add(space));
  });
  const sharedSpaces = new Set(["circulation", "all_rooms"]);
  return questions.filter(
    (question) => roomSpaces.has(question.space_type)
      || sharedSpaces.has(question.space_type),
  );
}

function visualSpaceForRoom(room, primaryId = null) {
  if (["primary_bedroom", "secondary_bedroom"].includes(room.visual_space_type)) {
    return room.visual_space_type;
  }
  if (room.type === "bedroom") {
    return room.id === primaryId ? "primary_bedroom" : "secondary_bedroom";
  }
  return ROOM_TO_VISUAL_SPACES[room.type]?.[0] || null;
}

export function questionsForIndividualRooms(questions = [], rooms = []) {
  const primaryId = primaryBedroomId(rooms);
  return rooms.flatMap((room) => {
    const roomSpace = visualSpaceForRoom(room, primaryId);
    const matching = questions.filter((question) =>
      question.space_type === roomSpace || question.space_type === "all_rooms"
    );
    return matching.map((question) => ({
      ...question,
      source_question_id: question.question_id,
      question_id: `${room.id}:${question.question_id}`,
      room_id: room.id,
      room_label: room.name || room.label || VISUAL_SPACE_LABELS[roomSpace] || roomSpace,
      room_type: room.type,
    }));
  });
}

export function suggestSharedRoomAnswers({
  questions = [],
  answers = {},
  sourceRoomId,
  targetRoomId,
} = {}) {
  const sourceAnswers = new Map();
  questions
    .filter(
      (question) => String(question.room_id) === String(sourceRoomId)
        && question.space_type === "all_rooms",
    )
    .forEach((question) => {
      const answer = answers[question.question_id];
      if (!answer?.optionId) return;
      sourceAnswers.set(question.source_question_id || question.question_id, answer);
    });

  return Object.fromEntries(
    questions
      .filter(
        (question) => String(question.room_id) === String(targetRoomId)
          && question.space_type === "all_rooms"
          && !answers[question.question_id]?.optionId,
      )
      .flatMap((question) => {
        const sourceQuestionId = question.source_question_id || question.question_id;
        const sourceAnswer = sourceAnswers.get(sourceQuestionId);
        if (!sourceAnswer) return [];
        const optionExists = sourceAnswer.optionId === "both"
          ? question.allow_both === true
          : question.options?.some(
            (option) => option.option_id === sourceAnswer.optionId,
          );
        if (!optionExists) return [];
        return [[question.question_id, {
          optionId: sourceAnswer.optionId,
          custom: sourceAnswer.custom || "",
          suggested: true,
          suggestedFromRoomId: String(sourceRoomId),
        }]];
      }),
  );
}

export function occupantsFromBasicAnswers(basic = {}) {
  const occupants = { adults: 2, children: 0, elderly: 0, pets: 0 };
  const household = basic.household || "";
  if (household === "一人") occupants.adults = 1;
  if (household === "親子家庭") occupants.children = 1;
  if (household === "三代同堂") {
    occupants.children = 1;
    occupants.elderly = 1;
  }
  const membersAndPets = basic.membersAndPets || "";
  if (membersAndPets === "有幼兒") occupants.children = Math.max(1, occupants.children);
  if (membersAndPets === "有長輩") occupants.elderly = Math.max(1, occupants.elderly);
  if (membersAndPets === "有貓" || membersAndPets === "有狗") occupants.pets = 1;
  return occupants;
}

export function answeredVisualQuestionIds(answers = {}) {
  return Object.entries(answers)
    .filter(([, answer]) => Boolean(answer?.optionId))
    .map(([questionId]) => questionId);
}

export function applyVisualPreferencesToSpecs(specs = [], visualPreferences = []) {
  const next = specs.map((spec) => [...spec]);
  const effects = Object.assign(
    {},
    ...visualPreferences.map((preference) => preference.engine_effects || {}),
  );
  next.forEach((spec) => {
    if (effects.sofa_layout === "sectional" && spec[0] === "sofa") {
      spec[1] = "l-shape";
      spec[2] = "極與極偏好：L 型沙發配置";
    }
    if (Number(effects.dining_capacity) >= 6 && spec[0] === "dining-table") {
      spec[1] = "rect-6";
      spec[2] = "極與極偏好：六人用餐";
    } else if (Number(effects.dining_capacity) === 4 && spec[0] === "dining-table") {
      spec[1] = "rect-4";
      spec[2] = "極與極偏好：日常四人用餐";
    }
  });
  const ensureAutoFurniture = (enabled, type, variant, reason) => {
    if (enabled && !next.some(([candidate]) => candidate === type)) {
      next.push([type, variant, reason, true]);
    }
  };
  ensureAutoFurniture(
    effects.entry_seat === true,
    "lounge-chair",
    "accent",
    "極與極偏好：玄關需要坐下換鞋",
  );
  ensureAutoFurniture(
    effects.entry_storage_priority === "high"
      || effects.storage_strategy === "distributed",
    "storage-cabinet",
    "tall",
    "極與極偏好：提高收納配置",
  );
  ensureAutoFurniture(
    effects.dining_anchor === "island",
    "kitchen-island",
    "standard",
    "極與極偏好：中島用餐",
  );
  return next;
}

export function visualQuestionnaireProgress({
  questions = [],
  answers = {},
  skippedSpaceTypes = [],
} = {}) {
  const skipped = new Set(skippedSpaceTypes);
  const resolved = questions.filter(
    (question) => answers[question.question_id]?.optionId
      || skipped.has(question.space_type),
  );
  return {
    completed: resolved.length,
    total: questions.length,
    ready: questions.length > 0 && resolved.length === questions.length,
  };
}

export function finishesGate(finishes = {}) {
  const missing = [];
  if (!finishes.stylePackId) missing.push("style_card");
  if (!finishes.wallMaterial) missing.push("wall_material");
  if (!finishes.wallColor) missing.push("wall_color");
  if (!finishes.floorMaterial) missing.push("floor_material");
  if (!finishes.floorColor) missing.push("floor_color");
  if (!finishes.ceilingMaterial) missing.push("ceiling_material");
  if (!finishes.ceilingStyle) missing.push("ceiling_style");
  if (!finishes.lightStyle) missing.push("light_style");
  return {
    ready: missing.length === 0 && finishes.confirmed === true,
    missing,
  };
}

export function questionnaireSummary({
  basic = {},
  visualQuestions = [],
  visualAnswers = {},
  skippedSpaceTypes = [],
  finishes = {},
  stylePacks = [],
} = {}) {
  const stylePack = stylePacks.find((pack) => pack.id === finishes.stylePackId);
  const visualSelections = visualQuestions
    .map((question) => {
      const answer = visualAnswers[question.question_id];
      if (!answer?.optionId) return null;
      const option = question.options.find(
        (candidate) => candidate.option_id === answer.optionId,
      );
      return {
        questionId: question.question_id,
        question: question.title_zh,
        answer: answer.optionId === "both"
          ? "兩者平衡"
          : option?.label_zh || answer.optionId,
        custom: answer.custom || "",
      };
    })
    .filter(Boolean);
  return {
    basic,
    answeredSpaceCount: new Set(
      visualQuestions
        .filter((question) => visualAnswers[question.question_id]?.optionId)
        .map((question) => question.space_type),
    ).size,
    skippedSpaceCount: new Set(skippedSpaceTypes).size,
    visualSelections,
    finishes: {
      style: stylePack
        ? `${stylePack.styleLabel}｜${stylePack.name}`
        : finishes.stylePackId || "",
      wallMaterial: finishes.wallMaterial || "",
      wallColor: finishes.wallColor || "",
      floorMaterial: finishes.floorMaterial || "",
      floorColor: finishes.floorColor || "",
      ceilingMaterial: finishes.ceilingMaterial || "",
      ceilingStyle: finishes.ceilingStyle || "",
      lightStyle: finishes.lightStyle || "",
      ceilingColor: finishes.ceilingColor || "",
    },
  };
}
