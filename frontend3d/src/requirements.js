export const STYLE_OPTIONS = [
  { style_id: 'scandinavian', style_name_zh: '北歐風' },
  { style_id: 'japanese', style_name_zh: '日式' },
  { style_id: 'modern_minimal', style_name_zh: '現代簡約' },
  { style_id: 'cream', style_name_zh: '奶油風' },
  { style_id: 'industrial', style_name_zh: '工業風' },
  { style_id: 'american', style_name_zh: '美式' },
]

export const ROOM_USE_OPTIONS = {
  living_room: [
    ['family_gathering', '家人交流'], ['relaxing', '放鬆休息'], ['watching_tv', '影音娛樂'],
    ['hosting_guests', '接待訪客'], ['reading', '閱讀'], ['living_storage', '客廳收納'],
  ],
  dining_room: [
    ['daily_meals', '日常用餐'], ['hosting_meals', '多人聚餐'], ['work_study', '工作／寫作業'],
    ['dining_storage', '餐具收納'],
  ],
  bedroom: [
    ['sleeping', '睡眠'], ['clothing_storage', '衣物收納'], ['dressing', '梳妝更衣'],
    ['reading', '床邊閱讀'], ['work_study', '工作／學習'],
  ],
  study: [
    ['work_study', '工作／學習'], ['reading', '閱讀'], ['book_storage', '書籍收納'],
    ['guest_sleeping', '臨時客房'],
  ],
  kitchen: [
    ['daily_cooking', '日常烹飪'], ['baking', '烘焙'], ['kitchen_storage', '廚具收納'],
    ['small_appliances', '小家電使用'],
  ],
  bathroom: [['daily_washing', '日常洗浴'], ['accessible_washing', '友善洗浴'], ['bathroom_storage', '衛浴收納']],
  toilet: [['daily_toilet', '日常如廁'], ['accessible_toilet', '友善如廁']],
  entry: [['shoes_and_entry_storage', '鞋物收納'], ['seating_for_shoes', '坐著穿鞋'], ['display', '入口展示']],
  corridor: [['circulation', '主要通行'], ['display', '走道展示'], ['corridor_storage', '走道收納']],
  balcony: [['drying_and_relaxing', '曬衣與休憩'], ['planting', '植栽'], ['balcony_storage', '陽台收納']],
  storage: [['general_storage', '綜合收納'], ['seasonal_storage', '換季收納']],
  laundry: [['laundry', '洗衣'], ['drying', '晾曬'], ['laundry_storage', '清潔用品收納']],
  other: [['flexible_use', '彈性使用'], ['storage', '收納'], ['relaxing', '休憩']],
}

export const DEFAULT_USES_BY_ROOM = Object.fromEntries(
  Object.entries(ROOM_USE_OPTIONS).map(([roomType, options]) => [
    roomType,
    options.slice(0, roomType === 'living_room' || roomType === 'bedroom' ? 2 : 1).map(([value]) => value),
  ]),
)

export const MATERIAL_OPTIONS = [
  ['easy_cleaning', '易清潔'],
  ['low_voc', '低甲醛／低揮發'],
  ['slip_resistant', '止滑'],
  ['moisture_resistant', '防潮耐水'],
  ['scratch_resistant', '耐抓耐磨'],
  ['soft_touch', '柔軟觸感'],
]

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

function integer(value, fallback = 0) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback
}

export function makeRequirementsDraft(rooms = [], initial = null) {
  const initialRooms = new Map(
    (initial?.room_requirements || []).map((room) => [room.room_id, room]),
  )
  return {
    style_id: initial?.style_id || 'scandinavian',
    occupants: {
      adults: integer(initial?.occupants?.adults, 1),
      children: integer(initial?.occupants?.children),
      elderly: integer(initial?.occupants?.elderly),
      pets: integer(initial?.occupants?.pets),
    },
    customization_mode: initial?.customization_mode || 'default',
    room_requirements: rooms.map((room) => {
      const previous = initialRooms.get(room.room_id)
      const roomType = room.room_type || 'other'
      return {
        room_id: room.room_id,
        room_type: roomType,
        label_zh: room.label_zh || room.label || roomType,
        uses: clone(previous?.uses || DEFAULT_USES_BY_ROOM[roomType] || ['flexible_use']),
        required_furniture_ids: clone(previous?.required_furniture_ids || []),
        special_materials: clone(previous?.special_materials || []),
        special_notes: previous?.special_notes || '',
      }
    }),
    special_notes: initial?.special_notes || '',
    allow_openrouter: initial?.special_requirements?.openrouter?.requested === true,
  }
}

export function updateRequirementRoom(draft, roomId, update) {
  return {
    ...draft,
    room_requirements: draft.room_requirements.map((room) => (
      room.room_id === roomId ? { ...room, ...update } : room
    )),
  }
}

export function toggleValue(values = [], value) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value]
}

export function validateRequirementsDraft(draft) {
  if (!draft?.style_id) return '請選擇風格方向。'
  const occupants = draft.occupants || {}
  if (['adults', 'children', 'elderly', 'pets'].some((key) => integer(occupants[key]) > 30)) {
    return '各類居住成員數量不可超過 30。'
  }
  if (integer(occupants.adults) + integer(occupants.children) + integer(occupants.elderly) < 1) {
    return '至少需要一位居住者。'
  }
  if (!draft.room_requirements?.length) return '目前沒有可填寫需求的已確認空間。'
  if (draft.room_requirements.some((room) => !room.room_id || !room.room_type)) {
    return '空間資料不完整，請回到上一步重新確認。'
  }
  return null
}

function basePayload(draft) {
  const isDefault = draft.customization_mode === 'default'
  return {
    style_id: draft.style_id,
    occupants: {
      adults: integer(draft.occupants.adults),
      children: integer(draft.occupants.children),
      elderly: integer(draft.occupants.elderly),
      pets: integer(draft.occupants.pets),
    },
    customization_mode: isDefault ? 'default' : 'advanced',
    room_requirements: draft.room_requirements.map((room) => ({
      room_id: room.room_id,
      room_type: room.room_type,
      uses: isDefault
        ? clone(DEFAULT_USES_BY_ROOM[room.room_type] || ['flexible_use'])
        : clone(room.uses || []),
      required_furniture_ids: isDefault ? [] : clone(room.required_furniture_ids || []),
      special_materials: isDefault ? [] : clone(room.special_materials || []),
      special_notes: isDefault ? '' : String(room.special_notes || '').trim(),
    })),
    special_notes: isDefault ? '' : String(draft.special_notes || '').trim(),
  }
}

export function requirementsAnalyzePayload(draft, expectedRevision) {
  return {
    expected_revision: expectedRevision,
    ...basePayload(draft),
    allow_openrouter: Boolean(draft.allow_openrouter),
  }
}

export function requirementsConfirmationPayload(draft, expectedRevision, suggestion) {
  return {
    expected_revision: expectedRevision,
    ...basePayload(draft),
    suggestion: clone(suggestion),
  }
}
