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
    id: "membersAndPets",
    label: "年齡層、孩童與寵物",
    type: "select",
    options: ["皆為成人、無寵物", "有幼兒", "有長輩", "有貓", "有狗", "其他（於特殊條件補充）"],
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
]);
