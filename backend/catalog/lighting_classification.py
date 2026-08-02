"""燈具分類：把型錄記錄判成 LIGHTING_CEILING_CATALOG_CONTRACT 的 lighting_type。

2026-07-30 的型錄切換把 793 筆「燈具或燈具分類」記錄從 `items` 移除
(`removed_lighting_rule`)，但那批資產的 GLB 與三視角圖早已上傳 CloudFront。要把
它們接回 lighting lane，得先決定每一筆到底是哪種燈具。

證據優先序：canonical_category_zh > VLM description > 品名。

品名不能單獨採信——被移除的那批記錄有「床 - Amazon Basics Poly Globe Pendant」
這種錯誤前綴(型錄 review 已知的 name/category 衝突)。VLM description 是看四視角
圖生成的，實測能明確講出「吊燈」「雙頭壁掛浴室燈具」，是這裡最可靠的訊號。

契約列舉只有 pendant|track|downlight|wall|table|floor。實測那 793 筆裡有三種
不屬於任何一種，各自獨立成桶而不是硬塞進契約列舉：

  shade_base            燈罩與燈座,是燈具的零件不是燈具本體
  unclassified_lighting 確認會發光但看不出燈種,實測幾乎都是蠟燭/茶燈燈籠
  not_lighting          被移除規則掃進來但根本不是燈(啞鈴、花園凳、保溫瓶)
"""

from __future__ import annotations

import re

PENDANT = "pendant"
TRACK = "track"
DOWNLIGHT = "downlight"
WALL = "wall"
TABLE = "table"
FLOOR = "floor"

#: 契約 `lighting_type` 的合法值。
CONTRACT_LIGHTING_TYPES = (PENDANT, TRACK, DOWNLIGHT, WALL, TABLE, FLOOR)

SHADE_BASE = "shade_base"
UNCLASSIFIED = "unclassified_lighting"
NOT_LIGHTING = "not_lighting"

#: 契約列舉之外、需要人工分流的桶。
REVIEW_BUCKETS = (SHADE_BASE, UNCLASSIFIED, NOT_LIGHTING)

LIGHTING_TYPES = CONTRACT_LIGHTING_TYPES + REVIEW_BUCKETS

# canonical_category_zh 本身就講明燈種的，直接採用。
_CATEGORY_MAP = {
    "檯燈": TABLE,
    "落地燈": FLOOR,
    "壁燈": WALL,
    "吊燈": PENDANT,
    "吸頂燈": DOWNLIGHT,
    # 契約沒有 task 這一類。工作燈擺在桌面，歸 table 最接近實際擺放面。
    "工作燈": TABLE,
    "燈罩與燈座": SHADE_BASE,
}

# 先判最 specific 的：軌道燈也含「燈」，吊燈也可能寫「天花」。
_TYPE_PATTERNS = (
    (TRACK, r"軌道燈|軌道式|track ?light"),
    (PENDANT, r"吊燈|懸吊|吊掛|枝形|pendant|chandelier"),
    (DOWNLIGHT, r"吸頂|嵌燈|崁燈|筒燈|downlight|flush ?mount|ceiling ?light"),
    (WALL, r"壁燈|壁掛式?燈|牆面燈|sconce|wall ?(lamp|light|sconce)"),
    (FLOOR, r"落地燈|立燈|直立式?燈|floor ?lamp|uplighter"),
    (TABLE, r"檯燈|桌燈|床頭燈|table ?lamp|desk ?lamp|reading ?lamp|clamp ?spot"),
)

# 明確不是燈具的品項。這批是移除規則誤掃進來的。
_NOT_LIGHTING_PATTERN = (
    r"啞鈴|dumbbell|花園凳|garden ?stool|地毯|\brug\b|立鏡|穿衣鏡|full-?length mirror"
    r"|保溫瓶|vacuum ?flask|衣[架帽]|garment|餐桌|dining ?table|扶手椅|armchair"
    r"|衣櫃|wardrobe|燭[臺台]|candle ?holder"
)

# 會發光但不是電氣燈具的裝飾品，多半是蠟燭載體。
_LANTERN_PATTERN = r"燈籠|lantern|茶燈|tealight|tea ?light|柱狀蠟燭|pillar ?candle"

_ANY_LIGHT_PATTERN = r"燈|lamp|light|luminaire"


def classify_lighting_type(
    canonical_category_zh: str | None,
    description: str | None = None,
    name: str | None = None,
) -> tuple[str, str]:
    """回傳 ``(lighting_type, basis)``。

    ``basis`` 記錄判斷依據，寫進 manifest 讓人能追為什麼這樣分。
    """
    category = (canonical_category_zh or "").strip()
    desc = (description or "").strip().lower()
    title = (name or "").strip().lower()

    # 1) 描述說了不是燈就不是燈。描述比品名可靠，先看它。
    if desc and re.search(_NOT_LIGHTING_PATTERN, desc):
        return NOT_LIGHTING, "描述顯示非燈具"

    # 2) 蠟燭燈籠不是電氣燈具，但也不該被當成一般家具丟掉。
    if re.search(_LANTERN_PATTERN, desc) or re.search(_LANTERN_PATTERN, title):
        return UNCLASSIFIED, "蠟燭/茶燈燈籠，非電氣燈具"

    # 3) canonical 分類明確者直接採用。
    if category in _CATEGORY_MAP:
        return _CATEGORY_MAP[category], f"分類「{category}」"

    # 4) canonical 是籠統的「燈具」時，靠描述再靠品名。
    for kind, pattern in _TYPE_PATTERNS:
        if re.search(pattern, desc):
            return kind, "VLM 描述"
    for kind, pattern in _TYPE_PATTERNS:
        if re.search(pattern, title):
            return kind, "品名"

    if re.search(_NOT_LIGHTING_PATTERN, title):
        return NOT_LIGHTING, "品名顯示非燈具"
    if re.search(_ANY_LIGHT_PATTERN, f"{desc} {title}"):
        return UNCLASSIFIED, "確認是燈具但看不出燈種"
    return NOT_LIGHTING, "無任何燈具跡象"


def is_contract_fixture(lighting_type: str) -> bool:
    """只有契約列舉內的燈種才算可交付的燈具本體。"""
    return lighting_type in CONTRACT_LIGHTING_TYPES
