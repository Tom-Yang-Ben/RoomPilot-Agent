"""
資料結構定義: Room、Wall、ClearanceZone、FurnitureCatalogItem、PlacedFurniture

對應 SSOT 文件第 8 節「資料結構」:
- 型錄屬性(type/name/size/color/style/price)
- 擺放屬性(pos_x/pos_y/rotation) —— 這是 place_furniture / adjust_furniture 算出來要存的東西
- 淨空屬性(clearance) —— 開合家具(衣櫃/冰箱/五斗櫃)所需的保留空間
"""
from dataclasses import dataclass, field


@dataclass
class Wall:
    """一段牆,用起點跟終點表示"""

    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 0.1  # 公尺


@dataclass
class Room:
    """房間邊界 + 牆體清單"""

    width: float
    depth: float
    walls: list[Wall] = field(default_factory=list)


@dataclass
class ClearanceZone:
    """開合淨空需求: 家具的哪一面需要保留多少空間"""

    side: str
    depth: float


@dataclass
class FurnitureCatalogItem:
    """型錄屬性: 描述「這是什麼家具」,不含座標"""

    type: str
    name: str
    width: float
    depth: float
    height: float = 0.8
    style: str | None = None
    price: float | None = None
    glb_path: str | None = None
    clearance: ClearanceZone | None = None


@dataclass
class PlacedFurniture:
    """擺放屬性: place_furniture / adjust_furniture 的輸出結果"""

    id: str
    catalog: FurnitureCatalogItem
    pos_x: float = 0.0
    pos_y: float = 0.0
    rotation: float = 0.0

    def bounds(self) -> tuple[float, float, float, float]:
        """回傳未旋轉時的邊界 (min_x, min_y, max_x, max_y)"""
        hw, hd = self.catalog.width / 2, self.catalog.depth / 2
        return (self.pos_x - hw, self.pos_y - hd, self.pos_x + hw, self.pos_y + hd)

