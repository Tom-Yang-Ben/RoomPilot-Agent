export const FIRST_MEETING_SCHEMA_VERSION = "1.0";

export const FIRST_MEETING_STEPS = Object.freeze([
  { id: "residents", label: "居住者" },
  { id: "goals", label: "三項目標" },
  { id: "rooms", label: "優先空間" },
  { id: "constraints", label: "不可變條件" },
  { id: "budget", label: "預算時程" },
  { id: "style", label: "風格方向" },
  { id: "summary", label: "面談摘要" },
]);

export const FIRST_MEETING_GOALS = Object.freeze([
  { id: "circulation", label: "動線更順" },
  { id: "storage", label: "增加收納" },
  { id: "daylight", label: "改善採光" },
  { id: "lighting", label: "改善照明" },
  { id: "flexibility", label: "空間更彈性" },
  { id: "accessibility", label: "安全無障礙" },
  { id: "hosting", label: "適合聚會" },
  { id: "privacy", label: "增加隱私" },
]);

export const FIRST_MEETING_BUDGETS = Object.freeze([
  "尚未確定",
  "100 萬以下",
  "100–200 萬",
  "200–350 萬",
  "350 萬以上",
]);

export const FIRST_MEETING_TIMELINES = Object.freeze([
  "時間彈性",
  "3 個月內",
  "3–6 個月",
  "6–12 個月",
  "一年後",
]);

function uniqueStrings(values = [], limit = Infinity) {
  return [...new Set((Array.isArray(values) ? values : []).map(String).filter(Boolean))]
    .slice(0, limit);
}

function count(value, fallback = 0) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(parsed, 9)) : fallback;
}

export function normalizeFirstMeeting(saved = {}, rooms = []) {
  const roomIds = new Set(rooms.map((room) => String(room.id)));
  const savedRoomIds = uniqueStrings(saved.priorityRoomIds);
  const selectedRoomIds = (rooms.length
    ? savedRoomIds.filter((roomId) => roomIds.has(roomId))
    : savedRoomIds
  ).slice(0, 3);
  const roomNotes = Object.fromEntries(
    selectedRoomIds.map((roomId) => [roomId, String(saved.roomNotes?.[roomId] || "").slice(0, 160)]),
  );
  const goalIds = new Set(FIRST_MEETING_GOALS.map((goal) => goal.id));

  return {
    schemaVersion: FIRST_MEETING_SCHEMA_VERSION,
    started: saved.started === true,
    confirmed: saved.confirmed === true,
    residents: {
      adults: count(saved.residents?.adults, 2),
      children: count(saved.residents?.children),
      elderly: count(saved.residents?.elderly),
      pets: count(saved.residents?.pets),
      specialNeeds: String(saved.residents?.specialNeeds || "").slice(0, 200),
    },
    goalIds: uniqueStrings(saved.goalIds, 3).filter((goalId) => goalIds.has(goalId)),
    priorityRoomIds: selectedRoomIds,
    roomNotes,
    constraints: String(saved.constraints || "").slice(0, 300),
    budgetRange: FIRST_MEETING_BUDGETS.includes(saved.budgetRange)
      ? saved.budgetRange
      : "尚未確定",
    targetTimeline: FIRST_MEETING_TIMELINES.includes(saved.targetTimeline)
      ? saved.targetTimeline
      : "時間彈性",
    likedStylePackIds: uniqueStrings(saved.likedStylePackIds, 2),
    dislikedStylePackId: String(saved.dislikedStylePackId || ""),
    styleNote: String(saved.styleNote || "").slice(0, 200),
  };
}

export function firstMeetingStepStatus(meeting, step, rooms = []) {
  const normalized = normalizeFirstMeeting(meeting, rooms);
  if (step === "residents") {
    const people = normalized.residents.adults
      + normalized.residents.children
      + normalized.residents.elderly;
    return people > 0
      ? { ready: true, message: "" }
      : { ready: false, message: "請至少填入一位使用者。" };
  }
  if (step === "goals") {
    return normalized.goalIds.length === 3
      ? { ready: true, message: "" }
      : { ready: false, message: "請選擇最重要的三項目標。" };
  }
  if (step === "rooms") {
    return normalized.priorityRoomIds.length > 0
      ? { ready: true, message: "" }
      : { ready: false, message: "請先選擇一個優先討論的空間，最多三個。" };
  }
  if (step === "style") {
    return normalized.likedStylePackIds.length === 2 && Boolean(normalized.dislikedStylePackId)
      ? { ready: true, message: "" }
      : { ready: false, message: "請選兩張喜歡的風格圖，以及一張不喜歡的風格圖。" };
  }
  if (step === "summary") return firstMeetingReady(normalized, rooms);
  return { ready: true, message: "" };
}

