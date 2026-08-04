"""問卷／預設家具族系 → 型錄實際存在的分類對照。

問卷與 2D 型庫用的族系名（`SPACE_DEFAULTS`、`FURNITURE_ALIASES`、前端
`FURNITURE_2D_LIBRARY`）與 Kai 型錄實際的分類名有數處對不上。對不上的族系在
`choose_furniture_items` 一件候選都找不到，於是 2D 有這件家具、3D 永遠沒有，
而且畫面上只會安靜地少一件（QA 2026-08-04：第 6 步的電器櫃、浴櫃、高收納櫃
三件在 2D 有編號、3D 缺席，`placement.failed` 是空的，
`unavailable_types` 才是真正的原因）。

值一律是**型錄實際存在的分類名**。先前 `category_code` 與 `normalized_type` 是
兩個鍵空間（型錄叫 `planter`、payload 叫 `flower-pots-planter`），所以這張表與
`backend/spatial_data/rag/shortlist.py` 的 `FAMILY_CATEGORY_OVERRIDES` 內容重疊
卻不能互抄。那條改名已收進匯入層的 `CATEGORY_CODE_OVERRIDES`
（`scripts/sql/import_official_catalog_to_postgres.py`），兩者現在恆等。

這裡只做「族系本身查無候選才退而求其次」的後備，不改變已經找得到的族系，也
不放寬語意檢查（`catalog_item_matches_type_semantics` 一律以原始族系名判定，
櫃體仍然不能被當成床）。

型錄實況由 `tests/test_catalog_vocabulary_contract.py` 對
`tests/data/catalog_vocabulary_snapshot.json` 鎖住：這張表指向不存在的分類、或
某個族系兩條後端解析鏈的結果沒有交集，測試都會紅。
"""

from __future__ import annotations


# 只收「族系在型錄查無任何可用模型、且後備對象語意相同」的對照。實測數量取自
# 正式 payload（7,958 筆，has_model）：
FAMILY_CATALOG_FALLBACKS: dict[str, tuple[str, ...]] = {
    # 型錄只有 cabinet-cupboard 一種櫃體（146 筆），這三個名字都是 0 筆。
    # 前端 CATALOG_RETRIEVAL_ROUTES 早就這樣繞過，後端這側先前沒有對應的表。
    "storage-cabinet": ("cabinet-cupboard",),
    "appliance-cabinet": ("cabinet-cupboard",),
    "bathroom-vanity": ("cabinet-cupboard",),
    # 問卷會產生 lounge-chair（0 筆），型錄的休閒椅一律是 armchair（97 筆）。
    "lounge-chair": ("armchair",),
    # 以下兩個新資料不會再產生：`FURNITURE_ALIASES` 的「收納櫃」「床架」已改成
    # 直接指向型錄用語。留著是為了舊存檔——那些 scene_json 的
    # `required_furniture` 仍寫著這兩個型錄從來沒有的名字。
    "cabinets-cupboard": ("cabinet-cupboard",),
    "bed-frame": ("bed",),
}

# 型錄真的沒有對應品項、不能靠改名解決的族系。列在這裡是為了讓「2D 放得下、
# 3D 一定缺席」這件事有紀錄可查，而不是每次都要重新追一遍；要補齊得由 Kai 匯入
# 實際模型，不是加對照表。
FAMILIES_WITHOUT_CATALOG_MODELS: tuple[str, ...] = (
    "bathtub",
    "kitchen-island",
    "plant-shelf",
    "vanity-table",
)


# 反過來的缺口：型錄有模型、但沒有任何自動選件路徑會挑到它。使用者仍可在
# /library 手動加入，只是問卷與第 6 步不會主動推薦。
#
# 這裡只收「確實沒有 lane、且要不要進自動選件是產品決定」的型別。有自己的擺放
# lane 的品項（檯面小物、壁掛、地面覆蓋物）不列在這裡——它們由
# `backend/catalog/placement_surface.py` 的三組型別涵蓋，
# tests/test_catalog_vocabulary_contract.py 會自動認得。
#
#   room-divider（17 筆，屏風／隔間櫃）——放在哪個房型、算不算落地家具、要不要
#       參與動線計算都還沒定案，貿然進自動選件會在開放空間中央長出一道牆。
MANUAL_ONLY_TYPES: tuple[str, ...] = ("room-divider",)


def catalog_types_for_family(family: str) -> tuple[str, ...]:
    """回傳這個族系可接受的型錄 `normalized_type`，第一個永遠是族系本身。

    呼叫端必須依序嘗試：先用族系本身精準比對，查無候選才往後備走，這樣型錄日後
    真的補進 `storage-cabinet` 時會自動回到精準比對。
    """
    name = str(family or "")
    return (name, *FAMILY_CATALOG_FALLBACKS.get(name, ()))
