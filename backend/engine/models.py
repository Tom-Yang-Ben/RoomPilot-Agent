"""
資料結構定義：Room、Wall、ClearanceZone、FurnitureCatalogItem、PlacedFurniture。

單位與座標約定：
- 長度一律公分(cm)；X 向右、Y 向上，原點在平面圖左下角。
- position 是物件中心；rotation 是逆時針角度，0 度時家具正面朝 +Y。
- width 沿本地 X、depth 沿本地 Y、height 沿 Z。
"""
from dataclasses import dataclass, field
from typing import Literal


ClearanceKind = Literal["operation", "access"]
ClearanceMode = Literal["all", "any"]
IssueSeverity = Literal["error", "warning"]
OpeningKind = Literal["door", "window"]
WindowType = Literal["standard", "floor_to_ceiling"]

# 前端 scene_window_types.js 的預設窗台高；引擎沿用同一組數字，避免兩邊各有一套。
STANDARD_WINDOW_SILL_CM = 90.0
FLOOR_TO_CEILING_SILL_CM = 0.0


@dataclass
class Wall:
    """一段有厚度的牆，所有欄位皆為公分。"""

    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 10.0


@dataclass
class Opening:
    """房間邊界上的一段門或窗，座標為房間局部座標（公分）。

    資料來自 ``layout_json`` 的 doors／windows，由呼叫端換算成房間局部座標後傳入；
    引擎本身不讀取檔案，也不呼叫辨識管線。

    ``swing_x``／``swing_y`` 是門扇打開後掃過的另一端點（對應 layout_json 的
    ``swing_end``）。有值時代表這道門會往房內掃出一塊不可佔用的區域。
    """

    kind: OpeningKind
    x1: float
    y1: float
    x2: float
    y2: float
    window_type: WindowType | None = None
    sill_height_cm: float | None = None
    swing_x: float | None = None
    swing_y: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"door", "window"}:
            raise ValueError(f"不支援的開口種類: {self.kind}")
        if self.kind == "window" and self.window_type is None:
            # 與前端一致：未標示時一律當一般窗，落地窗必須明確標記。
            self.window_type = "standard"

    @property
    def sill_cm(self) -> float:
        """窗台高度；門一律 0（人要走過去，任何高度都算擋住）。"""
        if self.sill_height_cm is not None:
            return float(self.sill_height_cm)
        if self.kind == "door" or self.window_type == "floor_to_ceiling":
            return FLOOR_TO_CEILING_SILL_CM
        return STANDARD_WINDOW_SILL_CM

    def span_along(self, axis: str) -> tuple[float, float]:
        """回傳開口在指定軸上的投影區間，``axis`` 為 ``"x"`` 或 ``"y"``。"""
        if axis == "x":
            low, high = sorted((self.x1, self.x2))
        elif axis == "y":
            low, high = sorted((self.y1, self.y2))
        else:
            raise ValueError(f"不支援的軸: {axis}")
        return low, high


@dataclass
class Room:
    """房間矩形邊界、牆體清單與門窗開口。

    ``openings`` 預設為空：舊呼叫端不傳時，行為與加入本欄位之前完全相同。
    """

    width: float
    depth: float
    walls: list[Wall] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)

    def doors(self) -> list[Opening]:
        return [item for item in self.openings if item.kind == "door"]

    def windows(self) -> list[Opening]:
        return [item for item in self.openings if item.kind == "window"]


