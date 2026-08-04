"""自動牆厚 T 推導（derive_wall_T）——磨牆害徵防護測試。
floor13 實案：左上粗角塊把 max 法的 T 拉到 30（典型隔間僅 8px），
solid 開運算核 0.35T=10px 超過隔間牆厚，下半部牆整批被磨掉。
防護設計：T 照舊 max×2，僅在「牆存活率 <0.92」（solid 核正在磨牆）
時迴退 p99.5 穩健值——其他圖 T 零改變（floor04 的 max 是誠實外牆厚，
全域改 p99.5 已實測造成窗 P98/R96→97/88 大回歸）。"""
import numpy as np

import floorplan2dxf as fp


def _stripes(thick, size=1000, step=200):
    """等厚平行牆（無交叉、不貼影像邊界——邊界牆 DT 會量到整寬）。"""
    img = np.zeros((size, size), np.uint8)
    for v in range(20, size - thick, step):
        img[v:v + thick, :] = 255
    return img


def test_derive_wall_T_uniform_matches_thickness():
    # 等厚圖：無害徵，行為與現行 max 法相同
    assert 9 <= fp.derive_wall_T(_stripes(10)) <= 12
    assert 20 <= fp.derive_wall_T(_stripes(22)) <= 24


def test_derive_wall_T_harmless_blob_keeps_current_behavior():
    # 20×20 粗塊把 T 拉到 20，但 solid=7 磨不掉 10px 牆（無害徵）
    # → 維持現行 max 法輸出，零擾動保證
    img = _stripes(10)
    img[500:520, 500:520] = 255
    assert 18 <= fp.derive_wall_T(img) <= 21


def test_derive_wall_T_harmful_blob_falls_back():
    # floor13 情境：8px 細隔間＋30×30 粗塊 → T=30、solid=10 會把牆磨光
    # → 害徵觸發，迴退穩健值使 solid < 牆厚（T 須 <23）
    img = _stripes(8)
    img[500:530, 500:530] = 255
    T = fp.derive_wall_T(img)
    assert T <= 18, f"T={T}: solid=0.35T 仍會磨掉 8px 牆"
