"""
資料結構定義:Room、Wall、FurnitureCatalogItem、PlacedFurniture

對應 SSOT 文件第 8 節「資料結構」:
- 型錄屬性(type/name/size/color/style/price)
- 擺放屬性(pos_x/pos_y/rotation) —— 這是 place_furniture / adjust_furniture 算出來要存的東西
"""
from dataclasses import dataclass, field


@dataclass
class Wall:
    """一段牆,用起點跟終點表示(對應 2Dto3D.html 裡的 WALL_SEGS)"""
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 0.1  # 牆厚度(公尺),預留給碰撞判斷用


@dataclass
class Room:
    """房間邊界 + 牆體清單"""
    width: float   # 對應 ROOM.w
    depth: float   # 對應 ROOM.d
    walls: list[Wall] = field(default_factory=list)


@dataclass
class FurnitureCatalogItem:
    """型錄屬性:描述「這是什麼家具」,不含座標"""
    type: str          # e.g. "sofa", "bed", "table"
    name: str          # e.g. "三人座沙發"
    width: float       # 對應 size.w(公尺)
    depth: float       # 對應 size.d(公尺)
    height: float = 0.8  # 對應 size.h(公尺)
    style: str | None = None
    price: float | None = None
    glb_path: str | None = None


@dataclass
class PlacedFurniture:
    """擺放屬性:place_furniture / adjust_furniture 的輸出結果

    這正是 SSOT 文件第 8 節說「沒有這幾欄,配置算得出來卻無處存」的欄位。
    """
    id: str                     # 唯一識別碼,e.g. "sofa_1"
    catalog: FurnitureCatalogItem
    pos_x: float = 0.0
    pos_y: float = 0.0          # 對應原型的 z 軸(平面座標,注意不是高度)
    rotation: float = 0.0       # 角度,單位:度(0~360)

    def bounds(self) -> tuple[float, float, float, float]:
        """回傳未旋轉時的邊界 (min_x, min_y, max_x, max_y),旋轉版在 geometry.py 處理"""
        hw, hd = self.catalog.width / 2, self.catalog.depth / 2
        return (self.pos_x - hw, self.pos_y - hd, self.pos_x + hw, self.pos_y + hd)