export function firstMeetingReady(meeting, rooms = []) {
  for (const step of FIRST_MEETING_STEPS.slice(0, -1)) {
    const status = firstMeetingStepStatus(meeting, step.id, rooms);
    if (!status.ready) return status;
  }
  return { ready: true, message: "" };
}

export function firstMeetingSummary(meeting, rooms = [], stylePacks = []) {
  const normalized = normalizeFirstMeeting(meeting, rooms);
  const roomById = new Map(rooms.map((room) => [String(room.id), room]));
  const packById = new Map(stylePacks.map((pack) => [String(pack.id), pack]));
  const goalById = new Map(FIRST_MEETING_GOALS.map((goal) => [goal.id, goal.label]));
  const residents = normalized.residents;
  const residentParts = [
    residents.adults ? `成人 ${residents.adults}` : "",
    residents.children ? `兒童 ${residents.children}` : "",
    residents.elderly ? `長輩 ${residents.elderly}` : "",
    residents.pets ? `寵物 ${residents.pets}` : "",
  ].filter(Boolean);

  return {
    residents: residentParts.join("、") || "尚未填寫",
    specialNeeds: residents.specialNeeds || "無特別補充",
    goals: normalized.goalIds.map((goalId) => goalById.get(goalId) || goalId),
    priorityRooms: normalized.priorityRoomIds.map((roomId) => ({
      id: roomId,
      label: roomById.get(roomId)?.label || roomById.get(roomId)?.name || "未命名空間",
      note: normalized.roomNotes[roomId] || "面談時再補充",
    })),
    constraints: normalized.constraints || "目前沒有不可變條件",
    budgetTimeline: `${normalized.budgetRange}／${normalized.targetTimeline}`,
    likedStyles: normalized.likedStylePackIds.map((packId) => {
      const pack = packById.get(packId);
      return pack ? `${pack.styleLabel}・${pack.name}` : packId;
    }),
    dislikedStyle: (() => {
      const pack = packById.get(normalized.dislikedStylePackId);
      return pack ? `${pack.styleLabel}・${pack.name}` : "尚未指定";
    })(),
    styleNote: normalized.styleNote,
  };
}

export function legacyBasicAnswersFromFirstMeeting(meeting, stylePacks = []) {
  const normalized = normalizeFirstMeeting(meeting);
  const pack = stylePacks.find(
    (candidate) => String(candidate.id) === normalized.likedStylePackIds[0],
  );
  const residents = normalized.residents;
  const household = residents.children && residents.elderly
    ? "三代同堂"
    : residents.children
      ? "親子家庭"
      : residents.adults === 1 && !residents.elderly
        ? "一人"
        : "兩位以上成人";
  const membersAndPets = residents.children
    ? "有幼兒"
    : residents.elderly
      ? "有長輩"
      : residents.pets
        ? "有寵物"
        : "皆為成人、無寵物";
  const goals = normalized.goalIds
    .map((goalId) => FIRST_MEETING_GOALS.find((goal) => goal.id === goalId)?.label || goalId)
    .join("、");

  return {
    household,
    membersAndPets,
    lifestyle: goals,
    budgetTimeline: `${normalized.budgetRange}／${normalized.targetTimeline}`,
    overallStyle: pack?.styleLabel || "由設計師依參考圖整理",
    immutableNeeds: normalized.constraints || residents.specialNeeds || "無",
    aiAssistance: "提供推薦後由設計師與客戶確認",
    interviewSchemaVersion: FIRST_MEETING_SCHEMA_VERSION,
    occupants: { ...residents },
    designGoals: [...normalized.goalIds],
    priorityRooms: normalized.priorityRoomIds.map((roomId) => ({
      roomId,
      note: normalized.roomNotes[roomId] || "",
    })),
    budgetRange: normalized.budgetRange,
    targetTimeline: normalized.targetTimeline,
    likedStylePackIds: [...normalized.likedStylePackIds],
    dislikedStylePackId: normalized.dislikedStylePackId || null,
    styleNote: normalized.styleNote,
  };
}
