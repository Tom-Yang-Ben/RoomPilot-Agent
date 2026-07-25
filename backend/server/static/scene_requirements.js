export const WHOLE_HOUSE_QUESTIONS = Object.freeze([
  {
    id: "household",
    label: "家庭成員",
    type: "select",
    options: ["一人", "兩位大人", "親子家庭", "三代同堂", "其他（於特殊條件補充）"],
  },
  {
    id: "projectStatus",
    label: "房屋用途與工程狀態",
    type: "select",
    options: ["新成屋自住", "中古屋翻新自住", "出租", "局部改造"],
  },
  {
    id: "aiAssistance",
    label: "希望 RoomPilot 如何協助",
    type: "select",
    options: ["引導我選擇", "提供推薦後由我確認", "我想採用 AI 推薦"],
  },
  {
    id: "membersAndPets",
    label: "年齡層、孩童與寵物",
    type: "select",
    options: ["皆為成人、無寵物", "有幼兒", "有長輩", "有貓", "有狗", "其他（於特殊條件補充）"],
  },
  {
    id: "lifestyle",
    label: "日常生活習慣",
    type: "select",
    options: ["休息與日常生活", "常在家工作", "常聚餐", "重視大量收納", "其他（於特殊條件補充）"],
  },
  {
    id: "budgetTimeline",
    label: "預算與預計完成時間",
    type: "select",
    options: ["60 萬以下／彈性時程", "60–100 萬／三個月", "100–150 萬／三至六個月", "150 萬以上／另議"],
  },
  {
    id: "overallStyle",
    label: "全屋整體風格",
    type: "select",
    options: ["北歐風", "奶油風", "工業風", "美式風", "日式風", "現代風", "各房依逐房色卡"],
  },
  {
    id: "immutableNeeds",
    label: "特殊或不可變條件",
    type: "text",
    required: false,
    placeholder: "只有特殊需求才輸入，例如：廚衛主排水不動、保留鋼琴",
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
