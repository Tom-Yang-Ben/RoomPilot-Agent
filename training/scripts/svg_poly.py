# -*- coding: utf-8 -*-
"""svg_poly.py — GT 標注 SVG 的 Space 多邊形 → 像素座標。

答案集（own_eval / own_dataset / own_dataset_color / own_eval_color）的
model.svg 用 <polygon points="…"> 記多邊形：座標成對出現，對與對之間
以空白分隔、對內以逗號分隔，**每對是 (x, y)＝(欄, 列)**，字串以一個
尾隨空白收尾（歷史工具鏈的寫檔慣例）。本模組是評分工具鏈讀 GT 的
唯一入口。

2026-08-03 依 W3C SVG 1.1 §9.7.1 的 points 文法（數字以逗號或空白
分隔的平坦序列）與上述答案卷慣例**獨立重寫**，取代早前自第三方移植
的版本（見 git 歷史）。兩項行為屬既有量尺口徑、由對拍驗證釘住：
(1) 座標先四捨五入到整數格點再光柵化——GT 像素數字不因重寫漂移；
(2) 群組內無 <polygon> 時 raise StopIteration。
等價性驗證＝全部答案卷 63 檔逐 Space 群組跑新舊兩份實作，光柵化
輸出逐位元相等。

用法：
    from svg_poly import get_polygon
    rr, cc = get_polygon(g)   # g 為 minidom <g> 元素
"""
import numpy as np
from skimage.draw import polygon as _fill_polygon


def get_polygon(e):
    """minidom <g> 群組 → 第一個 <polygon> 的填滿像素 (rr, cc)。

    群組內沒有 <polygon> 時 raise StopIteration——Inkscape 殘留的空群組
    即此情況，呼叫端以 except StopIteration 跳過。座標依 SVG points 文法
    解析（逗號與空白皆為分隔符，尾隨空白自然被忽略），每對為
    (x, y)＝(欄, 列)，光柵化前四捨五入到整數格點（量尺口徑）。"""
    pol = next(iter(e.getElementsByTagName("polygon")))
    tokens = pol.getAttribute("points").replace(",", " ").split()
    if len(tokens) % 2:
        raise ValueError(f"points 數字個數為奇數（{len(tokens)}），非成對座標")
    nums = np.round(np.asarray(tokens, dtype=float))
    return _fill_polygon(nums[1::2], nums[0::2])