@dataclass
class ClearanceZone:
    """家具某一面的淨空需求。

    ``depth`` 是 v0.1 相容欄位；只給 depth 時，理想值與最低值都等於它。
    新資料應給 ``ideal_cm`` 與 ``floor_cm``。``operation`` 是門／抽屜等
    必須保留的空間；``access`` 是舒適使用空間，只產生警告。
    """

    side: str
    depth: float | None = None
    kind: ClearanceKind = "operation"
    ideal_cm: float | None = None
    floor_cm: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.side not in {"front", "back", "left", "right"}:
            raise ValueError(f"不支援的淨空方向: {self.side}")
        if self.kind not in {"operation", "access"}:
            raise ValueError(f"不支援的淨空種類: {self.kind}")

        legacy = self.depth
        floor = self.floor_cm if self.floor_cm is not None else legacy
        ideal = self.ideal_cm if self.ideal_cm is not None else legacy
        if floor is None:
            floor = ideal
        if ideal is None:
            ideal = floor
        if floor is None or ideal is None:
            raise ValueError("淨空必須提供 depth，或同時提供 ideal_cm / floor_cm")

        floor = float(floor)
        ideal = float(ideal)
        if floor <= 0 or ideal <= 0:
            raise ValueError("淨空距離必須大於 0 公分")
        if ideal < floor:
            raise ValueError("理想淨空不能小於最低淨空")

        # depth 永遠保留最低可接受距離，讓 v0.1 呼叫端繼續正常運作。
        self.depth = floor
        self.floor_cm = floor
        self.ideal_cm = ideal



@dataclass
class ClearanceSpec:
    """一面或多面淨空需求的組合規則。

    ``mode="all"``：每一面都要滿足。
    ``mode="any"``：至少一面滿足（例如床左右長側）。
    ``enforce_floor=True``：即使 zone.kind 是 access，低於 floor_cm 也會擋下
    （床／餐桌使用空間的硬門檻）。
    """

    zones: list[ClearanceZone]
    mode: ClearanceMode = "all"
    enforce_floor: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"all", "any"}:
            raise ValueError(f"不支援的淨空模式: {self.mode}")
        if not self.zones:
            raise ValueError("clearance_spec 至少要有一個淨空方向")


@dataclass
class FurnitureCatalogItem:
    """家具型錄屬性，不含座標。"""

    type: str
    name: str
    width: float
    depth: float
    height: float = 80.0
    style: str | None = None
    price: float | None = None
    glb_path: str | None = None
    clearance: ClearanceZone | None = None
    clearance_spec: ClearanceSpec | None = None


@dataclass
class PlacedFurniture:
    """已放置家具，平面座標與尺寸皆為公分。"""

    id: str
    catalog: FurnitureCatalogItem
    pos_x: float = 0.0
    pos_y: float = 0.0
    rotation: float = 0.0

    def bounds(self) -> tuple[float, float, float, float]:
        """回傳未旋轉邊界；旋轉版由 geometry.py 處理。"""
        hw, hd = self.catalog.width / 2, self.catalog.depth / 2
        return (self.pos_x - hw, self.pos_y - hd, self.pos_x + hw, self.pos_y + hd)


@dataclass
class PlacementIssue:
    """一條可由 Agent／後端直接使用的結構化驗證結果。"""

    code: str
    message_zh: str
    item_id: str
    rule: str
    severity: IssueSeverity = "error"
    related_item_id: str | None = None
    required_cm: float | None = None
    available_cm: float | None = None
    shortfall_cm: float | None = None

    def to_dict(self) -> dict:
        payload = {
            "code": self.code,
            "message_zh": self.message_zh,
            "item_id": self.item_id,
            "rule": self.rule,
            "severity": self.severity,
        }
        optional = {
            "related_item_id": self.related_item_id,
            "required_cm": self.required_cm,
            "available_cm": self.available_cm,
            "shortfall_cm": self.shortfall_cm,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return payload


@dataclass
class PlacementValidation:
    """完整驗證結果；errors 會擋下，warnings 只供提示／評分。"""

    errors: list[PlacementIssue] = field(default_factory=list)
    warnings: list[PlacementIssue] = field(default_factory=list)

    @property
    def legal(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "legal": self.legal,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def resolved_clearance_spec(catalog: FurnitureCatalogItem) -> ClearanceSpec | None:
    """優先使用 clearance_spec；否則把單一 clearance 包成 all 模式。"""
    if catalog.clearance_spec is not None:
        return catalog.clearance_spec
    if catalog.clearance is not None:
        return ClearanceSpec(
            zones=[catalog.clearance],
            mode="all",
            enforce_floor=catalog.clearance.kind == "operation",
        )
    return None
