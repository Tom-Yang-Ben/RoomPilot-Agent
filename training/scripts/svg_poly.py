"""svg_poly.py — GT 標注 SVG 的 Space 多邊形 → 像素座標。

答案集（own_eval / own_dataset / CubiCasa5k）的 model.svg 都用同一種
<polygon points="y,x y,x ... "> 慣例，本函式是評分工具鏈讀 GT 的唯一入口。

逐行照抄自 CubiCasa5k floortrans/loaders/svg_utils.py 的 get_polygon()，
讓評分不再 import floortrans（沒下載資料集的機器也能跑量尺）。柵格化本來
就是 skimage.draw.polygon 在做，CubiCasa 只負責解字串，故輸出逐位元相同
——對拍證據：tests/test_svg_poly_parity.py。

抄寫時三個不可動的細節：
  [:-1]           points 尾端有空格，split 出的最後一項是空字串，要砍
  y, x = split    SVG 存的順序是 y,x——寫反整張圖轉置
  np.round        四捨五入，不是 int() 截斷——差一像素就跟舊報表對不上
"""
import numpy as np
from skimage.draw import polygon


def get_polygon(e):
    pol = next(p for p in e.childNodes if p.nodeName == "polygon")
    points = pol.getAttribute("points").split(' ')
    points = points[:-1]

    X, Y = np.array([]), np.array([])
    for a in points:
        y, x = a.split(',')
        X = np.append(X, np.round(float(x)))
        Y = np.append(Y, np.round(float(y)))

    rr, cc = polygon(X, Y)

    return rr, cc
