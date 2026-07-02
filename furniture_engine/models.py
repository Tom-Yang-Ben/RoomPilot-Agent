"""
資料結構定義:Room、Wall、ClearanceZone、FurnitureCatalogItem、PlacedFurniture

對應 SSOT 文件第 8 節「資料結構」:
- 型錄屬性(type/name/size/color/style/price)
- 擺放屬性(pos_x/pos_y/rotation) —— 這是 place_furniture / adjust_furniture 算出來要存的東西
- 淨空屬性(clearance)—— 開合家具(衣櫃/冰箱/五斗櫃)所需的保留空間
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
class ClearanceZone:
    """開合淨空需求:家具的哪一面需要保留多少空間

    side 以「未旋轉時家具自己的方向」為準:
      front = +y 方向(面向房間)、back = -y、left = -x、right = +x
    家具旋轉時,淨空範圍會跟著 rotation 一起轉(在 clearance.py 處理)。
    """
    side: str          # "front" / "back" / "left" / "right"
    depth: float       # 開合所需額外深度(公尺),如抽屜拉出 0.5、門扇打開 0.6


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
    clearance: ClearanceZone | None = None   # None = 此家具無開合淨空需求(如沙發、茶几)


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