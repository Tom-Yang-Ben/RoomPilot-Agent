export const WHOLE_HOUSE_QUESTIONS = Object.freeze([
  {
    id: "household",
    label: "家庭成員",
    type: "choice",
    options: ["一人居住", "兩位大人", "親子家庭", "三代同堂", "其他"],
  },
  {
    id: "projectStatus",
    label: "房屋用途與工程狀態",
    type: "choice",
    options: ["新屋自住", "舊屋翻新", "出租住宅", "局部改造"],
  },
  {
    id: "aiAssistance",
    label: "希望 RoomPilot 如何協助",
    type: "choice",
    options: ["一步一步引導", "推薦後由我確認", "採用系統推薦"],
  },
  {
    id: "membersAndPets",
    label: "年齡層、孩童與寵物",
    type: "text",
    placeholder: "例如：兩位大人、一位幼兒、一隻貓",
  },
  {
    id: "lifestyle",
    label: "日常生活習慣",
    type: "text",
    placeholder: "例如：常在家工作、每週聚餐、需要大量收納",
  },
  {
    id: "budgetTimeline",
    label: "預算與預計完成時間",
    type: "text",
    placeholder: "可填範圍與希望入住日期",
  },
  {
    id: "immutableNeeds",
    label: "一定要保留或不能改動的條件",
    type: "text",
    placeholder: "例如：既有鋼琴、神明桌、特定櫃體或管線",
  },
]);

export const ROOM_QUESTION_TEMPLATES = Object.freeze({
  living_room: {
    uses: ["日常休息", "親友聚會", "影音娛樂", "親子活動", "居家工作"],
    furniture: ["沙發", "茶几", "電視櫃", "單椅", "收納櫃"],
  },
  bedroom: {
    uses: ["睡眠休息", "閱讀", "更衣", "化妝保養", "簡易工作"],
    furniture: ["床", "床頭櫃", "衣櫃", "梳妝台", "書桌"],
  },
  dining_room: {
    uses: ["日常用餐", "多人聚餐", "工作閱讀", "親子手作"],
    furniture: ["圓桌", "長桌", "餐椅", "餐邊櫃"],
  },
  kitchen: {
    uses: ["簡易料理", "每日下廚", "烘焙", "多人共煮"],
    furniture: ["冰箱", "電器櫃", "中島", "餐櫃"],
  },
  bathroom: {
    uses: ["淋浴", "泡澡", "乾濕分離", "衣物收納"],
    furniture: ["浴櫃", "鏡櫃", "浴缸", "收納架"],
  },
  balcony: {
    uses: ["洗曬衣物", "植栽", "休閒座位", "儲物"],
    furniture: ["洗衣機", "收納櫃", "戶外椅", "植栽架"],
  },
  default: {
    uses: ["依現況使用", "收納", "休息", "工作"],
    furniture: ["收納櫃", "桌", "椅"],
  },
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
      const planned = answer?.confirmed === true
        && Array.isArray(answer.uses)
        && answer.uses.length > 0;
      return !planned && !keepExisting.has(roomId);
    });
  if (unresolvedRoomIds.length) blockers.push("room_requirements_incomplete");
  return {
    ready: blockers.length === 0,
    blockers,
    unresolvedRoomIds,
  };
}

export function roomQuestionTemplate(roomType) {
  return ROOM_QUESTION_TEMPLATES[roomType] || ROOM_QUESTION_TEMPLATES.default;
}
